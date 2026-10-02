# Fully Autonomous YouTube Shorts Automation

A production-ready, fully autonomous Python pipeline that monitors real-time news from X (Twitter) via a hybrid twscrape + Playwright browser engine, generates scripts with LLM, voices them with Edge TTS, renders vertical video with FFmpeg, and uploads to multiple YouTube channels — completely hands-free.

---

## 🚀 Features

* **Hybrid Real-Time X (Twitter) Monitoring**: Dual-engine ingestion using lightning-fast **twscrape** as the primary choice (with full Twitter media extraction) and headless **Playwright** browser as an automatic fallback — zero API fees, high-speed ingestion, and complete failure resilience.
* **5-Minute Continuous Scheduler**: Runs as a `while True` loop with automated ingestion, smart scraping (only scrapes categories with empty backlogs), and failure recovery.
* **Multi-Channel Auto-Routing**: Dynamically routes uploads to separate YouTube channels based on topic category using isolated per-channel OAuth tokens:
  | Channel | Categories |
  |---|---|
  | `entertainment` | CDrama |
  | `sports` | Sports |
  | `tech_world` | Tech, World News |
  | `anime` | Anime |
* **Correct YouTube Category Tagging**: Each video is tagged with the proper YouTube category ID (Sports → 17, Tech → 28, News → 25, Entertainment → 24).
* **3-Layer Deduplication Engine**:
  * **Database Tracking (`data/tweets.db`)**: SQLite tracking ensures tweet IDs are never processed twice.
  * **Entity Keyword Clustering**: Merges similar stories reported by multiple accounts into a single trending video.
  * **Semantic Memory (`data/topics.json`)**: 48-hour topic cache prevents re-creating videos on similar themes.
* **Intelligent Visual Fetching & 8-Source Fallback Chain**:
  1. Article `og:image` / `twitter:image` scraping (from URLs in tweets + DuckDuckGo article discovery)
  2. Wikipedia / Wikimedia Commons
  3. DuckDuckGo Images
  4. Bing Image Search
  5. TMDB (movies/shows/actors)
  6. SerpAPI Google Images
  7. Stability AI (AI-generated visuals)
  8. Pexels / Pixabay (stock fallback)
* **Gemini Vision Safety Check**: Every fetched image is verified for NSFW content and topic relevance using Gemini 3.5 Flash Vision before use.
* **LLM Script Generation with Auto-Refinement**: 14-provider LLM fallback chain (Ollama → Groq → OpenRouter → Nvidia → Cloudflare → HuggingFace → Mistral → LLM7 → OpenAI → Gemini → Cohere → Zhipu). Scripts are auto-evaluated and refined if rejected.
* **RAG Context Injection**: Fetches real-time search snippets via DuckDuckGo to ground LLM scripts in facts and prevent hallucinations.
* **Edge TTS Narration**: Natural-sounding Microsoft Azure voices (free via `edge-tts`), with speed boost and pitch adjustment for energetic delivery.
* **Dynamic Video Rendering**:
  * Ken Burns zoom effect on images, crossfade transitions between segments
  * YouTube Shorts-optimized ASS subtitles with word-by-word green karaoke highlighting
  * Programmatic thumbnail generation with bold keyword overlay
* **X Scraper Health Circuit Breaker**: Automatic degraded/disabled states if X scraping fails repeatedly, with 15-minute auto-recovery.
* **Self-Cleaning Storage**: Garbage collector purges temp files and outputs older than 1 hour.

---

## 🗂 Project Structure

```
├── main.py                          # Entry point — continuous scheduler
├── config/
│   ├── accounts.json                # X accounts to monitor per category
│   ├── channels.json                # YouTube channel routing config
│   └── channels/                    # Per-channel OAuth credentials
│       ├── entertainment/
│       ├── sports/
│       ├── tech_world/
│       └── india/                   # (repurposed for anime channel)
├── src/
│   ├── ingestion/                   # Tweet fetching, filtering, topic generation
│   │   ├── orchestrator.py          # LLM topic generation from tweets/RSS
│   │   ├── scraper_job.py           # Phase 1 ingestion pipeline
│   │   ├── filter.py                # Dedup cache & topic validation
│   │   └── x/                       # Playwright-based X scraper
│   │       ├── browser.py           # Playwright scraping engine
│   │       ├── parser.py            # Tweet DOM parser
│   │       ├── fetcher.py           # Account manager & async pipeline
│   │       └── health.py            # Circuit breaker health checks
│   ├── filters/                     # Pre-filter (spam, old, short) & LLM news filter
│   ├── llm/                         # LLM provider chain, script gen, validation
│   ├── audio/                       # Edge TTS, Piper TTS, audio processing
│   ├── visuals/                     # Image fetching (8 sources), subtitle generation
│   ├── render/                      # FFmpeg video segments, concat, mix, thumbnails
│   ├── upload/                      # YouTube upload, playlist management, metadata
│   └── storage/                     # SQLite database, trending backlog
├── scripts/                         # Cached LLM scripts (auto-generated)
├── data/                            # Runtime data (tweets.db, topics.json, temp files)
├── output/                          # Final rendered videos
└── logs/                            # System logs
```

