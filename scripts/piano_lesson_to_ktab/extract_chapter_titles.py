#!/usr/bin/env python3
"""
extract_chapter_titles.py

Find section-title cards (light text on a black screen) in a video and
print their timestamps and OCR'd titles.

Usage:
    python extract_chapter_titles.py lesson.mp4
    python extract_chapter_titles.py lesson.mp4 --interval 0.5 --csv chapters.csv

Requirements:
    pip install opencv-python pytesseract numpy
    + ffmpeg/ffprobe on PATH (used for fast decoding)
    + the Tesseract binary (apt install tesseract-ocr / brew install tesseract /
      Windows installer from https://github.com/UB-Mannheim/tesseract/wiki)

Why it's fast:
    * ffmpeg decodes with -skip_frame noref: B-frames (often ~75% of a video)
      aren't decoded at all, and deblocking is skipped. Neither matters for
      spotting a black title card.
    * ffmpeg's fps filter hands back only one grayscale frame per interval.
    * Only one frame per title card is OCR'd, and OCR runs in parallel.
"""

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from difflib import SequenceMatcher

import cv2
import numpy as np
import pytesseract


# ----------------------------------------------------------------------------
# Detection
# ----------------------------------------------------------------------------

def is_title_frame(gray, dark_level=40, min_dark_frac=0.90,
                   bright_level=150, min_bright_frac=0.002, max_bright_frac=0.10):
    """
    A title card is almost entirely black with a small amount of bright text.
    `gray` is a single-channel frame; it's downscaled for speed.
    """
    small = cv2.resize(gray, (320, 180), interpolation=cv2.INTER_AREA)
    total = small.size
    dark_frac = np.count_nonzero(small < dark_level) / total
    bright_frac = np.count_nonzero(small > bright_level) / total
    return (dark_frac >= min_dark_frac
            and min_bright_frac <= bright_frac <= max_bright_frac)


def text_mask(gray, bright_level=150):
    """Low-res mask of the bright (text) pixels, used to tell titles apart."""
    return cv2.resize(gray, (320, 180), interpolation=cv2.INTER_AREA) > bright_level


def same_text(mask_a, mask_b, min_overlap=0.6):
    """
    True if two title frames likely show the same text. Measured as the share
    of the smaller mask covered by the larger, so fade-ins (text getting
    brighter / more pixels) still count as the same. Animated titles (zoom,
    slide) may still split; those pieces are re-merged after OCR.
    """
    smaller = min(np.count_nonzero(mask_a), np.count_nonzero(mask_b))
    return smaller == 0 or np.count_nonzero(mask_a & mask_b) / smaller >= min_overlap


def similar_titles(a, b, min_ratio=0.8):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio() >= min_ratio


# ----------------------------------------------------------------------------
# OCR
# ----------------------------------------------------------------------------

