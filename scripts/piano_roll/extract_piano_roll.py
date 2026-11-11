#!/usr/bin/env python3
"""Melody notes from a falling-notes piano video (Synthesia style, e.g. Arup Paul's tutorials).

    python scripts/piano_roll/extract_piano_roll.py data/raw_data/video/rs000864_src000397.mp4

Writes <out-dir>/<name>_notes.csv (default data/intermediate_data/piano_roll/<song_id>/):
one row per melody note: onset (s, when its bar reaches the keyboard), duration (s), midi, key name.

How it reads the video
  * Keyboard: found automatically. The row with the most black keys (dark runs) is the keyboard;
    black keys come in groups of 2 (C# D#) and 3 (F# G# A#), which fixes the octave pattern and
    the white-key width; every key gets an x position. The C# nearest the middle of the screen
    is taken as C#4 (true for a full 88-key keyboard; for a cropped one the octave may be off,
    which only shifts every note by 12). The falling area ends just above the keyboard.
  * Bars fall towards the keyboard at a constant speed, measured from the video.
  * The melody (right hand) is drawn in cyan/blue, the accompaniment in green or orange: only bars
    whose hue is 175-245 degrees are read, so chords and arpeggios of the left hand are ignored.
  * A note is counted when the BOTTOM EDGE of its bar crosses a scan line at --scan (fraction
    of the falling area, default 0.6). Two notes on the same key are two bars with a gap, so
    each has its own bottom edge and is never merged into one long note. Edges are tracked from
    frame to frame, because duplicate frames make a bar jump further than one frame's fall.
  * Only a band of rows around the scan line is decoded and examined (+-BAND px), and the hue is
    worked out only for bright, saturated pixels: about 20x faster than examining the whole falling
    area. A note ends when its bar's TOP edge crosses the scan line, so duration = the time between
    the two crossings (at the bars' constant speed, the same as bar length / speed, and long bars
    are not cut off by the top of the screen). If several melody keys start together (a chord in the
    right hand), only the highest is kept.
"""
import argparse
import csv
import os
import subprocess

import numpy as np

W, H = 1280, 720
BAND = 40                               # rows read above and below the scan line
FALL_TOP = 0
FALL_BOTTOM = 490                       # set by find_layout()
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


def dark_runs(row, lo=8, hi=24):
    """centres of dark runs lo..hi px wide (black keys) in a grey row"""
    dark, runs, x = row < 100, [], 0
    while x < len(row):
        if dark[x]:
            s = x
            while x < len(row) and dark[x]:
                x += 1
            if lo <= x - s <= hi:
                runs.append((s + x - 1) / 2)
        else:
            x += 1
    return runs


BLACK_OFF = {1: 0.0, 3: 1.02, 6: 3.0, 8: 4.02, 10: 5.0}    # black keys, in white-key widths from C#


