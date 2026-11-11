#!/usr/bin/env python3
"""Where do the independent sources disagree with a draft? Note by note, with the tab's line:column.

    python scripts/review/source_check.py [rs000842 ...]       (default: every draft not in data/dataset/)
        -> data/intermediate_data/comparison/source_check.csv  (one row per flagged spot)

The draft's notes are taken in played order as roundtrip_check.py expands them (each with its place
in the tab). Each source the draft was NOT made from is aligned to them:
  roll       Arup Paul's piano roll (data/intermediate_data/piano_roll/<id>/*_notes.csv)
  midi       the MIDI melody (midi_swara_abc.midi_bars), unless the draft's notes came from it
  swaralipi  the SNLTR swaralipi (swara_abc.song_events), unless the draft's notes came from it
Repeated notes are merged on both sides (a roll re-strikes what a tab holds). Each source gets its
own transposition (the one whose pitch classes line up best); then a global alignment (match, other
note, or a gap: repeats and ornaments the draft lacks) pairs each draft note with the source's note.
Flags, per draft note:
  strong   two sources agree on another note than the tab's
  weak     one source has another note, and so do its neighbours (two or more in a row): a run, not a
           single ornament
  octave   the MIDI has the same note an octave away from where the rest of the song sits (one note
           out of place; the roll is not used for octaves: its reader often takes the other hand)
"""
import csv
import glob
import os
import re
import sys
from collections import Counter

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'scripts', 'review'))
sys.path.insert(0, os.path.join(ROOT, 'scripts', 'swaralipi_player'))
import roundtrip_check as RC  # noqa: E402
import ktab  # noqa: E402

NAMES = 'C C# D D# E F F# G G# A A# B'.split()


def runs(ps):
    """merge repeated pitches: -> (pitches, index of the first original note of each run)"""
    out, idx = [], []
    for i, p in enumerate(ps):
        if not out or p != out[-1]:
            out.append(p); idx.append(i)
    return out, idx


def best_shifts(a, b):
    """pitch-class shifts s (b + s ~ a) ranked by how well the pitch-class histograms line up"""
    ha, hb = Counter(p % 12 for p in a), Counter(p % 12 for p in b)
    sc = sorted(((sum(ha[c] * hb[(c - s) % 12] for c in range(12)), s) for s in range(12)), reverse=True)
    return [s for _, s in sc[:2]]


def align(a, b):
    """global alignment of pitch-class sequences a (draft) and b (source): -> list, per a index, of the
    b index paired with it (None: gap); match +2, other note -1, gap -1"""
    n, m = len(a), len(b)
    G = -1
    prev = [j * G for j in range(m + 1)]
    back = []
    for i in range(1, n + 1):
        cur = [i * G] + [0] * m
        bk = [2] + [0] * m                     # 0 diag, 1 up (gap in b), 2 left (gap in a)
        ai = a[i - 1]
        for j in range(1, m + 1):
            d = prev[j - 1] + (2 if ai == b[j - 1] else -1)
            u = prev[j] + G
            l = cur[j - 1] + G
            if d >= u and d >= l:
                cur[j], bk[j] = d, 0
            elif u >= l:
                cur[j], bk[j] = u, 1
            else:
                cur[j], bk[j] = l, 2
        back.append(bk)
        prev = cur
    pair = [None] * n
    i, j = n, m
    while i > 0 and j > 0:
        k = back[i - 1][j]
        if k == 0:
            pair[i - 1] = j - 1; i -= 1; j -= 1
        elif k == 1:
            i -= 1
        else:
            j -= 1
    return pair, prev[m]


def source_pitches(s, pipeline):
    src = {}
    rolls = glob.glob(f'data/intermediate_data/piano_roll/{s}/*_notes.csv')
    if rolls:
        rows = list(csv.DictReader(open(rolls[0])))
        src['roll'] = [int(r['midi']) for r in rows if float(r['duration']) >= 0.06]
    if pipeline != 'midi_to_ktab' and os.path.exists(f'data/raw_data/midi/{s}.mid'):
        try:
            import midi_swara_abc as M
            bars = M.midi_bars(s)[0]
            src['midi'] = [p for b in bars for _, p, tied in b if p is not None and not tied]
        except Exception:
            pass
    if pipeline != 'swaralipi_to_ktab' and os.path.exists(f'data/intermediate_data/swaralipi/{s}.json'):
        try:
            import swara_abc as S
            src['swaralipi'] = [e['midi'] for e in S.song_events(s)[2]]
        except Exception:
            pass
    return src


