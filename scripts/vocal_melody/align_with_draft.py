#!/usr/bin/env python3
"""Check an ABC draft against a sung rendition: stanzas found by LCS, then matched by note pairs.

    python scripts/vocal_melody/align_with_draft.py data/intermediate_data/abc/rs000864/v1.abc \
        data/intermediate_data/vocal_melody/rs000864/rs000864_src001749_notes.csv

The sung notes come from extract_vocal_melody.py (semitones from the singer's Sa); the draft is
read with Sa = C4. Pitches are compared as scale degrees (octave ignored), repeats merged.

  1. Stanzas: the singing is cut at breath points (gaps >= 0.25 s) and split, in order, into the
     draft's P: sections, maximizing each stanza's LCS minus the matches expected by chance
     (1/7 per sung note). Sung stretches can stay unassigned (a singer's lead-in or extra repeats).
  2. Match: inside each stanza, the LCS of consecutive note pairs. Single notes match by chance
     too easily; pairs do not. --shuffle N repeats the run with the sung notes shuffled N times
     (same notes, no melody) to show the chance level.
"""
import argparse, csv, re, sys, random
import numpy as np
sys.path.insert(0, 'scripts/piano_lesson_to_ktab')
from abc_to_ktab import parse_abc

def merge(x): return [v for i, v in enumerate(x) if i == 0 or v != x[i - 1]]

def lcs(a, b):
    """length of the LCS and, for each a[i], whether it is in one LCS"""
    n, m = len(a), len(b)
    L = np.zeros((n + 1, m + 1), dtype=np.int32)
    for i in range(1, n + 1):
        ai = a[i - 1]; row, prev = L[i], L[i - 1]
        for j in range(1, m + 1):
            row[j] = prev[j - 1] + 1 if ai == b[j - 1] else (row[j - 1] if row[j - 1] > prev[j] else prev[j])
    used = [False] * n; i, j = n, m
    while i and j:
        if a[i - 1] == b[j - 1]: used[i - 1] = True; i -= 1; j -= 1
        elif L[i - 1, j] >= L[i, j - 1]: i -= 1
        else: j -= 1
    return int(L[n, m]), used

def load(abc, notes, shuffle=None):
    txt = open(abc).read()
    names = [l[2:].strip() for l in txt.splitlines() if l.startswith('P:')]
    _, st = parse_abc(txt)
    wl = [re.sub(r'[-_|*]+', ' ', l[2:]).split() for l in txt.splitlines() if l.startswith('w:')]
    stanzas, k = [], 0
    for name, s in zip(names, st):
        seq, line_of = [], []
        for ln in s:
            q = merge([e['midi'] - 60 for e in ln if e['kind'] == 'note'])
            seq += q; line_of += [k] * len(q); k += 1
        merged = [(v, lo) for i, (v, lo) in enumerate(zip(seq, line_of)) if i == 0 or v != seq[i - 1]]
        stanzas.append(dict(name=name, seq=[v % 12 for v, _ in merged], line_of=[lo for _, lo in merged]))
    rows = list(csv.DictReader(open(notes)))
    vals = [int(r['semitones_from_sa']) for r in rows]
    if shuffle is not None:
        random.seed(shuffle); random.shuffle(vals)
    S, T, E, gaps = [], [], [], []
    for r, v in zip(rows, vals):
        s, e = float(r['start']), float(r['end'])
        if S and v == S[-1] and s - E[-1] < 0.06: E[-1] = e; continue
        if S: gaps.append(s - E[-1])
        S.append(v % 12); T.append(s); E.append(e)
    # segment boundaries: breath points (gap >= 0.25 s)
    bounds = [0] + [i + 1 for i, g in enumerate(gaps) if g >= 0.25] + [len(S)]
    return stanzas, wl, S, T, E, bounds

