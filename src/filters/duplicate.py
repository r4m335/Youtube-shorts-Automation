import logging
import re
from collections import defaultdict
from src.storage.database import is_processed


def remove_known_tweets(tweets):
    """
    Filters out tweets whose IDs already exist in the database.

    Args:
        tweets: List of normalized tweet dicts.

    Returns:
        List of tweet dicts that are NOT already in the database.
    """
    new_tweets = []
    skipped = 0
    for tweet in tweets:
        if is_processed(tweet["tweet_id"]):
            skipped += 1
        else:
            new_tweets.append(tweet)

    if skipped > 0:
        logging.info(f"Duplicate filter: skipped {skipped} already-processed tweets.")
    return new_tweets


STOPWORDS = {
    'a', 'an', 'the', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
    'to', 'in', 'of', 'for', 'on', 'with', 'at', 'by', 'from', 'up', 'about',
    'into', 'over', 'after', 'just', 'new', 'tv', 'gets', 'announced', 'announces',
    'releases', 'official', 'video', 'news', 'set', 'sets', 'brings', 'reveals',
    'shows', 'says', 'claims', 'reports', 'unveils', 'unveiled', 'upcoming'
}


def _extract_keywords(text):
    text = text.lower()
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'#\w+', '', text)
    text = re.sub(r'@\w+', '', text)
    text = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', text)
    words = set(re.findall(r'\b\w+\b', text))
    return {w for w in words if w not in STOPWORDS and len(w) > 1}


def _is_similar_story(text_a, text_b):
    kw_a = _extract_keywords(text_a)
    kw_b = _extract_keywords(text_b)
    if not kw_a or not kw_b:
        return False
    intersection = kw_a & kw_b
    min_len = min(len(kw_a), len(kw_b))
    if min_len == 0:
        return False
    overlap_ratio = len(intersection) / min_len
    return (len(intersection) >= 2 and overlap_ratio >= 0.45) or (len(intersection) >= 3)


def deduplicate_similar(tweets):
    """
    Groups tweets covering the same story (e.g. Reuters + BBC + AP reporting
    the same event) and keeps only the highest-engagement tweet from each cluster.
    """
    if len(tweets) <= 1:
        return tweets

    clusters = []
    assigned = set()

    for i, tweet_a in enumerate(tweets):
        if i in assigned:
            continue

        cluster = [tweet_a]
        assigned.add(i)

        for j, tweet_b in enumerate(tweets):
            if j in assigned or j <= i:
                continue

            if _is_similar_story(tweet_a["text"], tweet_b["text"]):
                cluster.append(tweet_b)
                assigned.add(j)

        clusters.append(cluster)

    # From each cluster, pick the tweet with the highest engagement and track story_count across accounts
    result = []
    merged_count = 0
    for cluster in clusters:
        unique_authors = set(t.get("author", "unknown") for t in cluster)
        story_count = len(unique_authors)

        if len(cluster) > 1:
            merged_count += len(cluster) - 1
            best = max(cluster, key=lambda t: t.get("likes", 0) + t.get("retweets", 0))
            best["story_count"] = story_count
            logging.info(
                f"🔥 TRENDING STORY DETECTED: {story_count} accounts (@{', @'.join(list(unique_authors)[:4])}) "
                f"posted about: '{best['text'][:60]}...'"
            )
        else:
            best = cluster[0]
            best["story_count"] = 1

        result.append(best)

    if merged_count > 0:
        logging.info(
            f"Semantic dedup: merged {merged_count} duplicate stories. "
            f"{len(result)} unique stories remain."
        )

    return result
