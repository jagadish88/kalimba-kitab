#!/usr/bin/env python3
"""The review list as a PDF: what to look at in each draft, song by song in readiness order.

    python scripts/review/review_report.py   -> data/intermediate_data/comparison/review_list.pdf

Rows: the open 'likely error' and 'check' flags of review_list.csv (triage.py), grouped by song in
the order of the readiness table (done, A, B, C), each with its bar, the tab's line:column, what was
found and the tab text around it. Variants, converter octave moves and flags already decided in
review_decisions.csv are left out. Record a decision by adding a row (song, tab, kind, decision,
note) to review_decisions.csv; the next triage.py run leaves it out.
"""
import collections
import csv
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'scripts', 'review'))
import readiness_table as RT  # noqa: E402

COMP = 'data/intermediate_data/comparison'


def tex(s):
    s = s.replace('\\', '/')
    for a, b in (('&', r'\&'), ('#', r'\#'), ('%', r'\%'), ('_', r'\_'), ('$', r'\$'), ('{', r'\{'), ('}', r'\}'),
                 ('^', r'\^{}'), ('~', r'\~{}')):
        s = s.replace(a, b)
    return s


def main():
    os.chdir(ROOT)
    order = RT.main()                              # also rebuilds the readiness table
    rank = {x['s']: (i, x) for i, x in enumerate(order)}
    rows = [r for r in csv.DictReader(open(f'{COMP}/review_list.csv', encoding='utf-8'))
            if not r['reviewed'] and r['verdict'] in ('likely error', 'check')]
    by = collections.defaultdict(list)
    for r in rows:
        by[r['song']].append(r)
    parts = []
    for s in sorted(by, key=lambda s: rank.get(s, (999, None))[0]):
        x = rank.get(s, (None, {'title': s, 'tier': '?'}))[1]
        rs = sorted(by[s], key=lambda r: (r['verdict'] != 'likely error', int(r['tab'].split(':')[0]), int(r['tab'].split(':')[1])))
        nerr = len({r['bar'] or r['tab'] for r in rs if r['verdict'] == 'likely error'})
        nchk = len({r['bar'] or r['tab'] for r in rs if r['verdict'] == 'check'})
        parts.append(r'\subsection*{%s \quad{\normalfont\small %s, tier %s: %d bar(s) likely wrong, %d to check}}' %
                     (tex(x['title']), s, x['tier'], nerr, nchk))
        parts.append(r'\begin{longtable}{p{0.6cm} p{1.2cm} p{2.4cm} p{1.7cm} p{8.8cm} p{8.4cm}}')
        parts.append(r'bar & tab & kind & verdict & what was found & tab text\\ \hline\endhead')
        for r in rs:
            parts.append(' & '.join([tex(r['bar']), tex(r['tab']), tex(r['kind']),
                                     r'\textbf{likely error}' if r['verdict'] == 'likely error' else 'check',
                                     tex(r['evidence'][:170]), r'\texttt{\scriptsize ' + tex(r['context'][-70:]) + '}']) + r'\\')
        parts.append(r'\end{longtable}')
    nerr = len({(r['song'], r['bar'] or r['tab']) for r in rows if r['verdict'] == 'likely error'})
    nchk = len({(r['song'], r['bar'] or r['tab']) for r in rows if r['verdict'] == 'check'})
    doc = r"""\documentclass[9pt]{article}
\usepackage[a4paper,landscape,margin=0.9cm]{geometry}
\usepackage{longtable}\usepackage[T1]{fontenc}\usepackage{lmodern}
\setlength{\parindent}{0pt}
\begin{document}
{\Large\bfseries Kalimba tab drafts: what to review}\\[3pt]
{\small %d bars likely wrong and %d bars to check, in %d drafts (songs in readiness order). From the checks:
round trip (tab = its ABC), independent sources (roll, MIDI, swaralipi), syllables, rhythm and octaves
against the swaralipi; sorted by triage.py. \textbf{Likely error}: two sources agree against the tab, the roll
sides with the swaralipi on a syllable's length, or a syllable is off the swaralipi's notes.
\textbf{Check}: one source only, or the syllables were placed by hand. Variants (another source plays the
tab's note) and decisions recorded in review\_decisions.csv are left out. \textbf{tab} = line:column in the ktab file.}
\footnotesize
""" % (nerr, nchk, len(by)) + '\n'.join(parts) + '\n\\end{document}\n'
    wd = '/tmp/kk_work/review_report'
    os.makedirs(wd, exist_ok=True)
    open(f'{wd}/review_list.tex', 'w').write(doc)
    for _ in range(2):
        subprocess.run(['pdflatex', '-interaction=nonstopmode', 'review_list.tex'], cwd=wd, capture_output=True)
    if os.path.exists(f'{wd}/review_list.pdf'):
        import shutil
        shutil.copy(f'{wd}/review_list.pdf', f'{COMP}/review_list.pdf')
    print(f'{nerr} bars likely wrong, {nchk} to check, {len(by)} drafts -> {COMP}/review_list.pdf')


if __name__ == '__main__':
    main()
