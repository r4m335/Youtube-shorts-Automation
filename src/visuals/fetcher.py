import os
import re
import requests
import logging
import random


def verify_image_safety_and_relevance(image_path, query):
    """
    Uses Gemini 3.5 Flash Vision to check if the image is safe (no nudity/NSFW)
    and if it is relevant to the query/topic.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return True # Skip verification if no key
        
    try:
        import base64
        import json
        import requests
        from PIL import Image
        import io
        
        # Compress image to save API payload size
        img = Image.open(image_path)
        img.thumbnail((512, 512))
        
        # Convert to JPEG bytes
        if img.mode != 'RGB':
            img = img.convert('RGB')
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=85)
        b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        prompt = f"""Analyze this image for content moderation and relevance.
1. Does it contain nudity, sexually explicit content, or NSFW elements?
2. Does this image accurately relate to the search query '{query}'?

Respond ONLY with a valid JSON object in this exact format:
{{"is_safe": true, "is_relevant": true}}"""
        
        payload = {
            'contents': [{
                'parts': [
                    {'text': prompt},
                    {'inline_data': {'mime_type': 'image/jpeg', 'data': b64}}
                ]
            }],
            'generationConfig': {'temperature': 0.0}
        }
        
        url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key={api_key}'
        r = requests.post(url, json=payload, timeout=15)
        if r.status_code == 200:
            text = r.json()['candidates'][0]['content']['parts'][0]['text'].strip()
            # Clean markdown JSON block
            if text.startswith('```json'): text = text[7:]
            if text.startswith('```'): text = text[3:]
            if text.endswith('```'): text = text[:-3]
            data = json.loads(text.strip())
            
            is_safe = data.get('is_safe', False)
            is_relevant = data.get('is_relevant', False)
            
            if not is_safe:
                logging.warning(f"Image rejected: NSFW content detected for query '{query}'.")
                return False
            if not is_relevant:
                logging.warning(f"Image rejected: Irrelevant to query '{query}'.")
                return False
                
            return True
            
    except Exception as e:
        logging.error(f"Image verification failed: {e}")
        return True # Default to True if API fails to avoid breaking pipeline
        
    return True

def is_valid_image(content):
    if content.startswith(b'\xff\xd8'): return True # JPEG
    if content.startswith(b'\x89PNG\r\n\x1a\n'): return True # PNG
    if content.startswith(b'GIF87a') or content.startswith(b'GIF89a'): return True
    if content.startswith(b'RIFF') and content[8:12] == b'WEBP': return True
    return False

STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did",
    "in", "on", "at", "to", "for", "with", "about", "by", "from", "up", "down", "of", "off", "over", "under",
    "and", "but", "or", "yet", "so", "if", "because", "as", "until", "while",
    "this", "that", "these", "those", "it", "its", "they", "them", "their", "he", "him", "his", "she", "her",
    "just", "now", "will", "can", "could", "would", "should", "must", "may", "might",
    "not", "no", "yes", "all", "every", "each", "more", "most", "much", "many", "some", "any",
    "very", "really", "also", "too", "than", "then", "only", "even", "still", "already",
    "new", "old", "big", "get", "got", "make", "made", "take", "took", "come", "came", "go", "went",
    "said", "says", "told", "know", "think", "want", "need", "look", "use", "find", "give", "tell",
    # Generic buzzwords / filler adjectives to filter out from visual keywords
    "breaking", "official", "officially", "massive", "biggest", "stunning", "shocking", "insane",
    "unbelievable", "wild", "crazy", "huge", "major", "latest", "important", "confirmed", "rumor",
    "update", "announcement", "report", "reported", "statement", "details", "reaction", "today"
}


def extract_keyword(line):
    """Extract a single best keyword from a line."""
    words = "".join(c for c in line if c.isalnum() or c.isspace()).split()
    valid_words = [w for w in words if w.lower() not in STOPWORDS and len(w) > 3]
    if valid_words:
        # Prioritize capitalized proper nouns first
        proper_nouns = [w for w in valid_words if w[0].isupper()]
        if proper_nouns:
            return proper_nouns[0]
        return sorted(valid_words, key=len, reverse=True)[0]
    return "news"


def extract_script_keywords(lines, topic=""):
    """
    Uses LLM to generate exactly 1-2 word keywords per line of the script.
    Falls back to frequency method if LLM fails.
    """
    try:
        from src.llm.providers import generate_groq
        script_text = "\n".join([f"Line {i+1}: {line}" for i, line in enumerate(lines)])
        prompt = f"""You are an image search expert. Given this video script, you must extract exactly ONE short keyword phrase (1-2 words max) as the best image search keyword for EACH line.
        
