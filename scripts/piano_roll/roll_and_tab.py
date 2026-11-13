#!/usr/bin/env python3
"""Piano roll and kalimba tab video in turn, line by line (like a jugalbandi).

    python scripts/piano_roll/roll_and_tab.py rs000920 --ktab data/intermediate_data/ktab/rs000920/v3.ktab --bpm 200

For every line of the tab, in the order it is played:
  1. the piano-roll video over that line, with only its melody heard (the right-hand notes read from
     the video, synthesized as in ear_check.py, so the chords don't cover them);
  2. the same line of the kalimba tab video (scripts/ktab_to_video/kalimba_video.py): its sound and
     its page, with the line being played.
With --groups (e.g. 1-13,14-23), the turns are whole groups of lines instead: the roll over the
whole group, then the tab over it (a stanza at a time). The tab sounds retuned when it has an
@retune header (or --retune).
The tab video is rendered first if --tab-video is not given. A tab line is found in the roll by
matching its notes (longest common subsequence, as in ear_check.py) within its stanza's best stretch.

Writes data/intermediate_data/comparison/<song>_roll_and_tab.mp4 (git-ignored).
"""
import argparse
import csv
import glob
import os
import re
import subprocess
import sys
import tempfile
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 'src'))
sys.path.insert(0, os.path.join(HERE, '..', 'vocal_melody'))
import ktab  # noqa: E402
import word_table as WT  # noqa: E402
from ear_check import lcs_early, tone, SR, FONT_DIR  # noqa: E402

INTRO = 1.5                                     # kalimba_video.py's silence before the first note
ENC = ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '23', '-r', '30', '-pix_fmt', 'yuv420p',
       '-c:a', 'aac', '-ar', '44100', '-ac', '2']


