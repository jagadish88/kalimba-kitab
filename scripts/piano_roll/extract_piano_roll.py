#!/usr/bin/env python3
"""Melody notes from a falling-notes piano video (Synthesia style, e.g. Arup Paul's tutorials).

    python scripts/piano_roll/extract_piano_roll.py data/raw_data/video/rs000864_src000397.mp4

Writes <out-dir>/<name>_notes.csv (default data/intermediate_data/piano_roll/<song_id>/):
one row per melody note: onset (s, when its bar reaches the keyboard), duration (s), midi, key name.

How it reads the video (1280x720 layout of these tutorials; change the constants if needed)
  * Keyboard: a full 88-key piano across the width (A0..C8, 52 white keys); the black keys are
    found as dark runs on a keyboard row, so every key has an x position.
  * Bars fall towards the keyboard at a constant speed, measured from the video.
  * The melody (right hand) is drawn in cyan/blue, the accompaniment in green: only bars whose
    hue is 175-225 degrees are read, so chords and arpeggios of the left hand are ignored.
  * A note is counted when the BOTTOM EDGE of its bar crosses a scan line at --scan (fraction
    of the falling area, default 0.6). Two notes on the same key are two bars with a gap, so
    each has its own bottom edge and is never merged into one long note. Edges are tracked from
    frame to frame, because duplicate frames make a bar jump further than one frame's fall.
  * Duration = bar length / falling speed. If several melody keys start together (a chord in
    the right hand), only the highest is kept.
"""
import argparse
import csv
import os
import subprocess

import numpy as np

W, H = 1280, 720
FALL_TOP, FALL_BOTTOM = 0, 490          # falling area
KEY_ROW = 545                           # a row through the black keys
NAMES = 'C C# D D# E F F# G G# A A# B'.split()


def frames(path, y0, y1, step=1):
    """yield (frame index, RGB array of rows y0..y1)"""
    h = y1 - y0
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', path, '-vf', f'crop={W}:{h}:0:{y0}',
                          '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], stdout=subprocess.PIPE)
    n, size = 0, W * h * 3
    while True:
        buf = p.stdout.read(size)
        if len(buf) < size:
            break
        if n % step == 0:
            yield n, np.frombuffer(buf, np.uint8).reshape(h, W, 3)
        n += 1


def one_frame(path, t, y0=0, y1=H):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', str(t), '-i', path, '-frames:v', '1', '-vf',
                          f'crop={W}:{y1 - y0}:0:{y0}', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                         capture_output=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(y1 - y0, W, 3).astype(int)


def key_centers(path):
    """x centre of every key, midi 21..108"""
    row = one_frame(path, 2.0, KEY_ROW, KEY_ROW + 2)[0].mean(1)
    dark = row < 100
    blacks, x = [], 0
    while x < W:
        if dark[x]:
            s = x
            while x < W and dark[x]:
                x += 1
            blacks.append((s + x - 1) / 2)
        else:
            x += 1
    ww = W / 52
    whites = [m for m in range(21, 109) if NAMES[m % 12].find('#') < 0]
    centers = {m: (i + 0.5) * ww for i, m in enumerate(whites)}
    black_midis = [m for m in range(21, 109) if '#' in NAMES[m % 12]]
    if len(blacks) != len(black_midis):
        raise SystemExit(f'found {len(blacks)} black keys, expected 36: check KEY_ROW')
    centers.update(dict(zip(black_midis, blacks)))
    return centers


def melody_mask(rgb):
    """True where a pixel belongs to a melody (cyan/blue) bar"""
    r, g, b = rgb[..., 0].astype(int), rgb[..., 1].astype(int), rgb[..., 2].astype(int)
    mx, mn = np.maximum(np.maximum(r, g), b), np.minimum(np.minimum(r, g), b)
    sat = (mx - mn) / np.maximum(mx, 1)
    hue = np.zeros_like(mx, dtype=float)
    d = np.maximum(mx - mn, 1)
    hue = np.where(mx == b, 240 + 60 * (r - g) / d, np.where(mx == g, 120 + 60 * (b - r) / d, (60 * (g - b) / d) % 360))
    return (hue >= 175) & (hue <= 225) & (sat > 0.45) & (mx > 90)


