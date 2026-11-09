#!/usr/bin/env python3
"""Swaralipi player: an ABC draft played with a ticker moving over the original Bengali swaralipi.

    python scripts/swaralipi_player/player.py rs000864

Makes data/intermediate_data/comparison/<song>_swaralipi_ticker.mp4 (git-ignored): the draft is
synthesized at its own tempo (Q:) while a box moves over the swaralipi page, matra by matra, and the
page scrolls to keep the sung line in view.

How the draft is tied to the page
  * The swaralipi PDF (data/raw_data/swaralipi/<song>.pdf) is rendered at 130 dpi. Each swara row
    is split into matras between its bar lines (I, ।); a syllable under a matra in the lyric row
    marks where a syllable starts. { } sections are expanded so they are sung twice, and when the
    draft ends by returning to its first section, the first row is appended.
  * Matra by matra (1 matra = 1 quarter note), the draft and the swaralipi are aligned by dynamic
    time warping on two marks: does a new note start (in the swaralipi: not a "-।" hold), and does a
    syllable start. Matras only one side has (the draft's longer holds, a pickup rest) are skipped.
"""
import argparse
import os
import subprocess
import sys
import tempfile
import wave

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', 'vocal_melody'))
sys.path.insert(0, os.path.join(HERE, '..', 'piano_lesson_to_ktab'))
import layout as SL  # noqa: E402
import word_table as WT  # noqa: E402
from abc_to_ktab import parse_abc  # noqa: E402

SR = 44100


def tone(midi, dur):
    """a plain piano-like tone: a few harmonics with an exponential decay"""
    f = 440.0 * 2 ** ((midi - 69) / 12)
    t = np.arange(int(SR * dur)) / SR
    y = sum(a * np.sin(2 * np.pi * f * h * t) for h, a in ((1, 1.0), (2, 0.45), (3, 0.2), (4, 0.1)))
    return y * np.exp(-t * 2.5) * np.minimum(1, t / 0.005) * np.minimum(1, (dur - t) / 0.03)

W, H, FPS = 1280, 720, 25
MIN_STAY = 0.08                                    # seconds the ticker stays on any matra


def draft(abc):
    """notes [(start beat, beats, rel to Sa, syllable, MIDI pitch)], quarter-note tempo, section names"""
    txt = open(abc).read()
    names, stz = WT.draft_stanzas(abc)
    _, st = parse_abc(txt)
    q = 120
    for l in txt.splitlines():
        if l.startswith('Q:') and '=' in l:
            q = float(l.split('=')[1])
    notes, b = [], 0.0
    for s, sn in zip(st, stz):
        k = 0
        for ln in s:
            for e in ln:
                n = e['eighths'] / 2
                if e['kind'] == 'note':
                    notes.append((b, n, sn[k]['rel'], sn[k]['syl'], e['midi'])); k += 1
                b += n
    return notes, q, names


def dtw(D, S, skip=1.2, free_start=False):
    """DTW of draft matras D with swaralipi matras S, each item (new note?, new syllable?).
    Returns ({swaralipi j: draft i} for matched matras, draft matras left unmatched, end j, cost).
    The end is free (the draft may stop before the page does); with free_start the start is too."""
    nd, ns = len(D), len(S)
    cost = lambda d, s: (d[0] != s[0]) + 1.5 * (d[1] != s[1])
    INF = 1e18
    dp = np.full((nd + 1, ns + 1), INF)
    dp[0, :] = 0 if free_start else np.arange(ns + 1) * skip
    dp[0, 0] = 0
    step = np.zeros((nd + 1, ns + 1), int)
    for i in range(1, nd + 1):
        for j in range(ns + 1):
            if j and dp[i - 1, j - 1] + cost(D[i - 1], S[j - 1]) < dp[i, j]:
                dp[i, j] = dp[i - 1, j - 1] + cost(D[i - 1], S[j - 1]); step[i, j] = 0
            if dp[i - 1, j] + skip < dp[i, j]:
                dp[i, j] = dp[i - 1, j] + skip; step[i, j] = 1      # a draft matra the swaralipi doesn't have
            if j and dp[i, j - 1] + skip < dp[i, j]:
                dp[i, j] = dp[i, j - 1] + skip; step[i, j] = 2      # a swaralipi matra the draft doesn't have
    j = jend = int(np.argmin(dp[nd]))
    i, at, unmatched = nd, {}, []
    while i:
        st_ = step[i, j]
        if st_ == 0:
            at[j - 1] = i - 1; i -= 1; j -= 1
        elif st_ == 1:
            unmatched.append(i - 1); i -= 1
        else:
            j -= 1
    return at, sorted(unmatched), jend, dp[nd, jend]


