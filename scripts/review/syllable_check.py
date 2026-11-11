#!/usr/bin/env python3
"""Are a draft's syllables, note lengths and octaves those of the swaralipi?

    python scripts/review/syllable_check.py [rs000842 ...]     (default: every draft with an SNLTR swaralipi)
        -> data/intermediate_data/comparison/syllable_check.csv  (one row per flagged spot)

The SNLTR swaralipi (swara_abc.song_events) gives each note and the syllable sung from it. Its notes
are aligned to the tab's notes in played order (pitch classes, the swaralipi's own transposition,
gaps allowed for ornaments and repeats the other lacks; repeated notes are not merged, since syllables
sit on them; note lengths break ties where a pitch repeats - note_align.py). At every pair of notes with the same pitch class:
  missing    the swaralipi starts a syllable there, the tab does not
  extra      the tab starts a syllable there, the swaralipi does not
  different  both start one, and the tab's text is unlike the swaralipi's (romanized) syllable
  rhythm     a syllable (from its start to the next syllable's, both paired) lasts much longer or shorter
             in the tab than in the swaralipi: more than 1.6x either way against the local tempo and at
             least a beat apart (splits inside a syllable, ornaments and tempo or metre changes do not count)
  octave     a paired note an octave or more from where the rest of the song sits against the swaralipi
             (labelled when the converter moved that stanza an octave to fit the kalimba)
Agreement = share of those pairs where the syllables agree. Two or more problems in a row are flagged (a
lone one is often a grace note or a held syllable); the CSV has the tab's line:column and context.
"""
import csv
import difflib
import os
import re
import sys
from collections import Counter

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'scripts', 'review'))
sys.path.insert(0, os.path.join(ROOT, 'scripts', 'swaralipi_player'))
import roundtrip_check as RC  # noqa: E402
import source_check as SC  # noqa: E402
import swara_abc as S  # noqa: E402
import note_align as NA  # noqa: E402
import match_snltr as M  # noqa: E402
import ktab  # noqa: E402
from ktab.model import Note, Hold  # noqa: E402


def key(s):
    return re.sub(r'[^a-z]', '', s.lower())


def tab_notes(song):
    """-> [(pitch, syllable text if a syllable starts here else None, (line, col))] in played order"""
    rt = {}
    for a in (song.headers.get('retune') or '').split(','):
        if ':' in a:
            x, y = a.strip().split(':')
            px, py = RC.parse_note(x), RC.parse_note(y)
            if px < 0:
                for o in range(60, 89):
                    if o % 12 == -1 - px:
                        rt[o] = o + ((-1 - py) - (-1 - px))
            else:
                rt[px] = py
    out = []
    for p in song.performance():
        for item in p.line.items:
            for syl in getattr(item, 'syllables', []):
                first = True
                for ev in syl.events:
                    if isinstance(ev, Note) and not ev.is_rest:
                        base = 60 + ev.semitone
                        out.append([rt.get(base, base), syl.text.strip() if first else None, ev.pos, float(ev.beats)])
                        first = False
                    elif out:                     # a hold (or a rest) lengthens the note before it
                        out[-1][3] += float(ev.beats)
    return out


