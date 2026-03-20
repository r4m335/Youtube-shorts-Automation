import subprocess
import os
import logging
import uuid
import tempfile

def process_audio(input_path, output_path, speed=1.1, silence_gap=0.3):
    """
    Normalizes speed and adds a trailing silence gap using FFmpeg.
    """
    command = [
        "ffmpeg", "-y", "-i", input_path,
        "-filter:a", f"atempo={speed},apad=pad_dur={silence_gap}",
        output_path
    ]
    try:
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Audio processing failed: {e.stderr.decode('utf-8', errors='ignore')}")
        return False

def concat_audio(file_paths, output_path):
    """Concatenates multiple audio files into one."""
    if not file_paths:
        return False
        
    # Create an intermediate file list for ffmpeg in temp dir
    list_fd, list_path = tempfile.mkstemp(suffix=".txt", text=True)
    with os.fdopen(list_fd, "w") as f:
        for path in file_paths:
            safe_path = os.path.abspath(path).replace('\\', '/')
            f.write(f"file '{safe_path}'\n")
            
    command = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", list_path, "-c", "copy", output_path
    ]
    
    try:
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        success = True
    except subprocess.CalledProcessError as e:
        logging.error(f"Audio concatenation failed: {e.stderr.decode('utf-8', errors='ignore')}")
        success = False
    finally:
        if os.path.exists(list_path):
            os.remove(list_path)
            
    return success

def create_full_audio_for_script(lines, temp_dir="data", speed=1.1, silence_gap=0.3):
    """
    Generates audio for each line, applies speed and silence, and concatenates them.
    Returns the path to the combined audio file, and a list of durations per line.
    """
    from .tts import generate_line_audio
    
    processed_files = []
    
    for i, line in enumerate(lines):
        raw_path = os.path.join(temp_dir, f"raw_line_{i}.wav")
        proc_path = os.path.join(temp_dir, f"proc_line_{i}.wav")
        
        # Generator
        if not generate_line_audio(line, raw_path):
            logging.error(f"Failed to generate audio for line {i}: {line}")
            return None
            
        # Processor
        if not process_audio(raw_path, proc_path, speed=speed, silence_gap=silence_gap):
            return None
            
        processed_files.append(proc_path)
        
    # Concat all
    final_output = os.path.join(temp_dir, "final_audio.wav")
    if concat_audio(processed_files, final_output):
        return final_output
    return None
