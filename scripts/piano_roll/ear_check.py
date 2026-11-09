#!/usr/bin/env python3
"""Hear a piano-roll video and the ABC draft in turn, line by line (like a jugalbandi).

    python scripts/piano_roll/ear_check.py rs000864                    # first two lines of the first stanza
    python scripts/piano_roll/ear_check.py rs000864 --stanza 2 --line 0 --count 2

Makes data/intermediate_data/comparison/<song>_s<stanza>_l<line>_ear.mp4 (git-ignored); for each
line in turn:
  1. the piano-roll video for those lines, with only its melody heard: the right-hand notes read
     from the video (the top note where two sound together), synthesized, so the chords don't
     cover them;
  2. the same lines of the ABC, synthesized note by note with the ABC's own rhythm, at the
     roll's tempo (so the two sound alike when the draft is right), with the lyrics and the
     sargam on screen and the current syllable highlighted.
Lines are the ABC's music lines (one w: line each). The roll's stretch is found by matching the
whole stanza to the roll (longest common subsequence, earliest occurrence).
"""
import argparse
import csv
import glob
import os
import subprocess
import sys
import tempfile
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'vocal_melody'))
sys.path.insert(0, os.path.join(HERE, '..', 'piano_lesson_to_ktab'))
import word_table as WT  # noqa: E402
from abc_to_ktab import parse_abc  # noqa: E402

SR = 44100
FONT_DIR = os.path.abspath(os.path.join(HERE, '..', 'ktab_to_video', 'fonts'))


def stanza_notes(abc, k):
    """notes of stanza k: dicts rel (to Sa), eighths, syl, word, line"""
    names, stz = WT.draft_stanzas(abc)
    _, st = parse_abc(open(abc).read())
    out, i = [], 0
    for li, ln in enumerate(st[k]):
        for e in ln:
            if e['kind'] == 'note':
                n = stz[k][i]; i += 1
                out.append(dict(rel=n['rel'], eighths=e['eighths'], syl=n['syl'], word=n['word'], line=li))
            elif out:                                                  # a rest lengthens the note before it
                out[-1]['eighths'] += e['eighths']
    return names[k], out


def lcs_early(a, b):
    """LCS mapping on the earliest positions in b (a repeated refrain matches its first occurrence)"""
    m = WT.lcs_map(a[::-1], b[::-1])
    return {len(a) - 1 - i: len(b) - 1 - j for i, j in m.items()}


def tone(midi, dur):
    """a plain piano-like tone: a few harmonics with an exponential decay"""
    f = 440.0 * 2 ** ((midi - 69) / 12)
    t = np.arange(int(SR * dur)) / SR
    y = sum(a * np.sin(2 * np.pi * f * h * t) for h, a in ((1, 1.0), (2, 0.45), (3, 0.2), (4, 0.1)))
    return y * np.exp(-t * 2.5) * np.minimum(1, t / 0.005) * np.minimum(1, (dur - t) / 0.03)


