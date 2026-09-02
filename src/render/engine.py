import os
import subprocess
import logging

def create_video_segment(visual_data, duration, output_path, fps=30, is_hook=False):
    """
    Creates a video segment from a visual asset (MP4 or JPG).
    The output is cropped/scaled to 1080x1920 (9:16 portrait).
    
    If visual_data is a tuple (image_path, video_path) and duration > 2.0,
    it shows the image for the first 2 seconds, then switches to the video.
    """
    frames = int(duration * fps)
    
    # Handle tuple format (image_path, video_path)
    if isinstance(visual_data, tuple):
        img_path, vid_path = visual_data
        logging.info(f"DEBUG: create_video_segment received tuple. img_path type={type(img_path)}, vid_path type={type(vid_path)}")
    else:
        # Backward compatibility if a string was passed
        img_path, vid_path = visual_data, None
        logging.info(f"DEBUG: create_video_segment received non-tuple: {type(visual_data)}")
        
    # If no video is provided or duration is too short, just use the image
    if not vid_path or duration <= 2.0:
        if isinstance(img_path, tuple):
            logging.error(f"FATAL DEBUG: img_path IS A TUPLE! {img_path}")
            
        if img_path.lower().endswith('.mp4'):
            # It's actually a video string passed directly
            vf_filters = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1"
            if is_hook:
                vf_filters += f",zoompan=z='min(zoom+0.002,1.12)':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps={fps}"
            
            command = [
                "ffmpeg", "-y", "-stream_loop", "-1", "-i", img_path,
                "-t", str(duration),
                "-vf", vf_filters,
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(fps),
                "-an", output_path
            ]
        else:
            zoom_speed = "0.002" if is_hook else "0.001"
            max_zoom = "1.15" if is_hook else "1.12"
            command = [
                "ffmpeg", "-y", "-loop", "1", "-i", img_path,
                "-t", str(duration),
                "-vf", (
                    f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
                    f"zoompan=z='min(zoom+{zoom_speed},{max_zoom})':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920"
                ),
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(fps),
                output_path
            ]
    else:
        # Hybrid mode: image for 2s, then video
        img_frames = int(2.0 * fps)
        vid_duration = duration - 2.0
        
        zoom_speed = "0.002" if is_hook else "0.001"
        max_zoom = "1.15" if is_hook else "1.12"
        
        img_loop_flag = "-stream_loop" if img_path.lower().endswith('.mp4') else "-loop"
        img_loop_val = "-1" if img_path.lower().endswith('.mp4') else "1"
        
        command = [
            "ffmpeg", "-y",
            img_loop_flag, img_loop_val, "-i", img_path,
            "-stream_loop", "-1", "-i", vid_path,
            "-t", str(duration),
            "-filter_complex",
            (
                f"[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
                f"zoompan=z='min(zoom+{zoom_speed},{max_zoom})':d={img_frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps={fps},"
                f"trim=duration=2.0,setpts=PTS-STARTPTS,setsar=1,format=yuv420p[img_v]; "
                f"[1:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
                f"fps={fps},setsar=1,trim=duration={vid_duration},setpts=PTS-STARTPTS,format=yuv420p[vid_v]; "
                f"[img_v][vid_v]concat=n=2:v=1:a=0[outv]"
            ),
            "-map", "[outv]",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(fps),
            "-an", output_path
        ]

    try:
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to create video segment: {e.stderr[-500:] if e.stderr else 'Unknown error'}")
        return False

