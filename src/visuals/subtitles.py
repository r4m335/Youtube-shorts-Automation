import os
import subprocess
import logging

def get_audio_duration(file_path):
    """Returns duration in seconds using ffprobe."""
    command = [
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration", "-of", "default=noprint_wrappers=1:nokey=1",
        file_path
    ]
    try:
        result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return float(result.stdout.decode('utf-8').strip())
    except Exception as e:
        logging.error(f"Failed to get duration for {file_path}: {e}")
        return 0.0

def format_timestamp(seconds):
    """Formats seconds into SRT timestamp HH:MM:SS,mmm"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

def generate_srt(lines, audio_files, output_path):
    """
    Generates an advanced SRT subtitle file with word-by-word highlighting.
    Returns the total duration.
    """
    if len(lines) != len(audio_files):
        logging.error("Lines and audio files mismatch for SRT generation.")
        return 0.0

    current_time = 0.0
    block_index = 1
    
    with open(output_path, "w", encoding="utf-8") as f:
        for i, (line, audio_file) in enumerate(zip(lines, audio_files)):
            duration = get_audio_duration(audio_file)
            
            words = line.split()
            if not words:
                current_time += duration
                continue
                
            word_dur = duration / len(words)
            
            for j in range(len(words)):
                start_stamp = format_timestamp(current_time + (j * word_dur))
                # Make end stamp slightly exact to contiguous borders
                end_stamp = format_timestamp(current_time + ((j + 1) * word_dur))
                
                # Build the dynamic highlighted string
                highlighted_words = []
                for w_idx, w in enumerate(words):
                    if w_idx == j:
                        # Bright yellow highlight for the active spoken word
                        highlighted_words.append(f'<font color="#FFFF00">{w}</font>')
                    else:
                        highlighted_words.append(w)
                
                display_line = " ".join(highlighted_words)
                
                f.write(f"{block_index}\n")
                f.write(f"{start_stamp} --> {end_stamp}\n")
                f.write(f"{display_line}\n\n")
                block_index += 1
                
            current_time += duration
            
    logging.info(f"Generated advanced SRT at {output_path} with total duration {current_time:.2f}s")
    return current_time
