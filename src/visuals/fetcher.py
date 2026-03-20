import os
import requests
import logging

STOPWORDS = {"the","a","an","is","are","was","were","be","been","being",
             "have","has","had","do","does","did",
             "in","on","at","to","for","with","about","by","from","up","down","of","off","over","under",
             "and","but","or","yet","so","if","because","as","until","while",
             "this","that","these","those","it","its","they","them","their","he","him","his","she","her"}

def extract_keyword(line):
    words = "".join(c for c in line if c.isalnum() or c.isspace()).split()
    valid_words = [w for w in words if w.lower() not in STOPWORDS and len(w) > 3]
    if valid_words:
        # Sort by length, assuming longest word is the most descriptive "noun"
        return sorted(valid_words, key=len, reverse=True)[0]
    return "nature" # fallback

def fetch_video_pexels(keyword, output_path):
    api_key = os.getenv("PEXELS_API_KEY")
    if not api_key: return False
    
    url = f"https://api.pexels.com/videos/search?query={keyword}&orientation=portrait&per_page=1"
    headers = {"Authorization": api_key}
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        if data.get("videos"):
            video_files = data["videos"][0].get("video_files", [])
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

def fetch_image_pexels(keyword, output_path):
    api_key = os.getenv("PEXELS_API_KEY")
    if not api_key:
        return False
    
    url = f"https://api.pexels.com/v1/search?query={keyword}&orientation=portrait&per_page=1"
    headers = {"Authorization": api_key}
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        if data.get("photos"):
            img_url = data["photos"][0]["src"]["large2x"] # High quality
            img_data = requests.get(img_url).content
            with open(output_path, "wb") as f:
                f.write(img_data)
            return True
    except Exception as e:
        logging.error(f"Pexels image fetch failed for {keyword}: {e}")
    return False

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

def get_visual_for_line(line, temp_dir, index):
    keyword = extract_keyword(line)
    logging.info(f"Extracted keyword '{keyword}' for line: '{line[:20]}...'")
    
    # Try Pexels Video (.mp4)
    mp4_path = os.path.join(temp_dir, f"visual_{index}.mp4")
    if fetch_video_pexels(keyword, mp4_path):
        return mp4_path
        
    # Fallback to Pexels Image (.jpg)
    jpg_path = os.path.join(temp_dir, f"visual_{index}.jpg")
    logging.info("Falling back to Pexels Image")
    if fetch_image_pexels(keyword, jpg_path):
        return jpg_path
    
    # Fallback to Unsplash Image (.jpg)
    logging.info("Falling back to Unsplash")
    if fetch_image_unsplash(keyword, jpg_path):
        return jpg_path
    
    logging.warning(f"Could not fetch visual for keyword: {keyword}")
    return None