def write_wav(path, y):
    with wave.open(path, 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        s16 = (y * 32767).astype(np.int16)
        w.writeframes(np.stack([s16, s16], 1).tobytes())


def retune_shifts(spec):
    """'G4:G#4,F:F#' -> {semitone above C4: shift} for single tines, {pitch class: shift} for all octaves"""
    letter = dict(C=0, D=2, E=4, F=5, G=7, A=9, B=11)
    tine, every = {}, {}
    for part in filter(None, (x.strip() for x in (spec or '').split(','))):
        (l1, a1, o1), (l2, a2, o2) = (re.fullmatch(r'([A-G])([#b]*)(\d?)', x.strip()).groups() for x in part.split(':'))
        p1 = letter[l1] + a1.count('#') - a1.count('b')
        p2 = letter[l2] + a2.count('#') - a2.count('b')
        if o1 and o2:
            tine[p1 + 12 * (int(o1) - 4)] = p2 + 12 * int(o2) - p1 - 12 * int(o1)
        else:
            every[p1 % 12] = (p2 - p1 + 6) % 12 - 6
    return tine, every


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('song')
    ap.add_argument('--ktab', required=True)
    ap.add_argument('--bpm', type=float, help='tab tempo; default: the tempo at which each tab line lasts as long '
                    'as its piano-roll segment, over the whole song (so the two play for the same duration)')
    ap.add_argument('--tab-video', help='the tab video made by kalimba_video.py at this bpm (made if missing)')
    ap.add_argument('--roll', help='piano-roll notes CSV (default: the one in piano_roll/<song>/)')
    ap.add_argument('--stretch', action='store_true', help='speed each tab line up or down to last exactly as long as '
                    'its piano-roll line (the tab then follows the pianist\'s tempo line by line)')
    ap.add_argument('--out', help='output file (default: comparison/<song>_roll_and_tab.mp4)')
    ap.add_argument('--lines', help='only these tab lines, e.g. 1-6 (1-based, in playing order)')
    ap.add_argument('--groups', help='take turns a group of lines at a time, e.g. 1-13,14-23 (1-based, in playing '
                    'order; replaces --lines)')
    ap.add_argument('--retune', help='tine retuning for the tab sound, as kalimba_video.py --retune '
                    '(default: the tab\'s @retune header)')
    a = ap.parse_args()
    song = ktab.parse_file(a.ktab)
    retune = a.retune or song.headers.get('retune')

    def lines_played(bpm):
        """tab lines in playing order: [line index, stanza, start, end in the tab video]"""
        tl = ktab.timeline(song, bpm, start=INTRO)
        played = []
        for w in tl.words:
            if not played or played[-1][0] != w.line or w.word == 0:
                played.append([w.line, w.stanza, w.start, w.end])
            played[-1][3] = w.end
        for k, p in enumerate(played):
            p[3] = played[k + 1][2] if k + 1 < len(played) else tl.end + 1.0
        return played

    played = lines_played(a.bpm or 60)
    tine, every = retune_shifts(retune)
    notes_of = {}                               # tab line -> its notes as they sound (after any retuning)
    for li, line in enumerate(song.lines):
        notes_of[li] = [ev.semitone + tine.get(ev.semitone, every.get(ev.semitone % 12, 0)) for wd in line.words for syl in wd.syllables for ev in syl.events
                        if isinstance(ev, ktab.Note) and not ev.is_rest]

    roll = a.roll or glob.glob(f'data/intermediate_data/piano_roll/{a.song}/*_notes.csv')[0]
    rows = list(csv.DictReader(open(roll)))
    midis = [int(r['midi']) for r in rows]
    onset = [float(r['onset']) for r in rows]
    dur = [float(r['duration']) for r in rows]
    video = 'data/raw_data/video/' + os.path.basename(roll).replace('_notes.csv', '.mp4')
    whole = [n for p in played for n in notes_of[p[0]]]
    base = max(range(min(midis) - 36, max(midis) + 1), key=lambda b: len(WT.lcs_map(whole, [m - b for m in midis])))
    P = [m - base for m in midis]

    def span_of(text):
        lo, _, hi = text.partition('-')
        return list(range(int(lo) - 1, min(int(hi or lo), len(played))))

    if a.groups:
        units = [span_of(g) for g in a.groups.split(',')]
    else:
        units = [[k] for k in (span_of(a.lines) if a.lines else range(len(played)))]
    sel = [k for u in units for k in u]

    # each stanza (in playing order) -> its best stretch of the roll -> each line's matched roll notes
    # (with --groups: each group in turn, searched from where the previous group ended in the roll)
    if a.groups:
        blocks = units
    else:
        blocks, k = [], 0
        while k < len(played):
            k2 = k
            while k2 + 1 < len(played) and played[k2 + 1][1] == played[k][1]:
                k2 += 1
            blocks.append(list(range(k, k2 + 1)))
            k = k2 + 1
    match = {}                                  # index in `played` -> roll note indices
    after = 0
    for group in blocks:
        d = [n for g in group for n in notes_of[played[g][0]]]
        span = int(len(d) * 1.5) + 8
        j = max(range(after, max(after + 1, len(P) - len(d) // 2), 2),
                key=lambda j: len(WT.lcs_map(d, P[j:j + span])))
        mp = {i: j + q for i, q in lcs_early(d, P[j:j + span]).items()}
        off = 0
        for g in group:
            n = len(notes_of[played[g][0]])
            match[g] = [mp[i] for i in range(off, off + n) if i in mp]
            off += n
        if a.groups and mp:
            after = max(mp.values()) + 1
        print(f'lines {group[0] + 1}-{group[-1] + 1}: {len(mp)}/{len(d)} notes found in the roll, '
              + ' '.join(str(len(match[g])) for g in group))


    def roll_span(k):
        """(start, end) in the roll video of tab line k, or None if the line was not found in the roll"""
        hit = match.get(k, [])
        if len(hit) < 2:
            return None
        nxt = next((match[q] for q in range(k + 1, len(played)) if match.get(q)), [])
        r0 = onset[min(hit)] - 0.4
        end = (onset[min(nxt)] - 0.05 if nxt and onset[min(nxt)] > onset[max(hit)]
               else onset[max(hit)] + dur[max(hit)])
        return r0, min(end, onset[max(hit)] + dur[max(hit)] + 3.0) + 0.5

    # roll time of a line = its first note to the next line's first note (no clip padding, no held tails)
    def played_sec(k):
        hit = match[k]
        nxt = next((match[q] for q in range(k + 1, len(played)) if match.get(q)), [])
        if nxt and onset[min(nxt)] > onset[min(hit)]:
            return onset[min(nxt)] - onset[min(hit)]
        return onset[max(hit)] + dur[max(hit)] - onset[min(hit)]

    if a.bpm is None:
        # the tab line lasts (end - start) at 60 bpm; at b bpm it lasts that x 60 / b
        both = [k for k in sel if roll_span(k)]
        tab60 = sum(played[k][3] - played[k][2] for k in both)
        rollsec = sum(played_sec(k) for k in both)
        a.bpm = round(60 * tab60 / rollsec, 1)
        print(f'tab tempo {a.bpm} bpm: {len(both)} lines, roll {rollsec:.1f} s, tab {tab60 * 60 / a.bpm:.1f} s')
        played = lines_played(a.bpm)

    with tempfile.TemporaryDirectory() as tmp:
        tab_video = a.tab_video
        if not tab_video:
            tab_video = os.path.join(tmp, 'tab.mp4')
            subprocess.run([sys.executable, os.path.join(ROOT, 'scripts/ktab_to_video/kalimba_video.py'), a.ktab,
                            os.path.join(ROOT, 'data/raw_data/image/paper_texture_brown.png'), '-o', tab_video,
                            '--bpm', str(a.bpm)] + (['--retune', retune] if retune else []),
                           check=True, capture_output=True)
        parts = []
        for unit in units:
            k = unit[0]
            t0, t1 = played[unit[0]][2], played[unit[-1]][3]
            words = lambda q: ' '.join('-'.join(s.text for s in wd.syllables) for wd in song.lines[played[q][0]].words)
            if len(unit) == 1:
                text, tag = words(k), f'{k + 1}'
            else:
                text, tag = words(unit[0]) + ' …', f'lines {unit[0] + 1}-{unit[-1] + 1}'
            spans = [roll_span(q) for q in unit if roll_span(q)]
            span = (spans[0][0], spans[-1][1]) if spans else None
            if len(spans) < len(unit):
                print(f'{tag}: {len(unit) - len(spans)} line(s) not found in the roll')
            if span:
                r0, r1 = span
                yr = np.zeros(int((r1 - r0) * SR) + SR)
                for m, on, du in zip(midis, onset, dur):
                    if r0 <= on < r1 - 0.5:
                        t = tone(m, max(0.15, min(du, r1 - on)) + 0.2)
                        q = int((on - r0) * SR); yr[q:q + len(t)] += t[:max(0, len(yr) - q)]
                yr *= 0.6 / max(1e-9, np.abs(yr).max())
                wr = os.path.join(tmp, f'r{k}.wav'); write_wav(wr, yr)
                p1 = os.path.join(tmp, f'p{k}r.mp4')
                label = f"Piano roll (Arup Paul), melody  ·  {tag}: {text}".replace("'", "’").replace(':', '\\:')
                subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{r0:.3f}', '-t', f'{r1 - r0:.3f}', '-i', video,
                                '-i', wr, '-map', '0:v', '-map', '1:a',
                                '-vf', f"scale=1280:720,drawtext=fontfile={FONT_DIR}/texgyreheros-bold.otf:"
                                f"text='{label}':x=20:y=20:fontsize=26:fontcolor=white:box=1:boxcolor=black@0.6",
                                '-shortest'] + ENC + [p1], check=True)
                parts.append(p1)
            else:
                print(f'{tag} ({text}): not found in the roll, tab only')
            p2 = os.path.join(tmp, f'p{k}t.mp4')
            s0 = max(0.0, t0 - 0.3)
            f = ((t1 - t0) / sum(played_sec(q) for q in unit if match.get(q))
                 if a.stretch and span else 1.0)     # >1: tab line played faster
            atempo = ''
            g = f
            while g > 2.0 or g < 0.5:                                      # atempo takes 0.5 - 2.0 per stage
                step = 2.0 if g > 2.0 else 0.5
                atempo += f'atempo={step},'; g /= step
            atempo += f'atempo={g:.5f},'
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{s0:.3f}', '-t', f'{t1 - s0 + 0.2:.3f}', '-i', tab_video,
                            '-vf', f'scale=1280:720,setpts=PTS/{f:.5f}',
                            '-af', atempo + 'afade=t=out:st=%.3f:d=0.2' % ((t1 - s0) / f),
                            '-shortest'] + ENC + [p2], check=True)
            parts.append(p2)
        lst = os.path.join(tmp, 'list.txt')
        open(lst, 'w').write(''.join(f"file '{p}'\n" for p in parts))
        out = a.out or f'data/intermediate_data/comparison/{a.song}_roll_and_tab.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', lst, '-c', 'copy', out], check=True)
    print(f'{len(sel)} lines in {len(units)} turn(s), roll and tab in turn -> {out}')


if __name__ == '__main__':
    main()