def align(stanzas, S, bounds):
    """in-order segmentation of the sung notes into stanzas, maximizing the sum of (LCS - chance matches)"""
    K, B = len(stanzas), len(bounds)
    cache = {}
    def score(k, x, y):
        if (k, x, y) not in cache:
            d = stanzas[k]['seq']; seg = S[bounds[x]:bounds[y]]
            l, _ = lcs(d, seg)
            cache[(k, x, y)] = l - len(seg) / 7.0, l          # LCS minus the matches expected by chance
        return cache[(k, x, y)]
    NEG = -1e9
    dp = np.full((K + 1, B), NEG); dp[0, :] = 0                      # sung notes before stanza 0 are free
    back = {}
    for k in range(K):
        for x in range(B):
            if dp[k, x] == NEG: continue
            for y in range(x + 1, B):
                if bounds[y] - bounds[x] > 4 * len(stanzas[k]['seq']): break
                v = dp[k, x] + score(k, x, y)[0]
                if v > dp[k + 1, y]: dp[k + 1, y] = v; back[(k + 1, y)] = (k, x)
        for x in range(1, B):                                          # unassigned sung segment
            if dp[k + 1, x - 1] > dp[k + 1, x]: dp[k + 1, x] = dp[k + 1, x - 1]; back[(k + 1, x)] = (k + 1, x - 1)
    y = int(np.argmax(dp[K])); k = K; out = {}
    while k > 0:
        pk, px = back[(k, y)]
        if pk == k - 1: out[k - 1] = (px, y)
        k, y = pk, px
    return out, score

def bigrams(x): return [(a, b) for a, b in zip(x, x[1:])]


def run(abc, notes, shuffle=None, detail=False):
    stanzas, wl, S, T, E, bounds = load(abc, notes, shuffle)
    out, _ = align(stanzas, S, bounds)
    tot = dict(d1=0, l1=0, d2=0, l2=0); rows = []
    for k, st in enumerate(stanzas):
        if k not in out:
            rows.append((st['name'], None)); continue
        x, y = out[k]; seg = S[bounds[x]:bounds[y]]
        l1, used = lcs(st['seq'], seg); l2, _ = lcs(bigrams(st['seq']), bigrams(seg))
        d1, d2 = len(st['seq']), len(st['seq']) - 1
        tot['d1'] += d1; tot['l1'] += l1; tot['d2'] += d2; tot['l2'] += l2
        lines = []
        if detail:
            for ln in sorted(set(st['line_of'])):
                idx = [i for i, lo in enumerate(st['line_of']) if lo == ln]
                lines.append((ln, ' '.join(wl[ln][:4]), sum(used[i] for i in idx), len(idx)))
        rows.append((st['name'], dict(t0=T[bounds[x]], t1=E[bounds[y] - 1], notes=l1 / d1, pairs=l2 / d2, lines=lines)))
    return rows, tot['l1'] / tot['d1'], tot['l2'] / tot['d2']


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('abc'); ap.add_argument('notes')
    ap.add_argument('--shuffle', type=int, default=5, help='shuffled runs for the chance level (default 5)')
    a = ap.parse_args()
    rows, n1, n2 = run(a.abc, a.notes, detail=True)
    for name, r in rows:
        if r is None:
            print(f'{name:9s} not found'); continue
        print(f"{name:9s} {r['t0']:6.1f}-{r['t1']:6.1f}s   notes {r['notes']:4.0%}   note pairs {r['pairs']:4.0%}")
        for ln, words, got, n in r['lines']:
            print(f"      line {ln:2d} {words[:30]:30s} {got:2d}/{n:2d}")
    print(f'TOTAL  notes {n1:.0%}   note pairs {n2:.0%}')
    if a.shuffle:
        ch = [run(a.abc, a.notes, shuffle=s)[1:] for s in range(1, a.shuffle + 1)]
        print(f"chance (sung notes shuffled, {a.shuffle} runs): notes {np.mean([c[0] for c in ch]):.0%}   "
              f"note pairs {np.mean([c[1] for c in ch]):.0%}")