def check(s, kpath, abc_path, T):
    song = ktab.parse_file(kpath)
    lines = open(kpath, encoding='utf-8').read().split('\n')
    tn = tab_notes(song)
    # the meant notes (as source_check: not the neighbour a missing tine is played on)
    _, stanzas = RC.A.parse_abc(open(abc_path, encoding='utf-8').read())
    shift = RC.A.plan([[e['midi'] for ln in st for e in ln if e['kind'] == 'note'] for st in stanzas], T)[0]
    meant = [e['midi'] + shift[si] for si, st in enumerate(stanzas) for ln in st for e in ln if e['kind'] == 'note']
    stanza_of = [si for si, st in enumerate(stanzas) for ln in st for e in ln if e['kind'] == 'note']
    usual_shift = Counter(shift[si] for si in stanza_of).most_common(1)[0][0] if stanza_of else 0
    tp = meant if len(meant) == len(tn) else [n[0] for n in tn]
    if len(meant) != len(tn):
        stanza_of = [0] * len(tn)
    ev = S.song_events(s)[2]
    sp = [e['midi'] for e in ev]
    # pitches and lengths: where a pitch repeats, the note of the right length is paired
    pair, sh = NA.align(tp, sp, [n[3] for n in tn], [e['units'] for e in ev])
    status = []                                   # per tab note: None (not compared), 'ok', or a problem
    for i, j in enumerate(pair):
        if j is None or tp[i] % 12 != (sp[j] + sh) % 12:
            status.append(None); continue
        t_syl, s_syl = tn[i][1], ev[j]['syl']
        if s_syl and not t_syl:
            status.append('missing')
        elif t_syl and not s_syl:
            status.append('extra')
        elif t_syl and s_syl:
            a, b = key(t_syl), key(M.translit(s_syl, final_o=True))
            r = difflib.SequenceMatcher(None, a, b).ratio() if a and b else 1
            # a syllable spelled the Geetabitan way ('bnaadh' for the swaralipi's 'baan') still counts
            status.append('ok' if r >= 0.4 or (a[:1] == b[:1]) else 'different')
        else:
            status.append('ok')
    compared = [x for x in status if x]
    agree = sum(1 for x in compared if x == 'ok') / max(1, len(compared))
    flags = []
    for i, x in enumerate(status):
        if x in (None, 'ok'):
            continue
        near = [status[k] for k in (i - 1, i + 1) if 0 <= k < len(status)]
        if not any(y not in (None, 'ok') for y in near):
            continue
        ln, col = tn[i][2]
        j = pair[i]
        flags.append(dict(song=s, kind=x, tab=f'{ln}:{col}', tab_syllable=tn[i][1] or '',
                          swaralipi_syllable=(M.translit(ev[j]['syl'], final_o=True) if ev[j]['syl'] else ''),
                          context=lines[ln - 1][max(0, col - 40):col + 20].strip(), ktab=kpath))
    flags += rhythm_flags(s, kpath, lines, tn, tp, ev, pair, sh)
    flags += register_flags(s, kpath, lines, tn, tp, sp, pair, sh, stanza_of, shift, usual_shift)
    counts = Counter(x for x in compared if x != 'ok')
    for f in flags:
        if f['kind'] in ('rhythm', 'octave', 'octave (stanza moved to fit the kalimba)'):
            counts[f['kind']] += 1
    return agree, len(compared), counts, flags


