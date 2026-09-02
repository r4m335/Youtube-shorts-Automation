import asyncio
import logging
import random

from .account_manager import load_accounts
from .health import check_health_status, XHealthState, record_failure, record_success
from .session import get_account_state, update_account_success, record_account_failure
from .browser import scrape_profile
from .exceptions import XSessionState, XTimeoutError, XNetworkError, XParseError, XScraperError
from .models import Tweet

CATEGORY_PRIORITY = [
    "sports", "world", "India", "Tech", "Movie", "Anime", "Cdrama", "Kdrama"
]

def fetch_and_filter_tweets(tweets_per_account=10, target_category=None):
    """
    Synchronous entry point for the X tweet pipeline.
    Uses Playwright as the primary engine. Legacy wrappers (twscrape, Twikit) are DISABLED.
    Returns:
        List of normalized tweet dicts, or empty list on failure.
    """
    state = check_health_status()
    if state == XHealthState.DISABLED:
        logging.warning("X ingestion is globally DISABLED by the circuit breaker. Skipping X fetch.")
        return []
    elif state == XHealthState.DEGRADED:
        logging.info("X ingestion is DEGRADED. Will attempt cautiously.")

    accounts = load_accounts()
    if target_category and accounts:
        accounts = {c: u for c, u in accounts.items() if c.lower() == target_category.lower()}
        
    if not accounts:
        logging.info("No X accounts configured. Skipping X ingestion.")
        return []

    # Build account list prioritizing highest-ranked categories first
    def category_rank(cat_name):
        cat_lower = cat_name.lower()
        for idx, prio in enumerate(CATEGORY_PRIORITY):
            if prio.lower() == cat_lower:
                return idx
        return len(CATEGORY_PRIORITY)

    sorted_categories = sorted(accounts.keys(), key=category_rank)
    
    sampled_accounts = []
    max_accounts_per_run = 18
    for cat in sorted_categories:
        usernames = list(accounts[cat])
        random.shuffle(usernames)
        for u in usernames:
            sampled_accounts.append((cat, u))
            if len(sampled_accounts) >= max_accounts_per_run:
                break
        if len(sampled_accounts) >= max_accounts_per_run:
            break

    try:
        results = asyncio.run(_process_accounts_async(sampled_accounts, tweets_per_account))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            results = loop.run_until_complete(_process_accounts_async(sampled_accounts, tweets_per_account))
        finally:
            loop.close()

    logging.info(f"Normalized {len(results)} tweets from X.")
    return [t.to_dict() for t in results]


async def _process_accounts_async(sampled_accounts, limit):
    all_tweets = []
    
    for category, username in sampled_accounts:
        acc_state = get_account_state(username)
        if acc_state.get("consecutive_failures", 0) > 3:
            logging.info(f"Skipping @{username} due to previous account-level failures.")
            continue
            
        try:
            logging.info(f"X: Starting profile @{username}")
            last_id = acc_state.get("last_seen_tweet_id")
            session_state, tweets = await scrape_profile(username, last_seen_tweet_id=last_id)
            
            if session_state == XSessionState.LOGIN_REQUIRED:
                logging.error("[WARNING] X authentication required! Please run scripts/setup_x_session.py")
                # Force 3 failures to trigger global disable
                record_failure("__AUTH__")
                record_failure("__AUTH__")
                record_failure("__AUTH__")
                break
            elif session_state == XSessionState.CHALLENGE:
                logging.error(f"[WARNING] X account challenged! Skipping.")
                record_failure("__AUTH__")
                break
                
            logging.info(f"X: Collected {len(tweets)} tweets for @{username}")
            
            if tweets:
                # Enforce the token-saving limit before passing to orchestrator
                tweets = tweets[:limit]
                
                for t in tweets:
                    t.category = category
                    all_tweets.append(t)
                    
                highest_id = last_id
                valid_ids = [int(t.id) for t in tweets if t.id.isdigit()]
                if last_id and last_id.isdigit():
                    valid_ids.append(int(last_id))
                
                if valid_ids:
                    highest_id = str(max(valid_ids))
                    
                update_account_success(username, highest_id)
                record_success()
                
        except (XTimeoutError, XNetworkError, XParseError) as e:
            logging.warning(f"X: Failure on @{username}: {type(e).__name__} - {e}")
            record_account_failure(username)
            global_state = record_failure(username)
            
            if global_state == XHealthState.DISABLED:
                logging.error("X Scraper Health Check Failed. Aborting X ingestion cycle.")
                break
        except Exception as e:
            logging.warning(f"X: Unexpected error on @{username}: {e}")
            
    return all_tweets
