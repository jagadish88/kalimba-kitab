#!/usr/bin/env python3
"""Sort the checks' flags into likely errors and likely variants: the review list.

    python scripts/review/triage.py    -> data/intermediate_data/comparison/review_list.csv (+ a summary)

Reads source_check.csv and syllable_check.csv (run those first) and decides per flag:
  note, strong                      likely error: two independent sources agree on another note
  note, weak, a source agrees       likely variant: another independent source plays the tab's note
  note, weak, none agrees           check (one source only: the roll reader and a MIDI arrangement err too)
  rhythm                            the piano roll's timing of that syllable decides: as long as in the
                                    tab -> likely variant (the tab's source and the roll agree); as long
                                    as in the swaralipi -> likely error; no roll or neither -> check
  octave, MIDI-based draft          variant: the MIDI (raw data) plays it in that octave
  octave, stanza moved to fit       converter: the stanza was moved an octave to fit the kalimba
  octave, other drafts              likely error
  syllable (missing/extra/different) likely error; "check" in drafts whose syllables were placed by
                                    hand (older reflowed drafts, piano lessons)
Each row has the bar (of the draft's ABC), the tab's line:column, the evidence and the tab context.
Decisions already recorded in data/intermediate_data/comparison/review_decisions.csv are applied
(their flags are marked reviewed and left out of the counts).
"""
import collections
import csv
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'scripts', 'review'))
sys.path.insert(0, os.path.join(ROOT, 'scripts', 'swaralipi_player'))
sys.path.insert(0, os.path.join(ROOT, 'scripts', 'piano_lesson_to_ktab'))
import roundtrip_check as RC  # noqa: E402
import note_align as NA  # noqa: E402
import abc_offkey_score as OS  # noqa: E402
import ktab  # noqa: E402
from ktab.model import Note  # noqa: E402

COMP = 'data/intermediate_data/comparison'
HAND = {'reflow_ktab', 'piano_lesson_to_ktab', 'hand_edit'}


def note_bars(abc_text):
    _, items = OS.read_abc(abc_text)
    bars, b, prev_tie, prev_m = [], 1, False, None
    for it in items:
        if it[0] != 'line':
            continue
        for e in it[1]:
            if e[0] == 'bar':
                b += 1; continue
            if e[0] == 'note':
                if prev_tie and prev_m == e[1]:
                    prev_tie = e[3]; continue
                bars.append(b); prev_tie, prev_m = e[3], e[1]
    return bars


def tab_notes(song):
    """played order: [pitch, starts syllable, (line, col), beats incl. holds]"""
    rt = {}
    for a in (song.headers.get('retune') or '').split(','):
        if ':' in a:
            x, y = a.strip().split(':')
            px, py = RC.parse_note(x), RC.parse_note(y)
            if px >= 0:
                rt[px] = py
    out = []
    for p in song.performance():
        for it in p.line.items:
            for syl in getattr(it, 'syllables', []):
                first = True
                for ev in syl.events:
                    if isinstance(ev, Note) and not ev.is_rest:
                        b = 60 + ev.semitone
                        out.append([rt.get(b, b), first, ev.pos, float(ev.beats)]); first = False
                    elif out:
                        out[-1][3] += float(ev.beats)
    return out