def check(s, kpath, abc_path, T, pipeline):
    song = ktab.parse_file(kpath)
    tab_lines = open(kpath, encoding='utf-8').read().split('\n')
    got, _ = RC.played(song)
    # the notes the song means, not the neighbour the kalimba plays for a note it has no tine for
    # (those semitone-off notes are known and listed by the catalog; the sources should agree with
    # the meant note). Same order and length as the tab's notes when the round trip is exact.
    _, stanzas = RC.A.parse_abc(open(abc_path, encoding='utf-8').read())
    shift = RC.A.plan([[e['midi'] for ln in st for e in ln if e['kind'] == 'note'] for st in stanzas], T)[0]
    meant = [e['midi'] + shift[si] for si, st in enumerate(stanzas) for ln in st for e in ln if e['kind'] == 'note']
    draft = meant if len(meant) == len(got) else [g[0] for g in got]
    dr, didx = runs(draft)
    votes = [dict() for _ in dr]               # run index -> {source: pitch}
    octv = [dict() for _ in dr]
    used = []
    for name, ps in source_pitches(s, pipeline).items():
        sr, _ = runs(ps)
        if len(sr) < 10:
            continue
        best = None
        for sh in best_shifts(dr, sr):
            pair, score = align([p % 12 for p in dr], [(p + sh) % 12 for p in sr])
            if best is None or score > best[1]:
                best = (pair, score, sh)
        pair, score, sh = best
        matched = sum(1 for i, j in enumerate(pair) if j is not None and dr[i] % 12 == (sr[j] + sh) % 12)
        if matched < 0.5 * len(dr):                 # this source is another tune or another song
            used.append(f'{name} ignored ({100 * matched // len(dr)}% only)')
            continue
        used.append(f'{name} {100 * matched // len(dr)}%')
        offs = Counter((sr[j] + sh - dr[i]) for i, j in enumerate(pair) if j is not None and dr[i] % 12 == (sr[j] + sh) % 12)
        base = offs.most_common(1)[0][0] if offs else 0
        for i, j in enumerate(pair):
            if j is None:
                continue
            q = sr[j] + sh
            votes[i][name] = q % 12
            if name == 'midi' and q % 12 == dr[i] % 12 and abs((q - base) - dr[i]) == 12:
                # octaves: the MIDI only (the roll reader often takes a note from the other hand)
                octv[i][name] = q - base
    flags = []
    differs = [any(v != dr[i] % 12 for v in votes[i].values()) for i in range(len(dr))]
    for i in range(len(dr)):
        other = {k: v for k, v in votes[i].items() if v != dr[i] % 12}
        kind = None
        if len(other) >= 2 and len(set(other.values())) == 1:
            kind = 'strong'
        elif other and ((i > 0 and differs[i - 1]) or (i + 1 < len(dr) and differs[i + 1])):
            kind = 'weak'
        if octv[i] and not (i > 0 and octv[i - 1]) and not (i + 1 < len(dr) and octv[i + 1]):
            kind = kind or 'octave'           # one note out of place (a whole phrase moved is the arranger's choice)
        elif octv[i]:
            octv[i] = {}
        if kind:
            g = got[didx[i]]
            ln = tab_lines[g[3][0] - 1] if g[3][0] - 1 < len(tab_lines) else ''
            flags.append(dict(song=s, kind=kind, tab=f'{g[3][0]}:{g[3][1]}', note=RC.A.name(dr[i]),
                              context=ln[max(0, g[3][1] - 40):g[3][1] + 20].strip(),
                              sources='; '.join(f'{k} {NAMES[v]}' for k, v in sorted(other.items())) +
                                      ('; '.join(f'{k} octave {RC.A.name(v)}' for k, v in octv[i].items())),
                              ktab=kpath))
    return flags, used, len(dr)


def results(songs=None):
    """-> ({song: dict(notes, sources, strong, weak, octave)}, flags)"""
    os.chdir(ROOT)
    last, rows_by_path, all_songs = RC.drafts()
    per, allflags = {}, []
    for s in songs or all_songs:
        r = last[s]
        src = RC.source_of(s, rows_by_path, r)
        if not src:
            continue
        pipeline = r[3] if r[3] in ('midi_to_ktab', 'swaralipi_to_ktab') else \
            (rows_by_path.get(r[5], r)[3] if r[5].endswith('.ktab') else r[3])
        try:
            flags, used, n = check(s, r[2], *src, pipeline)
        except Exception as e:
            per[s] = dict(error=f'{type(e).__name__}: {str(e)[:120]}'); continue
        c = Counter(f['kind'] for f in flags)
        per[s] = dict(notes=n, sources=used, strong=c['strong'], weak=c['weak'], octave=c['octave'],
                      strong_lines=sorted({f['tab'].split(':')[0] for f in flags if f['kind'] == 'strong'}, key=int))
        allflags += flags
    return per, allflags


def main():
    per, allflags = results(sys.argv[1:] or None)
    for s, d in per.items():
        if 'error' in d:
            print(f"{s}: ERROR {d['error']}"); continue
        print(f"{s}: {d['notes']} notes; sources: {', '.join(d['sources']) or 'none'}; strong {d['strong']}, "
              f"weak {d['weak']}, octave {d['octave']}" + (f"; strong at tab lines {', '.join(d['strong_lines'][:8])}" if d['strong_lines'] else ''))
    out = 'data/intermediate_data/comparison/source_check.csv'
    with open(out, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['song', 'kind', 'tab', 'note', 'sources', 'context', 'ktab'])
        w.writeheader(); w.writerows(allflags)
    tot = Counter(f['kind'] for f in allflags)
    nos = sum(1 for d in per.values() if 'error' not in d and not [u for u in d['sources'] if 'ignored' not in u])
    print(f"\n{len(per)} drafts checked ({nos} with no usable independent source): "
          f"strong {tot['strong']}, weak {tot['weak']}, octave {tot['octave']} -> {out}")


if __name__ == '__main__':
    main()
