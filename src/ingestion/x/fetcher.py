import asyncio
import random
import logging

from .client import get_client, setup_account
from .account_manager import load_accounts, get_category_for_user
from .parser import normalize_all

# Retry config
MAX_RETRIES = 3
RETRY_BASE_DELAY = 5  # seconds


async def fetch_account_tweets(api, username, limit=10):
    """
    Fetches the latest tweets from a single account.

    Args:
        api: The twscrape API instance.
        username: X username to fetch tweets from.
        limit: Maximum number of tweets to fetch.

    Returns:
        List of twscrape Tweet objects, or empty list on failure.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            user = await api.user_by_login(username)
            if not user:
                logging.warning(f"Could not resolve user '{username}'.")
                return []

            tweets = []
            async for tweet in api.user_tweets(user.id, limit=limit):
                tweets.append(tweet)

            logging.info(f"Fetched {len(tweets)} tweets from @{username}.")
            return tweets

        except Exception as e:
            if attempt < MAX_RETRIES:
                delay = RETRY_BASE_DELAY * attempt
                logging.warning(
                    f"Fetch failed for @{username} (attempt {attempt}/{MAX_RETRIES}): {e}. "
                    f"Retrying in {delay}s..."
                )
                await asyncio.sleep(delay)
            else:
                logging.error(
                    f"Fetch failed for @{username} after {MAX_RETRIES} attempts: {e}. Skipping."
                )
                return []


async def _fetch_all_accounts_async(accounts_by_category, tweets_per_account=5, max_accounts_per_run=15):
    """
    Fetches tweets from a sampled subset of monitored accounts per cycle.
    Adds rate-limit safety timeouts to prevent hanging when X limits are reached.

    Args:
        accounts_by_category: Dict of {category: [username_list]}
        tweets_per_account: Max tweets to fetch per account.
        max_accounts_per_run: Max total accounts to query per cycle.

    Returns:
        Dict of {category: [Tweet_objects]}
    """
    api = get_client()

    # Setup account if not already done
    account_ready = await setup_account()
    if not account_ready:
        logging.warning("No X account available. Skipping X fetch.")
        return {}

    results = {}

    # Gather accounts by category and sample up to max_accounts_per_run
    account_list = []
    for category, usernames in accounts_by_category.items():
        for username in usernames:
            account_list.append((category, username))

    random.shuffle(account_list)
    sampled_accounts = account_list[:max_accounts_per_run]

    total_fetched = 0
    logging.info(f"X Ingestion: sampling {len(sampled_accounts)} accounts out of {len(account_list)} total...")

    for i, (category, username) in enumerate(sampled_accounts):
        if i > 0:
            delay = random.uniform(1.0, 2.5)
            await asyncio.sleep(delay)

        try:
            # 12-second timeout per account to prevent twscrape from sleeping through rate-limit windows
            tweets = await asyncio.wait_for(
                fetch_account_tweets(api, username, limit=tweets_per_account),
                timeout=12.0
            )

            if tweets:
                if category not in results:
                    results[category] = []
                results[category].extend(tweets)
                total_fetched += len(tweets)

        except asyncio.TimeoutError:
            logging.warning(
                f"Fetch timeout/rate-limit hit at @{username}. "
                f"Wrapping up fetch cycle with {total_fetched} tweets collected so far."
            )
            break
        except Exception as e:
            logging.warning(f"Error fetching @{username}: {e}")
            continue

    logging.info(
        f"Tweet fetch complete: {total_fetched} tweets from "
        f"{len(sampled_accounts)} sampled accounts."
    )
    return results


def fetch_and_filter_tweets(tweets_per_account=10):
    """
    Synchronous entry point for the X tweet pipeline.
    Loads accounts, fetches tweets, normalizes them.

    Returns:
        List of normalized tweet dicts, or empty list on failure.
    """
    accounts = load_accounts()
    if not accounts:
        logging.info("No X accounts configured. Skipping X ingestion.")
        return []

    try:
        # Run the async fetch in a new event loop
        tweets_by_category = asyncio.run(
            _fetch_all_accounts_async(accounts, tweets_per_account)
        )
    except RuntimeError:
        # If there's already a running event loop, use nest_asyncio pattern
        loop = asyncio.new_event_loop()
        try:
            tweets_by_category = loop.run_until_complete(
                _fetch_all_accounts_async(accounts, tweets_per_account)
            )
        finally:
            loop.close()

    if not tweets_by_category:
        return []

    # Normalize all tweets into pipeline-friendly dicts
    normalized = normalize_all(tweets_by_category)
    logging.info(f"Normalized {len(normalized)} tweets from X.")
    return normalized
