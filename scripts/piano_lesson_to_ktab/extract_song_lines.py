#!/usr/bin/env python3
"""
extract_song_lines.py

For every "Right Hand (Separately)" chapter of a piano-lesson video, find the
lines of the slow section (lyrics with piano note names in the top 30% of the
screen) and write one CSV row per line:

    chapter_no, chapter_title, chapter_time_interval, stanza_no, line_no,
    line, notes, line_timestamp_start_slow, line_timestamp_end_slow

Chapters are found with extract_chapter_titles.py (must sit next to this file).
Each Right Hand chapter teaches one stanza, so stanza_no is its ordinal.
Within a chapter, the slow section is the run of screens whose second text row
is note names; it ends where the "Fast" screens begin.

Usage:
    python extract_song_lines.py lesson.mp4 -o song_lines.csv

Requirements: same as extract_chapter_titles.py (ffmpeg, OpenCV, pytesseract).
"""

import argparse
import csv
import json
import re
import subprocess
import threading
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from difflib import SequenceMatcher

import cv2
import numpy as np
import pytesseract

from extract_chapter_titles import scan as scan_chapters, fmt_ts

TARGET_CHAPTER = "Right Hand (Separately)"
BAND = 0.30                 # top fraction of the screen holding lyrics + notes, if it can't be measured
NOTE_WL = "-c tessedit_char_whitelist=ABCDEFGb#"   # b = flat (Bb, Eb), # = sharp
NOTE_RE = re.compile(r"^([A-G][#b]?)+$")


# ----------------------------------------------------------------------------
# Video helpers
# ----------------------------------------------------------------------------

def probe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,r_frame_rate:format=duration",
         "-of", "json", path], capture_output=True, text=True, check=True).stdout
    j = json.loads(out)
    s = j["streams"][0]
    num, den = s["r_frame_rate"].split("/")
    return int(s["width"]), int(s["height"]), float(num) / float(den), float(j["format"]["duration"])


def one_frame(path, t, w, h):
    b = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", path, "-frames:v", "1",
                        "-vf", "format=gray", "-f", "rawvideo", "-"], capture_output=True).stdout
    return np.frombuffer(b, np.uint8).reshape(h, w) if len(b) == w * h else None


def band_height(path, start, end, w, h, samples=6):
    """Height of the lyrics band at the top of the screen in this chapter:
    rows mostly of the band's own background colour, down to where the
    keyboard starts. Videos differ (a light band with dark text, a dark band
    with white text, taller or shorter), so it is measured: the band
    seen in most of a few frames (the median), kept between 25% and 45% of
    the screen."""
    bottoms = []
    for t in np.linspace(start + 3, end - 1, samples):
        g = one_frame(path, t, w, h)
        if g is None:
            continue
        bg = int(np.median(g[:8]))
        frac = (np.abs(g.astype(int) - bg) < 25).mean(1)   # share of each row in the band colour
        run = 0
        for y in range(int(h * 0.1), h):
            run = run + 1 if frac[y] < 0.5 else 0
            if run >= 6:
                bottoms.append(y - 5)
                break
    # the median: a frame with a long, bold notes row can look like the
    # keyboard has started at that row, and a title card has no band at all
    bh = int(np.median(bottoms)) - 4 if bottoms else int(h * BAND)
    return int(min(max(bh, h * 0.25), h * 0.45)) // 2 * 2


def band_frames(path, start, end, w, h, fps, bh):
    """Yield (t, gray top band of height bh) for every frame between start and end."""
    cmd = ["ffmpeg", "-v", "error", "-ss", f"{start:.3f}", "-to", f"{end:.3f}",
           "-i", path, "-an", "-sn",
           "-vf", f"crop={w}:{bh}:0:0,format=gray", "-f", "rawvideo", "-"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, bufsize=w * bh * 8)
    size, i = w * bh, 0
    try:
        while True:
            buf = proc.stdout.read(size)
            if len(buf) < size:
                break
            yield start + i / fps, np.frombuffer(buf, np.uint8).reshape(bh, w)
            i += 1
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.stdout.close()
        proc.wait()


