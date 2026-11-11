#!/usr/bin/env python3
"""PDF table: every kalimba tab draft, sorted by how ready it is for data/dataset/.

    python scripts/review/readiness_table.py        -> data/intermediate_data/comparison/draft_readiness.pdf

Per song (its latest draft in data/intermediate_data/ktab/ktab_catalog.csv):
  MIDI       a MIDI file in data/raw_data/midi/midi_catalog.csv
  Swaralipi  SNLTR text (data/intermediate_data/swaralipi/<id>.json), else Geetabitan PDF, else --
  Roll       share of the draft's notes Arup Paul's piano roll plays, in order (comparison/roll_vs_abc.csv)
  Scale      the note the tab puts Sa on (the ABC's key + the catalog's --transpose; the kalimba is in C)
  Retuned    the tab's @retune header, as tine -> new note
  Off notes  notes with no tine after that retuning (played a semitone off), count and share
  Lyrics     share of the tab's words that are words of the Geetabitan lyrics
Tiers: A = off notes <= 2%, <= 1 retune, roll >= 94%; B = <= 5%, <= 2 retunes, roll >= 87% or no roll;
C = the rest; done = in data/dataset/. Within a tier: roll - 3 x off% - 4 x retunes (+5 for MIDI notes).
"""
import csv
import os
import re
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'scripts', 'piano_lesson_to_ktab'))
import abc_to_ktab as A  # noqa: E402

NAMES = 'C C# D Eb E F F# G Ab A Bb B'.split()
WHITE = [0, 2, 4, 5, 7, 9, 11]
TINES = [p for p in range(60, 89) if p % 12 in WHITE]          # 17 tines, C4..E6


def tine_label(p):
    i = TINES.index(p)
    return f"{i % 7 + 1}{chr(39) * (i // 7)}"


def parse_note(s):
    """'A#5', 'Bb4', 'F#4' -> MIDI number"""
    m = re.match(r'^([A-G])([#b]?)(-?\d)$', s.strip())
    base = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}[m.group(1)]
    return 12 * (int(m.group(3)) + 1) + base + {'#': 1, 'b': -1, '': 0}[m.group(2)]


def key_tonic(abc):
    m = re.search(r'^K:\s*([A-G][b#]?)', abc, re.M)
    if not m:
        return 0
    return (NAMES.index(m.group(1)) if m.group(1) in NAMES else
            {'Db': 1, 'D#': 3, 'Gb': 6, 'G#': 8, 'A#': 10, 'Cb': 11, 'E#': 5, 'B#': 0, 'Fb': 4}.get(m.group(1), 0))


def fmt_flags(f):
    if not f:
        return '--'
    return f"{f['strong']}/{f['weak'] + f['octave']}"


def key(s):
    return re.sub(r'[^a-z]', '', s.lower())


def tex(s):
    return s.replace('&', r'\&').replace('#', r'\#').replace('%', r'\%').replace('_', r'\_')


