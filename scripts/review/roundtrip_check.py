#!/usr/bin/env python3
"""Round trip: does each ktab draft play exactly the ABC it was made from?

    python scripts/review/roundtrip_check.py [rs000842 ...]     (default: every draft not in data/dataset/)

For each song's latest draft (ktab_catalog.csv; a draft made from another ktab is traced back to the
ABC at the start of the chain):
  expected  the ABC's notes, placed on the kalimba as abc_to_ktab.py places them with the catalog's
            --transpose (its octave shift per stanza, its retuned tines, the notes it plays a semitone off)
  played    the tab parsed by ktab, repeats unfolded (:| and :||), each tine's pitch after @retune
and compares
  pitches   the two pitch sequences, note for note (any difference is an error)
  lengths   each note's length in beats; allowed: a rest after the note merged into its hold, a rest
            dropped at the start, an end hold cut short at the end of a line (reflow's limit)
  syllables which notes start a syllable
  retune    the @retune header against the tines the notes need
Prints one line per song (OK or the first problems, with the tab's line:column) and a summary.
Exit status 1 if any song has a pitch, syllable or retune error.
"""
import csv
import os
import re
import sys
from collections import Counter
from fractions import Fraction as Fr

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'scripts', 'piano_lesson_to_ktab'))
sys.path.insert(0, os.path.join(ROOT, 'src'))
import abc_to_ktab as A  # noqa: E402
import ktab  # noqa: E402
from ktab.model import Note, Hold  # noqa: E402


# drafts that differ from their ABC on purpose (checked by hand): reported, not counted as errors
KNOWN = {
    'rs001381': 'v5+ sings each stanza once, as asked (the ABC repeats them); v6 merges the two sixteenth pairs into eighths',
    'rs001619': 'the tab follows an earlier reading of the piano lesson, not abc v1 (to be settled by ear)',
}


def parse_note(s):
    """'A#5' -> MIDI number; 'F#' (no octave: every such tine) -> pitch class as a negative number - 1"""
    m = re.match(r'^([A-G])([#b]?)(-?\d)?$', s.strip())
    base = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}[m.group(1)] + {'#': 1, 'b': -1, '': 0}[m.group(2)]
    if m.group(3) is None:
        return -1 - base % 12
    return 12 * (int(m.group(3)) + 1) + base


def written_beats(eighths):
    """the length abc_to_ktab writes for a note this long (it rounds what ktab can't write)"""
    beats = Fr(eighths) / 2
    for s in range(0, 5):
        for dot in (1, Fr(3, 2)):
            r = beats - Fr(1, 2 ** s) * dot
            if r >= 0 and r.denominator == 1:
                return beats
    q = round(beats * 4) / Fr(4)
    return q if q > 0 else Fr(1, 4)


def source_of(s, rows_by_path, row):
    """follow made_from back to an ABC: -> (abc path, transpose) or None"""
    seen = set()
    while row and row[2] not in seen:
        seen.add(row[2])
        m = re.search(r'(?:--transpose|best fit) ([+-]?\d+)', row[7])
        if row[5].endswith('.abc'):
            if m:
                return row[5], int(m.group(1))
            if 'abc_to_ktab.py output' in row[7]:
                return row[5], None               # the converter chose the key itself
        row = rows_by_path.get(row[5])
    return None


def expected(abc_text, T):
    _, stanzas = A.parse_abc(abc_text)
    pitches = [[e['midi'] for ln in st for e in ln if e['kind'] == 'note'] for st in stanzas]
    shift, retune, play_as, _ = A.plan(pitches, T)
    notes = []                                    # (pitch, beats, rest after (beats), starts syllable)
    for si, st in enumerate(stanzas):
        first_note, seen_syl = len(notes), False
        for ln in st:
            for e in ln:
                if e['kind'] == 'rest':
                    if notes:
                        notes[-1][2] += written_beats(e['eighths'])
                    continue
                m = e['midi'] + shift[si]
                tok = e.get('tok', ('*',))
                starts = tok[0] not in ('_', '*') and bool(re.sub(r'[:()\r\n?]', '', tok[0]).strip())
                if starts and not seen_syl:      # notes before a stanza's first syllable join it
                    seen_syl = True
                    if first_note < len(notes):
                        notes[first_note][3] = True
                        starts = False
                notes.append([play_as.get(m, m), written_beats(e['eighths']), Fr(0), starts])
    # a note with no syllable before the first syllable is held into it (abc_to_ktab's 'waiting')
    return notes, retune


def played(song):
    rt = {}
    for a in (song.headers.get('retune') or '').split(','):
        if ':' in a:
            x, y = a.strip().split(':')
            px, py = parse_note(x), parse_note(y)
            if px < 0:                            # every tine of that note: all octaves
                for o in range(60, 89):
                    if o % 12 == -1 - px:
                        rt[o] = o + ((-1 - py) - (-1 - px))
            else:
                rt[px] = py
    out = []                                      # (pitch, beats, starts syllable, pos, last of its line)
    for p in song.performance():
        line_notes = []
        for item in p.line.items:
            for k, syl in enumerate(getattr(item, 'syllables', [])):
                first = True
                for ev in syl.events:
                    if isinstance(ev, Note):
                        if ev.is_rest:
                            if line_notes:
                                line_notes[-1][1] += ev.beats
                            continue
                        base = 60 + ev.semitone
                        line_notes.append([rt.get(base, base), ev.beats, first, ev.pos, False])
                        first = False
                    elif isinstance(ev, Hold) and line_notes:
                        line_notes[-1][1] += ev.beats
        if line_notes:
            line_notes[-1][4] = True
        out += line_notes
    return out, rt


