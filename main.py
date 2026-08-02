import os
import sys
import logging
import time
import glob
import random
import shutil
from dotenv import load_dotenv

from src.ingestion import get_topics
from src.llm import generate_script_for_topic
from src.audio.tts import generate_line_audio
from src.audio.processor import process_audio, concat_audio
from src.visuals.fetcher import get_visual_for_line, extract_keyword
from src.visuals import generate_srt, get_audio_duration
from src.render.engine import create_video_segment, concat_video_segments, mix_final_video, generate_thumbnail
from src.upload import generate_metadata, upload_video

load_dotenv()

# Setup logging
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/system.log", encoding="utf-8"),
        logging.StreamHandler(stream=open(sys.stdout.fileno(), mode='w', encoding='utf-8', closefd=False))
    ]
)



def run_garbage_collection(days_old=2):
    """Deletes temporary rendering files and outputs older than 'days_old' to prevent storage bloat."""
    logging.info(f"Running Garbage Collector (Cleaning pipeline artifacts older than {days_old} days)...")
    now = time.time()
    cutoff = now - (days_old * 86400)
    
    # 1. Clean data/ temp folders
    if os.path.exists("data"):
        # Files to preserve in data/
        PRESERVE = {"topics.json", "tweets.db", "accounts.db"}
        for item in os.listdir("data"):
            if item in PRESERVE: continue
            item_path = os.path.join("data", item)
            if os.path.isdir(item_path):
                try:
                    if os.path.getmtime(item_path) < cutoff:
                        shutil.rmtree(item_path)
                        logging.info(f"GC: Reclaimed storage from old temp directory {item_path}")
                except Exception as e:
                    logging.warning(f"GC: Could not delete {item_path}: {e}")
                    
    # 2. Clean output/ videos
    if os.path.exists("output"):
        for item in os.listdir("output"):
            item_path = os.path.join("output", item)
            if os.path.isfile(item_path):
                try:
                    if os.path.getmtime(item_path) < cutoff:
                        os.remove(item_path)
                        logging.info(f"GC: Reclaimed storage from old output video {item_path}")
                except Exception as e:
                    logging.warning(f"GC: Could not delete {item_path}: {e}")

def process_single_topic(topic, category):
    logging.info(f"--- Starting pipeline for topic: '{topic}' ---")
    
    # 1. Script Generation
    lines, topic_hash = generate_script_for_topic(topic)
    if not lines:
        logging.error("Pipeline aborted: Script generation failed.")
        return False
        
    logging.info(f"Generated {len(lines)} lines for script.")
    
    # 2. Audio & Visuals Per Line
    temp_dir = os.path.join("data", topic_hash)
    os.makedirs(temp_dir, exist_ok=True)
    
    audio_files = []
    image_files = []
    
    for i, line in enumerate(lines):
        logging.info(f"Processing line {i+1}/{len(lines)}...")
        raw_audio = os.path.join(temp_dir, f"raw_{i}.wav")
        proc_audio = os.path.join(temp_dir, f"proc_{i}.wav")
        
        # Audio
        if not generate_line_audio(line, raw_audio): return False
        if not process_audio(raw_audio, proc_audio, speed=1.1, silence_gap=0.3): return False
        audio_files.append(proc_audio)
        
        # Visual
        visual_path = get_visual_for_line(line, temp_dir, i)
        if not visual_path:
            logging.error("Failed to fetch visual. Aborting topic.")
            return False
        image_files.append(visual_path)
        
    # 3. Combine Audio
    full_audio = os.path.join(temp_dir, "full_audio.wav")
    if not concat_audio(audio_files, full_audio): return False
    
    # 4. Generate Subtitles
    srt_path = os.path.join(temp_dir, "subtitles.srt")
    total_duration = generate_srt(lines, audio_files, srt_path)
    if total_duration == 0: return False
    
    # 5. Video Segments
    video_segments = []
    for i, (vis, aud) in enumerate(zip(image_files, audio_files)):
        dur = get_audio_duration(aud)
        seg_out = os.path.join(temp_dir, f"seg_{i}.mp4")
        if not create_video_segment(vis, dur, seg_out): return False
        video_segments.append(seg_out)
        
    # 6. Concat Videos
    vid_concat = os.path.join(temp_dir, "vid_concat.mp4")
    if not concat_video_segments(video_segments, vid_concat): return False
    
    # 7. Mix Final
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    final_mp4 = os.path.join(output_dir, f"{topic_hash}_final.mp4")
    
    bgm_dir = os.path.join("assets", "bgm")
    bgm_files = glob.glob(os.path.join(bgm_dir, "*.mp3")) if os.path.exists(bgm_dir) else []
    bgm_path = random.choice(bgm_files) if bgm_files else None
    if bgm_path: logging.info(f"Selected BGM: {bgm_path}")
    
    if not mix_final_video(vid_concat, full_audio, srt_path, final_mp4, bgm_path=bgm_path): return False
    logging.info(f"Video rendered successfully to {final_mp4}")
    
    # 7.5 Thumbnail Generation
    thumb_path = os.path.join(temp_dir, "thumbnail.jpg")
    hook_keyword = extract_keyword(lines[0])
    generate_thumbnail(image_files[0], hook_keyword.upper(), thumb_path)
    
    # 8. Upload
    title, desc, tags = generate_metadata(topic, lines[0])
    upload_video(final_mp4, title, desc, tags, thumbnail_path=thumb_path)
    
    logging.info(f"--- Pipeline complete for topic: '{topic}' ---")
    return True


