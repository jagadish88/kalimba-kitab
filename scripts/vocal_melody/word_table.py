#!/usr/bin/env python3
"""Word-by-word notes of a song from every source: the ABC draft, piano rolls and sung renditions.

    python scripts/vocal_melody/word_table.py rs000864
    python scripts/vocal_melody/word_table.py rs000864 --abc data/intermediate_data/abc/rs000864/v1.abc

Reads
  * the draft: data/intermediate_data/abc/<id>/v1.abc (Sa = C4)
  * piano rolls: data/intermediate_data/piano_roll/<id>/*_notes.csv (extract_piano_roll.py)
  * renditions: data/intermediate_data/vocal_melody/<id>/*_notes.csv (extract_vocal_melody.py)
and writes data/intermediate_data/comparison/<id>_words.md and .csv: one row per word of the draft,
its notes in sargam, and for every other source the notes it plays or sings over that word.

Correspondence
  * piano roll: per stanza (P: section), the stretch of the roll with the most notes in common with
    the draft, matched note for note (pitch with octave); Sa = the transposition sharing most notes.
  * renditions: stanzas found in order by align_with_draft.py, then the LCS of scale degrees.
A source's column shows its notes from the first to the last note matched in that word;
"=" marks a piano-roll word identical to the draft, "·" a word nothing could be matched to.
"""
import argparse
import csv
import difflib
import glob
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'piano_lesson_to_ktab'))
sys.path.insert(0, HERE)
from abc_to_ktab import parse_abc  # noqa: E402
import align_with_draft as A  # noqa: E402

DEG = 'S r R g G m M P d D n N'.split()


