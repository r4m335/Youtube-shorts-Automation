import os
import json
import time
import logging

BACKLOG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "trending_backlog.json")
EXPIRY_DAYS = 7

def _load_backlog():
    if os.path.exists(BACKLOG_FILE):
        try:
            with open(BACKLOG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Error loading backlog: {e}")
    return {}

def _save_backlog(data):
    os.makedirs(os.path.dirname(BACKLOG_FILE), exist_ok=True)
    try:
        with open(BACKLOG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        logging.error(f"Error saving backlog: {e}")

def add_to_backlog(tweet_dict):
    """Adds a trending tweet to the backlog."""
    data = _load_backlog()
    tweet_id = str(tweet_dict.get("tweet_id", ""))
    if not tweet_id:
        return
        
    # Only add if it doesn't exist to preserve original discovery time
    if tweet_id not in data:
        tweet_dict["_backlog_timestamp"] = time.time()
        data[tweet_id] = tweet_dict
        _save_backlog(data)
        logging.info(f"Added tweet '{tweet_dict.get('text', '')[:30]}...' to Trending Backlog.")

def get_unprocessed_trending_tweet():
    """
    Returns the highest-engagement tweet from the backlog that hasn't expired.
    Automatically cleans out expired tweets.
    """
    data = _load_backlog()
    current_time = time.time()
    
    valid_tweets = []
    expired_ids = []
    
    for tid, tweet in data.items():
        timestamp = tweet.get("_backlog_timestamp", current_time)
        age_days = (current_time - timestamp) / (24 * 3600)
        
        if age_days > EXPIRY_DAYS:
            expired_ids.append(tid)
        else:
            valid_tweets.append(tweet)
            
    # Clean up expired
    if expired_ids:
        for tid in expired_ids:
            del data[tid]
        _save_backlog(data)
        logging.info(f"Cleaned {len(expired_ids)} expired tweets from the Trending Backlog.")
        
    if not valid_tweets:
        return None
        
    # Sort by highest engagement (likes + retweets)
    valid_tweets.sort(key=lambda t: t.get("likes", 0) + t.get("retweets", 0), reverse=True)
    
    # Return the top one
    return valid_tweets[0]

def remove_from_backlog(tweet_id):
    """Removes a tweet from the backlog after successful processing."""
    data = _load_backlog()
    tweet_id = str(tweet_id)
    if tweet_id in data:
        del data[tweet_id]
        _save_backlog(data)
        logging.info(f"Removed processed tweet '{tweet_id}' from Trending Backlog.")
