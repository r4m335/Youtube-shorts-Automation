import logging
from src.ingestion.x.fetcher import fetch_and_filter_tweets
from src.filters.duplicate import remove_known_tweets, deduplicate_similar
from src.filters.news_filter import pre_filter
from src.storage.database import insert_tweet, mark_tweet_status, update_tweet_dedup

def run_ingestion_phase(target_category=None):
    """
    PHASE 1: Scrapes accounts, filters out spam/short/duplicates, 
    and leaves only high-quality video-worthy tweets as 'pending' in the DB.
    Does NOT call the LLM to generate topics.
    """
    logging.info("=" * 60)
    cat_str = target_category if target_category else "Global"
    logging.info(f"PHASE 1: Starting Ingestion Pass ({cat_str})")
    logging.info("=" * 60)

    # 1. Scrape accounts
    raw_tweets = fetch_and_filter_tweets(tweets_per_account=50, target_category=target_category)
    if not raw_tweets:
        logging.info("Phase 1: No raw tweets collected.")
        return False

    logging.info(f"Phase 1: Fetched {len(raw_tweets)} raw tweets total.")

    # 2. Filter out already processed tweets (by ID)
    new_tweets = remove_known_tweets(raw_tweets)
    if not new_tweets:
        logging.info("Phase 1: All fetched tweets are already in DB.")
        return False

    # 3. Insert ALL new tweets into DB as 'pending'
    # We must insert even spam/short ones so the DB knows we saw them and doesn't scrape them again.
    for tw in new_tweets:
        insert_tweet(tw)

    # 4. Pre-filter (drop short, spam, old)
    filtered_tweets = pre_filter(new_tweets, max_age_hours=24)
    
    # 5. Semantic deduplication (merges multi-account stories)
    deduped_tweets = deduplicate_similar(filtered_tweets)

    # 6. Update the DB with the aggregated text and story_count for the deduped head tweets
    for tw in deduped_tweets:
        update_tweet_dedup(tw["tweet_id"], tw["text"], tw.get("story_count", 1))

    # 7. Identify the ones that were dropped during pre_filter and dedup
    valid_ids = {str(t["tweet_id"]) for t in deduped_tweets}
    
    dropped_count = 0
    for tw in new_tweets:
        tid = str(tw["tweet_id"])
        if tid not in valid_ids:
            # Mark it as completed/failed so Phase 2 ignores it
            mark_tweet_status(tid, "completed")
            dropped_count += 1

    logging.info(f"Phase 1 Complete: {len(deduped_tweets)} new tweets added to pending backlog. {dropped_count} filtered out.")
    return True
