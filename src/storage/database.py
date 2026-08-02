import os
import sqlite3
import time
import logging

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


def mark_processed(tweet_id, topic="", youtube_id=None):
    """Marks a tweet as processed after the video pipeline completes."""
    conn = _get_connection()
    try:
        conn.execute(
            """
            UPDATE tweets
            SET processed = 1,
                video_generated = ?,
                topic = ?,
                youtube_id = ?
            WHERE tweet_id = ?
            """,
            (
                1 if youtube_id else 0,
                topic,
                youtube_id,
                str(tweet_id),
            ),
        )
        conn.commit()
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
