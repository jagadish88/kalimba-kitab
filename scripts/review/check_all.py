#!/usr/bin/env python3
"""All draft checks at once, against a saved baseline: fails only when something got worse.

    python scripts/review/check_all.py                    # check; exit 1 on a regression
    python scripts/review/check_all.py --update-baseline  # accept the current results as the baseline

Per draft (the latest ktab of each song in ktab_catalog.csv; songs in data/dataset/ get the lint only):
  roundtrip  roundtrip_check.py: exact / lengths / error / known / skip
  sources    source_check.py: strong, weak, octave flags
  syllables  syllable_check.py: % of syllables on the swaralipi's notes (drafts with an SNLTR swaralipi)
  lint       the tab parses; counts of notes off the 17 tines, rests, capitals inside a line, a
             placeholder title (@title: rs...), a retune note in @subtitle without an @retune header
Baseline: data/intermediate_data/comparison/check_baseline.json.
Fails on: a draft that was exact and is not; a new round-trip error; more strong flags; syllable
agreement down 2 points or more; more lint problems; a new draft that is not clean (round trip exact
or known, no lint problems, no strong flags). Warns on: more weak flags, syllable agreement down 1.
The git pre-commit hook (scripts/review/pre-commit) runs this when drafts or scripts are committed.
"""
import argparse
import csv
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'scripts', 'review'))
import roundtrip_check as RC  # noqa: E402
import source_check as SC  # noqa: E402
import syllable_check as SY  # noqa: E402
import ktab  # noqa: E402
from ktab.model import Note  # noqa: E402

BASELINE = 'data/intermediate_data/comparison/check_baseline.json'
RANK = {'exact': 0, 'known': 0, 'lengths': 1, 'skip': 1, 'error': 2}


def lint(path):
    out = dict(parse=0, off_tine=0, rests=0, mid_capitals=0, placeholder_title=0, retune_header=0)
    try:
        song = ktab.parse_file(path)
    except Exception:
        out['parse'] = 1
        return out
    for n in song.notes():
        if isinstance(n, Note):
            if n.is_rest:
                out['rests'] += 1
            elif not 0 <= n.scale_index <= 16:      # 17 tines: 1 .. 3''
                out['off_tine'] += 1
    text = open(path, encoding='utf-8').read()
    body = text.split('\n\n', 1)[-1]
    for line in body.split('\n'):
        words = re.findall(r'(?:\([^)]*\))+', line)
        out['mid_capitals'] += sum(1 for w in words[1:] if re.match(r'\(\s*[A-Z]', w))
    if re.search(r'^@title:\s*rs\d+\s*$', text, re.M):
        out['placeholder_title'] = 1
    if re.search(r'^@subtitle:.*retune', text, re.M) and not re.search(r'^@retune:', text, re.M):
        out['retune_header'] = 1
    return out


def current():
    os.chdir(ROOT)
    last, _, songs = RC.drafts()
    ds = [r[0] for r in csv.reader(open('data/dataset/dataset_catalog.csv', encoding='utf-8')) if r and r[0].startswith('rs')]
    rt = RC.results()
    sc, _ = SC.results()
    sy, _ = SY.results()
    res = {}
    for s in songs:
        d = dict(roundtrip=rt.get(s, ('skip', ''))[0])
        if s in sc and 'error' not in sc[s]:
            d.update(strong=sc[s]['strong'], weak=sc[s]['weak'], octave=sc[s]['octave'])
        if s in sy and 'agree' in sy[s]:
            d['syllables'] = sy[s]['agree']
        d['lint'] = lint(last[s][2])
        res[s] = d
    for s in ds:                                   # finished tabs: the lint only
        rows = [r for r in csv.reader(open('data/dataset/dataset_catalog.csv', encoding='utf-8')) if r and r[0] == s]
        p = next((c for c in rows[-1] if c.endswith('.ktab')), None) if rows else None
        if p and os.path.exists(p):
            res[f'dataset:{s}'] = dict(lint=lint(p))
    return res, rt


def compare(base, cur, rt):
    fails, warns = [], []
    for s, d in sorted(cur.items()):
        b = base.get(s)
        lnew = {k: v for k, v in d['lint'].items() if v}
        if b is None:
            if (d.get('roundtrip', 'exact') not in ('exact', 'known') or lnew or d.get('strong', 0)):
                fails.append(f"{s}: new draft not clean: round trip {d.get('roundtrip')}, lint {lnew}, strong flags {d.get('strong', 0)}")
            continue
        if 'roundtrip' in d and RANK[d['roundtrip']] > RANK[b.get('roundtrip', 'exact')]:
            fails.append(f"{s}: round trip {b.get('roundtrip')} -> {d['roundtrip']}: {rt.get(s, ('', ''))[1][:200]}")
        if d.get('strong', 0) > b.get('strong', 0):
            fails.append(f"{s}: strong source flags {b.get('strong', 0)} -> {d['strong']}")
        if d.get('weak', 0) > b.get('weak', 0):
            warns.append(f"{s}: weak source flags {b.get('weak', 0)} -> {d['weak']}")
        if 'syllables' in d and 'syllables' in b:
            drop = b['syllables'] - d['syllables']
            if drop >= 2:
                fails.append(f"{s}: syllables on the swaralipi's notes {b['syllables']}% -> {d['syllables']}%")
            elif drop >= 1:
                warns.append(f"{s}: syllables {b['syllables']}% -> {d['syllables']}%")
        for k, v in d['lint'].items():
            if v > b['lint'].get(k, 0):
                fails.append(f"{s}: lint {k} {b['lint'].get(k, 0)} -> {v}")
    for s in base:
        if s not in cur:
            warns.append(f'{s}: no longer checked (removed or moved to the dataset)')
    return fails, warns


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--update-baseline', action='store_true')
    a = ap.parse_args()
    cur, rt = current()
    if a.update_baseline or not os.path.exists(os.path.join(ROOT, BASELINE)):
        json.dump(cur, open(os.path.join(ROOT, BASELINE), 'w'), indent=1, sort_keys=True)
        n = sum(1 for s in cur if not s.startswith('dataset:'))
        print(f'baseline saved: {n} drafts, {len(cur) - n} finished tabs -> {BASELINE}')
        return
    base = json.load(open(os.path.join(ROOT, BASELINE)))
    fails, warns = compare(base, cur, rt)
    for w in warns:
        print('warning:', w)
    for f in fails:
        print('FAIL:', f)
    print(f"\n{len(cur)} tabs checked against the baseline: {len(fails)} regression(s), {len(warns)} warning(s)"
          + ('' if not fails else '\n(fix them, or accept intended changes with --update-baseline)'))
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()