def rhythm_flags(s, kpath, lines, tn, tp, ev, pair, sh, lo=0.6, hi=1.67):
    """stretches between two paired notes: the tab's beats against the swaralipi's units, each judged
    against the local tempo (median of the 41 stretches around it); outside lo..hi x is flagged"""
    # anchors: notes paired with the same pitch where the swaralipi starts a syllable (the rhythm of the
    # words; dotted against even splits inside a syllable are performance, not reading)
    anchors, last_j = [], -1
    for i, j in enumerate(pair):
        if (j is not None and j > last_j and tp[i] % 12 == (ev[j]['midi'] + sh) % 12
                and ev[j]['syl'] and tn[i][1]):
            anchors.append((i, j)); last_j = j
    paired_j = {j for j in pair if j is not None}
    spans = []
    for (i0, j0), (i1, j1) in zip(anchors, anchors[1:]):
        # an instrumental passage or a repeat only one side has: structure, not rhythm
        if (sum(1 for i in range(i0, i1) if pair[i] is None) > 3
                or sum(1 for j in range(j0, j1) if j not in paired_j) > 3):
            continue
        tb = sum(n[3] for n in tn[i0:i1])
        su = sum(e['units'] for e in ev[j0:j1])
        if tb > 0 and su > 0:
            spans.append((i0, i1, tb, su, tb / su))
    out = []
    for k, (i0, i1, tb, su, r) in enumerate(spans):
        near = sorted(x[4] for x in spans[max(0, k - 20):k + 21])
        local = near[len(near) // 2]
        q = r / local
        if (q < lo or q > hi) and abs(tb - su * local) >= 1:     # and at least a beat apart
            ln, col = tn[i0][2]
            out.append(dict(song=s, kind='rhythm', tab=f'{ln}:{col}', tab_syllable=tn[i0][1] or '',
                            swaralipi_syllable=f'tab {tb:g} beats, swaralipi {su * local:.2g} beats at this tempo',
                            context=lines[ln - 1][max(0, col - 40):col + 20].strip(), ktab=kpath))
    return out


def register_flags(s, kpath, lines, tn, tp, sp, pair, sh, stanza_of, shift, usual_shift):
    """paired notes an octave (or more) away from where the rest of the song sits against the swaralipi"""
    d = {i: tp[i] - (sp[j] + sh) for i, j in enumerate(pair)
         if j is not None and tp[i] % 12 == (sp[j] + sh) % 12}
    if not d:
        return []
    base = Counter(d.values()).most_common(1)[0][0]
    out = []
    for i, off in sorted(d.items()):
        if off == base:
            continue
        moved = shift[stanza_of[i]] != usual_shift if stanza_of and i < len(stanza_of) else False
        ln, col = tn[i][2]
        out.append(dict(song=s, kind='octave (stanza moved to fit the kalimba)' if moved else 'octave',
                        tab=f'{ln}:{col}', tab_syllable=tn[i][1] or '',
                        swaralipi_syllable=f'{(off - base) // 12:+d} octave(s) from the rest of the song',
                        context=lines[ln - 1][max(0, col - 40):col + 20].strip(), ktab=kpath))
    return out


def results(songs=None):
    """-> ({song: dict(agree %, paired, missing, extra, different, pipeline)}, flags); drafts with an SNLTR swaralipi"""
    os.chdir(ROOT)
    last, rows_by_path, all_songs = RC.drafts()
    songs = songs or [s for s in all_songs if os.path.exists(f'data/intermediate_data/swaralipi/{s}.json')]
    per, allflags = {}, []
    for s in songs:
        r = last[s]
        src = RC.source_of(s, rows_by_path, r)
        if not src:
            continue
        try:
            agree, n, c, flags = check(s, r[2], *src)
        except Exception as e:
            per[s] = dict(error=f'{type(e).__name__}: {str(e)[:120]}'); continue
        per[s] = dict(agree=round(100 * agree), paired=n, missing=c['missing'], extra=c['extra'],
                      different=c['different'], pipeline=r[3], rhythm=c['rhythm'], octave=c['octave'],
                      octave_fit=c['octave (stanza moved to fit the kalimba)'],
                      flagged=sum(1 for f in flags if f['kind'] in ('missing', 'extra', 'different')))
        allflags += flags
    return per, allflags


def main():
    per, allflags = results(sys.argv[1:] or None)
    for s, d in sorted(per.items(), key=lambda x: x[1].get('agree', -1)):
        if 'error' in d:
            print(f"{s}: ERROR {d['error']}"); continue
        print(f"{s}: {d['agree']}% of {d['paired']} paired notes agree ({d['pipeline']}); missing {d['missing']}, "
              f"extra {d['extra']}, different {d['different']}; {d['flagged']} flagged (in runs); "
              f"rhythm {d['rhythm']}, octave {d['octave']}" + (f" (+{d['octave_fit']} in stanzas moved to fit)" if d['octave_fit'] else ''))
    out = 'data/intermediate_data/comparison/syllable_check.csv'
    with open(out, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['song', 'kind', 'tab', 'tab_syllable', 'swaralipi_syllable', 'context', 'ktab'])
        w.writeheader(); w.writerows(allflags)
    with open('data/intermediate_data/comparison/syllable_agreement.csv', 'w', newline='') as f:
        csv.writer(f).writerows([['song', 'syllable_agreement_pct', 'rhythm_flags', 'octave_flags']] +
                                sorted((s, d['agree'], d['rhythm'], d['octave'] + d['octave_fit'])
                                       for s, d in per.items() if 'agree' in d))
    by = {}
    for d in per.values():
        if 'agree' in d:
            by.setdefault(d['pipeline'], []).append(d['agree'])
    print('\n' + '; '.join(f'{p}: {len(v)} drafts, mean {sum(v) / len(v):.0f}%' for p, v in by.items()))
    print(f'{len(per)} drafts, {len(allflags)} flagged spots -> {out}')


if __name__ == '__main__':
    main()
