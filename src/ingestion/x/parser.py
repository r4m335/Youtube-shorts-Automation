import logging


def normalize_tweet(tweet, category):
    """
    Converts a twscrape Tweet object into a pipeline-friendly dict.

    Args:
        tweet: A twscrape Tweet object with attributes like id, rawContent, user, etc.
        category: The category string (e.g. "technology", "world", "sports").

    Returns:
        A normalized dict with consistent keys.
    """
    try:
        # Extract media URLs if present
        media_urls = []
        if hasattr(tweet, "media") and tweet.media:
            photos = getattr(tweet.media, "photos", []) or []
            for p in photos:
                if hasattr(p, "url") and p.url:
                    media_urls.append(p.url)
            videos = getattr(tweet.media, "videos", []) or []
            for v in videos:
                if hasattr(v, "thumbnailUrl") and v.thumbnailUrl:
                    media_urls.append(v.thumbnailUrl)

        return {
            "tweet_id": str(tweet.id),
            "author": tweet.user.username if tweet.user else "unknown",
            "author_name": tweet.user.displayname if tweet.user else "Unknown",
            "text": tweet.rawContent or "",
            "created_at": tweet.date.isoformat() if tweet.date else "",
            "likes": getattr(tweet, "likeCount", 0) or 0,
            "retweets": getattr(tweet, "retweetCount", 0) or 0,
            "url": tweet.url or f"https://x.com/{tweet.user.username}/status/{tweet.id}" if tweet.user else "",
            "category": category,
            "media": media_urls,
        }
    except Exception as e:
        logging.warning(f"Failed to normalize tweet {getattr(tweet, 'id', '?')}: {e}")
        return None


def normalize_all(tweets_by_category):
    """
    Normalizes all tweets from a {category: [Tweet_objects]} mapping
    into a flat list of dicts.

    Args:
        tweets_by_category: Dict of {category_name: [twscrape.Tweet, ...]}

    Returns:
        List of normalized tweet dicts.
    """
    result = []
    for category, tweets in tweets_by_category.items():
        for tweet in tweets:
            normalized = normalize_tweet(tweet, category)
            if normalized:
                result.append(normalized)
    return result