def ass_time(t):
    m, s = divmod(max(t, 0), 60)
    return f'0:{int(m):02d}:{s:05.2f}'


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('song')
    ap.add_argument('--stanza', type=int, default=0, help='P: section of the ABC, from 0')
    ap.add_argument('--line', type=int, default=0, help='first music line in that section, from 0')
    ap.add_argument('--count', type=int, default=2, help='how many lines')
    ap.add_argument('--abc')
    ap.add_argument('--roll', help='piano-roll notes CSV (default: the one in piano_roll/<song>/)')
    ap.add_argument('--video', help='piano-roll video (default: data/raw_data/video/<notes CSV name>.mp4)')
    a = ap.parse_args()
    abc = a.abc or f'data/intermediate_data/abc/{a.song}/v1.abc'
    roll = a.roll or glob.glob(f'data/intermediate_data/piano_roll/{a.song}/*_notes.csv')[0]
    video = a.video or 'data/raw_data/video/' + os.path.basename(roll).replace('_notes.csv', '.mp4')
    name, notes = stanza_notes(abc, a.stanza)

    rows = list(csv.DictReader(open(roll)))
    midis = [int(r['midi']) for r in rows]
    onset = [float(r['onset']) for r in rows]
    dur = [float(r['duration']) for r in rows]
    whole = [n['rel'] for s in WT.draft_stanzas(abc)[1] for n in s]
    base = max(range(min(midis) - 12, max(midis) + 1), key=lambda b: len(WT.lcs_map(whole, [m - b for m in midis])))
    P = [m - base for m in midis]
    d = [n['rel'] for n in notes]
    span = int(len(d) * 1.5) + 8
    j = max(range(0, max(1, len(P) - len(d) // 2), 2), key=lambda j: len(WT.lcs_map(d, P[j:j + span])))
    mp = {i: j + q for i, q in lcs_early(d, P[j:j + span]).items()}

    # tempo: seconds per eighth, from the matched notes of the whole stanza
    beat = np.cumsum([0] + [n['eighths'] for n in notes])
    anchors = sorted(mp)
    spe = float(np.median([(onset[mp[q]] - onset[mp[p]]) / (beat[q] - beat[p])
                           for p, q in zip(anchors, anchors[1:]) if beat[q] > beat[p]]))
    enc = ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '23', '-r', '30', '-pix_fmt', 'yuv420p',
           '-c:a', 'aac', '-ar', '44100', '-ac', '2']
    nlines = max(n['line'] for n in notes) + 1
    todo = [li for li in range(a.line, min(nlines, a.line + a.count))]

    def write_wav(path, y):
        with wave.open(path, 'wb') as w:
            w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
            s16 = (y * 32767).astype(np.int16)
            w.writeframes(np.stack([s16, s16], 1).tobytes())

    with tempfile.TemporaryDirectory() as tmp:
        parts = []
        for li in todo:
            sel = [i for i, n in enumerate(notes) if n['line'] == li]
            hit = [mp[i] for i in sel if i in mp]
            if len(hit) < 2:
                print(f'line {li + 1}: not found in the roll, skipped'); continue
            print(f'{name}, line {li + 1}: {len(hit)}/{len(sel)} draft notes found in the roll')
            # the roll's line: from its first matched note to the next line's first matched note
            nxt = [mp[i] for i, n in enumerate(notes) if n['line'] == li + 1 and i in mp]
            r0 = onset[min(hit)] - 0.5
            end = onset[min(nxt)] - 0.05 if nxt and onset[min(nxt)] > onset[max(hit)] else \
                onset[max(hit)] + max(dur[max(hit)], notes[sel[-1]]['eighths'] * spe)
            r1 = end + 0.7
            yr = np.zeros(int((r1 - r0) * SR) + SR)
            for m, on, du in zip(midis, onset, dur):
                if r0 <= on < end:
                    t = tone(m, max(0.15, min(du, end - on + 0.3)) + 0.2)
                    k = int((on - r0) * SR); yr[k:k + len(t)] += t[:max(0, len(yr) - k)]
            yr *= 0.6 / max(1e-9, np.abs(yr).max())
            # the ABC's line at the roll's tempo
            lead = 0.5
            starts = [lead + (beat[i] - beat[sel[0]]) * spe for i in sel]
            lengths = [notes[i]['eighths'] * spe for i in sel]
            total = starts[-1] + lengths[-1] + 0.7
            y = np.zeros(int(total * SR) + SR)
            for i, st_, ln in zip(sel, starts, lengths):
                t = tone(notes[i]['rel'] + base, max(0.15, ln) + 0.2)
                k = int(st_ * SR); y[k:k + len(t)] += t
            y *= 0.6 / max(1e-9, np.abs(y).max())
            wr, wa = os.path.join(tmp, f'r{li}.wav'), os.path.join(tmp, f'a{li}.wav')
            write_wav(wr, yr); write_wav(wa, y)
            # screen for the ABC line: sargam over lyrics, the sounding note highlighted
            hl = lambda txt, on: ('{\\c&H00FFFF&}' + txt + '{\\c&HFFFFFF&}') if on else txt
            ass = ['[Script Info]', 'PlayResX: 1280', 'PlayResY: 720', '', '[V4+ Styles]',
                   'Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Italic, '
                   'BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV',
                   'Style: T,TeX Gyre Heros,30,&H00BBBBBB,&H00000000,&H00000000,0,0,1,0,0,8,20,20,60',
                   'Style: N,TeX Gyre Heros,44,&H00FFFFFF,&H00000000,&H00000000,-1,0,1,0,0,5,20,20,0', '',
                   '[Events]', 'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text',
                   f'Dialogue: 0,{ass_time(0)},{ass_time(total)},T,,0,0,0,,ABC draft  ·  {name}, line {li + 1}']
            for k, i in enumerate([None] + sel):
                t_on = 0 if i is None else starts[k - 1]
                t_off = starts[k] if k < len(sel) else total
                sar = '  '.join(hl(WT.sg(notes[q]['rel']), q == i) for q in sel)
                syl = '  '.join(hl(notes[q]['syl'], q == i) for q in sel if notes[q]['syl'])
                ass.append(f'Dialogue: 0,{ass_time(t_on)},{ass_time(t_off)},N,,0,0,0,,{sar}\\N{{\\fs32}}{syl}')
            sub = os.path.join(tmp, f'a{li}.ass')
            open(sub, 'w').write('\n'.join(ass) + '\n')
            p1, p2 = os.path.join(tmp, f'p{li}r.mp4'), os.path.join(tmp, f'p{li}a.mp4')
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{r0:.3f}', '-t', f'{r1 - r0:.3f}', '-i', video,
                            '-i', wr, '-map', '0:v', '-map', '1:a',
                            '-vf', f"scale=1280:720,drawtext=fontfile={FONT_DIR}/texgyreheros-bold.otf:"
                            f"text='Piano roll (Arup Paul), melody only  ·  line {li + 1}':x=20:y=20:fontsize=30:"
                            f"fontcolor=white:box=1:boxcolor=black@0.6", '-shortest'] + enc + [p1], check=True)
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i',
                            f'color=c=0x1b1b1f:s=1280x720:r=30:d={total:.3f}', '-i', wa,
                            '-vf', f'subtitles={sub}:fontsdir={FONT_DIR}', '-shortest'] + enc + [p2], check=True)
            parts += [p1, p2]
        lst = os.path.join(tmp, 'list.txt')
        open(lst, 'w').write(''.join(f"file '{p}'\n" for p in parts))
        out = f'data/intermediate_data/comparison/{a.song}_s{a.stanza}_l{a.line}_ear.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', lst, '-c', 'copy', out],
                       check=True)
    print(f'{len(parts) // 2} lines, roll and ABC in turn -> {out}')


if __name__ == '__main__':
    main()
