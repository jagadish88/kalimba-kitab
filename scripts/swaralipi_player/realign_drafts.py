#!/usr/bin/env python3
"""Redo the syllables of drafts made from SNLTR swaralipis with swara_abc.align_song (whole-song alignment).

    python scripts/swaralipi_player/realign_drafts.py [rs001248 ...] [--dry-run]   (default: every such draft)

For each draft not in data/dataset/ whose latest ktab came from swaralipi_to_ktab or midi_to_ktab:
1. the ABC is made again (swara_abc.py or midi_swara_abc.py) into a scratch folder; where its notes,
   bars and fields equal those of the draft's ABC (title aside), the draft's w: lines are replaced
   by the new ones;
2. the ktab is made again from the ABC it came from, the same way (abc_to_ktab.py with the catalog's
   --transpose, leading rest dropped, fold_repeats.py with the draft's @title/@subtitle/@retune,
   then fix_lyric_lines.py's line breaks); it replaces the draft only if its notes are the draft's
   notes, in order (so hand edits are never overwritten: such drafts are reported and left);
3. a preview PDF next to the ktab is made again.
"""
import argparse
import csv
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'scripts', 'ktab_to_video'))
import fix_lyric_lines as F  # noqa: E402
import reflow_ktab as R  # noqa: E402

TITLES = {r[0]: r[1] for r in csv.reader(open(os.path.join(ROOT, 'data/raw_data/text/catalog.csv'), encoding='utf-8')) if r}
TMP = os.environ.get('KK_TMP', '/tmp/kk_work/realign')
PY = sys.executable


def run(*a):
    return subprocess.run([PY, *a], cwd=ROOT, capture_output=True, text=True)


def body_notes(text):
    body = text.split('\n\n', 1)[-1]
    return [t.rstrip('-') for _, n in R.groups(body) for t in n.split() if t.rstrip('-')]


def build(s, abc_text, T, hdr, out, tag):
    """ABC -> ktab the pipeline's way: abc_to_ktab, leading rest dropped, fold_repeats with the
    draft's headers, fix_lyric_lines' line breaks"""
    open(f'{out}/{tag}.abc', 'w', encoding='utf-8').write(abc_text)
    res = run('scripts/piano_lesson_to_ktab/abc_to_ktab.py', f'{out}/{tag}.abc', '--transpose', T, '--out', f'{out}/{tag}_a.ktab')
    if res.returncode:
        return None
    kt = open(f'{out}/{tag}_a.ktab', encoding='utf-8').read()
    kt = re.sub(r'\(([^:]*): 0[^ )]* ', r'(\1: ', kt, count=1)
    kt = '\n'.join(l for l in kt.split('\n') if not l.startswith('@title:'))
    open(f'{out}/{tag}_a.ktab', 'w', encoding='utf-8').write(kt)
    res = run('scripts/ktab_to_video/fold_repeats.py', f'{out}/{tag}_a.ktab', f'{out}/{tag}_b.ktab', *hdr)
    if res.returncode:
        return None
    b = open(f'{out}/{tag}_b.ktab', encoding='utf-8').read()
    head, body = b.split('\n\n', 1)                # @title, @subtitle, @retune first
    order = ['title', 'subtitle', 'retune']
    head = '\n'.join(sorted(head.split('\n'), key=lambda l: order.index(l[1:].split(':')[0]) if l[1:].split(':')[0] in order else 3))
    poem = F.poem_lines(s)
    return F.fix(head + '\n\n' + body, poem, 6, 10, 3, F.poem_phrases(s), F.sections(s, poem))[0]


