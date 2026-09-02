import os
import json
from datetime import datetime

ACCOUNT_STATE_FILE = os.path.join("data", "x", "account_state.json")

def _load_state():
    if not os.path.exists(ACCOUNT_STATE_FILE):
        return {}
    try:
        with open(ACCOUNT_STATE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_state(data):
    os.makedirs(os.path.dirname(ACCOUNT_STATE_FILE), exist_ok=True)
    with open(ACCOUNT_STATE_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_account_state(username: str):
    data = _load_state()
    return data.get(username, {
        "last_seen_tweet_id": None,
        "last_success": None,
        "consecutive_failures": 0
    })

def update_account_success(username: str, last_seen_id: str):
    data = _load_state()
    if username not in data:
        data[username] = {}
        
    data[username]["last_success"] = datetime.now().isoformat()
    data[username]["consecutive_failures"] = 0
    if last_seen_id:
        data[username]["last_seen_tweet_id"] = last_seen_id
        
    _save_state(data)

def record_account_failure(username: str):
    data = _load_state()
    if username not in data:
        data[username] = {"last_seen_tweet_id": None, "last_success": None, "consecutive_failures": 0}
        
    data[username]["consecutive_failures"] = data[username].get("consecutive_failures", 0) + 1
    _save_state(data)