Topic: {topic}

Script:
{script_text}

Rules:
- Return exactly {len(lines)} keywords, separated by commas.
- Each keyword must be 1 to 2 words maximum.
- Use concrete nouns/entities (e.g., 'Poland', 'EU Economy', 'Car Factory', 'President').
- Do NOT include line numbers or any other text.
- Example output: Poland, EU Economy, Belgium, Factory
"""
        result = generate_groq(prompt).strip()
        
        # Clean quotes if any
        result = result.replace('"', '').replace("'", "")
        
        # Parse the result
        words = [w.strip() for w in result.split(',')]
        
        # Ensure we have exactly len(lines) words, padding or truncating if necessary
        if len(words) < len(lines):
            words.extend(["news"] * (len(lines) - len(words)))
        elif len(words) > len(lines):
            words = words[:len(lines)]
            
        # We don't force them to be a single word anymore, just keeping the phrase
        logging.info(f"LLM script keywords: {words}")
        return words
    except Exception as e:
        logging.warning(f"LLM keyword generation failed, using fallback: {e}")
        from collections import Counter
        combined_raw = f"{topic} " + " ".join(lines)
        words_list = "".join(c for c in combined_raw if c.isalnum() or c.isspace()).split()
        valid_words = [w for w in words_list if w.lower() not in STOPWORDS and len(w) > 2]
        if not valid_words:
            return ["news"] * len(lines)
        word_counts = Counter(valid_words)
        sorted_keywords = [item[0] for item in word_counts.most_common()]
        if not sorted_keywords:
            return ["news"] * len(lines)
        return [sorted_keywords[i % len(sorted_keywords)] for i in range(len(lines))]


def extract_visual_keywords(line, topic=""):
    """
    Extract multiple search keywords from a line and topic for better visual matching.
    Prioritizes proper nouns (player names, team names, companies) over generic words.
    Returns a list of search queries from most specific to most generic.
    """
    combined_raw = f"{line} {topic}"
    words = "".join(c for c in combined_raw if c.isalnum() or c.isspace()).split()
    valid_words = [w for w in words if w.lower() not in STOPWORDS and len(w) > 2]
    
    if not valid_words:
        return ["news"]
    
    # Categorize proper nouns (capitalized) vs normal words
    proper_nouns = [w for w in valid_words if w[0].isupper()]
    
    queries = []
    
    # 1. Topic proper nouns combined (e.g. "Messi Inter Miami" or "Real Madrid Yamal")
    if len(proper_nouns) >= 2:
        queries.append(" ".join(dict.fromkeys(proper_nouns[:3])))
    elif proper_nouns:
        queries.append(proper_nouns[0])
    
    # 2. Two longest words combined
    sorted_words = sorted(valid_words, key=len, reverse=True)
    if len(sorted_words) >= 2:
        two_words = f"{sorted_words[0]} {sorted_words[1]}"
        if two_words not in queries:
            queries.append(two_words)
    
    # 3. Single main keyword fallback
    if sorted_words[0] not in queries:
        queries.append(sorted_words[0])
        
    return queries


def generate_smart_search_query(line, topic="", category=""):
    """
    Uses LLM (Groq, fast) to generate a precise, context-aware image search query.
    E.g. for topic "Messi Signs With Inter Miami" → "Lionel Messi Inter Miami jersey photo"
    instead of generic keyword extraction that might return "Signs Inter" or "Messi" alone.
    Falls back to extract_visual_keywords if LLM call fails.
    """
    try:
        from src.llm.providers import generate_groq
        
        prompt = f"""You are an image search expert. Given this news topic and script line, generate the BEST Google Image search query to find a highly relevant, real photo for this news story.

Topic: {topic}
Script line: {line}
Category: {category}

Rules:
- Return ONLY the search query string, nothing else
- Use full proper names (e.g. "Lionel Messi" not just "Messi")
- Include context words like team names, company names, product names
- Add "photo" or "news" at the end for better image results
- Keep it under 6 words
- Do NOT include quotes, hashtags, or special characters

