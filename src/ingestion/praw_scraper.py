import os
import praw
import logging
from dotenv import load_dotenv

load_dotenv()

def get_reddit_trends(subreddits=['Showerthoughts', 'todayilearned', 'explainlikeimfive', 'interestingasfuck'], limit=10):
    """Fetches top daily posts from selected subreddits."""
    client_id = os.getenv('REDDIT_CLIENT_ID')
    client_secret = os.getenv('REDDIT_CLIENT_SECRET')
    user_agent = os.getenv('REDDIT_USER_AGENT', 'ShortsBot 1.0')
    
    if not client_id or not client_secret:
        logging.warning("Reddit API credentials not found. Skipping Reddit ingestion.")
        return []

    try:
        reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent
        )
        
        topics = []
        for sub in subreddits:
            logging.info(f"Fetching top posts from r/{sub}")
            subreddit = reddit.subreddit(sub)
            for submission in subreddit.top(time_filter="day", limit=limit):
                if not submission.over_18 and not submission.stickied:
                    topics.append(submission.title)
        
        logging.info(f"Found {len(topics)} topics from Reddit.")
        return topics
    except Exception as e:
        logging.error(f"Error fetching Reddit trends: {e}")
        return []

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(get_reddit_trends())