def segments(frames, diff_thresh=6.0, min_len=0.25):
    """
    Split a frame stream into screens of stable content. A new screen starts
    when a frame differs enough from the first frame of the current screen
    (comparing to the first frame, not the previous one, also catches fades).
    Returns [(t_start, t_end_exclusive, representative_frame), ...].
    """
    segs, ref, cur, last_t = [], None, None, None
    for t, band in frames:
        small = cv2.resize(band, (320, 54), interpolation=cv2.INTER_AREA).astype(np.int16)
        if ref is None or np.abs(small - ref).mean() > diff_thresh:
            if cur is not None:
                cur[1] = t
                segs.append(cur)
            ref, cur = small, [t, None, []]
        cur[2].append(band)
        last_t = t
    if cur is not None:
        cur[1] = last_t
        segs.append(cur)
    out = []
    for t0, t1, frs in segs:
        if t1 - t0 >= min_len:
            out.append((t0, t1, frs[len(frs) // 2].copy()))
    return out


# ----------------------------------------------------------------------------
# Reading a lyrics + notes screen
# ----------------------------------------------------------------------------

def binarize(gray):
    _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    return cv2.morphologyEx(bw, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))


def spans(profile, min_val, min_gap, min_len):
    """Runs where profile > min_val, joining gaps shorter than min_gap."""
    out, s, e, gap = [], None, None, 0
    for i, v in enumerate(profile):
        if v > min_val:
            if s is None:
                s = i
            e, gap = i, 0
        elif s is not None:
            gap += 1
            if gap >= min_gap:
                if e - s + 1 >= min_len:
                    out.append((s, e + 1))
                s = None
    if s is not None and e - s + 1 >= min_len:
        out.append((s, e + 1))
    return out


def text_rows(bw):
    return spans((bw > 0).sum(1), 3, 4, 12)


def columns(bw, a, b):
    """Word boxes in a text row, split on gaps wider than ~30% of row height."""
    return spans((bw[a:b] > 0).sum(0), 0, max(10, int((b - a) * 0.3)), 4)


def ocr(img, config, bg=255):
    img = cv2.copyMakeBorder(img, 30, 30, 30, 30, cv2.BORDER_CONSTANT, value=bg)
    return pytesseract.image_to_string(img, config=config).strip()


def read_note_token(gray, bw, a, b, x0, x1):
    """OCR one note token with several variants and vote."""
    x0, a, b = max(x0 - 6, 0), max(a - 8, 0), b + 8
    crops = {"bw": 255 - bw[a:b, x0:x1 + 6], "gray": gray[a:b, x0:x1 + 6]}
    single = (x1 - x0) < (b - a) * 0.9          # narrow: probably one letter
    cands = []
    for name, img in crops.items():
        bg = int(np.median(img))
        for scale in (1, 2):
            im = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC) if scale > 1 else img
            # A whitelist in line mode returns nothing for lone letters, so
            # narrow tokens also get word mode and an un-whitelisted read.
            configs = [f"--psm 7 {NOTE_WL}"]
            if single:
                configs += [f"--psm 8 {NOTE_WL}", "--psm 8", "--psm 13"]
            for cfg in configs:
                v = ocr(im, cfg, bg)
                if NOTE_RE.match(v):
                    cands.append(v)
    vote = "?"
    if cands:
        # Majority on the letters; OCR drops '#' far more often than it invents one,
        # so among candidates with those letters take the one with the most '#'.
        bare = lambda c: c.replace("#", "").replace("b", "")
        letters = Counter(bare(c) for c in cands).most_common(1)[0][0]
        vote = max((c for c in cands if bare(c) == letters), key=lambda c: c.count("#") + c.count("b"))
    return vote


def check_note_token(vote, gray, bw, a, b, x0, x1):
    """The voted reading must have one character per shape in the token
    ('F#F#' has 4). If it doesn't (a bold '#F' read as 'E', say), read the
    token shape by shape instead."""
    glyphs = token_glyphs(bw, a, b, x0, x1)
    if vote != "?" and len(vote) == len(glyphs):
        return vote
    chars = []
    for gx, gw, shape in glyphs:
        crop = 255 - bw[max(a - 6, 0):b + 6, max(x0 + gx - 3, 0):x0 + gx + gw + 3]
        chars.append(classify_glyph(shape, crop) or "?")
    redo = "".join(chars)
    return redo if NOTE_RE.match(redo) else vote


# ----------------------------------------------------------------------------
# Checking a note token glyph by glyph
# ----------------------------------------------------------------------------

GLYPHS = {}                       # char -> list of 24x32 shapes seen in this video's font
GLYPH_LOCK = threading.Lock()


def token_glyphs(bw, a, b, x0, x1):
    """The separate shapes of a note token, left to right: each letter and each
    '#' is one (tiny specks ignored). Returns [(x, w, shape 24x32 0/1)]."""
    tok = (bw[a:b, x0:x1] > 0).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(tok)
    if n <= 1:
        return []
    big = max(st[1:, 4])
    out = []
    for i in range(1, n):
        x, y, w, h, area = st[i]
        if area < 0.15 * big:
            continue
        shape = cv2.resize(((lab[y:y + h, x:x + w] == i) * 255).astype(np.uint8), (24, 32),
                           interpolation=cv2.INTER_AREA) > 127
        out.append((x, w, shape))
    return sorted(out, key=lambda g: g[0])


def remember_glyphs(token, glyphs):
    """A token whose reading has as many characters as it has shapes labels
    each shape: examples of this video's font."""
    with GLYPH_LOCK:
        for ch, (_, _, shape) in zip(token, glyphs):
            ex = GLYPHS.setdefault(ch, [])
            if len(ex) < 40:
                ex.append(shape)


def classify_glyph(shape, crop):
    """One shape -> 'A'..'G' or '#': the closest examples of this video's font
    (overlap of the shapes), else Tesseract on the glyph alone."""
    with GLYPH_LOCK:
        ex = {ch: list(v) for ch, v in GLYPHS.items()}
    best, best_ch = 0.0, None
    for ch, shapes in ex.items():
        for e in shapes:
            iou = np.count_nonzero(shape & e) / max(1, np.count_nonzero(shape | e))
            if iou > best:
                best, best_ch = iou, ch
    if best >= 0.75:
        return best_ch
    for cfg in (f"--psm 10 {NOTE_WL}", "--psm 10"):
        v = "".join(c if c in "#b" else c.upper() for c in re.sub(r"[^A-Ga-g#]", "", ocr(crop, cfg)))
        if len(v) == 1:
            return v
    return best_ch


def clean_word(w):
    w = re.sub(r"[^A-Za-z']", "", w)
    if w.upper() in {"QO", "OO", "O0", "Q", "0"}:
        w = "O"
    return w


def read_lyric_row(gray, bw, a, b, cols):
    """Whole-row OCR (best for words); fall back to per-word OCR if counts differ."""
    crop = 255 - bw[max(a - 8, 0):b + 8]
    words = [clean_word(w) for w in ocr(crop, "--psm 7").split()]
    words = [w for w in words if w]
    if len(words) == len(cols):
        return words
    out = []
    for x0, x1 in cols:
        w = clean_word(ocr(255 - bw[max(a - 8, 0):b + 8, max(x0 - 6, 0):x1 + 6], "--psm 8"))
        out.append(w or "O")       # an unreadable lone glyph here is the round "O"
    return out


def dark_text(gray):
    """The band with dark text on a light background, whichever way the video
    draws it (some use dark text on a light band, others white text on a dark
    band): a dark background is inverted."""
    return 255 - gray if np.median(gray) < 128 else gray


def quick_kind(gray):
    """Cheap first pass (one OCR call): 'black', 'other', 'fast' or 'candidate'."""
    if gray.std() < 8:                          # one flat colour: no text (title card, fade)
        return "black"
    gray = dark_text(gray)
    bw = binarize(gray)
    rows = text_rows(bw)
    if len(rows) < 2:
        return "other"
    a2, b2 = rows[1]
    second = ocr(255 - bw[max(a2 - 8, 0):b2 + 8], "--psm 7")
    # "Fast" (allowing one OCR slip: "Fact", "Fas")
    t = re.sub(r"[^a-z]", "", second.lower())
    return "fast" if t and SequenceMatcher(None, t, "fast").ratio() >= 0.75 else "candidate"


def read_notes_screen(gray):
    """Full read of a lyrics + notes screen: ('notes'|'other', words, notes)."""
    gray = dark_text(gray)
    bw = binarize(gray)
    (a1, b1), (a2, b2) = text_rows(bw)[:2]
    note_cols = columns(bw, a2, b2)
    notes = [read_note_token(gray, bw, a2, b2, x0, x1) for x0, x1 in note_cols]
    # tokens read with one character per shape teach the font; then any token
    # whose reading doesn't match its shapes is read again shape by shape
    for tok, (x0, x1) in zip(notes, note_cols):
        g = token_glyphs(bw, a2, b2, x0, x1)
        if tok != "?" and len(tok) == len(g):
            remember_glyphs(tok, g)
    notes = [check_note_token(tok, gray, bw, a2, b2, x0, x1) for tok, (x0, x1) in zip(notes, note_cols)]
    if sum(n != "?" for n in notes) < max(1, len(notes) * 0.6):
        return "other", [], []
    words = read_lyric_row(gray, bw, a1, b1, columns(bw, a1, b1))
    return "notes", words, notes


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------

def is_target(title):
    # Must say "Right" (Left Hand titles are otherwise nearly identical);
    # the fuzzy match tolerates small OCR slips in the rest of the title.
    t = title.lower()
    return re.search(r"\bright\s*hand", t) is not None and \
        SequenceMatcher(None, t, TARGET_CHAPTER.lower()).ratio() >= 0.8


def process_chapter(path, ch, w, h, fps):
    bh = band_height(path, ch["start"], ch["end"], w, h)
    segs = segments(band_frames(path, ch["start"], ch["end"], w, h, fps, bh))
    with ThreadPoolExecutor() as pool:
        kinds = list(pool.map(lambda s: quick_kind(s[2]), segs))
        # The slow section ends where the first "Fast" screen appears.
        n_slow = kinds.index("fast") if "fast" in kinds else len(kinds)
        slow = [s for s, k in zip(segs[:n_slow], kinds[:n_slow]) if k == "candidate"]
        reads = list(pool.map(lambda s: read_notes_screen(s[2]), slow))
    lines = []
    for (t0, t1, _), (kind, words, notes) in zip(slow, reads):
        if kind != "notes":
            continue
        line, note_str = " ".join(words), " ".join(notes)
        if lines and lines[-1]["line"] == line and lines[-1]["notes"] == note_str \
                and t0 - lines[-1]["end"] < 0.1:
            lines[-1]["end"] = t1                   # same screen split by a flicker
            continue
        lines.append({"line": line, "notes": note_str, "start": t0, "end": t1})
    return lines


def main():
    ap = argparse.ArgumentParser(description="Extract slow-section lines (lyrics + notes) of Right Hand chapters.")
    ap.add_argument("video")
    ap.add_argument("-o", "--out", default="song_lines.csv")
    args = ap.parse_args()

    w, h, fps, duration = probe(args.video)
    chapters = scan_chapters(args.video)
    for i, ch in enumerate(chapters):
        ch["no"] = i + 1
        ch["end"] = chapters[i + 1]["start"] if i + 1 < len(chapters) else duration

    targets = [c for c in chapters if is_target(c["title"])]
    if not targets:
        sys.exit(f"No '{TARGET_CHAPTER}' chapters found.")

    rows = []
    for stanza_no, ch in enumerate(targets, 1):
        interval = f"{fmt_ts(ch['start'])}-{fmt_ts(ch['end'])}"
        lines = process_chapter(args.video, ch, w, h, fps)
        print(f"Chapter {ch['no']} ({interval}) {ch['title']}: {len(lines)} lines", file=sys.stderr)
        for line_no, ln in enumerate(lines, 1):
            rows.append([ch["no"], TARGET_CHAPTER, interval, stanza_no, line_no,
                         ln["line"], ln["notes"], f"{ln['start']:.2f}", f"{ln['end']:.2f}"])

    with open(args.out, "w", newline="", encoding="utf-8") as fh:
        wr = csv.writer(fh)
        wr.writerow(["chapter_no", "chapter_title", "chapter_time_interval", "stanza_no", "line_no",
                     "line", "notes", "line_timestamp_start_slow", "line_timestamp_end_slow"])
        wr.writerows(rows)
    print(f"Wrote {len(rows)} lines to {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
