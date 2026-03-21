import random
import logging
import json
import datetime
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from src.llm.providers import PROVIDERS

CATEGORIES = [
    {
        "name": "Hollywood & Entertainment",
        "description": "Trending Hollywood news, Marvel, DC, Star Wars, major casting rumors, and new movie trailers."
    },
    {
        "name": "European Football",
        "description": "Latest match reports, shock transfers, or drama regarding Barcelona, Real Madrid, Bayern Munich, Chelsea, Arsenal, Man City, Man Utd, Liverpool, or PSG."
    },
    {
        "name": "Tech & AI",
        "description": "Breaking tech news, AI advancements, major gadget releases, or software releases."
    },
    {
        "name": "Global News & Events",
        "description": "Major global incidents, geopolitics, wars, or historic trustful news media reports."
    },
    {
        "name": "Trivia & Quiz",
        "description": "Engaging interactive trivia questions where the audience has to guess the answer."
    },
    {
        "name": "Conspiracy & Paranormal",
        "description": "Engaging conspiracy theories, alien sightings, paranormal events, or unexplained mysteries."
    }
]

def fetch_real_time_news(category_name):
    query_map = {
        "Hollywood & Entertainment": "Hollywood movies entertainment celebrity",
        "European Football": "European football soccer premier league transfers",
        "Tech & AI": "Technology Artificial Intelligence Gadgets",
        "Global News & Events": "World breaking news",
        "Trivia & Quiz": "Interesting obscure facts trivia",
        "Conspiracy & Paranormal": "Unexplained mystery UFO paranormal"
    }
    query_str = query_map.get(category_name, category_name)
    url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query_str)}&hl=en-US&gl=US&ceid=US:en"
    
    headlines = []
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            xml_data = response.read()
            
        root = ET.fromstring(xml_data)
        for item in root.findall('./channel/item')[:15]: 
            title = item.find('title').text
            if " - " in title:
                title = title.rsplit(" - ", 1)[0]
            headlines.append(title)
            
    except Exception as e:
        logging.warning(f"Failed to fetch live RSS news for {category_name}: {e}")
        
    return headlines

def generate_category_topics():
    category = random.choice(CATEGORIES)
    logging.info(f"Orchestrator selected category: {category['name']}")
    
    today = datetime.datetime.now().strftime("%B %d, %Y")
    
    # Pre-fetch the exact internet headlines right now
    live_headlines = fetch_real_time_news(category['name'])
    live_context = "\n".join([f"- {h}" for h in live_headlines]) if live_headlines else "No live context available. Rely on exact date."
    
    prompt = f"""
Today's date is: {today}. 

To ensure 100% factual and current information, here are the absolute latest real breaking news headlines pulled from the internet right now for this category:
{live_context}

You MUST ONLY select massive real global news stories from TODAY based explicitly on those real headlines above. DO NOT invent fictional events. DO NOT use old news from past months or years. 

Generate 3 highly engaging, distinct, and currently trending REAL breaking news topics that fit this specific category:
Category: {category['name']}
Focus guidelines: {category['description']}

Return ONLY a valid JSON array of strings containing the 3 absolute latest trending topics. No markdown, no intro.
Example output format:
["Topic 1", "Topic 2", "Topic 3"]
"""
    
    for provider_name, provider_func in PROVIDERS:
        try:
            raw_response = provider_func(prompt)
            raw_response = raw_response.replace("```json", "").replace("```", "").strip()
            topics = json.loads(raw_response)
            if isinstance(topics, list) and len(topics) >= 1:
                logging.info(f"Orchestrator successfully generated exact topics via {provider_name}.")
                return category["name"], topics
        except Exception as e:
            logging.warning(f"Orchestrator failed to generate topics with {provider_name}")
            
    logging.error("All providers failed to generate categorical topics.")
    return category["name"], []
