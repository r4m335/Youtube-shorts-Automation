import subprocess
import logging
import os
import asyncio
import random

# --------------------------------------------------------------------------- #
# Voice pool — randomly picks one per video for variety
# --------------------------------------------------------------------------- #
TTS_VOICES = [
    "en-US-GuyNeural",          # Confident, urgent news presenter
]

# Pick one voice per session (consistent within a single video)
_session_voice = None

def _get_session_voice():
    global _session_voice
    if _session_voice is None:
        _session_voice = random.choice(TTS_VOICES)
        logging.info(f"TTS voice selected for this video: {_session_voice}")
    return _session_voice

def reset_session_voice():
    """Call at the start of each new topic to pick a fresh voice."""
    global _session_voice
    _session_voice = None

# --------------------------------------------------------------------------- #
# Edge TTS (Primary — natural-sounding Microsoft Azure voices, FREE)
# --------------------------------------------------------------------------- #
async def _edge_tts_async(text, output_path, voice="en-US-GuyNeural"):
    """Generate TTS using Edge TTS (Microsoft Azure voices via edge-tts package)."""
    import edge_tts
    # Add +15% rate and +2Hz pitch to transform the flat 'reading' tone into an energetic 'presentation' tone
    communicate = edge_tts.Communicate(text, voice, rate="+15%", pitch="+2Hz")
    await communicate.save(output_path)


def generate_tts_edge(text, output_path, voice=None):
    """
    Generate TTS using Edge TTS with natural-sounding voices.
    
    Voices used:
    - en-US-JennyNeural (female, storytelling, facts — ⭐⭐⭐⭐⭐)
    - en-US-AndrewNeural (male, documentary, educational — ⭐⭐⭐⭐⭐)
    """
    voice = voice or os.getenv("EDGE_TTS_VOICE", _get_session_voice())
    
    try:
        # Retry loop for transient network/DNS errors to Bing servers
        for attempt in range(3):
            try:
                # Run async edge-tts in a sync context
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(_edge_tts_async(text, output_path, voice))
                finally:
                    loop.close()
                break # Success!
            except Exception as e:
                logging.warning(f"Edge TTS attempt {attempt + 1}/3 failed: {e}")
                if attempt == 2:
                    raise
                import time
                time.sleep(2)
        
        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            logging.error("Edge TTS succeeded but output file is empty or missing.")
            return False
        
        # Edge TTS outputs MP3 — convert to WAV for pipeline compatibility
        wav_path = output_path
        if output_path.lower().endswith('.wav'):
            mp3_temp = output_path + ".mp3"
            os.rename(output_path, mp3_temp)
            command = [
                "ffmpeg", "-y", "-i", mp3_temp,
                "-acodec", "pcm_s16le", "-ar", "22050", "-ac", "1",
                wav_path
            ]
            subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
            os.remove(mp3_temp)
        
        return True
    except Exception as e:
        logging.error(f"Edge TTS failed: {e}")
        return False


# --------------------------------------------------------------------------- #
# Piper TTS (Fallback 1 — offline, fast)
# --------------------------------------------------------------------------- #
def generate_tts_piper(text, output_path, model_path=None):
    """Generate TTS using Piper via CLI."""
    model_full_path = model_path or os.getenv("PIPER_MODEL_PATH", r"C:\piper\models\en_US-lessac-medium.onnx")
    
    if not os.path.exists(model_full_path):
        logging.error(f"Piper model not found at {model_full_path}")
        return False
    
    # Simple escape for quotes in text
    safe_text = text.replace('"', '\\"')
    command = f'echo "{safe_text}" | piper -m "{model_full_path}" -f "{output_path}"'
    
    try:
        # We use shell=True for echo piping
        result = subprocess.run(command, shell=True, check=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            logging.error("Piper succeeded but output file is empty or missing.")
            return False
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Piper TTS failed: {e.stderr.decode('utf-8', errors='ignore')}")
        return False

# --------------------------------------------------------------------------- #
# Coqui TTS (Fallback 2)
# --------------------------------------------------------------------------- #
def generate_tts_coqui(text, output_path):
    """Fallback TTS using Coqui TTS via CLI."""
    safe_text = text.replace('"', '\\"')
    command = f'tts --text "{safe_text}" --out_path "{output_path}"'
    try:
        subprocess.run(command, shell=True, check=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Coqui TTS failed: {e.stderr.decode('utf-8', errors='ignore')}")
        return False

# --------------------------------------------------------------------------- #
# Main TTS entry point with fallback chain
# --------------------------------------------------------------------------- #
def generate_line_audio(text, output_path):
    """
    Attempts to generate TTS for a single line using the best available engine.
    Fallback chain: Edge TTS → Piper → Coqui
    """
    # Primary: Edge TTS (natural-sounding, free)
    if generate_tts_edge(text, output_path):
        return True
    
    # Fallback 1: Piper (offline, fast)
    logging.warning("Edge TTS failed, falling back to Piper TTS")
    if generate_tts_piper(text, output_path):
        return True
    
    # Fallback 2: Coqui
    logging.warning("Piper failed, falling back to Coqui TTS")
    return generate_tts_coqui(text, output_path)
