import os
import sys
import argparse
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
from src.visuals.fetcher import get_visual_for_line, extract_keyword, discover_articles, scrape_article_images, fetch_topic_context
from src.visuals import generate_ass, get_audio_duration
from src.render.engine import create_video_segment, concat_video_segments, mix_final_video, generate_thumbnail
from src.upload import generate_metadata, upload_video, add_to_playlist, get_all_channels

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



def run_garbage_collection(hours_old=1):
    """Deletes temporary rendering files, loaded images, and outputs older than hours_old to prevent storage bloat."""
    logging.info(f"Running Garbage Collector (Cleaning loaded images and temp files older than {hours_old}h)...")
    now = time.time()
    cutoff = now - (hours_old * 3600)
    
    # 1. Clean data/ temp folders (loaded images, audio, video segments)
    if os.path.exists("data"):
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

def cleanup_topic_temp_files(temp_dir):
    """Deletes all loaded images, downloaded tweet media, temporary video segments, and audio files for a topic."""
    if not temp_dir or not os.path.exists(temp_dir):
        return
    try:
        shutil.rmtree(temp_dir)
        logging.info(f"GC: Automatically cleaned up loaded images and temp directory: {temp_dir}")
    except Exception as e:
        logging.warning(f"GC: Could not clean up {temp_dir}: {e}")

