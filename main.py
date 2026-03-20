import os
import sys
import logging
import time
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
        logging.FileHandler("logs/system.log"),
        logging.StreamHandler()
    ]
)

MAX_VIDEOS_PER_RUN = 1

def process_single_topic(topic):
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
    import glob, random
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
    # Uncomment to actually upload:
    upload_video(final_mp4, title, desc, tags, thumbnail_path=thumb_path)
    
    logging.info(f"--- Pipeline complete for topic: '{topic}' ---")
    return True

def main():
    logging.info("Starting YouTube Shorts Pipeline Run")
    topics = get_topics()
    
    if not topics:
        logging.info("No new valid topics found. Exiting.")
        return
        
    success_count = 0
    for topic in topics:
        if success_count >= MAX_VIDEOS_PER_RUN:
            logging.info(f"Reached max videos per run ({MAX_VIDEOS_PER_RUN}). Stopping.")
            break
            
        try:
            if process_single_topic(topic):
                success_count += 1
                with open("logs/success.log", "a") as f:
                    f.write(f"{time.time()},{topic}\n")
        except Exception as e:
            logging.error(f"Top level error processing topic '{topic}': {e}")
            with open("logs/error.log", "a") as f:
                f.write(f"{time.time()},{topic},{str(e)}\n")
                
    logging.info(f"Run completed. Generated {success_count} videos.")

if __name__ == "__main__":
    main()
