import os
import json
import logging

CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "config",
    "accounts.json",
)


def load_accounts():
    """
    Loads the monitored accounts config from config/accounts.json.
    Returns a dict: {category: [username_list]}
    """
    if not os.path.exists(CONFIG_PATH):
        logging.warning(f"Accounts config not found at {CONFIG_PATH}")
        return {}

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        cleaned_data = {}
        for cat, users in data.items():
            valid_users = [u.strip() for u in users if isinstance(u, str) and u.strip()]
            if valid_users:
                cleaned_data[cat] = valid_users
        total = sum(len(v) for v in cleaned_data.values())
        logging.info(f"Loaded {total} monitored accounts across {len(cleaned_data)} categories.")
        return cleaned_data
    except Exception as e:
        logging.error(f"Failed to load accounts config: {e}")
        return {}


def get_all_usernames(accounts):
    """Returns a flat list of all unique usernames across categories."""
    seen = set()
    result = []
    for usernames in accounts.values():
        for u in usernames:
            if u not in seen:
                seen.add(u)
                result.append(u)
    return result


def get_category_for_user(username, accounts):
    """Reverse lookup: returns the category for a given username."""
    for category, usernames in accounts.items():
        if username in usernames:
            return category
    return "unknown"
