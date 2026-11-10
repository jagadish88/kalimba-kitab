#!/usr/bin/env python3
"""Check an ABC draft against the swaralipi text, note by note.

    python scripts/swaralipi_player/check_abc.py rs002164 --abc data/intermediate_data/abc/rs002164/v2.abc

Both sides become note sequences in singing order: pitch (semitones from Sa, with octave), start
(in matras; one matra = one quarter note in the ABC), and whether a syllable starts on the note.
The swaralipi comes from data/intermediate_data/swaralipi/<song>.json (our transcription) via text_player.py. Its grace
notes are optional: the MIDI often plays a grace as a full note, often carrying the syllable, which
then counts for the swaralipi's next main note. Syllables come from the lyric row (also on "-" cells);
a lone vowel (ও-ই), a bare final consonant (মো-র) or a "৹ও" tail may be joined to the syllable before
or not: either way agrees. The ABC's Sa is read from its "Sa = X" note.
A note that repeats the pitch before it without a new syllable is merged into it on both sides
(one source re-strikes, the other holds). The two are aligned (Needleman-Wunsch: match +2, other pitch -1, a note only one side has -1; grace notes
match +1 and may be left out freely),
and the report lists every difference with its lyric.

Writes data/intermediate_data/comparison/<song>_<abc version>_swaralipi_check.md.
"""
import argparse
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', 'piano_lesson_to_ktab'))
sys.path.insert(0, os.path.join(HERE, '..', 'vocal_melody'))
import text_player as TP  # noqa: E402
import word_table as WT  # noqa: E402
from abc_to_ktab import parse_abc  # noqa: E402


def swaralipi_notes(song):
    """[(rel, start matra, length, syllable start?, lyric, line, grace?)]"""
    doc, lines = TP.load(f'data/intermediate_data/swaralipi/{song}.json')
    order = TP.singing_order(lines)
    out, t = [], 0.0
    for li, ci in order:
        sw, ly = lines[li]
        p = TP.parse_cell(sw[ci])
        lyr = ly[ci] if ci < len(ly) else ''
        if not p['notes']:
            if out: out[-1][2] += 1
            t += 1; continue
        share = 1 / len(p['notes'])
        for k, (semi, octv, graces) in enumerate(p['notes']):
            # the lyric row decides: a syllable starts where its cell has one (even on a "-" cell);
            # "৹ও"-like cells (a vowel sung on, continuing the syllable) may be written either way
            lt = lyr.replace('\u200d', '').replace('\u200c', '').replace('\u200e', '').strip().strip('"')
            syl = k == 0 and bool(lt) and not lt.startswith('৹')
            if k == 0 and lt.startswith('৹') and lt.strip('৹'):
                syl = None                       # optional: either way agrees
            core = lt.strip('৹')
            if syl and (re.fullmatch(r'[\u0985-\u0994]', core) or                  # a lone vowel: ও-ই, পা-ই
                        re.fullmatch(r'[\u0995-\u09b9\u09dc-\u09df\u09ce]\u09cd?', core)):  # a bare consonant: মো-র
                syl = None                       # the drafts join these to the syllable before
            for gs, go in graces:                # a grace note: may or may not be in the draft
                out.append([gs + 12 * go, t + k * share, 0.0, False, '', li, True])
            out.append([semi + 12 * octv, t + k * share, share, syl, lyr.replace('৹', '') if k == 0 else '', li, False])
        t += 1
    return out


def draft_notes(abc):
    txt = open(abc).read()
    m = re.search(r'^N:.*?Sa = ([A-G])([#b]?)', txt, re.M)
    sa = 60 + ('C D EF G A B'.index(m.group(1)) + {'#': 1, 'b': -1, '': 0}[m.group(2)] if m else 0)
    names, stz = WT.draft_stanzas(abc)
    _, st = parse_abc(txt)
    out, b = [], 0.0
    for s, sn, name in zip(st, stz, names):
        k = 0
        for ln in s:
            for e in ln:
                n = e['eighths'] / 2
                if e['kind'] == 'note':
                    out.append([e['midi'] - sa, b, n, bool(sn[k]['syl']), sn[k]['syl'], name]); k += 1
                b += n
    return out