def sg(rel):
    return DEG[rel % 12] + ("'" * (rel // 12) if rel >= 12 else "," * (-(rel // 12)) if rel < 0 else "")


def draft_stanzas(abc):
    txt = open(abc).read()
    names = [l[2:].strip() for l in txt.splitlines() if l.startswith('P:')]
    _, st = parse_abc(txt)
    out = []
    for s in st:
        notes, word = [], -1
        for ln in s:
            for e in ln:
                if e['kind'] != 'note':
                    continue
                t = e.get('tok')
                if t and t[0] not in ('_', '*'):
                    if t[1] or word < 0:
                        word += 1
                    notes.append(dict(rel=e['midi'] - 60, word=word, syl=t[0]))
                else:
                    notes.append(dict(rel=e['midi'] - 60, word=max(word, 0), syl=''))
        out.append(notes)
    return names, out


def song_scale(song):
    for r in csv.DictReader(open('data/raw_data/metadata/scale_catalog.csv')):
        if r['song_id'] == song and r['method'] == 'read':
            return ' '.join(d for d in DEG if r[d] == '1')
    return 'S R G m P D N'



def lcs_map(a, b):
    n, m = len(a), len(b)
    L = np.zeros((n + 1, m + 1), dtype=np.int32)
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            L[i, j] = L[i - 1, j - 1] + 1 if a[i - 1] == b[j - 1] else max(L[i - 1, j], L[i, j - 1])
    mp, i, j = {}, n, m
    while i and j:
        if a[i - 1] == b[j - 1]:
            mp[i - 1] = j - 1; i -= 1; j -= 1
        elif L[i - 1, j] >= L[i, j - 1]:
            i -= 1
        else:
            j -= 1
    return mp


def label_of(path, titles):
    src = os.path.basename(path).split('_')[1]
    t = titles.get(src, src)
    for name in ('Jayati', 'Lopamudra', 'Indrani', 'Srabani', 'Sraboni', 'Hemanta', 'Rupankar', 'Arup Paul', 'Kanika',
                 'Rezwana', 'Debabrata', 'Srikanto', 'Swagatalakshmi'):
        if name.lower() in t.lower():
            return f'{name} ({src})'
    return src


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('song')
    ap.add_argument('--abc')
    a = ap.parse_args()
    song = a.song
    abc = a.abc or f'data/intermediate_data/abc/{song}/v1.abc'
    names, stz = draft_stanzas(abc)
    titles = {r['source_id']: r['title'] for r in csv.DictReader(open('sources/sources.csv'))}
    scale = song_scale(song)
    cols = []                                   # (label, function(stanza k, draft indices) -> text)

    for pr in sorted(glob.glob(f'data/intermediate_data/piano_roll/{song}/*_notes.csv')):
        rows = list(csv.DictReader(open(pr)))
        midis = [int(r['midi']) for r in rows]
        # the roll's Sa: the transposition under which it shares the most notes with the draft
        # (a scale fit alone can't tell e.g. C with tivra Ma from G major)
        whole = [n['rel'] for notes in stz for n in notes]
        base = max(range(int(min(midis)) - 12, int(max(midis)) + 1),
                   key=lambda b: sum(x.size for x in difflib.SequenceMatcher(
                       None, whole, [m - b for m in midis], autojunk=False).get_matching_blocks()))
        P = [m - base for m in midis]
        maps, pos = [], 0
        for notes in stz:
            d = [n['rel'] for n in notes]
            best = None
            for j in range(pos, max(pos + 1, len(P) - len(d) // 2)):
                w = P[j:j + int(len(d) * 1.3) + 5]
                for shift in (0, 12, -12):                                 # the roll may sit an octave off
                    sm = difflib.SequenceMatcher(None, [x + shift for x in d], w, autojunk=False)
                    m = sum(b.size for b in sm.get_matching_blocks())
                    if best is None or m > best[0]:
                        best = (m, j, sm)
            m, j, sm = best
            mp = {b.a + k: j + b.b + k for b in sm.get_matching_blocks() for k in range(b.size)}
            maps.append(mp)
            if mp:
                pos = max(mp.values()) + 1
        def piano_col(k, idx, P=P, maps=maps):
            hit = [maps[k][i] for i in idx if i in maps[k]]
            return ' '.join(sg(P[q]) for q in range(min(hit), max(hit) + 1)) if hit else '·'
        cols.append((f'Piano roll, {label_of(pr, titles)}', piano_col, True))

    for vn in sorted(glob.glob(f'data/intermediate_data/vocal_melody/{song}/*_notes.csv')):
        stanzas, wl, S, T, E, bounds = A.load(abc, vn)
        full = []
        for r in csv.DictReader(open(vn)):
            v = int(r['semitones_from_sa'])
            if full and v == full[-1][0] and float(r['start']) - full[-1][2] < 0.06:
                full[-1][2] = float(r['end']); continue
            full.append([v, float(r['start']), float(r['end'])])
        out, _ = A.align(stanzas, S, bounds)
        per = []
        for k, notes in enumerate(stz):
            if k not in out:
                per.append({}); continue
            x, y = out[k]
            seg = list(range(bounds[x], bounds[y]))
            mp = lcs_map([n['rel'] % 12 for n in notes], [S[q] for q in seg])
            per.append({i: seg[jj] for i, jj in mp.items()})
        def voc_col(k, idx, per=per, full=full):
            hit = [per[k][i] for i in idx if i in per[k]]
            return ' '.join(sg(full[q][0]) for q in range(min(hit), max(hit) + 1)) if hit else '·'
        cols.append((label_of(vn, titles), voc_col, False))

    os.makedirs('data/intermediate_data/comparison', exist_ok=True)
    head = ['Stanza', 'Word', 'Draft (MIDI + swaralipi)'] + [c[0] for c in cols]
    md = ['| ' + ' | '.join(head) + ' |', '|' + '---|' * len(head)]
    rows_csv = []
    for k, (name, notes) in enumerate(zip(names, stz)):
        words = {}
        for i, n in enumerate(notes):
            w = words.setdefault(n['word'], dict(syl=[], idx=[]))
            if n['syl']:
                w['syl'].append(n['syl'])
            w['idx'].append(i)
        for wi in sorted(words):
            w = words[wi]
            draft = ' '.join(sg(notes[i]['rel']) for i in w['idx'])
            vals = []
            for label, fn, is_piano in cols:
                v = fn(k, w['idx'])
                same = v.replace("'", '').replace(',', '') == draft.replace("'", '').replace(',', '')
                vals.append(v + (' =' if is_piano and same else ''))
            row = [name if wi == min(words) else '', '-'.join(w['syl']) or '(held)', draft] + vals
            md.append('| ' + ' | '.join(row) + ' |')
            rows_csv.append([name, '-'.join(w['syl']), draft] + [fn(k, w['idx']) for _, fn, _ in cols])
    mdp = f'data/intermediate_data/comparison/{song}_words.md'
    open(mdp, 'w').write('\n'.join(md) + '\n')
    with open(mdp[:-3] + '.csv', 'w', newline='') as f:
        w = csv.writer(f); w.writerow(['stanza', 'word', 'draft'] + [c[0] for c in cols]); w.writerows(rows_csv)
    print(f'{len(rows_csv)} words, {len(cols)} sources -> {mdp}')


if __name__ == '__main__':
    main()
