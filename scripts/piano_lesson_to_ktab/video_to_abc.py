#!/usr/bin/env python3
"""
video_to_abc.py

From a piano-lesson video to ABC sheet music of the right-hand melody, with
the lyrics in syllables under the notes. One command:

    python video_to_abc.py lesson.mp4
    python video_to_abc.py lesson.mp4 --title "Ekla Cholo Re" --out song.abc

Steps (each is its own script in this folder):
  1. extract_song_lines.py   finds the chapters (extract_chapter_titles.py) and,
                             in every "Right Hand (Separately)" chapter, the
                             slow lines: lyrics, on-screen note names and times
                             -> <video>_lines.csv
  2. piano_notes_from_audio.py  takes the notes from that CSV and, from the
                             audio, their octave and lengths -> <video>.abc,
                             and every note with its times in the video
                             -> <video>_notes.csv (also printed)

Needs in this folder: extract_chapter_titles.py, extract_song_lines.py,
piano_notes_from_audio.py, notes_from_audio.py.
Needs installed: ffmpeg, Tesseract, and  pip install opencv-python pytesseract numpy

Options:
  --title    song title in the ABC (default: the video's file name)
  --out      ABC file (default: <video name>.abc next to the video)
  --tempo    quarter notes per minute (default: median of the tempos played)
  --key      major key the song is played in (default: read from the video's
             "Scale/Key - C Major" title card, else worked out from the notes)
  --to-key   transpose the ABC to this major key, e.g. C (default: as played)
  --strict   no accidentals: notes outside the key replaced by notes of the key
  --lengths  CSV of note lengths known from elsewhere, e.g. the song's swaralipi
             (stanza_no,line_no,note_no,note,eighths,source). A file named
             <video>_lengths.csv next to the video is used automatically.
  --meter    4/4 (default), 6/8, or auto
"""

import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
NEEDED = ["extract_chapter_titles.py", "extract_song_lines.py",
          "piano_notes_from_audio.py", "notes_from_audio.py"]


def run(script, *args):
    cmd = [sys.executable, str(HERE / script), *map(str, args)]
    print(f"\n== {script}", flush=True)
    if subprocess.run(cmd, cwd=HERE).returncode != 0:
        sys.exit(f"{script} failed")


def main():
    ap = argparse.ArgumentParser(description="Piano-lesson video -> ABC of the right-hand melody with lyrics.")
    ap.add_argument("video")
    ap.add_argument("--title")
    ap.add_argument("--out")
    ap.add_argument("--tempo", type=int)
    ap.add_argument("--key", default="auto")
    ap.add_argument("--to-key")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--lengths")
    ap.add_argument("--meter", default="4/4", choices=["4/4", "6/8", "auto"])
    args = ap.parse_args()

    missing = [f for f in NEEDED if not (HERE / f).exists()]
    if missing:
        sys.exit(f"missing next to this script: {', '.join(missing)}")
    video = Path(args.video).resolve()
    if not video.exists():
        sys.exit(f"no such file: {video}")

    lines_csv = video.with_name(video.stem + "_lines.csv")
    abc = Path(args.out).resolve() if args.out else video.with_suffix(".abc")

    run("extract_song_lines.py", video, "-o", lines_csv)
    with open(lines_csv, encoding="utf-8") as fh:
        if sum(1 for _ in fh) <= 1:
            sys.exit("no lyric lines were read from the Right Hand chapters, so there is nothing to "
                     f"transcribe; the frames in {lines_csv.name}'s chapters may look different from "
                     "what the scripts expect")
    extra = ["--key", args.key, "--meter", args.meter, "--title", args.title or video.stem, "--out", abc]
    if args.tempo:
        extra += ["--tempo", args.tempo]
    if args.to_key:
        extra += ["--to-key", args.to_key]
    if args.strict:
        extra.append("--strict")
    lengths = Path(args.lengths).resolve() if args.lengths else video.with_name(video.stem + "_lengths.csv")
    if lengths.exists():
        extra += ["--lengths", lengths]
        print(f"note lengths from {lengths.name}")
    run("piano_notes_from_audio.py", video, lines_csv, *extra)

    print(f"\nlines: {lines_csv}\nabc:   {abc}\nnotes: {abc.with_name(abc.stem + '_notes.csv')}")


if __name__ == "__main__":
    main()
