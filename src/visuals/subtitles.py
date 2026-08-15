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
        result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        return float(result.stdout.strip())
    except Exception as e:
        logging.error(f"Failed to get duration for {file_path}: {e}")
        return 0.0

def format_ass_timestamp(seconds):
    """Formats seconds into ASS timestamp H:MM:SS.cs"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centis = int(round((seconds - int(seconds)) * 100))
    return f"{hours}:{minutes:02d}:{secs:02d}.{centis:02d}"

def generate_ass(lines, audio_files, output_path, max_words_per_chunk=3):
    """
    Generates an advanced YouTube Shorts ASS subtitle file with short 2-3 word chunks
    and green background karaoke highlighting.
    """
    if len(lines) != len(audio_files):
        logging.error("Lines and audio files mismatch for ASS generation.")
        return 0.0

    current_time = 0.0
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\n\n")
        f.write("[V4+ Styles]\n")
        f.write("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n")
        f.write("Style: Default,Impact,55,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,5,2,2,60,60,500,1\n\n")
        f.write("[Events]\n")
        f.write("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
        
        for i, (line, audio_file) in enumerate(zip(lines, audio_files)):
            duration = get_audio_duration(audio_file)
            words = line.split()
            if not words:
                current_time += duration
                continue
            
            chunks = [words[k:k + max_words_per_chunk] for k in range(0, len(words), max_words_per_chunk)]
            chunk_duration_base = duration / len(chunks) if chunks else duration
            
            for chunk_idx, chunk in enumerate(chunks):
                chunk_start = current_time + (chunk_idx * chunk_duration_base)
                chunk_end = current_time + ((chunk_idx + 1) * chunk_duration_base)
                
                word_count = len(chunk)
                word_duration = (chunk_end - chunk_start) / word_count if word_count > 0 else (chunk_end - chunk_start)
                
                for w_idx in range(word_count):
                    word_start = chunk_start + (w_idx * word_duration)
                    word_end = chunk_start + ((w_idx + 1) * word_duration)
                    
                    start_stamp = format_ass_timestamp(word_start)
                    end_stamp = format_ass_timestamp(word_end)
                    
                    highlighted_parts = []
                    active_tag = r"{\1c&HFFFFFF&\3c&H00D000&\bord22\shad0}"
                    reset_tag = r"{\1c&HFFFFFF&\3c&H000000&\bord5\shad2}"
                    
                    for j, word in enumerate(chunk):
                        if j == w_idx:
                            highlighted_parts.append(f"{active_tag}{word}{reset_tag}")
                        else:
                            highlighted_parts.append(word)
                    
                    text = " ".join(highlighted_parts)
                    f.write(f"Dialogue: 0,{start_stamp},{end_stamp},Default,,0,0,0,,{text}\n")
                    
            current_time += duration
            
    logging.info(f"Generated Shorts-optimized ASS with green highlighting at {output_path} with total duration {current_time:.2f}s")
    return current_time