def process_single_topic(topic, category, tweet_media_urls=None, tweet_text=""):
    logging.info(f"--- Starting pipeline for topic: '{topic}' ---")
    
    # Reset TTS voice for this video (randomly picks Jenny or Andrew)
    from src.audio.tts import reset_session_voice
    reset_session_voice()
    
    # 0.5 Fetch RAG Context to prevent hallucinations
    topic_context = fetch_topic_context(topic)

    # 1. Script Generation
    lines, topic_hash = generate_script_for_topic(topic, context=topic_context)
    if not lines:
        logging.error("Pipeline aborted: Script generation failed.")
        return False
        
    logging.info(f"Generated {len(lines)} lines for script.")
    
    # 1.5 Quality Gate Evaluation & Auto-Refinement
    from src.llm.validator import evaluate_script_quality
    from src.llm.generate import refine_script_with_feedback, save_script_to_cache
    
    is_good, reason = evaluate_script_quality(topic, lines)
    if not is_good:
        logging.warning(f"Initial script REJECTED for topic '{topic}': {reason}")
        logging.info("Attempting auto-refinement to fix feedback issues...")
        
        refined_lines = refine_script_with_feedback(topic, lines, reason, context=topic_context)
        if refined_lines:
            is_good_2, reason_2 = evaluate_script_quality(topic, refined_lines)
            if is_good_2:
                logging.info(f"Auto-refinement SUCCESSFUL for topic '{topic}': {reason_2}")
                lines = refined_lines
                save_script_to_cache(topic_hash, lines)
            else:
                logging.warning(f"Refined script REJECTED again for topic '{topic}': {reason_2}")
                logging.warning("Aborting video generation for unfixable content.")
                return False
        else:
            logging.warning("Script auto-refinement failed. Aborting topic.")
            return False
    else:
        logging.info(f"Script quality evaluation PASSED: {reason}")
    
    # 2. Audio & Visuals Per Line
    temp_dir = os.path.join("data", topic_hash)
    os.makedirs(temp_dir, exist_ok=True)
    try:
        audio_files = []
        image_files = []
        
        # Pre-fetch article images pool (MANDATORY — pipeline fails without images)
        article_image_pool = []
        
        # 1. Extract URLs from the tweet text and topic
        import re
        source_text = f"{tweet_text} {topic}".strip()
        topic_urls = re.findall(r'(https?://[^\s]+)', source_text)
        if topic_urls:
            article_image_pool.extend(scrape_article_images(topic_urls, temp_dir))
            
        # 2. Discover and scrape related articles (aggressive — fetch more)
        if len(article_image_pool) < len(lines):
            llm_urls = discover_articles(topic, limit=8)
            if llm_urls:
                article_image_pool.extend(scrape_article_images(llm_urls, temp_dir))
        
        # STRICT CHECK: If we have NO article images AND NO tweet media, abort immediately (except for world news which uses full visual API chain)
        has_tweet_media = bool(tweet_media_urls)
        is_world_news = (str(category).lower() == "world")
        if not is_world_news and not article_image_pool and not has_tweet_media:
            logging.error(
                f"PIPELINE ABORTED: No article images could be scraped and no tweet media available for topic '{topic}'. "
                f"Cannot produce on-topic visuals — refusing to use unrelated stock content."
            )
            return False
        
        logging.info(f"Visual pool: {len(article_image_pool)} article images, tweet_media={'yes' if has_tweet_media else 'no'}, is_world_news={is_world_news}")

        for i, line in enumerate(lines):
            logging.info(f"Processing line {i+1}/{len(lines)}...")
            raw_audio = os.path.join(temp_dir, f"raw_{i}.wav")
            proc_audio = os.path.join(temp_dir, f"proc_{i}.wav")
            
            # Audio
            if not generate_line_audio(line, raw_audio): return False
            if not process_audio(raw_audio, proc_audio, speed=1.1, silence_gap=0.3): return False
            audio_files.append(proc_audio)
            
            # Visual — use tweet media for ALL lines (not just first)
            line_media = tweet_media_urls if tweet_media_urls else None
            
            art_img = None
            # 1. Try to use a unique article image first
            if i < len(article_image_pool):
                art_img = article_image_pool[i]
            # 2. If pool is exhausted, loop the article pool
            elif article_image_pool:
                art_img = article_image_pool[i % len(article_image_pool)]
                    
            visual_result = get_visual_for_line(line, temp_dir, i, topic=topic, tweet_media_urls=line_media, category=category, article_image=art_img)
            if not visual_result or not visual_result[0]:
                logging.error(f"Failed to fetch on-topic visual for line {i+1}. Aborting topic.")
                return False
            
            # For world news: keep the tuple (img, bg_video) if bg_video exists for hybrid rendering
            if is_world_news and visual_result[1]:
                image_files.append(visual_result)
            else:
                image_files.append(visual_result[0])
            
        # 3. Combine Audio
        full_audio = os.path.join(temp_dir, "full_audio.wav")
        if not concat_audio(audio_files, full_audio): return False
        
        # 4. Generate Subtitles
        srt_path = os.path.join(temp_dir, "subtitles.ass")
        total_duration = generate_ass(lines, audio_files, srt_path)
        if total_duration == 0: return False
        
        # 5. Video Segments
        video_segments = []
        for i, (vis, aud) in enumerate(zip(image_files, audio_files)):
            dur = get_audio_duration(aud)
            seg_out = os.path.join(temp_dir, f"seg_{i}.mp4")
            if not create_video_segment(vis, dur, seg_out, is_hook=(i == 0)): return False
            video_segments.append(seg_out)
            
        # 6. Concat Videos
        vid_concat = os.path.join(temp_dir, "vid_concat.mp4")
        if not concat_video_segments(video_segments, vid_concat): return False
        
        # 7. Mix Final
        output_dir = "output"
        os.makedirs(output_dir, exist_ok=True)
        final_mp4 = os.path.join(output_dir, f"{topic_hash}_final.mp4")
        
        if not mix_final_video(vid_concat, full_audio, srt_path, final_mp4): return False
        logging.info(f"Video rendered successfully to {final_mp4}")
        
        # 7.5 Thumbnail Generation
        thumb_path = os.path.join(temp_dir, "thumbnail.jpg")
        hook_keyword = extract_keyword(lines[0])
        
        # If image_files[0] is a tuple (img_path, vid_path), use the primary image
        thumb_source = image_files[0][0] if isinstance(image_files[0], tuple) else image_files[0]
        generate_thumbnail(thumb_source, hook_keyword.upper(), thumb_path)
        
        # 8. Upload
        title, desc, tags = generate_metadata(topic, lines[0], script_lines=lines)
        video_id = upload_video(final_mp4, title, desc, tags, category=category, thumbnail_path=thumb_path)
        
        # 9. Add to category playlist
        if video_id:
            add_to_playlist(video_id, category)
        
        logging.info(f"--- Pipeline complete for topic: '{topic}' ---")
        return True
    finally:
        # 9. Clean up loaded images and temporary files for this topic
        cleanup_topic_temp_files(temp_dir)


# ---------------------------------------------------------------------------
# Scheduler Configuration
# ---------------------------------------------------------------------------
SCHEDULER_INTERVAL = 300  # 5 minutes in seconds