def non_w(text):
    return [l for l in text.split('\n') if not l.startswith('w:') and not l.startswith('T:')
            and not l.startswith('S:') and not l.startswith('N:') and not l.startswith('Q:')]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('songs', nargs='*')
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()
    os.chdir(ROOT)
    krows = list(csv.reader(open('data/intermediate_data/ktab/ktab_catalog.csv', encoding='utf-8')))
    last = {}
    for r in krows[1:]:
        if r and r[0].startswith('rs'):
            last[r[0]] = r
    ds = {r[0] for r in csv.reader(open('data/dataset/dataset_catalog.csv', encoding='utf-8')) if r}
    songs = a.songs or sorted(s for s, r in last.items() if s not in ds and r[3] in ('swaralipi_to_ktab', 'midi_to_ktab'))
    done, skipped = [], []
    for s in songs:
        r = last[s]
        kpath, src_abc, note = r[2], r[5], r[7]
        m = re.search(r'--transpose (-?\d+)', note)
        if not (m and src_abc.endswith('.abc') and os.path.exists(src_abc)):
            skipped.append((s, 'no transpose or source ABC in the catalog')); continue
        T = m.group(1)
        out = os.path.join(TMP, s)
        shutil.rmtree(out, ignore_errors=True); os.makedirs(out)
        if r[3] == 'swaralipi_to_ktab':
            res = run('scripts/swaralipi_player/swara_abc.py', s, '--out', f'{out}/v1.abc')
            made = {'v1.abc': f'{out}/v1.abc'}
        else:
            res = run('scripts/swaralipi_player/midi_swara_abc.py', s, '--out-dir', out)
            made = {'v1.abc': f'{out}/v1.abc', 'v2.abc': f'{out}/v2.abc'}
        if res.returncode:
            skipped.append((s, 'ABC not made: ' + res.stderr.strip()[-120:])); continue
        adir = os.path.dirname(src_abc)
        new_abc = {}
        ok = True
        for name, p in made.items():
            old_p = os.path.join(adir, name)
            if not os.path.exists(old_p) or not os.path.exists(p):
                continue
            old, new = open(old_p, encoding='utf-8').read(), open(p, encoding='utf-8').read()
            if non_w(old) != non_w(new):
                if old_p == src_abc:
                    ok = False
                continue
            # the draft's own lines, with the new w: lines in their places
            nw = iter([l for l in new.split('\n') if l.startswith('w:')])
            new_abc[old_p] = '\n'.join(next(nw) if l.startswith('w:') else l for l in old.split('\n'))
        if not ok or src_abc not in new_abc:
            skipped.append((s, f'{src_abc}: notes differ from a fresh run (edited by hand?)')); continue
        old_k = open(kpath, encoding='utf-8').read()
        hdr = [l for l in old_k.split('\n') if re.match(r'@(title|subtitle|retune):', l)]
        title = TITLES.get(s)
        hdr = [f'@title: {title}' if (l.startswith('@title:') and title and re.match(r'@title:\s*rs\d+\s*$', l)) else l for l in hdr]
        # the draft as the pipeline would make it from its own ABC: if that is not the draft, it was edited by hand
        rebuilt_old = build(s, open(src_abc, encoding='utf-8').read(), T, hdr, out, 'old')
        if rebuilt_old is None or body_notes(rebuilt_old) != body_notes(old_k):
            skipped.append((s, 'the draft is not what the pipeline makes from its ABC (edited by hand?)')); continue
        new_k = build(s, new_abc[src_abc], T, hdr, out, 'new')
        if new_k is None:
            skipped.append((s, 'ktab not made')); continue
        if a.dry_run:
            done.append(s); continue
        for p, txt in new_abc.items():
            open(p, 'w', encoding='utf-8').write(txt)
        open(kpath, 'w', encoding='utf-8').write(new_k)
        pdf = kpath[:-5] + '.pdf'
        if os.path.exists(pdf):
            shutil.copy(kpath, f'{out}/x.ktab')
            subprocess.run(['ktab', 'tex', 'x.ktab'], cwd=out, capture_output=True)
            if os.path.exists(f'{out}/x.pdf'):
                shutil.copy(f'{out}/x.pdf', pdf)
        done.append(s)
    print(f'{"would realign" if a.dry_run else "realigned"} {len(done)}: {" ".join(done)}')
    print(f'left as they are {len(skipped)}:')
    for s, why in skipped:
        print(f'  {s}: {why}')


if __name__ == '__main__':
    main()
