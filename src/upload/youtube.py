import os
import json
import logging
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES = ["https://www.googleapis.com/auth/youtube"]
CHANNELS_CONFIG = "config/channels.json"
PLAYLIST_CACHE_FILE = "config/playlist_cache.json"

# ---------------------------------------------------------------------------
# Channel Configuration
# ---------------------------------------------------------------------------

_channels_config = None
_category_to_channel = None

def _load_channels_config():
    """Load channels.json and build a category -> channel lookup."""
    global _channels_config, _category_to_channel
    if _channels_config is not None:
        return _channels_config, _category_to_channel

    with open(CHANNELS_CONFIG, "r", encoding="utf-8") as f:
        _channels_config = json.load(f)

    _category_to_channel = {}
    for channel_name, cfg in _channels_config.items():
        for cat in cfg.get("categories", []):
            _category_to_channel[cat] = channel_name

    logging.info(f"Loaded {len(_channels_config)} channel profiles: {list(_channels_config.keys())}")
    return _channels_config, _category_to_channel


def get_channel_for_category(category):
    """Returns (channel_name, channel_config) for the given category."""
    channels, cat_map = _load_channels_config()
    channel_name = cat_map.get(category)
    if not channel_name:
        logging.warning(f"No channel configured for category '{category}'. Falling back to first channel.")
        channel_name = list(channels.keys())[0]
    return channel_name, channels[channel_name]


def get_channel_categories(channel_name):
    """Returns the list of categories for a channel."""
    channels, _ = _load_channels_config()
    return channels.get(channel_name, {}).get("categories", [])


def get_all_channels():
    """Returns the full channels config dict."""
    channels, _ = _load_channels_config()
    return channels


# ---------------------------------------------------------------------------
# Authentication (per-channel, cached)
# ---------------------------------------------------------------------------

_service_cache = {}  # channel_name -> youtube service object

def get_authenticated_service(category):
    """
    Returns an authenticated YouTube API service for the channel
    that handles the given category. Caches per channel.
    """
    channel_name, cfg = get_channel_for_category(category)

    # Return cached service if available
    if channel_name in _service_cache:
        return _service_cache[channel_name]

    client_secret_file = cfg.get("client_secret")
    token_file = cfg.get("token_file")

    if not client_secret_file or not os.path.exists(client_secret_file):
        logging.error(f"client_secret.json not found for channel '{channel_name}' at '{client_secret_file}'")
        return None

    creds = None
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                logging.warning(f"Failed to refresh token for channel '{channel_name}': {e}. Re-authenticating...")
                if os.path.exists(token_file):
                    os.remove(token_file)
                flow = InstalledAppFlow.from_client_secrets_file(client_secret_file, SCOPES)
                creds = flow.run_local_server(port=0)
        else:
            flow = InstalledAppFlow.from_client_secrets_file(client_secret_file, SCOPES)
            creds = flow.run_local_server(port=0)

        os.makedirs(os.path.dirname(token_file), exist_ok=True)
        with open(token_file, "w") as f:
            f.write(creds.to_json())

    service = build("youtube", "v3", credentials=creds)
    _service_cache[channel_name] = service
    logging.info(f"Authenticated YouTube service for channel '{channel_name}'")
    return service


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

def upload_video(file_path, title, description, tags, category, privacy_status="public", thumbnail_path=None):
    """Upload a video to the YouTube channel that handles the given category."""
    channel_name, _ = get_channel_for_category(category)
    youtube = get_authenticated_service(category)
    if not youtube:
        return None

    logging.info(f"Uploading '{title}' to channel '{channel_name}'...")
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": "24"  # Entertainment
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False
        }
    }

    media = MediaFileUpload(file_path, chunksize=-1, resumable=True)
    request = youtube.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=media
    )

    try:
        response = request.execute()
        video_id = response['id']
        logging.info(f"Video '{video_id}' uploaded to channel '{channel_name}'.")

        if thumbnail_path and os.path.exists(thumbnail_path):
            try:
                youtube.thumbnails().set(
                    videoId=video_id,
                    media_body=MediaFileUpload(thumbnail_path)
                ).execute()
                logging.info(f"Custom thumbnail uploaded for video '{video_id}'.")
            except Exception as e:
                logging.error(f"Failed to upload custom thumbnail: {e}")

        return video_id
    except Exception as e:
        logging.error(f"Upload failed on channel '{channel_name}': {e}")
        return None


