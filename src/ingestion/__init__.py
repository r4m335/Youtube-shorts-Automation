import logging
from .pytrends_scraper import get_google_trends
from .filter import filter_and_cache_topics

def get_topics():
    """Fetches topics from Google Trends and returns a new filtered list."""
    logging.info("Starting topic ingestion process.")
    
    # 1. Fetch Google Trends
    gt_topics = get_google_trends()
    valid_gt = filter_and_cache_topics(gt_topics, source="google_trends")
    
    logging.info(f"Ingestion complete. Found {len(valid_gt)} new valid topics.")
    return valid_gt
