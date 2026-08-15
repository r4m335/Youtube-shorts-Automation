import os
import logging
import json
import datetime
import requests
import xml.etree.ElementTree as ET
from src.llm.providers import PROVIDERS

# ---------------------------------------------------------------------------
# Primary category
# ---------------------------------------------------------------------------
CATEGORIES = [
    {
        "name": "Top Trending Global News",
        "description": "The absolute biggest, most viral breaking news stories happening in the world right now across all major subjects (World Events, Science, Major Tech, Pop Culture)."
    }
]

# ---------------------------------------------------------------------------
# Fallback categories: Tech → Football → Movies → Anime
# Each has its own targeted Reddit subreddits and Google News RSS query so the
# LLM always receives live, on-topic headlines instead of empty context.
# ---------------------------------------------------------------------------
FALLBACK_CATEGORIES = [
    {
        "name": "Top Trending Tech News",
        "description": "The biggest breaking technology news right now — AI breakthroughs, major product launches, cybersecurity incidents, and viral tech moments.",
        "reddit": "technology+artificial+MachineLearning+programming+gadgets",
        "rss_query": "technology+AI+when%3A1d",
    },
    {
        "name": "Top Trending Football News",
        "description": "The hottest football (soccer) stories right now — transfer rumours, match results, manager drama, and viral moments from the world's biggest leagues.",
        "reddit": "soccer+football+PremierLeague+LaLiga+Champions_league",
        "rss_query": "football+soccer+transfer+when%3A1d",
    },
    {
        "name": "Top Trending Movies & TV News",
        "description": "The most talked-about movies and TV show news right now — trailers, box office records, casting shocks, and streaming releases everyone is discussing.",
        "reddit": "movies+television+boxoffice+NetflixBestOf+marvelstudios",
        "rss_query": "movies+trailer+TV+streaming+when%3A1d",
    },
    {
        "name": "Top Trending Anime News",
        "description": "The hottest anime news right now — new season announcements, episode reactions, manga adaptations, and viral moments from the anime community.",
        "reddit": "anime+manga+OnePiece+Naruto+attackontitan",
        "rss_query": "anime+manga+season+announcement+when%3A1d",
    },
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


# ---------------------------------------------------------------------------
# Headline fetchers
# ---------------------------------------------------------------------------

def fetch_google_news_fallback():
    """Fetches top generic World news from the last 24 hours via RSS."""
    url = "https://news.google.com/rss/search?q=world+news+when%3A1d&hl=en-US&gl=US&ceid=US:en"
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
    """Fetches global top-of-day headlines from Reddit; falls back to Google News RSS."""
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
        logging.warning(f"Reddit API failed for global fetch: {e}. Falling back to Google News RSS.")
        return fetch_google_news_fallback()

    if not headlines:
        return fetch_google_news_fallback()
    return headlines


def _fetch_reddit_headlines(subreddits, limit=15):
    """Fetches top-of-day headlines from the given combined subreddit string."""
    url = f"https://www.reddit.com/r/{subreddits}/top.json?t=day&limit={limit}"
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) YTAutomationBot/1.0'}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
        return [
            child.get('data', {}).get('title', '')
            for child in data.get('data', {}).get('children', [])
            if child.get('data', {}).get('title', '')
        ]
    except Exception as e:
        logging.warning(f"Reddit fetch failed for subreddits '{subreddits}': {e}")
        return []


def _fetch_rss_headlines(rss_query, limit=15):
    """Fetches headlines from Google News RSS for the given (already-encoded) query."""
    url = f"https://news.google.com/rss/search?q={rss_query}&hl=en-US&gl=US&ceid=US:en"
    headlines = []
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) NewsBot/1.0'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        root = ET.fromstring(response.text)
        for item in root.findall('./channel/item')[:limit]:
            title = item.find('title').text
            if " - " in title:
                title = title.rsplit(" - ", 1)[0]
            headlines.append(title)
    except Exception as e:
        logging.warning(f"RSS fetch failed for query '{rss_query}': {e}")
    return headlines


# ---------------------------------------------------------------------------
# LLM topic generation helpers
# ---------------------------------------------------------------------------

