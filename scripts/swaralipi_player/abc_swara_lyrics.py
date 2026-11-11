#!/usr/bin/env python3
"""Put the SNLTR swaralipi's syllables (Geetabitan spelling) on the notes of an existing ABC.

    python scripts/swaralipi_player/abc_swara_lyrics.py rs001740 data/.../v1.abc [data/.../v2.abc ...]

For ABCs whose notes came from elsewhere (a score read off the screen) and whose lyrics came with
them. The ABC's notes (tied notes joined) are paired with the swaralipi's notes by pitch class and
length (note_align.py); the syllables are spelled from the Geetabitan lyrics (swara_abc.align_song)
and placed as midi_swara_abc.place_syllables places them on MIDI notes. Only the w: lines change:
every music line stays as it is. Further ABCs given (e.g. v2, the same notes with halved values) get
the same w: lines; their notes must be the same notes in the same lines.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 'scripts', 'piano_lesson_to_ktab'))
import abc_offkey_score as OS  # noqa: E402  (read_abc: notes per line, with ties)
import midi_swara_abc as M  # noqa: E402
import note_align as NA  # noqa: E402
import swara_abc as SA  # noqa: E402


def heads(abc_text):
    """-> per music line (in order): [(midi, eighths, tied to the next)]"""
    _, items = OS.read_abc(abc_text)
    return [[(e[1], e[2], e[3]) for e in it[1] if e[0] == 'note'] for it in items if it[0] == 'line']


def line_text(toks):
    """per-head tokens of one line -> a w: line ('aa-_-pon': a word held over notes stays one word)"""
    out, join = '', False
    for t in toks:
        if isinstance(t, tuple):
            txt = re.sub(r"[^A-Za-z']", '', t[0]) or 'a'
            if t[2]:
                txt = txt[0].upper() + txt[1:]
            t = txt + ('' if t[1] else '-')
        if not out:
            out = t
        elif out.endswith('-'):
            out += t
        else:
            out += ('-' if join else ' ') + t
        if t not in ('_', '*'):
            join = t.endswith('-')
    return out


def main():
    song, first, *more = sys.argv[1:]
    text = open(first, encoding='utf-8').read()
    lines_h = heads(text)
    # notes with ties joined, and for each head the note it belongs to
    notes, lens, head_note = [], [], []
    prev_tie = False
    for lh in lines_h:
        hn = []
        for midi, eighths, tie in lh:
            if prev_tie and notes and notes[-1] == midi:
                lens[-1] += float(eighths); hn.append((len(notes) - 1, True))
            else:
                notes.append(midi); lens.append(float(eighths)); hn.append((len(notes) - 1, False))
            prev_tie = tie
        head_note.append(hn)
    _, _, sev = SA.song_events(song)
    glines = [l.strip() for l in open(os.path.join(ROOT, f'data/raw_data/text/lyrics/{song}.txt'), encoding='utf-8') if l.strip()]
    L = SA.Lyrics(glines)
    idx = [j for j, e in enumerate(sev) if e['syl']]
    latin = dict(zip(idx, SA.align_song([sev[j]['syl'] for j in idx], L)))
    pair, sh = NA.align([e['midi'] for e in sev], notes, [e['units'] for e in sev], lens)
    s2m = {j: mi for j, mi in enumerate(pair) if mi is not None and sev[j]['midi'] % 12 == (notes[mi] + sh) % 12}
    toks = M.place_syllables(sev, latin, s2m, len(notes))
    wlines = [line_text([('_' if tied else toks[ni]) for ni, tied in hn]) for hn in head_note]
    for path in [first] + more:
        t = open(path, encoding='utf-8').read()
        if [len(h) for h in heads(t)] != [len(h) for h in lines_h]:
            sys.exit(f'{path}: not the same notes per line as {first}')
        out, li, lines = [], 0, t.split('\n')
        i = 0
        while i < len(lines):
            l = lines[i]
            if l.startswith('w:'):
                i += 1; continue                   # old lyrics: replaced below
            if l.startswith('S:lyrics'):
                l = (f'S:lyrics: syllables of the SNLTR swaralipi, Latin from data/raw_data/text/lyrics/{song}.txt '
                     f'(Geetabitan), placed on these notes by abc_swara_lyrics.py')
            out.append(l)
            is_music = l and not re.match(r'^[A-Za-z]:', l) and not l.startswith('%')
            if is_music and li < len(wlines):
                if wlines[li].strip('_* '):
                    out.append('w: ' + wlines[li])
                li += 1
            i += 1
        open(path, 'w', encoding='utf-8').write('\n'.join(out))
        print(f'{path}: {sum(1 for x in toks if isinstance(x, tuple))} syllables on {len(notes)} notes '
              f'({len(s2m)} of {len(sev)} swaralipi notes paired)')


if __name__ == '__main__':
    main()