Example inputs/outputs:
- Topic "Apple M5 Chip Unveiled" → Apple M5 chip processor photo
- Topic "Mbappe Scores Hat Trick" → Kylian Mbappe Real Madrid goal
- Topic "FDA Approves New Drug" → FDA drug approval announcement photo
- Topic "Deadpool 3 Breaks Records" → Deadpool 3 movie poster
- Topic "India Moon Mission" → ISRO Chandrayaan moon landing photo"""

        result = generate_groq(prompt).strip().strip('"').strip("'")
        # Validate: should be short, no JSON, no markdown
        if result and len(result) < 80 and not result.startswith("{") and not result.startswith("["):
            logging.info(f"LLM smart search query: '{result}' (for topic: '{topic[:40]}')")
            return result
    except Exception as e:
        logging.warning(f"LLM smart search query failed, using keyword extraction: {e}")
    
    # Fallback to basic keyword extraction
    keywords = extract_visual_keywords(line, topic)
    return keywords[0] if keywords else "news"


# ---------------------------------------------------------------------------
# Source 1: Tweet Media (highest priority — real news images from tweet)
# ---------------------------------------------------------------------------
def download_tweet_media(media_urls, temp_dir, index):
    """Downloads the first available image from tweet media URLs."""
    if not media_urls:
        return None
    
    for url in media_urls:
        try:
            if not url:
                continue
            if ".mp4" in url.lower() or "video.twimg.com" in url.lower():
                ext = ".mp4"
            else:
                ext = ".png" if ".png" in url.lower() else ".jpg"
            output_path = os.path.join(temp_dir, f"tweet_media_{index}{ext}")
            
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            if len(response.content) > 1000:
                with open(output_path, "wb") as f:
                    f.write(response.content)
                logging.info(f"Downloaded tweet media for line {index}: {url[:60]}...")
                return output_path
        except Exception as e:
            logging.warning(f"Failed to download tweet media {url[:60]}: {e}")
    
    return None


# ---------------------------------------------------------------------------
# Source 1.5: Article Images via SerpAPI & Scraping
# ---------------------------------------------------------------------------
def discover_articles(topic, limit=5):
    """
    Uses DuckDuckGo HTML Lite search to find real article URLs about the topic.
    This guarantees real URLs and avoids LLM hallucination (which returns 404s).
    """
    try:
        from bs4 import BeautifulSoup
        urls = []
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'}
        url = 'https://html.duckduckgo.com/html/'
        r = requests.post(url, data={'q': f"{topic} news"}, headers=headers, timeout=10)
        
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            for a in soup.find_all('a', class_='result__url'):
                href = a.get('href')
                if href and href.startswith('http'):
                    urls.append(href)
                    if len(urls) >= limit:
                        break
                        
        logging.info(f"DDG HTML Search discovered {len(urls)} real article URLs for '{topic[:30]}...'")
        return urls
    except Exception as e:
        logging.error(f"Failed to discover articles via DDG HTML: {e}")
        return []

def scrape_article_images(urls, temp_dir):
    """
    Scrapes the provided URLs for their og:image or twitter:image.
    Downloads them to temp_dir and returns a list of valid image paths.
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        logging.error("BeautifulSoup not installed. Cannot scrape article images.")
        return []
        
    downloaded_paths = []
    
    for i, url in enumerate(urls):
        try:
            # Mask as a regular browser to avoid blocks
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
            }
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code != 200:
                continue
                
            soup = BeautifulSoup(r.content, 'html.parser')
            img_url = None
            
            # Look for standard metadata images
            og_img = soup.find("meta", property="og:image")
            if og_img and og_img.get("content"):
                img_url = og_img["content"]
            else:
                tw_img = soup.find("meta", attrs={"name": "twitter:image"})
                if tw_img and tw_img.get("content"):
                    img_url = tw_img["content"]
            
            if not img_url:
                continue
                
            # Handle relative URLs or missing schemes
            if img_url.startswith("//"):
                img_url = "https:" + img_url
            elif img_url.startswith("/"):
                from urllib.parse import urljoin
                img_url = urljoin(url, img_url)
                
            # Download the image
            ir = requests.get(img_url, headers=headers, timeout=10)
            if ir.status_code == 200 and len(ir.content) > 5000: # Ensure it's a real image, not tiny icon
                from src.visuals.fetcher import is_valid_image # Use existing helper
                if is_valid_image(ir.content):
                    out_path = os.path.join(temp_dir, f"article_img_{i}_{hash(url) % 10000}.jpg")
                    with open(out_path, "wb") as f:
                        f.write(ir.content)
                    downloaded_paths.append(out_path)
                    logging.info(f"Successfully scraped article image from {url[:40]}...")
                    
        except Exception as e:
            logging.warning(f"Failed to scrape article image from {url}: {e}")
            
    return downloaded_paths


