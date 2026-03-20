import subprocess
import logging
import os

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

def generate_line_audio(text, output_path):
    """Attempts to generate TTS for a single line using Piper, falling back to Coqui."""
    if generate_tts_piper(text, output_path):
        return True
    
    logging.warning("Piper failed, falling back to Coqui TTS")
    return generate_tts_coqui(text, output_path)
