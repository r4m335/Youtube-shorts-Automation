import re
import json
import logging
from datetime import datetime, timezone, timedelta
from src.llm.providers import PROVIDERS


# Keywords that indicate ads/promos
SPAM_KEYWORDS = [
    "sponsored", "promoted", "ad ", "#ad", "giveaway",
    "win a ", "enter to win", "discount code", "use code",
    "affiliate", "click the link in bio",
]


def pre_filter(tweets, max_age_hours=168):
    """
    Removes low-quality and old tweets before the LLM filter.

    Filters out:
    - Replies (text starts with @)
    - Retweets/reposts (text starts with "RT @")
    - Very short tweets (< 30 characters)
    - Old tweets (tweets posted older than max_age_hours timestamp, default 168h / 7 days)
    - Promotional/spam tweets

    Note: Historical incidents and history content ARE allowed as long as the tweet itself is recent!

    Args:
        tweets: List of normalized tweet dicts.
        max_age_hours: Maximum tweet posting age in hours (default: 168h / 7 days).

    Returns:
        Filtered list of tweet dicts.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=max_age_hours)
    result = []
    stats = {"replies": 0, "retweets": 0, "short": 0, "old": 0, "spam": 0}

    for tweet in tweets:
        text = tweet.get("text", "").strip()

        # Skip replies
        if text.startswith("@"):
            stats["replies"] += 1
            continue

        # Skip retweets
        if text.startswith("RT @"):
            stats["retweets"] += 1
            continue

        # Skip very short tweets
        clean_text = re.sub(r"https?://\S+", "", text).strip()
        if len(clean_text) < 30:
            stats["short"] += 1
            continue

        # Skip tweets whose posting timestamp is older than max_age_hours
        created_at = tweet.get("created_at", "")
        if created_at:
            try:
                if isinstance(created_at, str):
                    tweet_time = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                else:
                    tweet_time = created_at
                if tweet_time.tzinfo is None:
                    tweet_time = tweet_time.replace(tzinfo=timezone.utc)
                if tweet_time < cutoff:
                    stats["old"] += 1
                    continue
            except (ValueError, TypeError):
                pass

        # Skip spam/promotional tweets
        text_lower = text.lower()
        if any(kw in text_lower for kw in SPAM_KEYWORDS):
            stats["spam"] += 1
            continue

        result.append(tweet)

    total_removed = sum(stats.values())
    if total_removed > 0:
        logging.info(
            f"Pre-filter: removed {total_removed} tweets "
            f"(replies={stats['replies']}, RTs={stats['retweets']}, "
            f"short={stats['short']}, old={stats['old']}, spam={stats['spam']}). "
            f"{len(result)} remain."
        )
    return result


def _parse_llm_response(raw_response):
    """Attempts to parse the LLM's JSON response for the news filter."""
    raw = raw_response.strip()

    # Strip markdown code fences if present
    if raw.startswith("```json"):
        raw = raw[7:]
    if raw.startswith("```"):
        raw = raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]
    raw = raw.strip()

    try:
        data = json.loads(raw)
        return data
    except json.JSONDecodeError:
        # Fallback: check for simple YES/NO
        upper = raw.upper().strip()
        if "YES" in upper:
            return {"accepted": True, "reason": "LLM said YES", "importance": 5}
        elif "NO" in upper:
            return {"accepted": False, "reason": "LLM said NO", "importance": 0}
        return None


def llm_news_filter(tweets):
    """
    Uses the LLM provider chain to evaluate each tweet for newsworthiness or historical interest.

    Sends each tweet to the first available LLM with an editor prompt.
    Returns only accepted tweets, sorted by importance (highest first).

    Args:
        tweets: List of normalized tweet dicts.

    Returns:
        List of tweet dicts that passed the LLM news quality gate,
        sorted by importance score (descending).
    """
    if not tweets:
        return []

    accepted = []
    rejected = 0

    for tweet in tweets:
        prompt = f"""You are an experienced content editor for a YouTube Shorts channel (covering breaking news, history, technology, incidents, and viral events).

Determine whether this tweet is suitable for creating a factual, engaging YouTube Short video.

ACCEPT:
- Breaking news, current events, sports updates, technology announcements
- Fascinating historical events, historical incidents, documentaries, nature/science facts

REJECT if it is any of:
- An advertisement or promotion
- A personal opinion or hot take
- A meme or joke
- A reply to someone
- A personal update or life event
- Too vague to build a video around

Tweet text: "{tweet['text']}"
Author: @{tweet['author']}

Return ONLY valid JSON (no markdown, no intro):
{{"accepted": true, "reason": "brief reason", "importance": 7}}

Where importance is 1-10 (10 = massive viral news or incredible story, 1 = minor update).
"""
        result = None
        for provider_name, provider_func in PROVIDERS:
            try:
                raw = provider_func(prompt)
                result = _parse_llm_response(raw)
                if result is not None:
                    break
            except Exception as e:
                logging.debug(f"LLM news filter: {provider_name} failed: {e}")
                continue

        if result and result.get("accepted"):
            tweet["importance"] = result.get("importance", 5)
            tweet["filter_reason"] = result.get("reason", "")
            accepted.append(tweet)
            logging.debug(
                f"LLM accepted @{tweet['author']}: '{tweet['text'][:50]}...' "
                f"(importance={tweet['importance']})"
            )
        else:
            rejected += 1
            reason = result.get("reason", "unknown") if result else "LLM parse failed"
            logging.debug(
                f"LLM rejected @{tweet['author']}: '{tweet['text'][:50]}...' — {reason}"
            )

    # Sort by importance (highest first)
    accepted.sort(key=lambda t: t.get("importance", 0), reverse=True)

    logging.info(
        f"LLM news filter: {len(accepted)} accepted, {rejected} rejected "
        f"out of {len(tweets)} tweets."
    )
    return accepted