def main():
    os.chdir(ROOT)
    rows = list(csv.reader(open('data/intermediate_data/ktab/ktab_catalog.csv', encoding='utf-8')))
    last = {r[0]: r for r in rows[1:] if r and r[0].startswith('rs')}
    done = [r[0] for r in csv.reader(open('data/dataset/dataset_catalog.csv', encoding='utf-8')) if r and r[0].startswith('rs')]
    titles = {r[0]: r[1] for r in csv.reader(open('data/raw_data/text/catalog.csv', encoding='utf-8')) if r}
    midi = {r[0] for r in csv.reader(open('data/raw_data/midi/midi_catalog.csv', encoding='utf-8')) if len(r) > 2 and r[2].endswith('.mid')}
    roll = {r['song']: int(r['draft_pct']) for r in csv.DictReader(open('data/intermediate_data/comparison/roll_vs_abc.csv'))}
    sa = 'data/intermediate_data/comparison/syllable_agreement.csv'
    sylag = {r['song']: int(r['syllable_agreement_pct']) for r in csv.DictReader(open(sa))} if os.path.exists(sa) else {}
    flags = {}
    sc = 'data/intermediate_data/comparison/source_check.csv'
    if os.path.exists(sc):
        for f in csv.DictReader(open(sc, encoding='utf-8')):
            flags.setdefault(f['song'], {'strong': 0, 'weak': 0, 'octave': 0})[f['kind']] += 1
    out = []
    for s in sorted(set(last) | set(done)):
        r = last.get(s)
        info = dict(s=s, title=titles.get(s, s), midi='yes' if s in midi else '--',
                    sw='SNLTR' if os.path.exists(f'data/intermediate_data/swaralipi/{s}.json') else
                       'Geetabitan' if os.path.exists(f'data/raw_data/swaralipi/{s}.pdf') else '--',
                    roll=roll.get(s), scale='', ret=[], bad=None, n=0, lyr=None, tier='done' if s in done else '?')
        if r:
            kt = open(r[2], encoding='utf-8').read()
            t = re.search(r'^@title:\s*(.+)$', kt, re.M)
            if t and not re.match(r'rs\d+$', t.group(1).strip()):
                info['title'] = t.group(1).strip()
            ver = r[1] if r[1] != 'v1' else ''
            if ver:
                info['title'] += f' ({ver})'
            m = re.search(r'--transpose (-?\d+)', r[7])
            src = r[5]
            rt = re.search(r'^@retune:\s*(.+)$', kt, re.M)
            pairs = []
            if rt:
                for a in rt.group(1).split(','):
                    if ':' in a:
                        x, y = a.strip().split(':')
                        pairs.append((None, x, y))
            if m and src.endswith('.abc') and os.path.exists(src):
                T = int(m.group(1))
                abc = open(src, encoding='utf-8').read()
                info['scale'] = 'Sa = ' + NAMES[(key_tonic(abc) + T) % 12]
                _, st = A.parse_abc(abc)
                ps = [e['midi'] + T for x in st for ln in x for e in ln if e['kind'] == 'note']
                tines = set(TINES)
                lab = []
                for _, x, y in pairs:
                    try:
                        px, py = parse_note(x), parse_note(y)
                    except Exception:
                        px = py = None
                    if px in tines:
                        tines.discard(px); tines.add(py)
                        lab.append(f"{tine_label(px)}$\\to${tex(y)}")
                info['ret'] = lab
                info['bad'] = sum(1 for p in ps if p not in tines)
                info['n'] = len(ps)
            body = kt.split('\n\n', 1)[-1]
            lp = f'data/raw_data/text/lyrics/{s}.txt'
            if os.path.exists(lp):
                pw = set(key(w) for w in re.split(r'[\s\-,.;:!?]+', open(lp, encoding='utf-8').read()) if key(w))
                ws = [key(''.join(re.findall(r'\(([^:()]*):', w))) for w in re.findall(r'(?:\([^)]*\))+', body)]
                ws = [w for w in ws if w]
                info['lyr'] = round(100 * sum(w in pw for w in ws) / len(ws)) if ws else None
        if info['tier'] != 'done':
            if info['bad'] is None:
                info['tier'] = 'C'
            else:
                bp = 100 * info['bad'] / max(1, info['n'])
                nr = len(info['ret'])
                rl = info['roll']
                fl = flags.get(s, {})
                if bp <= 2 and nr <= 1 and rl is not None and rl >= 94 and not fl.get('strong'):
                    info['tier'] = 'A'
                elif bp <= 5 and nr <= 2 and (rl is None or rl >= 87):
                    info['tier'] = 'B'
                else:
                    info['tier'] = 'C'
        bp = 100 * (info['bad'] or 0) / max(1, info['n'])
        info['score'] = (info['roll'] if info['roll'] is not None else 85) - 3 * bp - 4 * len(info['ret']) + (5 if info['midi'] == 'yes' else 0)
        out.append(info)
    order = {'done': 0, 'A': 1, 'B': 2, 'C': 3}
    out.sort(key=lambda x: (order[x['tier']], -x['score']))
    color = {'done': 'cyan!12', 'A': 'green!15', 'B': 'yellow!20', 'C': 'red!12'}
    cnt = {t: sum(1 for x in out if x['tier'] == t) for t in order}
    lines = []
    for i, x in enumerate(out, 1):
        bad = '--' if x['bad'] is None else f"{x['bad']} ({100 * x['bad'] / max(1, x['n']):.1f}\\%)"
        lines.append(f"\\rowcolor{{{color[x['tier']]}}} {i} & {tex(x['title'])} & {x['s']} & {x['midi']} & {x['sw']} & "
                     f"{'--' if x['roll'] is None else str(x['roll']) + chr(92) + '%'} & {tex(x['scale']) or '--'} & "
                     f"{', '.join(x['ret']) or 'none'} & {bad} & {'--' if x['lyr'] is None else str(x['lyr']) + chr(92) + '%'} & {fmt_flags(flags.get(x['s']))} & {str(sylag[x['s']]) + chr(92) + '%' if x['s'] in sylag else '--'} & {x['tier']}\\\\")
    doc = r"""\documentclass[9pt]{article}
\usepackage[a4paper,landscape,margin=0.9cm]{geometry}
\usepackage{longtable,booktabs,xcolor,colortbl}
\usepackage[T1]{fontenc}\usepackage{lmodern}
\renewcommand{\arraystretch}{1.12}
\begin{document}
\begin{center}{\Large\bfseries Kalimba tab drafts: readiness for the main dataset}\\[3pt]
{\small %d songs: done %d, A %d, B %d, C %d. Sorted by tier, then by roll match $-$ 3$\times$off-note \%% $-$ 4$\times$retuned tines (+5 for MIDI notes).}\end{center}
\noindent{\small\textbf{Tier A}: off notes $\le$2\%%, at most 1 retuned tine, roll match $\ge$94\%%, no strong source flag.
\textbf{B}: off notes $\le$5\%%, $\le$2 retunes, roll match $\ge$87\%% or no roll. \textbf{C}: the rest. \textbf{done}: in data/dataset/.
\textbf{Roll}: share of the draft's notes Arup Paul's piano roll plays in order. \textbf{Off notes}: notes with no tine after the retuning, played a semitone off.
\textbf{Scale}: the note Sa is on (the kalimba is in C). \textbf{Lyrics}: share of the tab's words that are words of the Geetabitan lyrics.
\textbf{Flags}: places where independent sources disagree with the tab (source\_check.csv): strong (two sources agree on another note) / weak (one source, a run of notes). Tier A needs no strong flag.
\textbf{Syl}: share of the tab's syllables on the notes the SNLTR swaralipi puts them on (syllable\_check.py).}
\vspace{4pt}
\footnotesize\setlength{\tabcolsep}{4pt}
\begin{longtable}{r l l c l r l l r r r r c}
\toprule
\# & Song & id & MIDI & Swaralipi & Roll & Scale & Tines retuned & Off notes & Lyrics & Flags & Syl & Tier\\
\midrule\endhead
""" % (len(out), cnt['done'], cnt['A'], cnt['B'], cnt['C']) + '\n'.join(lines) + '\n\\bottomrule\\end{longtable}\\end{document}\n'
    wd = '/tmp/kk_work/rtable'
    os.makedirs(wd, exist_ok=True)
    open(f'{wd}/readiness.tex', 'w').write(doc)
    r = subprocess.run(['pdflatex', '-interaction=nonstopmode', 'readiness.tex'], cwd=wd, capture_output=True, text=True)
    subprocess.run(['pdflatex', '-interaction=nonstopmode', 'readiness.tex'], cwd=wd, capture_output=True, text=True)
    dst = 'data/intermediate_data/comparison/draft_readiness.pdf'
    if os.path.exists(f'{wd}/readiness.pdf'):
        import shutil
        shutil.copy(f'{wd}/readiness.pdf', dst)
    print(f"{len(out)} songs: " + ', '.join(f'{t} {n}' for t, n in cnt.items()) + f' -> {dst}')
    return out


if __name__ == '__main__':
    main()