def _build_topics_prompt(category, live_context, avoid_context, today):
    """Constructs the LLM prompt for any category dict."""
    return f"""
Today's date is: {today}. 

To ensure 100% factual and current information, here are the absolute latest real viral breaking news headlines pulled from the internet right now (past 24h):
{live_context}

CRITICAL ANTI-DUPLICATION RULE:
You MUST NOT generate any topic that covers the same event, person, or semantic meaning as these recently uploaded videos:
{avoid_context}

You MUST ONLY select massive real stories from exactly TODAY based explicitly on those real headlines above. DO NOT invent fictional events. DO NOT use old news from past months or years.

Generate 3 highly engaging, distinct, and currently trending REAL topics:
Category: {category['name']}
Focus guidelines: {category['description']}

Return ONLY a valid JSON array of strings containing the 3 absolute latest trending topics. No markdown, no intro.
Example output format:
["Topic 1", "Topic 2", "Topic 3"]
"""


def _try_generate_topics(category, live_headlines, avoid_context, today):
    """
    Tries every registered LLM provider in order to generate topics for `category`.
    Returns (category_name, topics_list).  topics_list is [] if all providers fail.
    """
    live_context = "\n".join([f"- {h}" for h in live_headlines]) if live_headlines else "No live context available"
    prompt = _build_topics_prompt(category, live_context, avoid_context, today)

    for provider_name, provider_func in PROVIDERS:
        try:
            raw = provider_func(prompt).strip()
            if raw.startswith("```json"):
                raw = raw[7:]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()

            topics = json.loads(raw)
            if isinstance(topics, list) and len(topics) >= 1:
                # Guard: LLM sometimes wraps the array in another list, e.g. [["t1", "t2"]]
                if len(topics) == 1 and isinstance(topics[0], list):
                    topics = topics[0]
                # Keep only string items; discard any remaining nested lists/dicts
                topics = [t for t in topics if isinstance(t, str)]
            if isinstance(topics, list) and len(topics) >= 1:
                logging.info(f"Generated topics via {provider_name} for '{category['name']}'.")
                return category["name"], topics
        except Exception as e:
            logging.warning(f"Provider {provider_name} failed for '{category['name']}': {e}")

    logging.warning(f"All providers failed for category '{category['name']}'.")
    return category["name"], []


# ---------------------------------------------------------------------------
# Main orchestration entry point
# ---------------------------------------------------------------------------

def generate_category_topics():
    """
    Tries Global News first.  If no topics are produced, falls back through
    Tech → Football → Movies → Anime in order, each with its own live
    Reddit + RSS headline context.
    """
    today = datetime.datetime.now().strftime("%B %d, %Y")
    recent_topics = get_recent_topics()
    avoid_context = "\n".join([f"- {t}" for t in recent_topics]) if recent_topics else "None"

    # --- Primary: Global News ---
    global_cat = CATEGORIES[0]
    logging.info(f"Orchestrator trying primary category: '{global_cat['name']}'")
    live_headlines = fetch_real_time_news()
    name, topics = _try_generate_topics(global_cat, live_headlines, avoid_context, today)
    if topics:
        return name, topics

    logging.warning("Primary global news produced no topics. Trying fallback categories...")

    # --- Fallbacks: Tech → Football → Movies → Anime ---
    for fb_cat in FALLBACK_CATEGORIES:
        logging.info(f"Orchestrator trying fallback category: '{fb_cat['name']}'")
        reddit_lines = _fetch_reddit_headlines(fb_cat["reddit"])
        rss_lines = _fetch_rss_headlines(fb_cat["rss_query"])

        # Merge, dedup (Reddit first — usually fresher)
        seen, merged = set(), []
        for h in reddit_lines + rss_lines:
            if h not in seen:
                seen.add(h)
                merged.append(h)

        name, topics = _try_generate_topics(fb_cat, merged[:20], avoid_context, today)
        if topics:
            return name, topics

        logging.warning(f"Fallback category '{fb_cat['name']}' produced no topics.")

    logging.error("All categories (global + all fallbacks) failed to produce topics.")
    return "Unknown", []


def get_headlines_for_category(category):
    """
    Public helper: returns a list of live headlines appropriate for `category`.
    Works for both the primary CATEGORIES entry and FALLBACK_CATEGORIES entries.
    """
    if "reddit" in category:
        # Fallback category — fetch from its dedicated subreddits + RSS
        reddit_lines = _fetch_reddit_headlines(category["reddit"])
        rss_lines = _fetch_rss_headlines(category["rss_query"])
        seen, merged = set(), []
        for h in reddit_lines + rss_lines:
            if h not in seen:
                seen.add(h)
                merged.append(h)
        return merged[:20]
    else:
        # Primary global category
        return fetch_real_time_news()