def timeline(D, S, min_run=6):
    """(times, js, cost): from draft time times[k] on, the ticker shows swaralipi matra js[k].
    Main pass: the draft against the singing order; matras between matched ones get times spread
    evenly, so every matra is visited. A run of >= min_run draft matras the main pass leaves
    unmatched (e.g. a return to the sthayi that the draft writes out) is aligned on its own,
    anywhere on the page, and the ticker goes there for it, then back to the main path."""
    at, unmatched, jend, cost = dtw(D, S)
    js = sorted(at)
    main = []
    if js:
        t = np.interp(np.arange(js[0], js[-1] + 1), js, [at[k] for k in js])
        main = list(zip(t, range(js[0], js[-1] + 1)))
    runs, cur = [], []
    for i in unmatched:
        if cur and i != cur[-1] + 1:
            runs.append(cur); cur = []
        cur.append(i)
    if cur: runs.append(cur)
    events = list(main)
    for run in runs:
        if len(run) < min_run:
            continue
        a, b = run[0], run[-1] + 1
        sub, _, _, c = dtw(D[a:b], S, free_start=True)
        if not sub or c / (b - a) > 0.8:
            continue                                                  # no convincing place on the page
        sj = sorted(sub)
        t = np.interp(np.arange(sj[0], sj[-1] + 1), sj, [a + sub[k] for k in sj])
        back = [j for tt, j in main if tt <= b]                        # where the main path is at the end of it
        events = [e for e in events if not (a <= e[0] < b)] + list(zip(t, range(sj[0], sj[-1] + 1)))
        if back:
            events.append((b, back[-1]))
        cost += c - len(run) * 1.2
    events.sort(key=lambda e: e[0])
    return np.array([e[0] for e in events], float), [e[1] for e in events], cost


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('song')
    ap.add_argument('--abc')
    ap.add_argument('--pdf')
    ap.add_argument('--matra', choices=('auto', 'quarter', 'eighth'), default='auto',
                    help='length of one swaralipi matra in the ABC (auto: whichever aligns better)')
    a = ap.parse_args()
    abc = a.abc or f'data/intermediate_data/abc/{a.song}/v1.abc'
    pdf = a.pdf or f'data/raw_data/swaralipi/{a.song}.pdf'
    notes, q, names = draft(abc)
    spb = 60.0 / q                                                    # seconds per beat (quarter)

    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(['pdftoppm', '-r', '130', '-png', pdf, os.path.join(tmp, 'p')], check=True)
        pages = sorted(os.path.join(tmp, f) for f in os.listdir(tmp) if f.startswith('p'))
        lay = [SL.page_layout(p) for p in pages]
        order = SL.singing_order(lay)
        if len(names) > 1 and names[-1] == names[0]:                  # the draft returns to its first section
            order += [(0, 0, m) for m in range(len(lay[0][0]['boxes']))]
        S = [(not lay[p][r]['hold'][m], lay[p][r]['syl'][m]) for p, r, m in order]
        best = None
        for unit in ((1.0, 'quarter'), (2.0, 'eighth')) if a.matra == 'auto' else \
                (((1.0, 'quarter'),) if a.matra == 'quarter' else ((2.0, 'eighth'),)):
            per = unit[0]                                             # matras per quarter note
            nb = int(np.ceil((notes[-1][0] + notes[-1][1]) * per))
            D = [[False, False] for _ in range(nb)]
            for b, n, rel, syl, _ in notes:
                D[int(b * per)][0] = True
                D[int(b * per)][1] = D[int(b * per)][1] or bool(syl)
            to, js_, cost = timeline([tuple(d) for d in D], S)
            if best is None or cost / nb < best[2] / best[3]:
                best = (to, js_, cost, nb, per, unit[1])
        to, js_, cost, nb, per, uname = best
        # every matra stays on screen at least MIN_STAY: arrive a little earlier where matras crowd
        gap = MIN_STAY / spb * per
        to = np.array(to, float)
        for k in range(len(to) - 2, -1, -1):                          # backward: make room before crowded matras
            to[k] = min(to[k], to[k + 1] - gap)
        for k in range(1, len(to)):                                   # forward: never before the start
            to[k] = max(to[k], to[k - 1] + gap)
        print(f'{len(order)} swaralipi matras in singing order, {nb} draft matras (1 matra = one {uname} note); '
              f'alignment cost {cost:.0f} ({cost / nb:.2f} per matra)')

        # audio
        total_beats = notes[-1][0] + notes[-1][1] + 2
        dur = total_beats * spb
        y = np.zeros(int(dur * SR) + SR)
        for b, n, rel, _, midi in notes:
            t = tone(midi, max(0.15, n * spb) + 0.2)                  # at the draft's own pitch
            k = int(b * spb * SR); y[k:k + len(t)] += t
        y *= 0.6 / max(1e-9, np.abs(y).max())
        wav = os.path.join(tmp, 'a.wav')
        with wave.open(wav, 'wb') as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
            w.writeframes((y * 32767).astype(np.int16).tobytes())

        imgs = [Image.open(p).convert('RGB') for p in pages]
        scale = W / imgs[0].width
        win = int(H / scale)                                          # page pixels visible at once
        out = f'data/intermediate_data/comparison/{a.song}_swaralipi_ticker.mp4'
        ff = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}',
                               '-r', str(FPS), '-i', '-', '-i', wav, '-c:v', 'libx264', '-preset', 'veryfast',
                               '-crf', '23', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest', out],
                              stdin=subprocess.PIPE)
        top_prev = None
        for f in range(int(dur * FPS)):
            beat = f / FPS / spb
            k = max(0, int(np.searchsorted(to, beat * per, side='right')) - 1)
            p, r, m = order[min(js_[k], len(order) - 1)]
            row = lay[p][r]
            x0, x1 = row['boxes'][m]
            # scroll so the sung row sits about a third of the way down
            top = int(np.clip(row['y0'] - win / 3, 0, imgs[p].height - win))
            top = top if top_prev is None or top_prev[0] != p else int(top_prev[1] + (top - top_prev[1]) * 0.25)
            top_prev = (p, top)
            frame = imgs[p].crop((0, top, imgs[p].width, top + win)).copy()
            d = ImageDraw.Draw(frame, 'RGBA')
            nxt = lay[p][r + 1]['y0'] if r + 1 < len(lay[p]) else row['y1'] + 70
            d.rectangle((x0 - 6, row['y0'] - 8 - top, x1 + 6, nxt - 10 - top), fill=(255, 200, 0, 90),
                        outline=(220, 120, 0, 255), width=2)
            ff.stdin.write(np.asarray(frame.resize((W, H))).tobytes())
        ff.stdin.close(); ff.wait()
    print(f'{dur:.0f} s -> {out}')


if __name__ == '__main__':
    main()
