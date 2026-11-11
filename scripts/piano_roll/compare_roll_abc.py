#!/usr/bin/env python3
"""How well an ABC draft agrees with the piano roll's melody, note for note.

    python scripts/piano_roll/compare_roll_abc.py rs002122 [rs000899 ...]   (default: every song with both)

Both sides become pitch sequences: the ABC's notes (tied notes joined) and the roll's melody notes
(data/intermediate_data/piano_roll/<song>/*_notes.csv; fragments shorter than 0.06 s dropped).
Repeated notes of the same pitch are merged on both sides, since one side may re-strike what the other
holds. The roll is shifted by every transposition and the longest common subsequence is taken.
Reports, per song: the shift, the share of the draft's notes found in the roll (draft %) and the share
of the roll's notes found in the draft (roll %). A low draft % means the draft has notes Arup Paul
does not play (other tune, wrong octave, a misread); a low roll % means the roll plays more
(repeats the draft lacks, ornaments, an introduction).
Writes data/intermediate_data/comparison/roll_vs_abc.csv.
"""
import csv
import glob
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'piano_lesson_to_ktab'))
import abc_to_ktab as A  # noqa: E402


def dedup(seq):
    return [p for i, p in enumerate(seq) if i == 0 or p != seq[i - 1]]


def lcs_len(a, b):
    a, b = np.asarray(a), np.asarray(b)
    prev = np.zeros(len(b) + 1, dtype=np.int32)
    for x in a:
        cur = np.zeros_like(prev)
        eq = (b == x)
        for j in range(1, len(b) + 1):
            cur[j] = prev[j - 1] + 1 if eq[j - 1] else max(prev[j], cur[j - 1])
        prev = cur
    return int(prev[-1])


def compare(song):
    abc = f'data/intermediate_data/abc/{song}/v1.abc'
    rolls = glob.glob(f'data/intermediate_data/piano_roll/{song}/*_notes.csv')
    if not os.path.exists(abc) or not rolls:
        return None
    _, st = A.parse_abc(open(abc, encoding='utf-8').read())
    d = dedup([e['midi'] for s in st for ln in s for e in ln if e['kind'] == 'note'])
    rows = list(csv.DictReader(open(rolls[0])))
    r = dedup([int(x['midi']) for x in rows if float(x['duration']) >= 0.06])
    if not d or not r:
        return None
    # candidate shifts: those that line up the most common pitches, then the best by LCS
    best = (0, 0)
    for sh in range(min(r) - max(d), max(r) - min(d) + 1):
        dd = [p + sh for p in d]
        overlap = len(set(dd) & set(r))
        if overlap < len(set(d)) // 2:
            continue
        n = lcs_len(dd, r)
        if n > best[0]:
            best = (n, sh)
    n, sh = best
    return dict(song=song, shift=sh, draft_notes=len(d), roll_notes=len(r), matched=n,
                draft_pct=round(100 * n / len(d)), roll_pct=round(100 * n / len(r)))


def main():
    songs = sys.argv[1:] or sorted({p.split('/')[-2] for p in glob.glob('data/intermediate_data/piano_roll/*/*_notes.csv')})
    out = [x for x in (compare(s) for s in songs) if x]
    path = 'data/intermediate_data/comparison/roll_vs_abc.csv'
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    for x in out:
        print(f"{x['song']}: shift {x['shift']:+d}, draft {x['draft_pct']}% of {x['draft_notes']}, "
              f"roll {x['roll_pct']}% of {x['roll_notes']}")
    print(f'{len(out)} songs -> {path}')


if __name__ == '__main__':
    main()