def check(s, kpath, abc_path, T):
    errs, warns = [], []
    song = ktab.parse_file(kpath)
    exp, retune = expected(open(abc_path, encoding='utf-8').read(), T)
    got, rt = played(song)
    # retune header vs the tines the notes need (retune: sounding pitch -> tine label)
    need = set(retune)                            # pitches that need a retuned tine
    have = set(rt.values())
    if need != have:
        errs.append(f"@retune gives {sorted(A.name(p) for p in have)}, the notes need {sorted(A.name(p) for p in need)}")
    ep = [n[0] for n in exp]
    gp = [n[0] for n in got]
    if ep != gp:
        i = next((k for k, (a, b) in enumerate(zip(ep, gp)) if a != b), min(len(ep), len(gp)))
        where = f"tab {got[i][3][0]}:{got[i][3][1]}" if i < len(got) else 'end of tab'
        errs.append(f"pitches differ at note {i + 1} ({where}): ABC {' '.join(A.name(p) for p in ep[i:i + 4])} | "
                    f"tab {' '.join(A.name(p) for p in gp[i:i + 4])} ({len(ep)} vs {len(gp)} notes)")
        return errs, warns
    bad_len = []
    for k, (e, g) in enumerate(zip(exp, got)):
        want, rest = e[1], e[2]
        have_b = g[1]
        if have_b == want or have_b == want + rest:
            continue
        if g[4] and have_b < want + rest and have_b >= 3:     # end hold cut at a line end
            continue
        if k == 0 and have_b > want:                  # notes held into the first syllable
            continue
        bad_len.append(f"{g[3][0]}:{g[3][1]} {A.name(g[0])} {have_b} beats, ABC {want}" + (f"+{rest} rest" if rest else ''))
    if bad_len:
        warns.append(f"{len(bad_len)} note length(s) differ, e.g. " + '; '.join(bad_len[:3]))
    es = [k for k, n in enumerate(exp) if n[3]]
    gs = [k for k, n in enumerate(got) if n[2]]
    if es != gs:
        a, b = set(es), set(gs)
        miss, extra = sorted(a - b), sorted(b - a)
        k = (miss + extra + [0])[0]
        where = f"tab {got[k][3][0]}:{got[k][3][1]}" if k < len(got) else ''
        errs.append(f"syllables start on different notes: {len(miss)} missing, {len(extra)} extra (first near note {k + 1}, {where})")
    return errs, warns


def drafts():
    """-> (latest catalog row per song, rows by ktab path, songs not in data/dataset/)"""
    rows = list(csv.reader(open('data/intermediate_data/ktab/ktab_catalog.csv', encoding='utf-8')))
    rows_by_path = {r[2]: r for r in rows[1:] if r and len(r) > 7}
    last = {r[0]: r for r in rows[1:] if r and r[0].startswith('rs')}
    ds = {r[0] for r in csv.reader(open('data/dataset/dataset_catalog.csv', encoding='utf-8')) if r}
    return last, rows_by_path, sorted(s for s in last if s not in ds)


def results(songs=None):
    """-> {song: (status, detail)}; status: exact, lengths, error, known, skip"""
    os.chdir(ROOT)
    last, rows_by_path, all_songs = drafts()
    out = {}
    for s in songs or all_songs:
        r = last[s]
        src = source_of(s, rows_by_path, r)
        if not src or not os.path.exists(src[0]):
            out[s] = ('skip', 'no ABC with a --transpose in the catalog chain'); continue
        try:
            errs, warns = check(s, r[2], *src)
        except Exception as e:                    # a tab that does not parse is an error too
            errs, warns = [f'{type(e).__name__}: {str(e)[:150]}'], []
        if errs and s in KNOWN:
            out[s] = ('known', KNOWN[s])
        elif errs:
            out[s] = ('error', f'{r[2]} <- {src[0]} ' + ' | '.join(errs + warns))
        elif warns:
            out[s] = ('lengths', f'{r[2]} <- {src[0]} ' + ' | '.join(warns))
        else:
            out[s] = ('exact', '')
    return out


def main():
    res = results(sys.argv[1:] or None)
    for s, (st, d) in res.items():
        print(f'{s}: ' + {'exact': 'OK', 'lengths': 'lengths', 'error': 'ERROR', 'known': 'KNOWN', 'skip': 'SKIP'}[st]
              + (f' {d}' if d else ''))
    c = Counter(st for st, _ in res.values())
    print(f"\n{len(res)} drafts: {c['exact']} exact, {c['lengths']} with note-length differences only, "
          f"{c['error']} with errors, {c['skip'] + c['known']} skipped or known")
    sys.exit(1 if c['error'] else 0)


if __name__ == '__main__':
    main()
