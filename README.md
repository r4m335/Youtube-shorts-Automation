# Fully Autonomous YouTube Shorts Automation

A production-ready, 100% Python-based automation pipeline that monitors real-time news and viral topics (via X/Twitter and RSS/Reddit), scripts, voices, renders, and uploads high-quality YouTube Shorts completely hands-free.

---

## 🚀 Features

* **Real-Time X (Twitter) Monitoring (`twscrape`)**: Monitors curated X accounts across multiple niches (**Technology, World News, Sports, Cinema, India, Entertainment, Nature, Anime, Drama**) without X API fees.
* **5-Minute Continuous Scheduler**: Continuous monitoring loop with automated rate-limiting, account sampling, and failure recovery.
* **3-Layer Deduplication Engine**:
  * **Database Tracking (`data/tweets.db`)**: SQLite tracking to ensure tweet IDs are never processed twice.
  * **Entity Keyword Clustering**: Merges similar stories reported by different outlets into a single high-engagement video.
  * **Semantic Memory (`data/topics.json`)**: 48-hour topic cache that prevents re-creating videos on similar themes.
* **History & Documentary Support**: Accepts historical events, past incidents, and documentary content alongside breaking news.
* **Source Attribution**: Automatically credits the original X author (`Source: @author on X`) in video descriptions.
* **Multi-Provider LLM Orchestration**: Generates scripts using Gemini with fallbacks to Groq, OpenRouter, and Ollama.
* **Voice & Audio Processing**: Uses local Piper TTS for natural narration, auto-synced silence gaps, and ducked Lo-Fi background music (`assets/bgm/`).
* **Dynamic B-Roll & Subtitles**: Fetches matching HD B-Roll via Pexels/Unsplash and generates word-by-word highlighted subtitles via FFmpeg.
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

2. Drop your YouTube API `client_secret.json` into the root directory for upload authentication.

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
