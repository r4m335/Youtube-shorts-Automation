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
    if len(words) > 10:
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

def filter_and_cache_topics(raw_topics, source="unknown"):
    """
    Validates topics and returns a list of *new* valid topics.
    Updates the cache with the new ones.
    """
    cache = load_topics_cache()
    cache = clean_expired_topics(cache)
    
    new_valid_topics = []
    
    for topic in raw_topics:
        # Check if already processed recently
        if topic in cache:
            continue
            
        valid, reason = is_valid_topic(topic)
        if valid:
            new_valid_topics.append(topic)
            cache[topic] = {
                "timestamp": time.time(),
                "source": source
            }
        else:
            logging.debug(f"Rejected topic '{topic[:30]}...': {reason}")
            
    save_topics_cache(cache)
    return new_valid_topics
