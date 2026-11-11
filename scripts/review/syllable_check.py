#!/usr/bin/env python3
"""Are a draft's syllables on the notes the swaralipi puts them on?

    python scripts/review/syllable_check.py [rs000842 ...]     (default: every draft with an SNLTR swaralipi)
        -> data/intermediate_data/comparison/syllable_check.csv  (one row per flagged spot)

The SNLTR swaralipi (swara_abc.song_events) gives each note and the syllable sung from it. Its notes
are aligned to the tab's notes in played order (pitch classes, the swaralipi's own transposition,
gaps allowed for ornaments and repeats the other lacks; repeated notes are not merged, since syllables
sit on them). At every pair of notes with the same pitch class:
  missing    the swaralipi starts a syllable there, the tab does not
  extra      the tab starts a syllable there, the swaralipi does not
  different  both start one, and the tab's text is unlike the swaralipi's (romanized) syllable
Agreement = share of those pairs where the two agree. Two or more problems in a row are flagged (a
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
                        out.append((rt.get(base, base), syl.text.strip() if first else None, ev.pos))
                        first = False
    return out


def check(s, kpath, abc_path, T):
    song = ktab.parse_file(kpath)
    lines = open(kpath, encoding='utf-8').read().split('\n')
    tn = tab_notes(song)
    # the meant notes (as source_check: not the neighbour a missing tine is played on)
    _, stanzas = RC.A.parse_abc(open(abc_path, encoding='utf-8').read())
    shift = RC.A.plan([[e['midi'] for ln in st for e in ln if e['kind'] == 'note'] for st in stanzas], T)[0]
    meant = [e['midi'] + shift[si] for si, st in enumerate(stanzas) for ln in st for e in ln if e['kind'] == 'note']
    tp = meant if len(meant) == len(tn) else [n[0] for n in tn]
    ev = S.song_events(s)[2]
    sp = [e['midi'] for e in ev]
    best = None
    for sh in SC.best_shifts(tp, sp):
        pair, score = SC.align([p % 12 for p in tp], [(p + sh) % 12 for p in sp])
        if best is None or score > best[1]:
            best = (pair, score, sh)
    pair, _, sh = best
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
    return agree, len(compared), Counter(x for x in compared if x != 'ok'), flags


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
                      different=c['different'], pipeline=r[3], flagged=len(flags))
        allflags += flags
    return per, allflags


def main():
    per, allflags = results(sys.argv[1:] or None)
    for s, d in sorted(per.items(), key=lambda x: x[1].get('agree', -1)):
        if 'error' in d:
            print(f"{s}: ERROR {d['error']}"); continue
        print(f"{s}: {d['agree']}% of {d['paired']} paired notes agree ({d['pipeline']}); missing {d['missing']}, "
              f"extra {d['extra']}, different {d['different']}; {d['flagged']} flagged (in runs)")
    out = 'data/intermediate_data/comparison/syllable_check.csv'
    with open(out, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['song', 'kind', 'tab', 'tab_syllable', 'swaralipi_syllable', 'context', 'ktab'])
        w.writeheader(); w.writerows(allflags)
    with open('data/intermediate_data/comparison/syllable_agreement.csv', 'w', newline='') as f:
        csv.writer(f).writerows([['song', 'syllable_agreement_pct']] +
                                sorted((s, d['agree']) for s, d in per.items() if 'agree' in d))
    by = {}
    for d in per.values():
        if 'agree' in d:
            by.setdefault(d['pipeline'], []).append(d['agree'])
    print('\n' + '; '.join(f'{p}: {len(v)} drafts, mean {sum(v) / len(v):.0f}%' for p, v in by.items()))
    print(f'{len(per)} drafts, {len(allflags)} flagged spots -> {out}')


if __name__ == '__main__':
    main()
