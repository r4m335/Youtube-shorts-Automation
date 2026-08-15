import subprocess
import os

# Create dummy image
subprocess.run(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'color=c=red:s=640x480:d=5', '-frames:v', '1', 'dummy.jpg'])
# Create dummy video at 25fps
subprocess.run(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'testsrc=size=640x480:rate=25', '-t', '5', 'dummy.mp4'])

fps = 30
img_frames = 2 * fps
vid_duration = 3.0
zoom_speed = '0.001'
max_zoom = '1.12'

cmd = [
    'ffmpeg', '-y',
    '-loop', '1', '-i', 'dummy.jpg',
    '-stream_loop', '-1', '-i', 'dummy.mp4',
    '-t', '5',
    '-filter_complex', (
        f"[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
        f"zoompan=z='min(zoom+{zoom_speed},{max_zoom})':d={img_frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps={fps},"
        f"trim=duration=2.0,setpts=PTS-STARTPTS,setsar=1,format=yuv420p[img_v]; "
        f"[1:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
        f"fps={fps},setsar=1,trim=duration={vid_duration},setpts=PTS-STARTPTS,format=yuv420p[vid_v]; "
        f"[img_v][vid_v]concat=n=2:v=1:a=0[outv]"
    ),
    '-map', '[outv]',
    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-r', str(fps),
    '-an', 'out_test.mp4'
]

res = subprocess.run(cmd, capture_output=True, text=True)
print('Return code:', res.returncode)
if res.returncode != 0:
    print(res.stderr[-1000:])
else:
    print("Success!")
