# Fully Autonomous YouTube Shorts Automation

A production-ready, fully Python-based automation pipeline that natively researches, scripts, voices, edits, and uploads high-quality YouTube Shorts completely hands-free.

## 🚀 Features

* **V3 Media Orchestrator**: Automatically rotates between curated niches (**Hollywood, Global News, Tech, Football, Trivia/Quiz, Conspiracy**) to keep your channel highly diverse.
* **Real-Time Search Grounding**: Integrates native Google Search directly into the Gemini LLM payload to strictly pull **breaking news from today or yesterday** (No outdated LLM hallucinations).
* **Advanced Subtitling**: Generates dynamic, word-by-word highlighting subtitles (similar to popular short-form creators) fully baked in via custom FFmpeg SubStation Alpha styling.
* **Dynamic B-Roll & Assets**: Extracts structural keywords from the generated script, queries the Pexels Video API for matching high-definition B-Roll, and automatically mixes it with looping, ducked Lo-Fi background music.
* **Programmatic Thumbnails**: Automatically rips the first frame of the generated video, overlays the bold script "Hook" text, and attaches it as a custom thumbnail to the video upload.
* **Robust Failovers**: Master LLM orchestration dynamically falls back to Groq if the primary Gemini rate-limits are ever exhausted.
* **Self-Cleaning Storage**: Built-in Garbage Collector automatically runs on every boot to securely purge `data/` and `output/` artifacts older than 48 hours to prevent SSD bloat.
* **Fully Hand-Free Scheduling**: Includes a pre-configured `.bat` script ready to plug directly into the Windows Task Scheduler for 100% daily automation.

## 🛠 Prerequisites

Ensure you have the following installed on your system:
* Python 3.10+
* **FFmpeg**: Must be installed and added to your system environment `PATH` variables.
* **Piper TTS**: The local Text-To-Speech engine must be downloaded and mapped.

## 🔑 Environment Variables
Create a `.env` file in the root directory containing your API keys:

```env
GEMINI_API_KEY=your_google_ai_studio_key
GROQ_API_KEY=your_groq_api_key
PEXELS_API_KEY=your_pexels_key
PIPER_MODEL_PATH=absolute_path_to_your_local_piper_model.onnx
```

*Note: You must also drop a valid `client_secret.json` from your Google Cloud Console into the project root to authenticate YouTube Data API uploads.*

## ⚙️ Installation

1. Clone the repository and navigate to the project directory:
   ```bash
   git clone https://github.com/r4m335/Youtube-shorts-Automation.git
   cd Youtube-shorts-Automation
   ```

2. Create and activate a Virtual Environment:
   ```bash
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

3. Install requirements:
   ```bash
   pip install -r requirements.txt
   ```

4. Prepare your local `assets/bgm/` folder with royalty-free `.mp3` tracks for the pipeline to randomly select from.

## 🎬 Usage

To manually trigger a complete pipeline run:
```bash
python main.py
```

### Windows Task Scheduler Automation
To run this automatically every day:
1. Open Windows Task Scheduler and click **Create Basic Task**.
2. Select your daily trigger time.
3. Choose **Start a Program**.
4. Point it to the `run_daily.bat` file located in this repository.
5. In the **"Start in"** dialogue box, explicitly paste the absolute path to this folder (e.g. `C:\mini project\youtube\`).
6. Save and let the system run completely autonomously!

## 📝 License
This project is for educational and personal automation purposes. Make sure to adhere to YouTube's TOS and Google Cloud API usage limits regarding programmatic uploads.
