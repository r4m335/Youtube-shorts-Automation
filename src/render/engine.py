import os
import subprocess
import logging

def create_video_segment(visual_path, duration, output_path, fps=30):
    """
    Creates a video segment from a visual asset (MP4 or JPG).
    The output is cropped/scaled to 1080x1920 (9:16 portrait).
    """
    frames = int(duration * fps)
    
    if visual_path.lower().endswith('.mp4'):
        # Video: Loop indefinitely, scale and crop to 9:16, trim exactly to duration.
        # -an strips any potentially corrupt audio from source Pexels clips;
        # background audio is mixed in later by mix_final_video().
        command = [
            "ffmpeg", "-y", "-stream_loop", "-1", "-i", visual_path,
            "-t", str(duration),
            "-vf", ("scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1"),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(fps),
            "-an",
            output_path
        ]
    else:
        # Image: Loop 1, zoompan, scale 9:16
        command = [
            "ffmpeg", "-y", "-loop", "1", "-i", visual_path,
            "-t", str(duration),
            "-vf", (
                f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
                f"zoompan=z='min(zoom+0.001,1.15)':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920"
            ),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(fps),
            output_path
        ]
    
    try:
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to create video segment for {visual_path}: {e.stderr.decode('utf-8', errors='ignore')}")
        return False

def concat_video_segments(segment_paths, output_path):
    """Concatenates video segments together."""
    list_path = os.path.join(os.path.dirname(output_path), "vid_concat_list.txt")
    with open(list_path, "w") as f:
        for path in segment_paths:
            # Reconstruct safe path for concat
            safe_path = os.path.abspath(path).replace('\\', '/')
            f.write(f"file '{safe_path}'\n")
            
    command = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", list_path, "-c", "copy", "-an", output_path
    ]
    try:
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Video concat failed: {e.stderr.decode('utf-8', errors='ignore')}")
        return False
    finally:
        if os.path.exists(list_path):
            os.remove(list_path)

def mix_final_video(video_path, audio_path, srt_path, output_path, bgm_path=None):
    """
    Mixes the concatenated video with the full audio, and burns the subtitles.
    Optionally overlays background music (ducked).
    """
    safe_srt = srt_path.replace('\\', '/').replace(':', '\\\\:')
    sub_style = "force_style='FontName=Arial,FontSize=24,PrimaryColour=&HFFFFFF&,OutlineColour=&H40000000&,BorderStyle=1,Outline=2,Shadow=1,Alignment=2,MarginV=60'"
    
    command = [
        "ffmpeg", "-y", 
        "-i", video_path,
        "-i", audio_path
    ]
    
    if bgm_path:
        command.extend(["-stream_loop", "-1", "-i", bgm_path])
        
    command.extend(["-vf", f"subtitles='{safe_srt}':{sub_style}"])
    
    if bgm_path:
        command.extend([
            "-filter_complex", 
            "[1:a]volume=1.0[main];[2:a]volume=0.08[bgm];[main][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]",
            "-map", "0:v",
            "-map", "[aout]"
        ])
    else:
        command.extend([
            "-c:a", "aac",
            "-map", "0:v",
            "-map", "1:a"
        ])

    command.extend(["-c:v", "libx264", "-pix_fmt", "yuv420p"])
    command.append(output_path)
    
    try:
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Final video mix failed: {e.stderr.decode('utf-8', errors='ignore')}")
        return False

def generate_thumbnail(visual_path, text, output_path):
    """
    Extracts the first frame of a visual asset and burns a massive keyword
    across the center to serve as a high-conversion custom thumbnail.
    """
    command = [
        "ffmpeg", "-y", "-i", visual_path, "-vframes", "1",
        "-vf", (
            f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
            f"drawtext=text='{text}':fontcolor=yellow:fontsize=150:x=(w-text_w)/2:y=(h-text_h)/2:"
            f"box=1:boxcolor=black@0.7:boxborderw=30"
        ),
        output_path
    ]
    try:
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Thumbnail generation failed: {e.stderr.decode('utf-8', errors='ignore')}")
        return False
