#!/usr/bin/env python3
"""
Attach an opening slide to the start of a video.

Sequence:
  1. The slide is on screen from the first frame (no fade-in) and holds.
  2. The slide's contents fade away over the fade duration, leaving plain paper.
  3. The plain paper stays on screen for a short gap (default 0.5 s).
  4. The main video starts, with its audio.

Usage:
    python add_intro.py slide.png paper.png main.mp4
    python add_intro.py slide.png paper.png main.mp4 -o final.mp4 --hold 4 --fade 2 --gap 0.5

slide.png  the opening slide, including its paper background
paper.png  the same paper with nothing on it
main.mp4   your tabs video

Requires ffmpeg and ffprobe on your PATH.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path


def probe(video):
    """Return width, height, frame rate and whether the video has audio."""
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(video)],
        capture_output=True, text=True, check=True,
    ).stdout
    streams = json.loads(out)["streams"]
    v = next(s for s in streams if s["codec_type"] == "video")
    num, den = v["r_frame_rate"].split("/")
    fps = float(num) / float(den)
    has_audio = any(s["codec_type"] == "audio" for s in streams)
    return int(v["width"]), int(v["height"]), fps, has_audio


def fit(label_in, label_out, w, h, fps):
    """Scale and crop an input to the video's size and frame rate."""
    return (f"[{label_in}]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
            f"setsar=1,fps={fps},format=yuv420p,settb=AVTB[{label_out}]")


def main():
    p = argparse.ArgumentParser(description="Attach an opening slide to the start of a video.")
    p.add_argument("slide", help="opening slide image, with its paper background")
    p.add_argument("paper", help="the plain paper image, with nothing on it")
    p.add_argument("video", help="main video (MP4)")
    p.add_argument("-o", "--output", help="output file (default: <video>_with_intro.mp4)")
    p.add_argument("--hold", type=float, default=4.0,
                   help="seconds the slide stays fully visible (default 4)")
    p.add_argument("--fade", type=float, default=2.0,
                   help="seconds for the slide contents to fade away (default 2)")
    p.add_argument("--gap", type=float, default=0.5,
                   help="seconds of plain paper before the video starts (default 0.5)")
    p.add_argument("--video-fade", type=float, default=0.0,
                   help="seconds for the video to fade in from the paper (default 0 = straight cut)")
    args = p.parse_args()

    slide, paper, video = Path(args.slide), Path(args.paper), Path(args.video)
    for f in (slide, paper, video):
        if not f.exists():
            sys.exit(f"File not found: {f}")
    out = Path(args.output) if args.output else video.with_name(video.stem + "_with_intro.mp4")

    w, h, fps, has_audio = probe(video)
    vfade = max(args.video_fade, 0.0)
    video_start = args.hold + args.fade + args.gap      # when the video begins to appear
    slide_len = args.hold + args.fade
    paper_len = args.fade + args.gap + vfade

    parts = [
        fit("0:v", "slide", w, h, fps),
        fit("1:v", "paper", w, h, fps),
        fit("2:v", "main", w, h, fps),
        # Slide contents fade away, leaving the plain paper.
        f"[slide][paper]xfade=transition=fade:duration={args.fade}:offset={args.hold}[intro]",
    ]
    if vfade > 0:
        parts.append(f"[intro][main]xfade=transition=fade:duration={vfade}:offset={video_start}[v]")
    else:
        parts.append("[intro][main]concat=n=2:v=1:a=0[v]")

    maps = ["-map", "[v]"]
    if has_audio:
        delay_ms = int(round(video_start * 1000))
        parts.append(f"[2:a]adelay={delay_ms}:all=1[a]")
        maps += ["-map", "[a]"]

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-framerate", str(fps), "-t", str(slide_len), "-i", str(slide),
        "-loop", "1", "-framerate", str(fps), "-t", str(paper_len), "-i", str(paper),
        "-i", str(video),
        "-filter_complex", ";".join(parts),
        *maps,
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
    ]
    if has_audio:
        cmd += ["-c:a", "aac", "-b:a", "192k"]
    cmd.append(str(out))

    print(f"Slide holds {args.hold}s, fades away over {args.fade}s, "
          f"plain paper for {args.gap}s, video starts at {video_start}s")
    print(f"Video: {w}x{h} @ {fps:g} fps, audio: {'yes' if has_audio else 'no'}")
    subprocess.run(cmd, check=True)
    print(f"Done: {out}")


if __name__ == "__main__":
    main()
