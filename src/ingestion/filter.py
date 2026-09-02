import os
import json
import time
import logging

TOPICS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "topics.json")
CACHE_EXPIRY_HOURS = 48

# Basic blocklist for demonstration (can be expanded)
BLOCKLIST = ["politics", "trump", "biden", "election", "democrat", "republican", "war", "death", "murder", "nsfw", "sex"]

def load_topics_cache():
    if os.path.exists(TOPICS_FILE):
        try:
            with open(TOPICS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Error reading topics cache: {e}")
            return {}
    return {}

def save_topics_cache(cache):
    os.makedirs(os.path.dirname(TOPICS_FILE), exist_ok=True)
    with open(TOPICS_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)

def clean_expired_topics(cache):
    """Removes topics older than CACHE_EXPIRY_HOURS"""
    now = time.time()
    expiry_sec = CACHE_EXPIRY_HOURS * 3600
    cleaned = {k: v for k, v in cache.items() if (now - v.get("timestamp", 0)) < expiry_sec}
    return cleaned

def is_valid_topic(topic):
    """Checks if a topic is suitable based on rules."""
    topic_lower = topic.lower()
    
    # 1. Reject vague or too short topics
    words = topic_lower.split()
    if len(words) < 2:
        return False, "Too short/vague"
        
    # 2. Reject excessively long topics (might be full questions or stories)
    if len(words) > 15:
        return False, "Too long, likely not a clean named entity"
        
    # 3. Reject high-risk/political
    for word in BLOCKLIST:
        if word in topic_lower:
            return False, f"Contains blocked word: {word}"
            
    # 4. Reject vague thought starters and conversational queries
    vague_phrases = ["life advice", "random thoughts", "how to", "why do", "what is", "best way", "my opinion", "question here"]
    for vague in vague_phrases:
        if vague in topic_lower:
            return False, f"Vague or conversational topic: {vague}"
            
    return True, "Valid"

import re

STOPWORDS = {
    'a', 'an', 'the', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
    'to', 'in', 'of', 'for', 'on', 'with', 'at', 'by', 'from', 'up', 'about',
    'into', 'over', 'after', 'just', 'new', 'tv', 'gets', 'announced', 'announces',
    'releases', 'official', 'video', 'news', 'set', 'sets', 'brings', 'reveals',
    'shows', 'says', 'claims', 'reports', 'unveils', 'unveiled', 'upcoming'
}


def extract_keywords(text):
    """Extracts core entity keywords by stripping common stopwords and normalizing numbers."""
    text = text.lower()
    text = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', text)
    words = set(re.findall(r'\b\w+\b', text))
    return {w for w in words if w not in STOPWORDS and len(w) > 1}


def is_semantic_duplicate(new_topic, cached_topics):
    """
    Checks if new_topic is semantically identical or shares key entities
    with ANY topic currently in cached_topics.
    """
    kw_new = extract_keywords(new_topic)
    if not kw_new:
        return False, None

    for cached_topic in cached_topics:
        kw_cached = extract_keywords(cached_topic)
        if not kw_cached:
            continue

        intersection = kw_new & kw_cached
        min_len = min(len(kw_new), len(kw_cached))
        if min_len == 0:
            continue

        overlap_ratio = len(intersection) / min_len

        # If 2+ key entities match and they cover >= 50% of the smaller keyword set
        if len(intersection) >= 2 and overlap_ratio >= 0.5:
            return True, cached_topic

        # If 3+ key entities match regardless of length
        if len(intersection) >= 3 and overlap_ratio >= 0.4:
            return True, cached_topic

    return False, None


def filter_and_cache_topics(raw_topics, source="unknown"):
    """
    Validates topics and returns a list of *new* valid topics.
    Updates the cache with the new ones.
    """
    cache = load_topics_cache()
    cache = clean_expired_topics(cache)
    
    new_valid_topics = []
    
    for topic in raw_topics:
        # Defensive guard: topics must be plain strings to be hashable cache keys
        if not isinstance(topic, str):
            logging.warning(f"Skipping non-string topic: {topic!r}")
            continue
            
        # 1. Exact match check
        if topic in cache:
            logging.info(f"DEDUP: Blocked exact duplicate topic '{topic}'")
            continue

        # 2. Semantic & Keyword Entity match check against past topics
        is_dup, matched_cached = is_semantic_duplicate(topic, cache.keys())
        if is_dup:
            logging.info(
                f"DEDUP: Blocked semantic duplicate topic '{topic}' "
                f"(matches existing video: '{matched_cached}')"
            )
            continue
            
        valid, reason = is_valid_topic(topic)
        if valid:
            new_valid_topics.append(topic)
            cache[topic] = {
                "timestamp": time.time(),
                "source": source
            }
        else:
            logging.info(f"Rejected topic '{topic[:30]}...': {reason}")
            
    save_topics_cache(cache)
    return new_valid_topics

def remove_from_cache(topic):
    """
    Removes a topic from the cache if video generation failed,
    allowing it to be retried in the future.
    """
    cache = load_topics_cache()
    if topic in cache:
        del cache[topic]
        save_topics_cache(cache)
        logging.info(f"Removed '{topic}' from cache due to generation failure.")