def concat_video_segments(segment_paths, output_path, fade_duration=0.3):
    """Concatenates video segments with crossfade transitions between them."""
    if not segment_paths:
        return False
        
    if len(segment_paths) == 1:
        # Single segment, just copy
        list_path = os.path.join(os.path.dirname(output_path), "vid_concat_list.txt")
        with open(list_path, "w") as f:
            safe_path = os.path.abspath(segment_paths[0]).replace('\\', '/')
            f.write(f"file '{safe_path}'\n")
        command = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", list_path, "-c", "copy", "-an", output_path
        ]
        try:
            subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
            return True
        except subprocess.CalledProcessError as e:
            logging.error(f"Video concat failed: {e.stderr[-500:] if e.stderr else 'Unknown error'}")
            return False
        finally:
            if os.path.exists(list_path):
                os.remove(list_path)
    
    # Multiple segments: use xfade crossfade transitions
    # Build FFmpeg filter_complex chain for sequential xfade
    try:
        command = ["ffmpeg", "-y"]
        for path in segment_paths:
            command.extend(["-i", path])
        
        # Build xfade filter chain: [0][1]xfade -> [v1], [v1][2]xfade -> [v2], etc.
        filter_parts = []
        n = len(segment_paths)
        
        if n == 2:
            # Simple case: just one xfade
            filter_parts.append(
                f"[0:v][1:v]xfade=transition=fade:duration={fade_duration}:offset=OFFSET_0[outv]"
            )
        else:
            # Chain multiple xfades
            for i in range(n - 1):
                if i == 0:
                    src1 = "[0:v]"
                    src2 = "[1:v]"
                    out_label = "[v1]"
                elif i == n - 2:
                    src1 = f"[v{i}]"
                    src2 = f"[{i+1}:v]"
                    out_label = "[outv]"
                else:
                    src1 = f"[v{i}]"
                    src2 = f"[{i+1}:v]"
                    out_label = f"[v{i+1}]"
                
                filter_parts.append(
                    f"{src1}{src2}xfade=transition=fade:duration={fade_duration}:offset=OFFSET_{i}{out_label}"
                )
        
        # Calculate offsets: we need the cumulative duration minus fade overlaps
        # Get each segment's duration via ffprobe
        from src.visuals.subtitles import get_audio_duration
        durations = []
        for path in segment_paths:
            dur = get_audio_duration(path)  # ffprobe works on video files too
            durations.append(dur if dur > 0 else 3.0)
        
        # Calculate xfade offsets
        cumulative = 0.0
        for i in range(len(filter_parts)):
            offset = cumulative + durations[i] - fade_duration
            filter_str = filter_parts[i].replace(f"OFFSET_{i}", f"{offset:.3f}")
            filter_parts[i] = filter_str
            cumulative += durations[i] - fade_duration
        
        filter_complex = ";".join(filter_parts)
        
        command.extend([
            "-filter_complex", filter_complex,
            "-map", "[outv]",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an",
            output_path
        ])
        
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        logging.info(f"Concatenated {n} segments with {fade_duration}s crossfade transitions")
        return True
        
    except Exception as e:
        logging.warning(f"Crossfade concat failed ({e}), falling back to simple concat...")
        # Fallback: simple concat without transitions
        list_path = os.path.join(os.path.dirname(output_path), "vid_concat_list.txt")
        with open(list_path, "w") as f:
            for path in segment_paths:
                safe_path = os.path.abspath(path).replace('\\', '/')
                f.write(f"file '{safe_path}'\n")
        command = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", list_path, "-c", "copy", "-an", output_path
        ]
        try:
            subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
            return True
        except subprocess.CalledProcessError as e2:
            logging.error(f"Fallback concat also failed: {e2.stderr[-500:] if e2.stderr else 'Unknown error'}")
            return False
        finally:
            if os.path.exists(list_path):
                os.remove(list_path)

def mix_final_video(video_path, audio_path, srt_path, output_path, bgm_path=None):
    """
    Mixes the concatenated video with the full audio, and burns the subtitles.
    Uses bold, clean, lower-centered captions optimized for YouTube Shorts.
    Optionally overlays background music (ducked but audible).
    """
    try:
        safe_srt = os.path.relpath(srt_path).replace('\\', '/').replace(':', '\\\\:')
    except Exception:
        safe_srt = srt_path.replace('\\', '/').replace(':', '\\\\:')
    
    # Styles are now embedded directly inside the ASS file.
    command = [
        "ffmpeg", "-y", 
        "-i", video_path,
        "-i", audio_path
    ]
    
    if bgm_path:
        command.extend(["-stream_loop", "-1", "-i", bgm_path])
        
    command.extend(["-vf", f"ass='{safe_srt}'"])
    
    if bgm_path:
        command.extend([
            "-filter_complex", 
            "[1:a]volume=1.0[main];[2:a]volume=0.18[bgm];[main][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]",
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
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Final video mix failed: {e.stderr[-500:] if e.stderr else 'Unknown error'}")
        return False

def generate_thumbnail(visual_path, text, output_path):
    """
    Extracts the first frame of a visual asset and burns a bold keyword
    across the center with gradient overlay for a high-conversion custom thumbnail.
    """
    words = text.split()[:3]
    thumb_text = ' '.join(words)
    
    command = [
        "ffmpeg", "-y", "-i", visual_path, "-vframes", "1",
        "-vf", (
            f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
            f"colorkey=black:0.01:0.0,"
            f"drawbox=x=0:y=ih*0.6:w=iw:h=ih*0.4:color=black@0.6:t=fill,"
            f"drawtext=text='{thumb_text}':"
            f"fontcolor=white:fontsize=120:"
            f"x=(w-text_w)/2:y=(h*0.68):"
            f"borderw=5:bordercolor=black:"
            f"font=Impact"
        ),
        output_path
    ]
    try:
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Thumbnail generation failed: {e.stderr[-500:] if e.stderr else 'Unknown error'}")
        return False
