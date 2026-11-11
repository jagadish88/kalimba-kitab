#!/usr/bin/env python3
"""Geetabitan spelling and word division for a ktab draft whose lyrics came from elsewhere.

    python scripts/ktab_to_video/respell_lyrics.py rs000101 [rs000017 ...] [--dry-run]
        (each song's latest draft in ktab_catalog.csv, changed in place)

Drafts read off a score, a piano lesson or an older aligner spell the syllables their own way
("sur-ya", "A-kash") and some write one syllable per word ("a ha a ji e bo o sho on te"). The draft's
syllables, in order, are aligned to the Geetabitan lyrics (data/raw_data/text/lyrics/<song>.txt) with
swara_abc.align_song (whole song at once, jumps for repeats); each syllable takes the poem's letters
it lines up with, and syllables are grouped into the poem's words. A syllable too unlike its match
keeps its own text and its own word division. Notes are not touched (checked). Then line breaks and
stanzas are redone by fix_lyric_lines.py.
"""
import argparse
import csv
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', 'swaralipi_player'))
import fix_lyric_lines as F  # noqa: E402
import reflow_ktab as R  # noqa: E402
import swara_abc as S  # noqa: E402

GROUP = re.compile(r'\(([^:()]*):([^()]*)\)')


def respell(text, song):
    head, body = text.split('\n\n', 1)
    glines = [l.strip() for l in open(f'data/raw_data/text/lyrics/{song}.txt', encoding='utf-8') if l.strip()]
    L = S.Lyrics(glines)
    # every group in order, with the separator that follows it on its line
    lines = body.split('\n')
    groups = []                                   # (line no, start, end, syllable)
    for li, l in enumerate(lines):
        for m in GROUP.finditer(l):
            groups.append((li, m.start(), m.end(), m.group(1)))
    syls = [g[3].strip() for g in groups]
    al = S.align_song(syls, L, latin=True)
    kept = sum(1 for (txt, _), s in zip(al, syls) if S.letters(txt) == S.letters(s))
    # rebuild each line: new syllable text; a space after a group where the poem's word ends
    new_lines = []
    gi = 0
    for li, l in enumerate(lines):
        mine = [k for k, g in enumerate(groups) if g[0] == li]
        if not mine:
            new_lines.append(l); continue
        out, pos = '', 0
        for n, k in enumerate(mine):
            _, a, b, syl = groups[k]
            txt, end = al[k]
            own = S.letters(txt) == S.letters(syl) or not S.letters(txt)
            if own:
                txt = syl.strip()
            notes = GROUP.match(l, a).group(2)
            prefix = l[pos:a]
            if n > 0:
                # separator before this group: the poem's word division (or the draft's own when kept)
                prev_k = mine[n - 1]
                prev_own = S.letters(al[prev_k][0]) == S.letters(groups[prev_k][3]) or not S.letters(al[prev_k][0])
                if not prev_own or not own:
                    prefix = re.sub(r'^\s*', '' if not al[prev_k][1] else ' ', prefix)
            out += prefix + f'({txt}:{notes})'
            pos = b
        out += l[pos:]
        new_lines.append(out)
    return head + '\n\n' + '\n'.join(new_lines), kept, len(syls)


def notes_only(text):
    return [t for _, n in GROUP.findall(text.split('\n\n', 1)[-1]) for t in n.split()]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('songs', nargs='+')
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()
    rows = list(csv.reader(open('data/intermediate_data/ktab/ktab_catalog.csv', encoding='utf-8')))
    last = {r[0]: r[2] for r in rows[1:] if r and r[0].startswith('rs')}
    for s in a.songs:
        p = last[s]
        old = open(p, encoding='utf-8').read()
        new, kept, n = respell(old, s)
        poem = F.poem_lines(s)
        new, starts, _ = F.fix(new, poem, 6, 10, 3, F.poem_phrases(s), F.sections(s, poem))
        assert notes_only(new) == [t if not set(t) <= {'-'} else t for t in notes_only(old)] or \
            [x.rstrip('-') for x in notes_only(new)] == [x.rstrip('-') for x in notes_only(old)], f'{s}: notes changed'
        print(f'{s}: {n - kept} of {n} syllables respelled, {starts} line starts')
        if not a.dry_run:
            open(p, 'w', encoding='utf-8').write(new)


if __name__ == '__main__':
    main()