def generate_topics_for_category(category):
    """
    Public: generate raw LLM topics for a specific category dict.
    Returns (category_name, topics_list).
    """
    today = datetime.datetime.now().strftime("%B %d, %Y")
    recent_topics = get_recent_topics()
    avoid_context = "\n".join([f"- {t}" for t in recent_topics]) if recent_topics else "None"
    live_headlines = get_headlines_for_category(category)
    return _try_generate_topics(category, live_headlines, avoid_context, today)


# ---------------------------------------------------------------------------
# Tweet-to-topic conversion (for X ingestion)
# ---------------------------------------------------------------------------

def _build_tweet_to_topic_prompt(tweets, avoid_context, today):
    """Builds a prompt that converts raw tweet texts into clean video topic titles."""
    tweet_lines = []
    for i, tweet in enumerate(tweets, 1):
        trending_tag = f" [TRENDING - Reported by {tweet['story_count']} accounts]" if tweet.get("story_count", 1) > 1 else ""
        tweet_lines.append(
            f"{i}.{trending_tag} @{tweet['author']}: \"{tweet['text'][:200]}\""
        )
    tweet_context = "\n".join(tweet_lines)

    return f"""Today's date is: {today}.

Here are real tweets from verified news accounts on X, posted in the last 24 hours (trending multi-account stories listed first):
{tweet_context}

CRITICAL ANTI-DUPLICATION RULE:
You MUST NOT generate any topic that covers the same event, person, or semantic meaning as these recently uploaded videos:
{avoid_context}

Convert each tweet into a clean, engaging topic title suitable for a YouTube Shorts video.

Rules:
- Give TOP PRIORITY to items tagged as [TRENDING - Reported by N accounts]
- GLOBAL NEWS RULE: Prioritize major international world news, global events, worldwide sports, tech, and entertainment. DO NOT generate topics about minor local US city/state politics (e.g. local primary polls, local state legislation, small US city council updates).
- Each topic must be a concise, factual headline (3-8 words)
- Do NOT copy the tweet text verbatim — rephrase into a clean title
- Do NOT include author names, @mentions, hashtags, or URLs
- Do NOT invent new information — only use what's in the tweets
- Skip any tweets that overlap with the recently uploaded topics listed above

Return ONLY a valid JSON array of strings. No markdown, no intro.
Example: ["OpenAI Releases GPT-6", "Apple Unveils M5 Chips"]
"""


CATEGORY_PRIORITY = [
    "world", "sports", "Anime"
]


def _get_category_rank(cat_name):
    cat_lower = str(cat_name).lower()
    for idx, prio in enumerate(CATEGORY_PRIORITY):
        if prio.lower() == cat_lower:
            return idx
    return len(CATEGORY_PRIORITY)


def generate_topics_from_tweets(filtered_tweets):
    """
    Converts filtered tweet dicts into clean topic titles using the LLM.
    Prioritizes multi-account trending stories first, then category priority rank.

    Args:
        filtered_tweets: List of normalized, filtered tweet dicts.

    Returns:
        (category_name, topics_list) — same format as generate_topics_for_category.
    """
    if not filtered_tweets:
        return "Unknown", []

    # Sort tweets: Multi-account trending stories FIRST (-story_count), then category priority rank, then importance
    sorted_tweets = sorted(
        filtered_tweets,
        key=lambda t: (
            -t.get("story_count", 1),
            _get_category_rank(t.get("category", "unknown")),
            -t.get("importance", 5),
            -(t.get("likes", 0) + t.get("retweets", 0))
        )
    )

    today = datetime.datetime.now().strftime("%B %d, %Y")
    recent_topics = get_recent_topics()
    avoid_context = "\n".join([f"- {t}" for t in recent_topics]) if recent_topics else "None"

    # Highest priority category present in the candidate set
    top_category = sorted_tweets[0].get("category", "world")

    prompt = _build_tweet_to_topic_prompt(sorted_tweets, avoid_context, today)

    for provider_name, provider_func in PROVIDERS:
        try:
            raw = provider_func(prompt).strip()
            if raw.startswith("```json"):
                raw = raw[7:]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()

            topics = json.loads(raw)
            if isinstance(topics, list) and len(topics) >= 1:
                if len(topics) == 1 and isinstance(topics[0], list):
                    topics = topics[0]
                topics = [t for t in topics if isinstance(t, str)]
            if isinstance(topics, list) and len(topics) >= 1:
                logging.info(
                    f"Generated {len(topics)} topic(s) from tweets via {provider_name} "
                    f"(category: {top_category})."
                )
                return top_category, topics
        except Exception as e:
            logging.warning(f"Provider {provider_name} failed for tweet-to-topic: {e}")

    logging.warning("All providers failed for tweet-to-topic conversion.")
    return top_category, []