# ---------------------------------------------------------------------------
# Source 2: SerpAPI Google Image Search (real news photos)
# ---------------------------------------------------------------------------
def fetch_image_serpapi(keyword, output_path):
    """
    Searches Google Images via SerpAPI and downloads the first result.
    Returns real news photos, player photos, product shots.
    """
    api_key = os.getenv("SERPAPI_KEY")
    if not api_key:
        return False
    
    try:
        params = {
            "engine": "google_images",
            "q": keyword,
            "api_key": api_key,
            "num": "5",
            "safe": "active",
            "ijn": "0"
        }
        response = requests.get("https://serpapi.com/search", params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        images = data.get("images_results", [])
        if images:
            for chosen in images[:5]:
                img_url = chosen.get("original") or chosen.get("thumbnail")
                if not img_url: continue
                img_response = requests.get(img_url, timeout=10, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
                })
                img_response.raise_for_status()
                
                if len(img_response.content) > 1000 and is_valid_image(img_response.content):
                    with open(output_path, "wb") as f:
                        f.write(img_response.content)
                    logging.info(f"SerpAPI image downloaded for '{keyword}': {img_url[:60]}...")
                    return True
    except Exception as e:
        logging.warning(f"SerpAPI image search failed for '{keyword}': {e}")
    return False


