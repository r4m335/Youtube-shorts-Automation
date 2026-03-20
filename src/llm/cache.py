import os
import hashlib

SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "scripts")

def get_topic_hash(topic):
    return hashlib.md5(topic.encode('utf-8')).hexdigest()

def get_cached_script(topic):
    topic_hash = get_topic_hash(topic)
    script_path = os.path.join(SCRIPTS_DIR, f"{topic_hash}.txt")
    if os.path.exists(script_path):
        with open(script_path, "r", encoding="utf-8") as f:
            return f.read(), topic_hash
    return None, topic_hash

def save_script_to_cache(topic_hash, script_lines):
    os.makedirs(SCRIPTS_DIR, exist_ok=True)
    script_path = os.path.join(SCRIPTS_DIR, f"{topic_hash}.txt")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write("\n".join(script_lines))
    return script_path
