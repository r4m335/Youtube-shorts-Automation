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
    "sports", "world", "Tech", "Anime", "Cdrama"
]


def extract_twscrape_media(t):
    """Extracts photo, video, and animated GIF URLs from a twscrape tweet object."""
    media_urls = []
    if not t or not getattr(t, 'media', None):
        return media_urls
        
    # Photos
    if getattr(t.media, 'photos', None):
        for p in t.media.photos:
            if getattr(p, 'url', None):
                media_urls.append(p.url)
                
    # Videos (pick highest bitrate mp4 variant)
    if getattr(t.media, 'videos', None):
        for v in t.media.videos:
            mp4_vars = [var for var in getattr(v, 'variants', []) if getattr(var, 'url', None) and ".mp4" in var.url.lower()]
            if mp4_vars:
                best_var = max(mp4_vars, key=lambda x: getattr(x, 'bitrate', 0) or 0)
                media_urls.append(best_var.url)
                
    # Animated GIFs
    if getattr(t.media, 'animated', None):
        for a in t.media.animated:
            if getattr(a, 'videoUrl', None):
                media_urls.append(a.videoUrl)
                
    return media_urls


async def _fetch_tweets_twscrape(username, limit=10):
    """
    Attempts to fetch tweets for username using twscrape.
    Returns list of Tweet objects, or raises an Exception if failed/empty.
    """
    from .client import get_client
    api = get_client()
    user = await api.user_by_login(username)
    if not user or not getattr(user, 'id', None):
        raise ValueError(f"User @{username} not found via twscrape")

    tweets = []
    async for t in api.user_tweets(user.id, limit=limit):
        media = extract_twscrape_media(t)
        tw = Tweet(
            id=str(t.id),
            username=t.user.username,
            text=t.rawContent,
            url=t.url,
            created_at=t.date,
            reply_count=getattr(t, 'replyCount', 0) or 0,
            repost_count=getattr(t, 'retweetCount', 0) or 0,
            like_count=getattr(t, 'likeCount', 0) or 0,
            view_count=getattr(t, 'viewCount', 0) or 0,
            media=media
        )
        tweets.append(tw)

    if not tweets:
        raise ValueError(f"twscrape returned 0 tweets for @{username}")

    return tweets


def fetch_and_filter_tweets(tweets_per_account=10, target_category=None):
    """
    Synchronous entry point for the X tweet pipeline.
    Uses a hybrid pipeline: twscrape (fast GraphQL API) as first choice,
    falling back seamlessly to headless Playwright browser if twscrape fails.
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
    
    # Check if twscrape account pool is ready
    twscrape_ready = False
    try:
        from .client import setup_account
        twscrape_ready = await setup_account()
        if twscrape_ready:
            logging.info("X: twscrape account pool is active and ready (Primary Choice).")
    except Exception as e:
        logging.warning(f"X: twscrape initialization failed ({e}). Will use Playwright browser scraper directly.")

    for category, username in sampled_accounts:
        acc_state = get_account_state(username)
        if acc_state.get("consecutive_failures", 0) > 3:
            logging.info(f"Skipping @{username} due to previous account-level failures.")
            continue
            
        tweets = []
        source_used = None
        
        # --- Choice 1: twscrape (fast GraphQL API) ---
        if twscrape_ready:
            try:
                logging.info(f"X (twscrape): Fetching profile @{username}...")
                tweets = await _fetch_tweets_twscrape(username, limit=limit)
                source_used = "twscrape"
                logging.info(f"X (twscrape): Collected {len(tweets)} tweets for @{username}")
            except Exception as e:
                logging.warning(f"X (twscrape) failed for @{username}: {e}. Falling back to Playwright browser scraper...")
                tweets = []

        # --- Choice 2: Playwright Headless Browser Fallback ---
        if not tweets:
            try:
                logging.info(f"X (Playwright): Starting browser profile @{username}")
                last_id = acc_state.get("last_seen_tweet_id")
                session_state, tweets = await scrape_profile(username, last_seen_tweet_id=last_id)
                
                if session_state == XSessionState.LOGIN_REQUIRED:
                    logging.error("[WARNING] X authentication required for browser scraper! Please run scripts/setup_x_session.py")
                    record_failure("__AUTH__")
                    record_failure("__AUTH__")
                    record_failure("__AUTH__")
                    break
                elif session_state == XSessionState.CHALLENGE:
                    logging.error(f"[WARNING] X account challenged! Skipping.")
                    record_failure("__AUTH__")
                    break
                    
                source_used = "playwright"
                logging.info(f"X (Playwright): Collected {len(tweets)} tweets for @{username}")
            except (XTimeoutError, XNetworkError, XParseError) as e:
                logging.warning(f"X (Playwright): Failure on @{username}: {type(e).__name__} - {e}")
                record_account_failure(username)
                global_state = record_failure(username)
                
                if global_state == XHealthState.DISABLED:
                    logging.error("X Scraper Health Check Failed. Aborting X ingestion cycle.")
                    break
                continue
            except Exception as e:
                logging.warning(f"X (Playwright): Unexpected error on @{username}: {e}")
                continue

        if tweets:
            tweets = tweets[:limit]
            
            for t in tweets:
                t.category = category
                all_tweets.append(t)
                
            last_id = acc_state.get("last_seen_tweet_id")
            highest_id = last_id
            valid_ids = [int(t.id) for t in tweets if t.id.isdigit()]
            if last_id and last_id.isdigit():
                valid_ids.append(int(last_id))
            
            if valid_ids:
                highest_id = str(max(valid_ids))
                
            update_account_success(username, highest_id)
            record_success()
            
    return all_tweets
