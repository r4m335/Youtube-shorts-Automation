# Fully Autonomous YouTube Shorts Automation

A production-ready, 100% Python-based automation pipeline that monitors real-time news and viral topics (via X/Twitter and RSS/Reddit), scripts, voices, renders, and uploads high-quality YouTube Shorts completely hands-free.

---

## 🚀 Features

* **Real-Time X (Twitter) Monitoring (`twscrape`)**: Monitors curated X accounts across multiple niches (**Technology, World News, Sports, Cinema, India, Entertainment, Nature, Anime, Drama**) without X API fees.
* **5-Minute Continuous Scheduler**: Continuous monitoring loop with automated rate-limiting, account sampling, and failure recovery.
* **Multi-Channel Auto-Routing**: Dynamically routes video uploads to completely separate YouTube channels based on the topic's category using isolated per-channel OAuth tokens. Automatically creates and manages category-specific playlists (e.g., "Movie News", "Tech News") on each channel.
* **3-Layer Deduplication Engine**:
  * **Database Tracking (`data/tweets.db`)**: SQLite tracking to ensure tweet IDs are never processed twice.
  * **Entity Keyword Clustering**: Merges similar stories reported by different outlets into a single high-engagement video.
  * **Semantic Memory (`data/topics.json`)**: 48-hour topic cache that prevents re-creating videos on similar themes.
* **Intelligent Visual Fetching & Auto-Fallback**:
  * **DuckDuckGo HTML Lite Scraping**: Bypasses search engine rate limits to reliably extract high-quality publisher `og:image` hero images for news topics.
  * Multi-source fallback priority (Tweet Media -> Scraped Article Images -> Wikipedia -> TMDB -> Bing -> DuckDuckGo -> AI-generated images).
* **LLM Script Auto-Refinement**: Built-in quality evaluator that automatically detects script violations and actively refines output until it passes content guidelines.
* **Voice & Audio Processing**: Uses local Piper TTS or Azure TTS for natural narration, auto-synced silence gaps, and ducked Lo-Fi background music (`assets/bgm/`).
* **Dynamic B-Roll & Advanced Subtitles**: 
  * Fetches matching HD B-Roll or generates AI images using Stability AI.
  * Generates TikTok-style native `.ass` subtitles with animated word-by-word green background highlighting and exact positioning to clear YouTube Shorts UI.
* **Programmatic Thumbnails**: Rips video frames and overlays bold script hooks for custom thumbnails.
* **Self-Cleaning Storage**: Built-in Garbage Collector automatically purges temporary directory artifacts older than 48 hours.

---

## 🛠 Prerequisites

Ensure you have the following installed on your system:
* **Python 3.10+**
* **FFmpeg**: Installed and added to system `PATH`.
* **Piper TTS**: Local Text-To-Speech model mapped in `.env`.

---

## 🔑 Environment Setup

1. Create a `.env` file in the root directory:

```env
# YouTube Data API
YOUTUBE_CLIENT_ID=your_client_id
YOUTUBE_CLIENT_SECRET=your_client_secret
YOUTUBE_PROJECT_ID=your_project_id

# LLM APIs
GEMINI_API_KEY=your_gemini_api_key
GROQ_API_KEY=your_groq_api_key
OPENROUTER_API_KEY=your_openrouter_api_key

# Visual APIs
PEXELS_API_KEY=your_pexels_key
UNSPLASH_ACCESS_KEY=your_unsplash_access_key

# TTS Configuration
PIPER_MODEL_PATH=C:\piper\models\en_US-hfc_male-medium.onnx

# X (Twitter) Credentials & Session Cookies
X_USERNAME=your_x_username
X_PASSWORD=your_x_password
X_EMAIL=your_x_email
X_EMAIL_PASSWORD=your_x_email_password
X_COOKIES=auth_token=YOUR_AUTH_TOKEN; ct0=YOUR_CT0
```

2. **Multi-Channel Configuration**: 
   The pipeline routes uploads to specific channels based on category. This is configured in `config/channels.json`. For each channel, you must provide a unique OAuth 2.0 Client ID (type: **Desktop app**) placed in its respective directory:
   ```
   config/channels/
   ├── entertainment/
   │   ├── client_secret.json  <-- Place your Google Cloud Desktop app credentials here
   ├── tech_sports/
   │   ├── client_secret.json
   └── world_news/
       ├── client_secret.json
   ```
   *Note: The pipeline will prompt you to authenticate via your browser on the very first upload for each channel. The resulting `token.json` will be saved next to the client secret.*

---

## ⚙️ Monitored Accounts Config

Edit `config/accounts.json` to add or remove monitored handles across any niche:

```json
{
    "technology": ["techradar", "beebomco", "ReutersTech"],
    "world": ["rawsalerts", "disclosetv", "GlobeEyeNews"],
    "sports": ["FabrizioRomano", "Transfermarkt", "David_Ornstein"],
    "cinema": ["DiscussingFilm", "CultureCrave", "DEADLINE"],
    "Anime": ["SugoiLITE", "myanimelist"]
}
```

---

## ⚙️ Installation

1. Clone the repository and enter the directory:
   ```bash
   git clone https://github.com/r4m335/Youtube-shorts-Automation.git
   cd Youtube-shorts-Automation
   ```

2. Create and activate a Virtual Environment:
   ```bash
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Drop royalty-free `.mp3` background music into `assets/bgm/`.

---

## 🎬 Usage

To start the continuous automated scheduler:
```bash
python main.py
```

The pipeline will run in a continuous loop every 5 minutes, checking for new viral tweets and news, generating videos, uploading them to YouTube, and sleeping between cycles.

---

## 📝 License

This project is for educational and personal automation purposes. Adhere to YouTube's Terms of Service and API guidelines regarding programmatic uploads.