def ocr_title(gray):
    """Crop to the text, make it black-on-white, upscale, and OCR it."""
    _, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Crop to the bounding box of the bright pixels (trim a small margin
    # first to ignore rounded-corner borders / UI chrome).
    h, w = mask.shape
    m = int(min(h, w) * 0.03)
    pts = cv2.findNonZero(mask[m:h - m, m:w - m])
    if pts is None:
        return ""
    x, y, bw, bh = cv2.boundingRect(pts)
    pad = 20
    x0, y0 = max(x + m - pad, 0), max(y + m - pad, 0)
    x1, y1 = min(x + m + bw + pad, w), min(y + m + bh + pad, h)
    crop = gray[y0:y1, x0:x1]

    # Upscale small text, then invert to dark text on white (Tesseract prefers it).
    if crop.shape[0] < 200:
        crop = cv2.resize(crop, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    _, bw_img = cv2.threshold(crop, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    text = pytesseract.image_to_string(bw_img, config="--psm 6")
    text = " ".join(text.split())                  # collapse newlines / spaces
    text = re.sub(r"^[^\w(]+|[^\w)]+$", "", text)  # strip stray edge punctuation
    return text


# ----------------------------------------------------------------------------
# Frame reading
# ----------------------------------------------------------------------------

def video_size(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "json", path],
        capture_output=True, text=True, check=True).stdout
    s = json.loads(out)["streams"][0]
    return int(s["width"]), int(s["height"])


def frames_ffmpeg(path, interval):
    """Yield (time_seconds, gray_frame) once per `interval`, decoded by ffmpeg."""
    w, h = video_size(path)
    cmd = ["ffmpeg", "-v", "error", "-threads", "0",
           "-skip_frame", "noref", "-skip_loop_filter", "all",
           "-i", path, "-an", "-sn",
           "-vf", f"fps=1/{interval},format=gray",
           "-f", "rawvideo", "-"]
    size = w * h
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, bufsize=size * 4)
    try:
        i = 0
        while True:
            buf = proc.stdout.read(size)
            if len(buf) < size:
                break
            yield i * interval, np.frombuffer(buf, np.uint8).reshape(h, w)
            i += 1
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.stdout.close()
        proc.wait()


def frames_opencv(path, interval):
    """Fallback when ffmpeg isn't installed (slower: decodes every frame)."""
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        sys.exit(f"Could not open video: {path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    step = max(1, int(round(fps * interval)))
    idx = 0
    while cap.grab():
        if idx % step == 0:
            ok, frame = cap.retrieve()
            if not ok:
                break
            yield idx / fps, cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        idx += 1
    cap.release()


# ----------------------------------------------------------------------------
# Main scan
# ----------------------------------------------------------------------------

def fmt_ts(seconds):
    seconds = int(round(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def scan(path, interval=1.0, verbose=False):
    if not os.path.exists(path):
        sys.exit(f"No such file: {path}")
    have_ffmpeg = shutil.which("ffmpeg") and shutil.which("ffprobe")
    if not have_ffmpeg:
        print("ffmpeg not found, falling back to slower OpenCV decoding", file=sys.stderr)
    frames = frames_ffmpeg(path, interval) if have_ffmpeg else frames_opencv(path, interval)

    # Runs of consecutive title frames: [start_t, end_t, [frames]]
    # A run also ends when the text changes, so two titles that follow each
    # other with a hard cut (no lesson footage between) are kept separate.
    runs, current, prev_mask = [], None, None
    for t, gray in frames:
        if is_title_frame(gray):
            mask = text_mask(gray)
            if current is not None and not same_text(mask, prev_mask):
                runs.append(current)
                current = None
            if current is None:
                current = [t, t, []]
            current[1] = t
            current[2].append(gray)
            prev_mask = mask
        elif current is not None:
            runs.append(current)
            current = None
        if verbose and int(t) % 60 == 0 and t == int(t):
            print(f"  scanned {fmt_ts(t)}", file=sys.stderr)
    if current is not None:
        runs.append(current)

    # OCR the middle frame of each run (fully faded in), in parallel.
    picks = [run_frames[len(run_frames) // 2] for _, _, run_frames in runs]
    with ThreadPoolExecutor(max_workers=os.cpu_count() or 2) as pool:
        titles = list(pool.map(ocr_title, picks))

    # Merge adjacent pieces of the same title (animations, brief flashes).
    # The title read from the longest piece wins.
    chapters = []
    for (start, end, run_frames), title in zip(runs, titles):
        title = title or "(unreadable)"
        n = len(run_frames)
        prev = chapters[-1] if chapters else None
        if prev and start - prev["end"] <= 2 * interval and similar_titles(prev["title"], title):
            prev["end"] = end
            if n >= prev["best_n"]:
                prev["title"], prev["best_n"] = title, n
            continue
        chapters.append({"start": start, "end": end, "title": title, "best_n": n})
    return chapters


def main():
    ap = argparse.ArgumentParser(description="Extract section-title cards (white text on black) with timestamps.")
    ap.add_argument("video", help="input video file")
    ap.add_argument("--interval", type=float, default=1.0, help="sampling interval in seconds (default 1.0)")
    ap.add_argument("--csv", help="also write results to this CSV file")
    ap.add_argument("-v", "--verbose", action="store_true", help="show scan progress")
    args = ap.parse_args()

    chapters = scan(args.video, interval=args.interval, verbose=args.verbose)

    if not chapters:
        print("No title cards found.")
        return

    for c in chapters:
        print(f"{fmt_ts(c['start'])}  {c['title']}")

    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["start_seconds", "start", "end_seconds", "title"])
            for c in chapters:
                w.writerow([f"{c['start']:.2f}", fmt_ts(c["start"]), f"{c['end']:.2f}", c["title"]])
        print(f"\nWrote {args.csv}", file=sys.stderr)


if __name__ == "__main__":
    main()
