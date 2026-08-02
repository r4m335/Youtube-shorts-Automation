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


def _try_x_ingestion():
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
    raw_tweets = fetch_and_filter_tweets(tweets_per_account=10)

    if not raw_tweets:
        logging.info("X Ingestion: no tweets fetched. Falling back.")
        return None, []

    logging.info(f"X Ingestion: fetched {len(raw_tweets)} raw tweets.")

    # Step 2: Remove already-processed tweets
    new_tweets = remove_known_tweets(raw_tweets)
    if not new_tweets:
        logging.info("X Ingestion: all tweets already processed. Falling back.")
        return None, []

    # Step 3: Insert new tweets into the database
    for tweet in new_tweets:
        insert_tweet(tweet)

    # Step 4: Pre-filter (replies, RTs, spam, old, short)
    filtered = pre_filter(new_tweets, max_age_hours=24)
    if not filtered:
        logging.info("X Ingestion: all tweets filtered out by pre-filter. Falling back.")
        return None, []

    # Step 5: Semantic deduplication (merge same-story tweets from different sources)
    deduped = deduplicate_similar(filtered)

    # Step 6: LLM news quality filter
    accepted = llm_news_filter(deduped)
    if not accepted:
        logging.info("X Ingestion: no tweets passed LLM news filter. Falling back.")
        return None, []

    # Step 7: Convert accepted tweets into topic titles via LLM
    category, topics = generate_topics_from_tweets(accepted)
    if not topics:
        logging.info("X Ingestion: tweet-to-topic conversion produced no topics. Falling back.")
        return None, []

    # Step 8: Filter through the existing cache dedup
    valid_topics = filter_and_cache_topics(topics, source=f"x_{category}")
    if not valid_topics:
        logging.info("X Ingestion: all topics were duplicates in cache. Falling back.")
        return None, []

    logging.info(
        f"X Ingestion complete: {len(valid_topics)} new valid topics "
        f"from category '{category}'."
    )
    return category, valid_topics


def get_topics():
    """
    Generates topics by trying X ingestion first, then falling back to the
    existing category-based Reddit/RSS pipeline.

    Priority:
      1. X (twscrape) — fetch tweets from monitored accounts
      2. Category walk — Global News → Tech → Football → Movies → Anime

    Returns:
        (category_name, topics_list)
    """
    logging.info("Starting topic ingestion process.")

    # --- Primary: X (twscrape) ingestion ---
    try:
        category, topics = _try_x_ingestion()
        if topics:
            return category, topics
    except Exception as e:
        logging.warning(f"X ingestion failed with error: {e}. Falling back to categories.")

    # --- Fallback: existing category-based pipeline ---
    logging.info("Falling back to category-based ingestion (Reddit/RSS).")

    for category in ALL_CATEGORIES:
        cat_name = category["name"]
        logging.info(f"Ingestion: trying category '{cat_name}'")

        for attempt in range(1, RETRIES_PER_CATEGORY + 1):
            name, generated_topics = generate_topics_for_category(category)

            if not generated_topics:
                logging.warning(
                    f"[{cat_name}] Attempt {attempt}: LLM returned no topics. "
                    f"{'Retrying...' if attempt < RETRIES_PER_CATEGORY else 'Moving to next category.'}"
                )
                continue

            valid_topics = filter_and_cache_topics(generated_topics, source=name)
            if valid_topics:
                logging.info(
                    f"Ingestion complete. Found {len(valid_topics)} new valid topics "
                    f"in '{cat_name}'."
                )
                return name, valid_topics

            logging.warning(
                f"[{cat_name}] Attempt {attempt}: All topics were duplicates/invalid. "
                f"{'Retrying...' if attempt < RETRIES_PER_CATEGORY else 'Moving to next category.'}"
            )

        logging.warning(f"Category '{cat_name}' exhausted — no unique valid topics found.")

    logging.error("All categories exhausted. No unique valid topics found.")
    return "Unknown", []
