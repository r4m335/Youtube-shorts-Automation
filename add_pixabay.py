import os
import requests

with open('src/visuals/fetcher.py', 'r', encoding='utf-8') as f:
    code = f.read()

pixabay_code = '''
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
            chosen = random.choice(hits[:3])
            img_url = chosen.get("largeImageURL")
            if img_url:
                ir = requests.get(img_url, timeout=10)
                ir.raise_for_status()
                if len(ir.content) > 2000 and is_valid_image(ir.content):
                    with open(output_path, "wb") as f:
                        f.write(ir.content)
                    logging.info(f"Pixabay image downloaded for '{keyword}'")
                    return True
    except Exception as e:
        logging.error(f"Pixabay image fetch failed for {keyword}: {e}")
    return False
'''

if 'def fetch_video_pixabay' not in code:
    code = code.replace('def get_visual_for_line', pixabay_code + '\ndef get_visual_for_line')
    
    # Add pixabay as fallback for video
    code = code.replace('if fetch_video_pexels(smart_query, mp4_path):\n                return mp4_path', 
                        'if fetch_video_pexels(smart_query, mp4_path):\n                return mp4_path\n            if fetch_video_pixabay(smart_query, mp4_path):\n                return mp4_path')
    code = code.replace('if fetch_video_pexels(query, mp4_path):\n            logging.info',
                        'if fetch_video_pexels(query, mp4_path) or fetch_video_pixabay(query, mp4_path):\n            logging.info')
    
    # Add pixabay as fallback for image
    code = code.replace('if fetch_image_pexels(query, jpg_path):\n                return jpg_path',
                        'if fetch_image_pexels(query, jpg_path):\n                return jpg_path\n            if fetch_image_pixabay(query, jpg_path):\n                return jpg_path')

    with open('src/visuals/fetcher.py', 'w', encoding='utf-8') as f:
        f.write(code)
    print('Updated fetcher.py with Pixabay')
else:
    print('Pixabay already injected')
