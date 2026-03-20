import logging
from pytrends.request import TrendReq

def get_google_trends(geo='US', hl='en-US'):
    """Fetches trending topics from Google Trends (Mocked for testing)."""
    logging.info(f"Fetching Google Trends for geo={geo}")
    import time
    timestamp = int(time.time())
    topics = [f"iPhone 17 leak {timestamp}", f"OpenAI new model release {timestamp}", f"SpaceX Mars landing {timestamp}"]
    logging.info(f"Found {len(topics)} trending topics from Google Trends.")
    return topics

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(get_google_trends())
