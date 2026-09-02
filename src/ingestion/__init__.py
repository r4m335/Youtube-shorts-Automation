import logging
from .orchestrator import (
    CATEGORIES,
    FALLBACK_CATEGORIES,
    generate_topics_for_category,
    generate_topics_from_tweets,
)
from .filter import filter_and_cache_topics

# Full ordered list of categories to try: Global News first, then fallbacks
ALL_CATEGORIES = CATEGORIES + FALLBACK_CATEGORIES

# How many times to retry the *same* category if the LLM returns topics but
# the filter rejects them all as duplicates.
RETRIES_PER_CATEGORY = 2


def _try_x_ingestion(target_category=None):
    """
    Attempts to fetch topics from X via twscrape.
    Returns (category, topics) or (None, []) if X is unavailable or yields nothing.
    """
    try:
        from src.ingestion.x.fetcher import fetch_and_filter_tweets
        from src.filters.duplicate import remove_known_tweets, deduplicate_similar
        from src.filters.news_filter import pre_filter, llm_news_filter
        from src.storage.database import init_db, insert_tweet
    except ImportError as e:
        logging.debug(f"X ingestion modules not available: {e}")
        return None, []

    # Initialize the tweet database
    init_db()

    # Step 1: Fetch tweets from all monitored accounts
    logging.info("X Ingestion: fetching tweets from monitored accounts...")
    raw_tweets = fetch_and_filter_tweets(tweets_per_account=50, target_category=target_category)

    if not raw_tweets:
        logging.info("X Ingestion: no tweets fetched. Falling back.")
        return None, [], []

    logging.info(f"X Ingestion: fetched {len(raw_tweets)} raw tweets.")

    # Step 2: Remove already-processed tweets
    new_tweets = remove_known_tweets(raw_tweets)
    if not new_tweets:
        logging.info("X Ingestion: all tweets already processed. Falling back.")
        return None, [], []

    # Step 3: Insert new tweets into the database
    for tweet in new_tweets:
        insert_tweet(tweet)

    # Step 4: Pre-filter (replies, RTs, spam, old, short)
    filtered = pre_filter(new_tweets, max_age_hours=24)
    if not filtered:
        logging.info("X Ingestion: all tweets filtered out by pre-filter. Falling back.")
        return None, [], []

    # Step 5: Semantic deduplication (merge same-story tweets from different sources)
    deduped = deduplicate_similar(filtered)

    # Step 6: LLM news quality filter
    accepted = llm_news_filter(deduped)
    if not accepted:
        logging.info("X Ingestion: no tweets passed LLM news filter. Falling back.")
        return None, [], []

    # Step 6.5: Save accepted tweets to the Backlog to protect against crashes/interrupts
    from src.storage.backlog import add_to_backlog
    for tw in accepted:
        add_to_backlog(tw)

    # Step 7: Convert accepted tweets into topic titles via LLM
    category, topics = generate_topics_from_tweets(accepted, target_category=target_category)
    if not topics:
        logging.info("X Ingestion: tweet-to-topic conversion produced no topics. Falling back.")
        return None, [], []

    # Step 8: Filter through the existing cache dedup
    valid_topics = filter_and_cache_topics(topics, source=f"x_{category}")
    if not valid_topics:
        logging.info("X Ingestion: all topics were duplicates in cache. Falling back.")
        return None, [], []

    logging.info(
        f"X Ingestion complete: {len(valid_topics)} new valid topics "
        f"from category '{category}'."
    )
    return category, valid_topics, accepted


def get_topics(target_category=None):
    """
    Generates topics by trying X ingestion first, then falling back to the
    existing category-based Reddit/RSS pipeline.

    Priority:
      1. X (twscrape) — fetch tweets from monitored accounts
      2. Category walk — Global News → Tech → Football → Movies → Anime

    Returns:
        (category_name, topics_list, source_tweets)
        source_tweets is a list of tweet dicts with 'media' URLs (empty list if from RSS/Reddit).
    """
    logging.info("Starting topic ingestion process.")

    # --- Primary: X (twscrape) ingestion ---
    try:
        category, topics, source_tweets = _try_x_ingestion(target_category=target_category)
        if topics:
            return category, topics, source_tweets
    except Exception as e:
        logging.warning(f"X ingestion failed with error: {e}.")

    logging.info(f"No valid topics found from X (Twitter) for '{target_category or 'all'}'. Skipping fallback and waiting for new tweets.")
    return "Unknown", [], []