def fall_speed(path, t=30.0, gap=15):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', str(t), '-i', path, '-vf',
                          f"select='eq(n\\,0)+eq(n\\,{gap})',crop={W}:{FALL_BOTTOM - 20}:0:20", '-vsync', '0',
                          '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True).stdout
    h = FALL_BOTTOM - 20
    a, b = [np.frombuffer(raw[i * W * h * 3:(i + 1) * W * h * 3], np.uint8).reshape(h, W, 3).mean(2) for i in (0, 1)]
    s = min(range(1, 400), key=lambda k: np.abs(a[:h - k] - b[k:]).mean())
    return s / gap


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('video')
    ap.add_argument('--out-dir')
    ap.add_argument('--scan', type=float, default=0.6, help='scan line, as a fraction of the falling area')
    a = ap.parse_args()
    name = os.path.splitext(os.path.basename(a.video))[0]
    out = a.out_dir or f"data/intermediate_data/piano_roll/{name.split('_')[0]}"
    os.makedirs(out, exist_ok=True)
    fps = eval(subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v', '-show_entries', 'stream=r_frame_rate',
                               '-of', 'csv=p=0', a.video], capture_output=True, text=True).stdout.strip())
    centers = key_centers(a.video)
    speed = fall_speed(a.video)                                        # px per frame
    y_scan = int(FALL_TOP + a.scan * (FALL_BOTTOM - FALL_TOP))
    lead = (FALL_BOTTOM - y_scan) / speed / fps                         # seconds from scan line to keyboard
    xs = {m: int(round(c)) for m, c in centers.items()}
    print(f'{len(centers)} keys, bars fall {speed:.2f} px/frame, scan line y={y_scan}')
    notes, last = [], {}
    # Track every bar's bottom edge from frame to frame, per key, and count a note when its edge
    # passes the scan line. Some frames are duplicates, so an edge can jump well over `speed`
    # pixels between two frames; tracking (not a fixed window) never misses it.
    prev = {m: [] for m in xs}                                      # bottom edges (y) in the last frame
    span = (FALL_BOTTOM - FALL_TOP)
    for n, fr in frames(a.video, FALL_TOP, FALL_BOTTOM):
        mask = melody_mask(fr)
        for m, x in xs.items():
            col = mask[:, max(0, x - 2):x + 3].mean(1) > 0.6
            edges = list(np.flatnonzero(col[:-1] & ~col[1:]))       # bar above, background below
            for e in edges:
                if e < y_scan:
                    continue
                # the same edge one frame earlier was 0..30 px higher; it crossed if it was above the line
                before = [p for p in prev[m] if 0 <= e - p <= 30]
                if before and max(before) < y_scan:
                    top = e
                    while top > 0 and col[top - 1]:
                        top -= 1
                    length = (e - top + 1) / speed / fps
                    t = n / fps + lead - (e - y_scan) / speed / fps   # when the edge was exactly on the line
                    notes.append((t, length, m))
            prev[m] = edges
    notes.sort()
    melody = []
    for t, d, m in notes:                                           # chord in the melody colour: keep the top note
        if melody and abs(t - melody[-1][0]) < 0.04:
            if m > melody[-1][2]:
                melody[-1] = (t, d, m)
            continue
        melody.append((t, d, m))
    path = os.path.join(out, f'{name}_notes.csv')
    with open(path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['onset', 'duration', 'midi', 'name'])
        for t, d, m in melody:
            w.writerow([f'{t:.3f}', f'{d:.3f}', m, f'{NAMES[m % 12]}{m // 12 - 1}'])
    print(f'{len(melody)} melody notes -> {path}')


if __name__ == '__main__':
    main()