# ---------------------------------------------------------------------------
# Scheduler Configuration
# ---------------------------------------------------------------------------
SCHEDULER_INTERVAL = 300  # 5 minutes in seconds


def main():
    logging.info("=" * 60)
    logging.info("Starting YouTube Shorts Pipeline — Continuous Scheduler Mode")
    logging.info(f"Cycle interval: {SCHEDULER_INTERVAL // 60} minutes")
    logging.info("=" * 60)

    run_garbage_collection(days_old=2)

    # Initialize tweet database
    try:
        from src.storage.database import init_db, cleanup_old
        init_db()
    except ImportError:
        pass

    cycle_count = 0

    while True:
        cycle_count += 1
        cycle_start = time.time()
        logging.info(f"--- Scheduler Cycle #{cycle_count} starting ---")

        total_success = 0
        total_attempted = 0

        try:
            # Clean old tweet DB entries periodically
            try:
                from src.storage.database import cleanup_old
                cleanup_old(days=7)
            except ImportError:
                pass

            logging.info("Fetching topics...")
            category, topics = get_topics()

            if not topics:
                logging.info(
                    f"No new topics found. Sleeping {SCHEDULER_INTERVAL // 60} minutes..."
                )
                time.sleep(SCHEDULER_INTERVAL)
                continue

            # Strip invisible Unicode characters
            topics = [
                t.replace('\u200b', '').replace('\u200c', '')
                 .replace('\u200d', '').replace('\ufeff', '')
                for t in topics
            ]

            logging.info(f"Got {len(topics)} new topic(s) from '{category}'. Processing...")

            for topic in topics:
                total_attempted += 1
                try:
                    if process_single_topic(topic, category):
                        total_success += 1
                        with open("logs/success.log", "a", encoding="utf-8") as f:
                            f.write(f"{time.time()},{category},{topic}\n")
                except Exception as e:
                    logging.error(f"Top level error processing topic '{topic}': {e}")
                    with open("logs/error.log", "a", encoding="utf-8") as f:
                        f.write(f"{time.time()},{topic},{str(e)}\n")

        except KeyboardInterrupt:
            logging.info("Scheduler interrupted by user. Shutting down.")
            break
        except Exception as e:
            logging.error(f"Scheduler cycle #{cycle_count} failed: {e}")

        elapsed = time.time() - cycle_start
        logging.info(
            f"--- Cycle #{cycle_count} complete: "
            f"{total_success}/{total_attempted} succeeded in {elapsed:.1f}s. "
            f"Sleeping {SCHEDULER_INTERVAL // 60} minutes... ---"
        )
        time.sleep(SCHEDULER_INTERVAL)

if __name__ == "__main__":
    main()