def main():
    parser = argparse.ArgumentParser(description="YouTube Shorts Automation Pipeline")
    parser.add_argument("--skip-channel", action="append", default=[], help="Skip processing for a specific channel (e.g. entertainment). Can be used multiple times.")
    parser.add_argument("--max-videos", type=int, default=32, help="Stop pipeline automatically after uploading this many videos (default: 32)")
    args = parser.parse_args()

    MAX_TOTAL_VIDEOS = args.max_videos

    logging.info("=" * 60)
    logging.info("Starting YouTube Shorts Pipeline — Continuous Scheduler Mode")
    logging.info(f"Cycle interval: {SCHEDULER_INTERVAL // 60} minutes")
    logging.info(f"Max video upload target: {MAX_TOTAL_VIDEOS}")
    if args.skip_channel:
        logging.info(f"Skipping channels: {args.skip_channel}")
    logging.info("=" * 60)

    logging.info("Checking for twscrape updates...")
    try:
        import subprocess
        subprocess.run(["pip", "install", "--upgrade", "twscrape"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        logging.warning(f"Failed to check for scraper updates: {e}")

    run_garbage_collection(hours_old=1)

    # Initialize tweet database and reset stuck states
    try:
        from src.storage.database import init_db, cleanup_old, reset_stale_processing_tweets
        init_db()
        cleanup_old(days=7)
        reset_stale_processing_tweets()
    except ImportError:
        pass

    global_success_count = 0
    first_run = True

    while True:
        if global_success_count >= MAX_TOTAL_VIDEOS:
            logging.info(f"🎯 Target limit of {MAX_TOTAL_VIDEOS} videos reached ({global_success_count}/{MAX_TOTAL_VIDEOS}). Pipeline stopping automatically.")
            break

        cycle_start = time.time()
        
        # ---------------------------------------------------------
        # PHASE 1: INGESTION
        # ---------------------------------------------------------
        try:
            from src.storage.database import get_backlog_stats
            from src.ingestion.x.account_manager import load_accounts
            
            stats = get_backlog_stats() or {}
            accounts = load_accounts()
            active_categories = list(accounts.keys()) if accounts else []
            
            from src.ingestion.scraper_job import run_ingestion_phase

            if first_run:
                logging.info("Initial startup: Scraping all categories to refresh backlog.")
                run_ingestion_phase(target_category=None)
                first_run = False
            else:
                # Find categories that are empty
                empty_cats = [cat for cat in active_categories if stats.get(cat, 0) == 0]
                
                if empty_cats:
                    logging.info(f"Smart Scrape: Categories {empty_cats} have 0 pending tweets. Scraping only these.")
                    for cat in empty_cats:
                        run_ingestion_phase(target_category=cat)
                else:
                    logging.info("Skipping Phase 1 Ingestion: Backlog has pending tweets for all active categories.")
        except Exception as e:
            import traceback
            logging.error(f"Phase 1 Ingestion failed: {e}\n{traceback.format_exc()}")
            
        # Verify and Print DB Stats
        try:
            from src.storage.database import get_backlog_stats
            stats = get_backlog_stats()
            logging.info("--- DATABASE BACKLOG STATS ---")
            if not stats:
                logging.info("tweets.db is completely empty (no pending tweets).")
            else:
                logging.info("tweets.db")
                for cat, count in stats.items():
                    logging.info(f"├── {cat:<12} {count} pending")
            logging.info("------------------------------")
        except Exception as e:
            pass

        # ---------------------------------------------------------
        # PHASE 2: VIDEO GENERATION (per-channel, 8 videos each)
        # ---------------------------------------------------------
        VIDEOS_PER_CHANNEL = 8
        channels = get_all_channels()
        total_target = len(channels) * VIDEOS_PER_CHANNEL
        
        logging.info(f"PHASE 2: Starting Video Generation — {len(channels)} channels × {VIDEOS_PER_CHANNEL} videos = {total_target} target")
        
        try:
            from src.storage.database import get_pending_tweet_for_category, mark_tweet_status
            from src.ingestion.orchestrator import generate_topics_from_tweets
            from src.ingestion.filter import filter_and_cache_topics, remove_from_cache
            
            for channel_name, channel_cfg in channels.items():
                if global_success_count >= MAX_TOTAL_VIDEOS:
                    break

                if channel_name in args.skip_channel:
                    logging.info(f"=== Skipping Channel '{channel_name}' due to --skip-channel ===")
                    continue
                
                channel_categories = channel_cfg.get("categories", [])
                channel_success = 0
                
                logging.info(f"=== Channel '{channel_name}' — categories: {channel_categories} ===")
                
                # Round-robin through this channel's categories until 8 videos
                max_passes = VIDEOS_PER_CHANNEL  # safety limit to avoid infinite loop
                for pass_num in range(max_passes):
                    if channel_success >= VIDEOS_PER_CHANNEL or global_success_count >= MAX_TOTAL_VIDEOS:
                        break
                    
                    all_skipped = True  # track if all categories had no tweets
                    
                    for category in channel_categories:
                        if channel_success >= VIDEOS_PER_CHANNEL or global_success_count >= MAX_TOTAL_VIDEOS:
                            break
                        
                        logging.info(f"[{channel_name}] Pass {pass_num+1}, checking '{category}' ({channel_success}/{VIDEOS_PER_CHANNEL})...")
                        
                        tweet = get_pending_tweet_for_category(category)
                        if not tweet:
                            logging.info(f"No pending tweets for '{category}'. Skipping.")
                            continue
                        
                        all_skipped = False
                        logging.info(f"Found pending tweet for '{category}': {tweet['text'][:50]}...")
                        
                        try:
                            _, topics = generate_topics_from_tweets([tweet], target_category=category)
                            
                            if not topics:
                                logging.warning(f"LLM failed to generate a topic for tweet {tweet['tweet_id']}. Marking as failed.")
                                mark_tweet_status(tweet["tweet_id"], "failed")
                                continue
                            
                            valid_topics = filter_and_cache_topics(topics, source="database")
                            if not valid_topics:
                                logging.info("Topic generated was a duplicate in cache. Marking as failed.")
                                mark_tweet_status(tweet["tweet_id"], "failed")
                                continue
                            
                            topic = valid_topics[0]
                            logging.info(f"Generating video for topic: '{topic}'")
                            best_tweet_media = tweet.get("media") or None
                            if best_tweet_media:
                                logging.info(f"Using {len(best_tweet_media)} real Twitter media URL(s) for topic: '{topic}'")
                            
                            if process_single_topic(topic, category, tweet_media_urls=best_tweet_media, tweet_text=tweet.get("text", "")):
                                channel_success += 1
                                global_success_count += 1
                                with open("logs/success.log", "a", encoding="utf-8") as f:
                                    f.write(f"{time.time()},{category},{topic}\n")
                                mark_tweet_status(tweet["tweet_id"], "completed", topic=topic, youtube_id="generated")
                                logging.info(f"[{channel_name}] '{category}' video done ({channel_success}/{VIDEOS_PER_CHANNEL}, total {global_success_count}/{total_target})")
                                if global_success_count >= MAX_TOTAL_VIDEOS:
                                    logging.info(f"🎯 Target limit of {MAX_TOTAL_VIDEOS} videos reached ({global_success_count}/{MAX_TOTAL_VIDEOS})! Pipeline completed successfully. Exiting.")
                                    return
                            else:
                                remove_from_cache(topic)
                                logging.warning(f"Failed to generate video for '{topic}'. Marking tweet as failed.")
                                mark_tweet_status(tweet["tweet_id"], "failed")
                        
                        except Exception as e:
                            import traceback
                            logging.error(f"Error processing '{category}': {e}\n{traceback.format_exc()}")
                            mark_tweet_status(tweet["tweet_id"], "failed")
                        
                        logging.info(f"Sleeping 15s before next topic...")
                        time.sleep(15)
                    
                    # If all categories had no tweets this pass, stop early
                    if all_skipped:
                        logging.info(f"[{channel_name}] All categories exhausted. Moving to next channel.")
                        break
                
                logging.info(f"=== Channel '{channel_name}' complete: {channel_success}/{VIDEOS_PER_CHANNEL} videos ===")
            
            logging.info(f"All channels processed. Total videos: {global_success_count}/{total_target}")
            if global_success_count >= MAX_TOTAL_VIDEOS:
                logging.info(f"🎯 Target limit of {MAX_TOTAL_VIDEOS} videos reached! Pipeline shutting down.")
                break

        except KeyboardInterrupt:
            logging.info("Scheduler interrupted by user. Shutting down.")
            break
        except Exception as e:
            logging.error(f"Phase 2 failed: {e}")

        elapsed = time.time() - cycle_start
        logging.info(f"--- Cycle complete in {elapsed:.1f}s. Sleeping {SCHEDULER_INTERVAL // 60} minutes... ---")
        time.sleep(SCHEDULER_INTERVAL)

if __name__ == "__main__":
    main()