# ---------------------------------------------------------------------------
# Playlist Management (per-channel)
# ---------------------------------------------------------------------------

# Human-friendly playlist titles per category
PLAYLIST_TITLES = {
    "Cdrama": "Cdrama News",
    "Kdrama": "Kdrama News",
    "sports": "Sports News",
    "Anime":  "Anime News",
    "Movie":  "Movie News",
    "Tech":   "Tech News",
    "world":  "World News",
    "India":  "India News",
}


def _load_playlist_cache():
    """Load the channel:category -> playlist_id mapping."""
    if os.path.exists(PLAYLIST_CACHE_FILE):
        try:
            with open(PLAYLIST_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_playlist_cache(cache):
    """Persist the channel:category -> playlist_id mapping."""
    os.makedirs(os.path.dirname(PLAYLIST_CACHE_FILE), exist_ok=True)
    with open(PLAYLIST_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)


def _get_or_create_playlist(youtube, channel_name, category):
    """
    Returns the playlist ID for the given category on the given channel.
    Checks local cache first, then searches existing playlists, then creates one.
    """
    cache = _load_playlist_cache()
    cache_key = f"{channel_name}:{category}"

    # 1. Check local cache
    if cache_key in cache:
        return cache[cache_key]

    playlist_title = PLAYLIST_TITLES.get(category, f"{category} News")

    # 2. Search existing playlists on the channel
    try:
        next_page = None
        while True:
            resp = youtube.playlists().list(
                part="snippet",
                mine=True,
                maxResults=50,
                pageToken=next_page
            ).execute()

            for item in resp.get("items", []):
                if item["snippet"]["title"] == playlist_title:
                    pid = item["id"]
                    logging.info(f"Found existing playlist '{playlist_title}' ({pid}) on channel '{channel_name}'")
                    cache[cache_key] = pid
                    _save_playlist_cache(cache)
                    return pid

            next_page = resp.get("nextPageToken")
            if not next_page:
                break
    except Exception as e:
        logging.warning(f"Could not search playlists on channel '{channel_name}': {e}")

    # 3. Create new playlist
    try:
        resp = youtube.playlists().insert(
            part="snippet,status",
            body={
                "snippet": {
                    "title": playlist_title,
                    "description": f"Auto-curated {playlist_title} shorts \u2014 updated daily."
                },
                "status": {
                    "privacyStatus": "public"
                }
            }
        ).execute()
        pid = resp["id"]
        logging.info(f"Created playlist '{playlist_title}' ({pid}) on channel '{channel_name}'")
        cache[cache_key] = pid
        _save_playlist_cache(cache)
        return pid
    except Exception as e:
        logging.error(f"Failed to create playlist '{playlist_title}' on channel '{channel_name}': {e}")
        return None


def add_to_playlist(video_id, category):
    """
    Adds a video to the category-specific playlist on the correct channel.
    Creates the playlist if it doesn't exist yet.
    """
    if not video_id or not category:
        return False

    channel_name, _ = get_channel_for_category(category)
    youtube = get_authenticated_service(category)
    if not youtube:
        return False

    playlist_id = _get_or_create_playlist(youtube, channel_name, category)
    if not playlist_id:
        return False

    try:
        youtube.playlistItems().insert(
            part="snippet",
            body={
                "snippet": {
                    "playlistId": playlist_id,
                    "resourceId": {
                        "kind": "youtube#video",
                        "videoId": video_id
                    }
                }
            }
        ).execute()
        logging.info(f"Added video '{video_id}' to playlist '{category}' ({playlist_id}) on channel '{channel_name}'")
        return True
    except Exception as e:
        logging.error(f"Failed to add video to playlist: {e}")
        return False
