import os
import random
import logging
import json
import datetime
import requests
import xml.etree.ElementTree as ET
from src.llm.providers import PROVIDERS

CATEGORIES = [
    {
        "name": "Top Trending Global News",
        "description": "The absolute biggest, most viral breaking news stories happening in the world right now across all major subjects (World Events, Science, Major Tech, Pop Culture)."
    }
]

def get_recent_topics():
    """Reads the JSON ledger to inject semantic awareness of what the channel already posted."""
    topics_file = os.path.join("data", "topics.json")
    if not os.path.exists(topics_file):
        return []
    try:
        with open(topics_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            sorted_topics = sorted(data.items(), key=lambda x: x[1].get('timestamp', 0), reverse=True)
            return [k for k, v in sorted_topics[:25]]
    except Exception as e:
        logging.warning(f"Could not read recent topics for deduplication: {e}")
        return []

def fetch_google_news_fallback():
    # Fetch top generic US/World news strictly from the last 24 hours
    url = "https://news.google.com/rss/search?q=when%3A1d&hl=en-US&gl=US&ceid=US:en"
    
    headlines = []
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) NewsBot/1.0'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        root = ET.fromstring(response.text)
        for item in root.findall('./channel/item')[:15]: 
            title = item.find('title').text
            if " - " in title:
                title = title.rsplit(" - ", 1)[0]
            headlines.append(title)
            
    except Exception as e:
        logging.warning(f"Failed to fetch live generic RSS news: {e}")
        
    return headlines

def fetch_real_time_news():
    # Combine the biggest worldwide subreddits into one massive viral fetch
    subreddits = "worldnews+news+technology+science+entertainment"
    url = f"https://www.reddit.com/r/{subreddits}/top.json?t=day&limit=15"
    
    headlines = []
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) YTAutomationBot/1.0'}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
            
        for child in data.get('data', {}).get('children', []):
            title = child.get('data', {}).get('title', '')
            if title:
                headlines.append(title)
                
    except Exception as e:
        logging.warning(f"Reddit API failed for global fetch: {e}. Falling back to generic Google News when:1d")
        return fetch_google_news_fallback()
        
    if not headlines:
        return fetch_google_news_fallback()
        
    return headlines

def generate_category_topics():
    category = CATEGORIES[0]
    logging.info(f"Orchestrator selected category: {category['name']}")
    
    today = datetime.datetime.now().strftime("%B %d, %Y")
    
    # Pre-fetch the exact internet headlines right now
    live_headlines = fetch_real_time_news()
    live_context = "\n".join([f"- {h}" for h in live_headlines]) if live_headlines else "No live context available"
    
    # Fetch recent video histories to completely prevent duplications
    recent_topics = get_recent_topics()
    avoid_context = "\n".join([f"- {t}" for t in recent_topics]) if recent_topics else "None"
    
    prompt = f"""
Today's date is: {today}. 

To ensure 100% factual and current information, here are the absolute latest real viral breaking news headlines pulled from the internet right now (past 24h):
{live_context}

CRITICAL ANTI-DUPLICATION RULE:
You MUST NOT generate any topic that covers the same event, person, or semantic meaning as these recently uploaded videos:
{avoid_context}

You MUST ONLY select massive real global news stories from exactly TODAY based explicitly on those real headlines above. DO NOT invent fictional events. DO NOT use old news from past months or years.

Generate 3 highly engaging, distinct, and currently trending REAL breaking news topics across those subjects:
Category: {category['name']}
Focus guidelines: {category['description']}

Return ONLY a valid JSON array of strings containing the 3 absolute latest trending topics. No markdown, no intro.
Example output format:
["Topic 1", "Topic 2", "Topic 3"]
"""
    
    for provider_name, provider_func in PROVIDERS:
        try:
            raw_response = provider_func(prompt)
            # Basic cleanup of markdown
            raw_response = raw_response.strip()
            if raw_response.startswith("```json"):
                raw_response = raw_response[7:]
            if raw_response.endswith("```"):
                raw_response = raw_response[:-3]
            raw_response = raw_response.strip()
            
            topics = json.loads(raw_response)
            if isinstance(topics, list) and len(topics) >= 1:
                logging.info(f"Orchestrator successfully generated exact topics via {provider_name}.")
                return category["name"], topics
        except Exception as e:
            logging.warning(f"Orchestrator failed to generate topics with {provider_name}: {e}")
            
    logging.error("All providers failed to generate categorical topics.")
    return category["name"], []