# ---------------------------------------------------------------------------
# Source 3: Bing Image Search (FREE real news photos, no API key, unlimited)
# ---------------------------------------------------------------------------
def fetch_image_bing(keyword, output_path):
    """
    Searches Bing Images via HTTP parsing — free, no API key required.
    Returns high-resolution news photos, athlete images, and breaking news graphics.
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        url = f"https://www.bing.com/images/search?q={keyword}&form=HDRSC2"
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        urls = re.findall(r'murl&quot;:&quot;(https?://[^&]+)&quot;', response.text)
        if urls:
            # Try top 5 URLs to find one that downloads cleanly
            for img_url in urls[:5]:
                try:
                    img_resp = requests.get(img_url, headers=headers, timeout=8)
                    if img_resp.status_code == 200 and len(img_resp.content) > 1000 and is_valid_image(img_resp.content):
                        with open(output_path, "wb") as f:
                            f.write(img_resp.content)
                        logging.info(f"Bing Image downloaded for '{keyword}': {img_url[:60]}...")
                        return True
                except Exception:
                    continue
    except Exception as e:
        logging.warning(f"Bing Image search failed for '{keyword}': {e}")
    return False


# ---------------------------------------------------------------------------
# Source 4: Wikipedia / Wikimedia Commons (free, no API key, great for people/logos)
# ---------------------------------------------------------------------------
def fetch_image_wikimedia(keyword, output_path):
    """
    Searches Wikipedia REST API — free, no API key.
    Best for named people (players, politicians, CEOs), landmarks, logos, movies.
    """
    try:
        headers = {
            "User-Agent": "YTShortsAutomation/1.0 (https://github.com/r4m335/Youtube-shorts-Automation; dotproduct456@gmail.com)"
        }
        search_url = "https://en.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "format": "json",
            "titles": keyword,
            "prop": "pageimages",
            "pithumbsize": "800",
            "redirects": "1"
        }
        
        response = requests.get(search_url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        pages = data.get("query", {}).get("pages", {})
        for page_id, page_data in pages.items():
            if page_id == "-1":
                continue
            thumb_url = page_data.get("thumbnail", {}).get("source")
            if thumb_url:
                img_response = requests.get(thumb_url, headers=headers, timeout=10)
                img_response.raise_for_status()
                
                if len(img_response.content) > 2000 and is_valid_image(img_response.content):
                    with open(output_path, "wb") as f:
                        f.write(img_response.content)
                    logging.info(f"Wikipedia image downloaded for '{keyword}'")
                    return True
    except Exception as e:
        logging.warning(f"Wikipedia image search failed for '{keyword}': {e}")
    return False


# ---------------------------------------------------------------------------
# Source 5: DuckDuckGo Images (free, no API key)
# ---------------------------------------------------------------------------
def fetch_image_duckduckgo(keyword, output_path):
    """
    Searches DuckDuckGo Images — free, no API key.
    Uses ddgs package.
    """
    try:
        from ddgs import DDGS
        import time
        
        time.sleep(0.3)
        results = list(DDGS().images(keyword, max_results=5))
        
        if results:
            chosen = random.choice(results[:3])
            img_url = chosen.get("image")
            
            if img_url:
                img_response = requests.get(img_url, timeout=10, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                })
                img_response.raise_for_status()
                
                if len(img_response.content) > 2000 and is_valid_image(img_response.content):
                    with open(output_path, "wb") as f:
                        f.write(img_response.content)
                    logging.info(f"DuckDuckGo image downloaded for '{keyword}'")
                    return True
    except Exception as e:
        logging.warning(f"DuckDuckGo image search failed for '{keyword}': {e}")
    return False


# ---------------------------------------------------------------------------
# Source 6: TMDB (movie posters, actor photos — for cinema category)
# ---------------------------------------------------------------------------
def fetch_image_tmdb(keyword, output_path):
    """
    Searches TMDB for movie/TV show posters and actor photos.
    Best for cinema/entertainment topics.
    """
    api_key = os.getenv("TMDB_API_KEY")
    if not api_key:
        return False
    
    try:
        url = f"https://api.themoviedb.org/3/search/multi?api_key={api_key}&query={keyword}&page=1"
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        results = data.get("results", [])
        if results:
            for result in results[:3]:
                img_path = (
                    result.get("poster_path") or 
                    result.get("backdrop_path") or 
                    result.get("profile_path")
                )
                if img_path:
                    img_url = f"https://image.tmdb.org/t/p/w780{img_path}"
                    img_response = requests.get(img_url, timeout=10)
                    img_response.raise_for_status()
                    
                    if len(img_response.content) > 2000 and is_valid_image(img_response.content):
                        with open(output_path, "wb") as f:
                            f.write(img_response.content)
                        logging.info(f"TMDB image downloaded for '{keyword}': {result.get('title') or result.get('name')}")
                        return True
    except Exception as e:
        logging.warning(f"TMDB image search failed for '{keyword}': {e}")
    return False


# ---------------------------------------------------------------------------
# Source 7: Stability AI (AI-generated visuals — unique custom 9:16 images)
# ---------------------------------------------------------------------------
def fetch_image_stability(keyword, output_path):
    """
    Generates a custom image using Stability AI's Stable Image Core API.
    Creates unique, eye-catching visuals when no real photo is available.
    """
    api_key = os.getenv("STABILITY_API_KEY")
    if not api_key:
        return False
    
    try:
        prompt = f"Breaking news visual: {keyword}. Dramatic cinematic lighting, photorealistic, 4K quality, news broadcast style, vertical portrait orientation 9:16"
        
        response = requests.post(
            "https://api.stability.ai/v2beta/stable-image/generate/core",
            headers={
                "authorization": f"Bearer {api_key}",
                "accept": "image/*"
            },
            files={
                "prompt": (None, prompt),
                "output_format": (None, "jpeg"),
                "aspect_ratio": (None, "9:16"),
            },
            timeout=30
        )
        
        if response.status_code == 200 and len(response.content) > 2000:
            with open(output_path, "wb") as f:
                f.write(response.content)
            logging.info(f"Stability AI image generated for '{keyword}'")
            return True
        else:
            logging.warning(f"Stability AI returned status {response.status_code}: {response.text[:200]}")
    except Exception as e:
        logging.warning(f"Stability AI image generation failed for '{keyword}': {e}")
    return False


# ---------------------------------------------------------------------------
# Source 8: Pexels Video (stock video clips)
# ---------------------------------------------------------------------------
def fetch_video_pexels(keyword, output_path):
    api_key = os.getenv("PEXELS_API_KEY")
    if not api_key: return False
    
    url = f"https://api.pexels.com/videos/search?query={keyword}&orientation=portrait&per_page=3"
    headers = {"Authorization": api_key}
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        if data.get("videos"):
            video = random.choice(data["videos"][:3])
            video_files = video.get("video_files", [])
            hd_files = [f for f in video_files if f.get("quality") == "hd"]
            target_file = hd_files[0] if hd_files else (video_files[0] if video_files else None)
            
            if target_file and target_file.get("link"):
                vid_url = target_file["link"]
                vid_data = requests.get(vid_url).content
                with open(output_path, "wb") as f:
                    f.write(vid_data)
                return True
    except Exception as e:
        logging.error(f"Pexels video fetch failed for {keyword}: {e}")
    return False


# ---------------------------------------------------------------------------
# Source 9: Pexels Image (stock photos)
# ---------------------------------------------------------------------------
def fetch_image_pexels(keyword, output_path):
    api_key = os.getenv("PEXELS_API_KEY")
    if not api_key:
        return False
    
    url = f"https://api.pexels.com/v1/search?query={keyword}&orientation=portrait&per_page=3"
    headers = {"Authorization": api_key}
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        if data.get("photos"):
            photo = random.choice(data["photos"][:3])
            img_url = photo["src"]["large2x"]
            img_data = requests.get(img_url).content
            with open(output_path, "wb") as f:
                f.write(img_data)
            return True
    except Exception as e:
        logging.error(f"Pexels image fetch failed for {keyword}: {e}")
    return False


# ---------------------------------------------------------------------------
# Source 10: Unsplash Image (final stock fallback)
# ---------------------------------------------------------------------------
def fetch_image_unsplash(keyword, output_path):
    api_key = os.getenv("UNSPLASH_ACCESS_KEY")
    if not api_key:
        return False
        
    url = f"https://api.unsplash.com/search/photos?page=1&query={keyword}&orientation=portrait&per_page=1"
    headers = {"Authorization": f"Client-ID {api_key}"}
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        if data.get("results"):
            img_url = data["results"][0]["urls"]["regular"]
            img_data = requests.get(img_url).content
            with open(output_path, "wb") as f:
                f.write(img_data)
            return True
    except Exception as e:
        logging.error(f"Unsplash fetch failed for {keyword}: {e}")
    return False


# ---------------------------------------------------------------------------
# Main visual fetcher with full 10-source priority chain
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Source 10: Pixabay Video (fallback stock video clips)
# ---------------------------------------------------------------------------
def fetch_video_pixabay(keyword, output_path):
    api_key = os.getenv("PIXABAY_API_KEY")
    if not api_key: return False
    try:
        url = f"https://pixabay.com/api/videos/?key={api_key}&q={keyword}&video_type=film"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        hits = data.get("hits", [])
        if hits:
            # Sort by highest resolution portrait or just take first
            chosen = hits[0]
            vid_url = chosen.get("videos", {}).get("large", {}).get("url") or chosen.get("videos", {}).get("medium", {}).get("url")
            if vid_url:
                vr = requests.get(vid_url, timeout=15)
                vr.raise_for_status()
                with open(output_path, "wb") as f:
                    f.write(vr.content)
                logging.info(f"Pixabay video downloaded for '{keyword}'")
                return True
    except Exception as e:
        logging.error(f"Pixabay video fetch failed for {keyword}: {e}")
    return False

# ---------------------------------------------------------------------------
# Source 11: Pixabay Image (fallback stock photos)
# ---------------------------------------------------------------------------
def fetch_image_pixabay(keyword, output_path):
    api_key = os.getenv("PIXABAY_API_KEY")
    if not api_key: return False
    try:
        url = f"https://pixabay.com/api/?key={api_key}&q={keyword}&image_type=photo&orientation=vertical"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        hits = data.get("hits", [])
        if hits:
            for chosen in hits[:3]:
                img_url = chosen.get("largeImageURL")
                if not img_url: continue
                
                ir = requests.get(img_url, timeout=10)
                ir.raise_for_status()
                if len(ir.content) > 1000 and is_valid_image(ir.content):
                    with open(output_path, "wb") as f:
                        f.write(ir.content)
                    logging.info(f"Pixabay image downloaded for '{keyword}'")
                    return True
    except Exception as e:
        logging.error(f"Pixabay image fetch failed for {keyword}: {e}")
    return False

def get_visual_for_line(line, temp_dir, index, topic="", tweet_media_urls=None, category="", article_image=None):
    """
    Fetches the best visual for a script line using a multi-source priority chain.
    
    Priority chain (As requested by User):
    1. Tweet media
    2. Article URL -> og:image
    3. LLM finds related articles -> og:image
    4. Wikipedia
    5. TMDB
    6. Bing
    7. Google
    8. DuckDuckGo
    9. AI-generated image
    """
    # Priority 1: Tweet media image (always most relevant)
    if tweet_media_urls:
        tweet_visual = download_tweet_media(tweet_media_urls, temp_dir, index)
        if tweet_visual:
            # Also try to fetch a background video for tweet media
            bg_video = None
            query_for_vid = generate_smart_search_query(line, topic, category)
            mp4_path = os.path.join(temp_dir, f"bg_video_{index}.mp4")
            if fetch_video_pexels(query_for_vid, mp4_path):
                bg_video = mp4_path
            return tweet_visual, bg_video
    
    # Priority 1.5: Scraped article image
    jpg_path = os.path.join(temp_dir, f"visual_{index}.jpg")
    if article_image and os.path.exists(article_image):
        import shutil
        shutil.copy2(article_image, jpg_path)
        logging.info(f"Using scraped article image for line {index}: {article_image}")
        return jpg_path, None
    
    # Generate search queries: LLM smart query (primary) + extracted keywords (fallbacks)
    smart_query = generate_smart_search_query(line, topic, category)
    fallback_keywords = extract_visual_keywords(line, topic)
    
    # Build ordered list of queries to try: smart query first, then fallbacks (deduplicated)
    all_queries = [smart_query]
    for kw in fallback_keywords:
        if kw.lower() != smart_query.lower():
            all_queries.append(kw)
    
    primary_image = None
    
    # Priority 3: Wikipedia / Wikimedia
    for query in all_queries:
        if fetch_image_wikimedia(query, jpg_path):
            primary_image = jpg_path
            break
            
    # Priority 4: TMDB (for cinema/entertainment categories)
    if not primary_image:
        cat_lower = category.lower() if category else ""
        if cat_lower in ("cinema", "entertainment", "anime", "drama", ""):
            for query in all_queries:
                if fetch_image_tmdb(query, jpg_path):
                    primary_image = jpg_path
                    break
                    
    # Priority 5: Bing Image Search
    if not primary_image:
        for query in all_queries:
            if fetch_image_bing(query, jpg_path):
                primary_image = jpg_path
                break
                
    # Priority 6: SerpAPI Google Images
    if not primary_image:
        for query in all_queries:
            if fetch_image_serpapi(query, jpg_path):
                primary_image = jpg_path
                break
                
    # Priority 7: DuckDuckGo Images
    if not primary_image:
        for query in all_queries:
            if fetch_image_duckduckgo(query, jpg_path):
                primary_image = jpg_path
                break
                
    # Priority 8: Stability AI
    if not primary_image:
        logging.info(f"Generating AI visual for '{smart_query}'...")
        ai_path = os.path.join(temp_dir, f"ai_visual_{index}.jpg")
        if fetch_image_stability(smart_query, ai_path):
            primary_image = ai_path
    
    if not primary_image:
        logging.warning(f"Could not fetch ANY visual for: {all_queries}")
        return None, None
    
    # Also fetch a Pexels video clip for the background (image shows first 2s, then video plays)
    bg_video = None
    mp4_path = os.path.join(temp_dir, f"bg_video_{index}.mp4")
    for query in all_queries:
        if fetch_video_pexels(query, mp4_path):
            bg_video = mp4_path
            break
    return primary_image, bg_video


# ---------------------------------------------------------------------------
# Semantic Context Extraction (RAG)
# ---------------------------------------------------------------------------
def fetch_topic_context(topic, limit=3):
    """
    Secretly searches DuckDuckGo HTML Lite for the topic and extracts the text snippets
    from the first few search results. This acts as real-world background context (RAG) 
    to prevent LLM hallucinations.
    """
    try:
        from bs4 import BeautifulSoup
        snippets = []
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'}
        url = 'https://html.duckduckgo.com/html/'
        r = requests.post(url, data={'q': f"{topic} news"}, headers=headers, timeout=10)
        
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            for div in soup.find_all('a', class_='result__snippet'):
                snippets.append(div.text.strip())
                if len(snippets) >= limit:
                    break
                    
        context_str = " ".join(snippets)
        logging.info(f"Fetched {len(snippets)} context snippets for topic: '{topic[:30]}...'")
        return context_str
    except Exception as e:
        logging.error(f"Failed to fetch context via DDG HTML: {e}")
        return ""