def keyboard_in(g):
    """(black-key x centres, top y of the keys) in a grey frame, or ([], 0) when there's no keyboard"""
    counts = [len(dark_runs(g[y])) for y in range(H // 2, H)]
    n = max(counts)
    if n < 10:
        return [], 0
    # the black-key band: the longest run of rows with nearly as many dark runs; read its middle
    bands, y = [], 0
    while y < len(counts):
        if counts[y] >= 0.8 * n:
            s0 = y
            while y < len(counts) and counts[y] >= 0.8 * n:
                y += 1
            bands.append((s0, y))
        else:
            y += 1
    b0, b1 = max(bands, key=lambda b: b[1] - b[0])
    if b1 - b0 < 25:                                                # text on a title card, not keys
        return [], 0
    runs = dark_runs(g[H // 2 + (b0 + b1) // 2])
    # keep the longest chain of evenly spaced runs (drops dark runs in overlays, e.g. a photo)
    sp = np.diff(runs)
    med = np.median(sp)
    chains, cur = [], [runs[0]]
    for x, d in zip(runs[1:], sp):
        if 0.6 * med <= d <= 2.2 * med:
            cur.append(x)
        else:
            chains.append(cur); cur = [x]
    chains.append(cur)
    top = (b0 + b1) // 2                                            # keys' top: climb while most keys still show
    while top > 0 and counts[top - 1] >= 0.5 * n:
        top -= 1
    return max(chains, key=len), H // 2 + top


def find_layout(path):
    """(key x centres {midi: x}, white-key width, keyboard top y) from frames showing the keyboard"""
    blacks, top = max((keyboard_in(one_frame(path, t).mean(2)) for t in (1.0, 3.0, 5.0, 7.0, 10.0, 20.0, 30.0, 45.0, 60.0)),   # early frames: no key lit yet
                      key=lambda r: len(r[0]))
    if len(blacks) < 10:
        raise SystemExit('no keyboard found')
    # groups: gaps inside a group are ~1.15 white keys, between groups ~1.75
    sp = np.diff(blacks)
    thr = (sp.min() + sp.max()) / 2
    groups, cur = [], [blacks[0]]
    for x, d in zip(blacks[1:], sp):
        if d > thr:
            groups.append(cur); cur = []
        cur.append(x)
    groups.append(cur)
    pairs = [gr[0] for gr in groups if len(gr) == 2]
    trip = [gr[0] for gr in groups if len(gr) == 3]
    octave = np.median(np.diff(pairs)) if len(pairs) > 1 else np.median(np.diff(trip))
    ww = octave / 7
    # every black key sits on a white-key boundary: x = c0 + ww * u, u in white-key widths from C#4.
    # Label each black key, fit c0 and ww by least squares, then place the white keys on that grid.
    c_sharp = min(pairs, key=lambda x: abs(x - W / 2))              # taken as C#4 (midi 61)
    us, labels = [], []
    for x in blacks:
        u = (x - c_sharp) / ww
        pc, o = min(((q, round((u - BLACK_OFF[q]) / 7)) for q in BLACK_OFF),   # nearest black-key slot
                    key=lambda t: abs(u - BLACK_OFF[t[0]] - 7 * t[1]))
        us.append(BLACK_OFF[pc] + 7 * o)
        labels.append(60 + pc + 12 * o)
    ww, c0 = np.polyfit(us, blacks, 1)
    centers = dict(zip(labels, blacks))                            # black keys: where they are measured
    for m in range(21, 109):
        pc = m % 12
        if pc in BLACK_OFF:
            continue
        wi = [0, 2, 4, 5, 7, 9, 11].index(pc)                        # white index from C
        x = c0 + ww * (wi - 0.5 + 7 * ((m - pc - 60) // 12))        # C's centre is half a key left of C#
        if blacks[0] - ww <= x <= blacks[-1] + ww:
            centers[m] = x
    return centers, ww, top


def melody_mask(rgb):
    """True where a pixel belongs to a melody (cyan/blue) bar: hue 175-245 degrees, saturation > 0.45,
    brightness > 90. The hue is worked out only for pixels that pass the cheap tests."""
    mx = rgb.max(axis=2)
    mn = rgb.min(axis=2)
    ok = (mx > 90) & ((mx.astype(np.int16) - mn) * 100 > 45 * mx.astype(np.int16))
    out = np.zeros(mx.shape, bool)
    if not ok.any():
        return out
    px = rgb[ok].astype(np.int32)
    r, g, b = px[:, 0], px[:, 1], px[:, 2]
    M, m = mx[ok].astype(np.int32), mn[ok].astype(np.int32)
    d = np.maximum(M - m, 1)
    hue = np.where(M == b, 240 + 60 * (r - g) / d, np.where(M == g, 120 + 60 * (b - r) / d, (60 * (g - b) / d) % 360))
    out[ok] = (hue >= 175) & (hue <= 245)
    return out


def bar_centres(mask, bridge=10, min_width=7):
    """x centre of the horizontal bar run through each pixel (inf off bars). Gaps up to `bridge` px
    inside a row are closed first, so a letter label printed on a bar doesn't split it; runs narrower
    than `min_width` (the thin strip some videos draw between two bars on one key) are ignored."""
    h, w = mask.shape
    c = np.concatenate([np.zeros((h, 1), int), np.cumsum(mask, 1)], 1)
    xs = np.arange(w)
    left = c[:, xs + 1] - c[:, np.maximum(xs - bridge, 0)] > 0               # bar within bridge px to the left
    right = c[:, np.minimum(xs + bridge + 1, w)] - c[:, xs] > 0             # ... and to the right
    m = mask | (left & right)
    start = np.where(m & ~np.pad(m, ((0, 0), (1, 0)))[:, :-1], xs, 0)
    start = np.maximum.accumulate(start, 1)
    end = np.where(m & ~np.pad(m, ((0, 0), (0, 1)))[:, 1:], xs, w)
    end = np.minimum.accumulate(end[:, ::-1], 1)[:, ::-1]
    return np.where(m & (end - start + 1 >= min_width), (start + end) / 2, np.inf)


def bars_mask(rgb):
    """True on any falling bar: saturated and bright"""
    r, g, b = (rgb[..., i].astype(int) for i in range(3))
    mx, mn = np.maximum(np.maximum(r, g), b), np.minimum(np.minimum(r, g), b)
    return ((mx - mn) / np.maximum(mx, 1) > 0.45) & (mx > 90)


def fall_speed(path, gap=15):
    """px per frame: median of the shift between frames `gap` apart at several moments (pauses give 0)"""
    v = [fall_shift(path, t, gap) for t in (20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0)]
    v = [x for x in v if x > 1]
    return float(np.median(v))


def fall_shift(path, t, gap):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', str(t), '-i', path, '-vf',
                          f"select='eq(n\\,0)+eq(n\\,{gap})',crop={W}:{FALL_BOTTOM - 20}:0:20", '-vsync', '0',
                          '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True).stdout
    h = FALL_BOTTOM - 20
    # compare only bar pixels (melody or green accompaniment), so static overlays don't pull the shift to 0
    a, b = [bars_mask(np.frombuffer(raw[i * W * h * 3:(i + 1) * W * h * 3], np.uint8).reshape(h, W, 3)).astype(float)
            for i in (0, 1)]
    if a.sum() < 500:
        return 0
    s = max(range(1, 400), key=lambda k: (a[:h - k] * b[k:]).sum())
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
    global FALL_BOTTOM
    centers, ww, kb_top = find_layout(a.video)
    FALL_BOTTOM = (kb_top - 25) // 2 * 2                          # even: ffmpeg crops to even heights
    hw = max(2, int(ww * 0.3))                                     # half-width of the column read per key
    speed = fall_speed(a.video)                                        # px per frame
    y_scan = int(FALL_TOP + a.scan * (FALL_BOTTOM - FALL_TOP))
    lead = (FALL_BOTTOM - y_scan) / speed / fps                         # seconds from scan line to keyboard
    xs = {m: int(round(c)) for m, c in centers.items()}
    print(f'{len(centers)} keys ({NAMES[min(centers) % 12]}{min(centers) // 12 - 1}-{NAMES[max(centers) % 12]}{max(centers) // 12 - 1}), keyboard top y={kb_top}, bars fall {speed:.2f} px/frame, scan line y={y_scan}')
    notes = []
    # Only a band of rows around the scan line is read (an edge moves at most ~30 px between frames).
    # A note starts when its bar's BOTTOM edge crosses the scan line and ends when its TOP edge does,
    # so the bar's length is never measured in one frame and long bars are not cut by the screen.
    b0 = max(FALL_TOP, (y_scan - BAND) // 2 * 2)
    b1 = min(FALL_BOTTOM, (y_scan + BAND) // 2 * 2)
    ys = y_scan - b0
    prev_bot = {m: [] for m in xs}
    prev_top = {m: [] for m in xs}
    open_note = {}                                                  # key -> index in notes of the sounding note
    started = {}                                                    # key -> frame of its last note start
    minw = max(4, int(ww / 3))

    def crossing(edges, prev):
        """edges (y in the band) that crossed the scan line since the last frame"""
        out = []
        for e in edges:
            if e < ys:
                continue
            before = [p for p in prev if 0 <= e - p <= 30]
            if before and max(before) < ys:
                out.append(e)
        return out

    def at_line(n, e):
        return n / fps + lead - (e - ys) / speed / fps              # when the edge was exactly on the line

    n = -1
    for n, fr in frames(a.video, b0, b1):
        cen = bar_centres(melody_mask(fr), min_width=minw)
        for m, x in xs.items():
            col = np.abs(cen[:, x] - x) < hw                        # a bar centred on this key (not a wide neighbour)
            bots = list(np.flatnonzero(col[:-1] & ~col[1:]))        # bar above, background below
            tops = list(np.flatnonzero(~col[:-1] & col[1:]) + 1)    # background above, bar below
            for e in crossing(tops, prev_top[m]):
                k = open_note.get(m)
                # a "top edge" just after the start is a gap inside the bar (a printed label): ignore it
                if k is not None and at_line(n, e) - notes[k][0] >= 0.08:
                    del open_note[m]
                    notes[k] = (notes[k][0], at_line(n, e) - notes[k][0], m)
            for e in crossing(bots, prev_bot[m]):
                t = at_line(n, e)
                if started.get(m) == n:                             # a second bottom edge in the same frame:
                    continue                                        # a gap inside the bar (a label), not a note
                started[m] = n
                k = open_note.pop(m, None)
                if k is not None:                                   # its top edge was missed: it ends here
                    notes[k] = (notes[k][0], max(0.0, t - notes[k][0]), m)
                top = e
                while top > 0 and col[top - 1]:
                    top -= 1
                if top > 0:                                         # the whole bar is inside the band
                    notes.append((t, (e - top + 1) / speed / fps, m))
                else:
                    notes.append((t, None, m))
                    open_note[m] = len(notes) - 1
            prev_bot[m], prev_top[m] = bots, tops
    end = n / fps + lead
    notes = [(t, d if d is not None else max(0.0, end - t), m) for t, d, m in notes]
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