---

## 🛠 Prerequisites

* **Python 3.10+**
* **FFmpeg**: Installed and on system `PATH`
* **Playwright**: Run `playwright install chromium` after installing dependencies

---

## 🔑 Environment Setup

1. Create a `.env` file in the root directory:

```env
# YouTube Data API
YOUTUBE_CLIENT_ID=your_client_id
YOUTUBE_CLIENT_SECRET=your_client_secret
YOUTUBE_PROJECT_ID=your_project_id

# LLM APIs (at least one required, all optional — uses fallback chain)
GROQ_API_KEY=your_groq_key
GEMINI_API_KEY=your_gemini_key
OPENROUTER_API_KEY=your_openrouter_key
OLLAMA_URL=http://localhost:11434/api/generate
OLLAMA_MODEL=gpt-oss:20b
# ... (supports 14 providers total, see src/llm/providers.py)

# Visual APIs
PEXELS_API_KEY=your_pexels_key
PIXABAY_API_KEY=your_pixabay_key
SERPAPI_KEY=your_serpapi_key
TMDB_API_KEY=your_tmdb_key
STABILITY_API_KEY=your_stability_key

# TTS
EDGE_TTS_VOICE=en-US-AndrewNeural

# X (Twitter) Session Cookies
X_COOKIES=auth_token=YOUR_AUTH_TOKEN; ct0=YOUR_CT0
```

2. **Multi-Channel Configuration**:
   Place a unique OAuth 2.0 Client ID (type: **Desktop app**) for each YouTube channel:
   ```
   config/channels/
   ├── entertainment/
   │   └── client_secret.json
   ├── sports/
   │   └── client_secret.json
   ├── tech_world/
   │   └── client_secret.json
   └── india/
       └── client_secret.json    ← used for anime channel
   ```
   *The pipeline will prompt browser auth on the first upload per channel. The `token.json` is saved automatically.*

---

## ⚙️ Monitored Accounts

Edit `config/accounts.json` to configure which X accounts to monitor per category:

```json
{
    "sports": ["David_Ornstein", "FabrizioRomano"],
    "Cdrama": ["ForCdrama"],
    "world": ["interesting_aIl", "pubity", "InternetH0F"],
    "Tech": ["Pirat_Nation"],
    "Anime": ["animeupdates"]
}
```

---

## ⚙️ Installation

1. Clone and enter:
   ```bash
   git clone https://github.com/r4m335/Youtube-shorts-Automation.git
   cd Youtube-shorts-Automation
   ```

2. Create venv and activate:
   ```bash
   python -m venv venv
   .\venv\Scripts\Activate.ps1    # Windows
   source venv/bin/activate        # Linux/Mac
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

---

## 🎬 Usage

### Run All Channels (Continuous 5-Minute Scheduler):
```bash
python main.py
```

### Run One Channel Only:
```bash
# Run only World News & Tech channel
python main.py --channel tech_world

# Run only Cdrama entertainment channel
python main.py --channel entertainment

# Run only Sports channel
python main.py --channel sports

# Run only Anime channel
python main.py --channel anime
```

### Run a Single Pass and Exit (No Continuous Loop):
```bash
# Generate 1 video for world news and exit
python main.py --channel tech_world --category world --max-videos 1 --once
```

### Skip Specific Channels:
```bash
python main.py --skip-channel sports --skip-channel entertainment
```

The pipeline runs in a continuous 5-minute cycle:
1. **Phase 1 (Ingestion)**: Scrapes X accounts, filters spam/duplicates, stores pending tweets in SQLite
2. **Phase 2 (Generation)**: For each channel, pulls pending tweets, generates topics via LLM, creates script → audio → visuals → video → uploads to YouTube

---

## 📝 License

This project is for educational and personal automation purposes. Adhere to YouTube's Terms of Service and API guidelines regarding programmatic uploads.