def merge_repeats(X, grace_col=None):
    """a note repeating the pitch before it without a new syllable is the same sung note
    (re-struck in one source, held in the other): merge it into the note before"""
    out = []
    for x in X:
        g = grace_col is not None and x[grace_col]
        prev = next((y for y in reversed(out) if not (grace_col is not None and y[grace_col])), None)
        if not g and prev is not None and prev[0] == x[0] and not x[3] and (grace_col is None or not out[-1][grace_col]):
            prev[2] = x[1] + x[2] - prev[1]
            continue
        out.append(list(x))
    return out


def align(A, B, grace, sa=None, sb=None):
    """global alignment of pitch sequences A (swaralipi, grace[i] marks its grace notes) and B;
    [(i or None, j or None)]. With syllable flags sa / sb, a pair that also agrees on whether a
    syllable starts scores a little more: among repeated pitches the syllables pick the pairing."""
    n, m = len(A), len(B)
    def sc(i, j):
        if A[i] == B[j]:
            if grace[i]: return 1
            bonus = 0.5 if sa is not None and (sa[i] is None or bool(sa[i]) == bool(sb[j])) else 0
            return 2 + bonus
        return -3 if grace[i] else -1
    gapA = lambda i: 0 if grace[i] else -1                   # leaving out a swaralipi note
    S = np.zeros((n + 1, m + 1))
    for i in range(1, n + 1): S[i, 0] = S[i - 1, 0] + gapA(i - 1)
    S[0, :] = -np.arange(m + 1)
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            S[i, j] = max(S[i - 1, j - 1] + sc(i - 1, j - 1), S[i - 1, j] + gapA(i - 1), S[i, j - 1] - 1)
    i, j, path = n, m, []
    while i or j:
        if i and j and S[i, j] == S[i - 1, j - 1] + sc(i - 1, j - 1):
            path.append((i - 1, j - 1)); i -= 1; j -= 1
        elif i and S[i, j] == S[i - 1, j] + gapA(i - 1):
            path.append((i - 1, None)); i -= 1
        else:
            path.append((None, j - 1)); j -= 1
    return path[::-1]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('song')
    ap.add_argument('--abc')
    a = ap.parse_args()
    abc = a.abc or f'data/intermediate_data/abc/{a.song}/v1.abc'
    S = merge_repeats(swaralipi_notes(a.song), grace_col=6)
    D = merge_repeats(draft_notes(abc))
    # the draft's key: its stated Sa may be missing or wrong (older drafts were transposed), so take
    # the transposition under which most of its notes match the swaralipi in order
    import difflib
    sp = [x[0] for x in S if not x[6]]
    def score(sh):
        return sum(b.size for b in difflib.SequenceMatcher(None, sp, [x[0] + sh for x in D], autojunk=False).get_matching_blocks())
    shift = max(range(-24, 25), key=score)
    for x in D:
        x[0] += shift
    path = align([x[0] for x in S], [x[0] for x in D], [x[6] for x in S], [x[3] for x in S], [x[3] for x in D])
    G = {i for i, x in enumerate(S) if x[6]}
    # a syllable the draft puts on a grace note belongs to the swaralipi's next main note
    for k, (i, j) in enumerate(path):
        if i in G and j is not None and D[j][3]:
            nxt = next(((i2, j2) for i2, j2 in path[k + 1:] if i2 is not None and i2 not in G), None)
            if nxt and nxt[1] is not None and not D[nxt[1]][3]:
                D[nxt[1]][3] = True; D[nxt[1]][4] = D[j][4]; D[j][3] = False
    main_n = sum(1 for x in S if not x[6])
    graces_in = sum(1 for i, j in path if i in G and j is not None and S[i][0] == D[j][0])
    same = sum(1 for i, j in path if i is not None and i not in G and j is not None and S[i][0] == D[j][0])
    sub = [(i, j) for i, j in path if i is not None and i not in G and j is not None and S[i][0] != D[j][0]]
    only_s = [i for i, j in path if j is None and i not in G]
    only_d = [j for i, j in path if i is None]
    pairs = [(i, j) for i, j in path if i is not None and i not in G and j is not None and S[i][0] == D[j][0]]
    # rhythm: position within the matra, and the time between consecutive matched notes
    in_matra = sum(1 for i, j in pairs if abs((S[i][1] % 1) - (D[j][1] % 1)) < 1e-6)
    gaps = [(S[i2][1] - S[i1][1]) - (D[j2][1] - D[j1][1]) for (i1, j1), (i2, j2) in zip(pairs, pairs[1:])]
    same_gap = sum(1 for g in gaps if abs(g) < 1e-6)
    for i, j in pairs:
        if S[i][3] is None: S[i][3] = D[j][3]
    syl_both = sum(1 for i, j in pairs if S[i][3] and D[j][3])
    syl_s = sum(1 for i, j in pairs if S[i][3] and not D[j][3])
    syl_d = sum(1 for i, j in pairs if D[j][3] and not S[i][3])

    sg = lambda r: WT.sg(r)
    lines = [f'# {a.song}: ABC draft against the swaralipi text, note by note', '',
             f'- draft: `{abc}` (transposed {shift:+d} semitones to match); swaralipi: `data/intermediate_data/swaralipi/{a.song}.json`',
             f'- swaralipi notes in singing order: {main_n} main + {len(G)} grace; draft notes: {len(D)} '
             f'({graces_in} of them play a swaralipi grace note as a full note)', '',
             '| | count | share |', '|---|---|---|',
             f'| same pitch | {same} | {same / main_n:.0%} of the swaralipi, {(same + graces_in) / len(D):.0%} of the draft (with graces) |',
             f'| other pitch | {len(sub)} | |',
             f'| in the swaralipi only | {len(only_s)} | |',
             f'| in the draft only | {len(only_d)} | |',
             f'| same place in the matra (matched notes) | {in_matra} / {len(pairs)} | {in_matra / max(1, len(pairs)):.0%} |',
             f'| same time to the next matched note | {same_gap} / {len(gaps)} | {same_gap / max(1, len(gaps)):.0%} |',
             f'| syllable starts on both | {syl_both} | |',
             f'| syllable in the swaralipi only | {syl_s} | |',
             f'| syllable in the draft only | {syl_d} | |', '',
             '## Differences in order', '',
             '| swaralipi | lyric | draft | draft syllable | section |', '|---|---|---|---|---|']
    for i, j in path:
        if i in G and (j is None or S[i][0] == D[j][0]):
            continue                             # a grace note: left out, or played as a note
        if i is not None and j is not None and S[i][0] == D[j][0] and S[i][3] == D[j][3]:
            continue
        sv = f'{sg(S[i][0])}' if i is not None else '—'
        lyr = S[i][4] if i is not None else ''
        dv = f'{sg(D[j][0])}' if j is not None else '—'
        ds = D[j][4] if j is not None else ''
        sec = D[j][5] if j is not None else ''
        kind = ''
        if i is not None and j is not None and S[i][0] == D[j][0]:
            kind = ' (syllable differs)'
        lines.append(f'| {sv}{kind} | {lyr} | {dv} | {ds} | {sec} |')
    out = f'data/intermediate_data/comparison/{a.song}_{os.path.basename(abc)[:-4]}_swaralipi_check.md'
    open(out, 'w').write('\n'.join(lines) + '\n')
    print('\n'.join(lines[:16]))
    print(f'... {len(lines) - 18} differences listed -> {out}')


if __name__ == '__main__':
    main()
