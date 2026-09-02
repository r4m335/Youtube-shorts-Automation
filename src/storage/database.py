import os
import sqlite3
import time
import logging
import re

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "tweets.db")


def _get_connection():
    """Returns a connection to the tweets database, creating it if needed."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Creates the tweets table if it doesn't exist."""
    conn = _get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tweets (
                tweet_id TEXT PRIMARY KEY,
                author TEXT,
                category TEXT,
                text TEXT,
                topic TEXT,
                created_at TEXT,
                processed INTEGER DEFAULT 0,
                video_generated INTEGER DEFAULT 0,
                youtube_id TEXT,
                inserted_at REAL
            )
        """)
        
        # Migration: Add status column if it doesn't exist
        cursor = conn.execute("PRAGMA table_info(tweets)")
        columns = [info["name"] for info in cursor.fetchall()]
        if "status" not in columns:
            conn.execute("ALTER TABLE tweets ADD COLUMN status TEXT DEFAULT 'pending'")
            # Migrate old processed states
            conn.execute("UPDATE tweets SET status = 'completed' WHERE processed = 1")
            conn.execute("UPDATE tweets SET status = 'pending' WHERE processed = 0")
            
        if "story_count" not in columns:
            conn.execute("ALTER TABLE tweets ADD COLUMN story_count INTEGER DEFAULT 1")
        
        conn.commit()
        logging.info("Tweet database initialized.")
    finally:
        conn.close()


def is_processed(tweet_id):
    """Returns True if the tweet_id already exists in the database."""
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT 1 FROM tweets WHERE tweet_id = ?", (str(tweet_id),)
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def clean_text_for_dup_check(text):
    """Removes URLs and punctuation for accurate duplicate text comparison."""
    if not text: return ""
    text = re.sub(r'http\S+', '', text)
    text = re.sub(r'[^a-zA-Z0-9\s]', '', text)
    return text.lower().strip()


def is_text_processed(author, text):
    """Returns True if the author has already tweeted very similar text."""
    conn = _get_connection()
    try:
        rows = conn.execute("SELECT text FROM tweets WHERE author = ?", (author,)).fetchall()
        clean_target = clean_text_for_dup_check(text)
        if not clean_target:
            return False
            
        for row in rows:
            db_text = clean_text_for_dup_check(row["text"])
            if not db_text: continue
            # Check for exact match or strong substring match
            if clean_target == db_text or (len(db_text) > 20 and db_text in clean_target) or (len(clean_target) > 20 and clean_target in db_text):
                return True
        return False
    finally:
        conn.close()


def insert_tweet(tweet_dict):
    """
    Inserts a new tweet record if it doesn't already exist.
    Returns True if inserted, False if it was a duplicate.
    """
    conn = _get_connection()
    try:
        conn.execute(
            """
            INSERT OR IGNORE INTO tweets
                (tweet_id, author, category, text, created_at, inserted_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                str(tweet_dict["tweet_id"]),
                tweet_dict.get("author", ""),
                tweet_dict.get("category", ""),
                tweet_dict.get("text", ""),
                str(tweet_dict.get("created_at", "")),
                time.time(),
            ),
        )
        conn.commit()
        return conn.total_changes > 0
    finally:
        conn.close()


def mark_tweet_status(tweet_id, status, topic="", youtube_id=None):
    """Marks a tweet as completed or failed."""
    conn = _get_connection()
    try:
        conn.execute(
            """
            UPDATE tweets
            SET status = ?,
                topic = ?,
                youtube_id = ?,
                processed = ?,
                video_generated = ?
            WHERE tweet_id = ?
            """,
            (
                status,
                topic,
                youtube_id,
                1 if status == 'completed' else 0,
                1 if youtube_id else 0,
                str(tweet_id),
            ),
        )
        conn.commit()
    finally:
        conn.close()

def reset_stale_processing_tweets():
    """Resets any stuck 'processing' tweets back to 'pending' on startup."""
    conn = _get_connection()
    try:
        conn.execute("UPDATE tweets SET status = 'pending' WHERE status = 'processing'")
        conn.commit()
        if conn.total_changes > 0:
            logging.info(f"Reset {conn.total_changes} stale processing tweets back to pending.")
    finally:
        conn.close()

def get_pending_tweet_for_category(category):
    """Atomically gets the oldest pending tweet for a category and marks it processing."""
    conn = _get_connection()
    try:
        row = conn.execute(
            """
            SELECT tweet_id, text, author, created_at, category, story_count FROM tweets 
            WHERE category = ? AND status = 'pending'
            ORDER BY story_count DESC, inserted_at DESC LIMIT 1
            """, 
            (category,)
        ).fetchone()
        
        if row:
            conn.execute("UPDATE tweets SET status = 'processing' WHERE tweet_id = ?", (row["tweet_id"],))
            conn.commit()
            return dict(row)
        return None
    finally:
        conn.close()

def update_tweet_dedup(tweet_id, new_text, story_count):
    """Updates the text and story_count of a tweet after deduplication aggregation."""
    conn = _get_connection()
    try:
        conn.execute(
            "UPDATE tweets SET text = ?, story_count = ? WHERE tweet_id = ?",
            (new_text, story_count, str(tweet_id))
        )
        conn.commit()
    finally:
        conn.close()

def get_backlog_stats():
    """Returns a dictionary of category -> count of pending tweets."""
    conn = _get_connection()
    try:
        rows = conn.execute("SELECT category, COUNT(*) as count FROM tweets WHERE status = 'pending' GROUP BY category").fetchall()
        return {r["category"]: r["count"] for r in rows}
    finally:
        conn.close()


def get_recent_topics(limit=25):
    """Returns recent topic strings for LLM dedup context."""
    conn = _get_connection()
    try:
        rows = conn.execute(
            """
            SELECT topic FROM tweets
            WHERE topic IS NOT NULL AND topic != ''
            ORDER BY inserted_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [row["topic"] for row in rows]
    finally:
        conn.close()


def cleanup_old(days=7):
    """Removes entries older than N days to keep the database lean."""
    cutoff = time.time() - (days * 86400)
    conn = _get_connection()
    try:
        cursor = conn.execute(
            "DELETE FROM tweets WHERE inserted_at < ?", (cutoff,)
        )
        conn.commit()
        deleted = cursor.rowcount
        if deleted > 0:
            logging.info(f"Tweet DB cleanup: removed {deleted} entries older than {days} days.")
    finally:
        conn.close()