def roll_judge(s, tn, flags_at):
    """rhythm flags: -> {tab index: ('variant'|'error'|'check', evidence)} using the piano roll's timing"""
    import glob
    rolls = glob.glob(f'{ROOT}/data/intermediate_data/piano_roll/{s}/*_notes.csv')
    if not rolls:
        return {}
    rows = [r for r in csv.DictReader(open(rolls[0])) if float(r['duration']) >= 0.06]
    rp = [int(r['midi']) for r in rows]
    ron = [float(r['onset']) for r in rows]
    rdur = [float(r['duration']) for r in rows]
    tp = [n[0] for n in tn]
    pair, sh = NA.align(tp, rp, [n[3] for n in tn], rdur)
    same = [pair[i] is not None and tp[i] % 12 == (rp[pair[i]] + sh) % 12 for i in range(len(tp))]
    starts = [i for i in range(len(tp)) if tn[i][1] and same[i]]
    spans = []
    for a, b in zip(starts, starts[1:]):
        tb = sum(n[3] for n in tn[a:b])
        rs = ron[pair[b]] - ron[pair[a]]
        if tb > 0 and rs > 0:
            spans.append((a, b, tb, rs))
    out = {}
    for k, (a, b, tb, rs) in enumerate(spans):
        if a not in flags_at:
            continue
        near = sorted(x[3] / x[2] for x in spans[max(0, k - 20):k + 21])
        spb = near[len(near) // 2]                    # seconds per beat here
        roll_beats = rs / spb
        sw_beats = flags_at[a]
        if 0.7 <= roll_beats / tb <= 1.43:
            out[a] = ('likely variant', f'the roll plays it {roll_beats:.2g} beats long, as the tab ({tb:g})')
        elif sw_beats and 0.7 <= roll_beats / sw_beats <= 1.43:
            out[a] = ('likely error', f'the roll plays it {roll_beats:.2g} beats long, as the swaralipi ({sw_beats:.2g}); tab {tb:g}')
        else:
            out[a] = ('check', f'the roll plays it {roll_beats:.2g} beats; tab {tb:g}, swaralipi {sw_beats:.2g}')
    return out


def main():
    os.chdir(ROOT)
    last, rbp, songs = RC.drafts()
    src = list(csv.DictReader(open(f'{COMP}/source_check.csv', encoding='utf-8')))
    syl = list(csv.DictReader(open(f'{COMP}/syllable_check.csv', encoding='utf-8')))
    decided = {}
    if os.path.exists(f'{COMP}/review_decisions.csv'):
        for r in csv.DictReader(open(f'{COMP}/review_decisions.csv', encoding='utf-8')):
            decided[(r['song'], r['tab'], r['kind'])] = r['decision']
    pipeline = {}
    for s in songs:
        r = last[s]
        p = r[3]
        if r[5].endswith('.ktab'):
            p = rbp.get(r[5], r)[3] if p == 'reflow_ktab' else p
        pipeline[s] = r[3] if r[3] in HAND else p
    out = []
    for s in songs:
        r = last[s]
        sr = RC.source_of(s, rbp, r)
        if not sr:
            continue
        song = ktab.parse_file(r[2])
        tn = tab_notes(song)
        nb = note_bars(open(sr[0], encoding='utf-8').read())
        pos_idx = {}
        for i, n in enumerate(tn):
            pos_idx.setdefault(f'{n[2][0]}:{n[2][1]}', i)
        bar = lambda pos: nb[pos_idx[pos]] if pos in pos_idx and len(nb) == len(tn) else ''
        rflags = {}
        for f in syl:
            if f['song'] == s and f['kind'] == 'rhythm' and f['tab'] in pos_idx:
                m = re.search(r'swaralipi ([\d.e+-]+) beats', f['swaralipi_syllable'])
                rflags[pos_idx[f['tab']]] = float(m.group(1)) if m else None
        judged = roll_judge(s, tn, rflags) if rflags else {}
        for f in (x for x in src if x['song'] == s):
            if f['kind'] == 'strong':
                v, ev = 'likely error', f"two sources: {f['sources']}"
            elif f['kind'] == 'weak':
                v, ev = (('likely variant', f"{f['agreeing']} plays the tab's note; {f['sources']}") if f['agreeing']
                         else ('check', f"one source only (the roll reader and the MIDI arrangement have their own errors): {f['sources']}"))
            else:
                v, ev = 'variant', f"MIDI octave: {f['sources']}"
            out.append(dict(song=s, bar=bar(f['tab']), tab=f['tab'], kind='note ' + f['kind'], verdict=v,
                            evidence=ev, context=f['context']))
        for f in (x for x in syl if x['song'] == s):
            k = f['kind']
            if k == 'rhythm':
                i = pos_idx.get(f['tab'])
                v, ev = judged.get(i, ('check', 'no piano roll to decide'))
                ev = f"{f['swaralipi_syllable']}; {ev}"
            elif k.startswith('octave'):
                if 'stanza moved' in k:
                    v = 'converter'
                elif pipeline.get(s) == 'midi_to_ktab':
                    v = 'variant'
                else:
                    v = 'likely error'
                ev = f['swaralipi_syllable']
            else:
                v = 'check' if pipeline.get(s) in HAND else 'likely error'
                ev = f"tab '{f['tab_syllable']}', swaralipi '{f['swaralipi_syllable']}'"
                k = 'syllable ' + k
            out.append(dict(song=s, bar=bar(f['tab']), tab=f['tab'], kind=k, verdict=v, evidence=ev, context=f['context']))
    for o in out:
        d = decided.get((o['song'], o['tab'], o['kind']))
        o['reviewed'] = d or ''
    order = {'likely error': 0, 'check': 1, 'converter': 2, 'likely variant': 3, 'variant': 4}
    out.sort(key=lambda o: (bool(o['reviewed']), order[o['verdict']], o['song'],
                            int(o['tab'].split(':')[0]), int(o['tab'].split(':')[1])))
    with open(f'{COMP}/review_list.csv', 'w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=['song', 'bar', 'tab', 'kind', 'verdict', 'evidence', 'reviewed', 'context'])
        w.writeheader(); w.writerows(out)
    open_ = [o for o in out if not o['reviewed']]
    c = collections.Counter(o['verdict'] for o in open_)
    bars = collections.defaultdict(set)
    for o in open_:
        bars[o['verdict']].add((o['song'], o['bar'] or o['tab']))
    print(f'{len(out)} flags ({len(out) - len(open_)} reviewed); open, by verdict:')
    for v in order:
        print(f'  {v:15s} {c[v]:4d} flags in {len(bars[v]):4d} bars, {len({b[0] for b in bars[v]})} drafts')
    err = collections.Counter(o['song'] for o in open_ if o['verdict'] == 'likely error')
    print('likely errors, most:', err.most_common(10))
    print(f'-> {COMP}/review_list.csv')


if __name__ == '__main__':
    main()
