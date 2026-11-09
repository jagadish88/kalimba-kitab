#!/usr/bin/env python3
"""Our own swaralipi transcription format, and lossless conversion from/to SNLTR's encoding.

    python scripts/swaralipi_player/notation.py            # convert all, verify the round trip

Reads  data/raw_data/swaralipi_text/<song>.json   (SNLTR's notation table; git-ignored)
Writes data/intermediate_data/swaralipi/<song>.json (our transcription; committed)

Our format keeps the whole structure of the printed swaralipi: every row in order on the same
column grid (so pickups stay aligned), swara rows and their lyric rows cell for cell, bar lines,
repeats, first-time parts, alternatives, end marks, and the header (title, tala, abartan).
Only the way a swara cell is written differs:

  S r R g G m M P d D n N   swaras (lowercase r g d n = komal, M = tivra ma)
  '  ,                      upper / lower octave, after the swara: S'  N,
  ^X                        grace note (kan) X before the next swara: ^RG
  -  (alone)                hold (the matra continues the note: -১)
  -  (before swaras)        the swaras continue the previous syllable: -Gm
  GmP                       several swaras in one matra share it equally
  ঃ                         visarga mark after the matra
  I  II  |                  bar lines; { } repeat; ( ) first time only; [ ] alternative
  <x>                       a mark kept as found (e.g. <w> <x> <y> at row starts, <h>, <L>)
Lyric cells are unchanged (Bengali; ৹ = the syllable continues).

The conversion is checked both ways: every SNLTR cell -> ours -> SNLTR must give the cell back.
"""
import glob
import json
import os
import re

TO_OURS = dict(s='S', v='r', r='R', t='g', g='G', m='m', k='M', p='P', d='d', q='D', u='n', n='N')
TO_SNLTR = {v: k for k, v in TO_OURS.items()}
BARS = {'l': 'I', 'll': 'II', 'A': '|', '|': '¦'}


def cell_to_ours(c):
    """one SNLTR cell -> our notation (or None if the row is not a swara row)"""
    if c == '':
        return ''
    if c in BARS:
        return BARS[c]
    out, i = '', 0
    while i < len(c):
        ch = c[i]
        if ch in '{}()[] ':
            out += ch
        elif ch == '-':
            out += '-'
        elif ch.lower() in TO_OURS:
            marks = ''
            while i + 1 < len(c) and c[i + 1].lower() in 'fh' and c[i + 1].islower() == ch.islower():
                marks += "'" if c[i + 1].lower() == 'f' else ','
                i += 1
            out += ('' if ch.islower() else '^') + TO_OURS[ch.lower()] + marks
        elif ch == 'a':
            out += '·'                            # the matra's closing া (kept: the cell is a matra)
        elif ch == 'i':
            out += 'ঃ'
        else:
            out += f'<{ch}>'
        i += 1
    return out


def cell_to_snltr(c):
    if c == '':
        return ''
    inv = {v: k for k, v in BARS.items()}
    if c in inv:
        return inv[c]
    out, i = '', 0
    while i < len(c):
        ch = c[i]
        if ch in '{}()[] -':
            out += ch
        elif ch == '<':
            j = c.index('>', i); out += c[i + 1:j]; i = j
        elif ch == '^' or ch in TO_SNLTR:
            grace = ch == '^'
            if grace:
                i += 1; ch = c[i]
            letter = TO_SNLTR[ch]
            out += letter.upper() if grace else letter
            while i + 1 < len(c) and c[i + 1] in "',":
                m = 'f' if c[i + 1] == "'" else 'h'
                out += m.upper() if grace else m
                i += 1
        elif ch == '·':
            out += 'a'
        elif ch == 'ঃ':
            out += 'i'
        else:
            raise ValueError(f'cannot convert {ch!r} in {c!r}')
        i += 1
    return out


def is_swara_row(r):
    cells = [c for c in r if c]
    return bool(cells) and all(all(ord(ch) < 128 for ch in c) for c in cells)


def convert(src):
    doc = json.load(open(src))
    rows, bad = [], []
    for r in doc['rows']:
        if is_swara_row(r):
            ours = [cell_to_ours(c) for c in r]
            back = [cell_to_snltr(c) for c in ours]
            bad += [(a, b, o) for a, b, o in zip(r, back, ours) if a != b]
            rows.append(dict(type='swara', cells=ours))
        else:
            rows.append(dict(type='lyric', cells=list(r)))
    out = dict(song_id=doc['song_id'], title=doc.get('title', ''), tala=doc.get('tala', ''),
               abartan=doc.get('abartan', ''),
               transcribed_from=doc.get('source', ''), song_page=doc.get('song_page', ''),
               accessed=doc.get('accessed', ''),
               format='scripts/swaralipi_player/notation.py (our transcription; the structure of the printed '
                      'swaralipi is kept row for row and cell for cell)',
               rows=rows)
    return out, bad


def load_snltr_rows(path):
    """our transcription -> rows in SNLTR's encoding, for the tools that read that encoding"""
    doc = json.load(open(path))
    rows = [[cell_to_snltr(c) for c in r['cells']] if r['type'] == 'swara' else r['cells'] for r in doc['rows']]
    return doc, rows


def main():
    os.makedirs('data/intermediate_data/swaralipi', exist_ok=True)
    for src in sorted(glob.glob('data/raw_data/swaralipi_text/*.json')):
        out, bad = convert(src)
        dst = f"data/intermediate_data/swaralipi/{out['song_id']}.json"
        with open(dst, 'w') as f:
            f.write('{\n')
            keys = [k for k in out if k != 'rows']
            for k in keys:
                f.write(f'  {json.dumps(k)}: {json.dumps(out[k], ensure_ascii=False)},\n')
            f.write('  "rows": [\n')
            f.write(',\n'.join('    ' + json.dumps(r, ensure_ascii=False) for r in out['rows']))
            f.write('\n  ]\n}\n')
        # the file read back gives SNLTR's table exactly
        _, back = load_snltr_rows(dst)
        orig = json.load(open(src))['rows']
        same = back == orig
        nsw = sum(1 for r in out['rows'] if r['type'] == 'swara')
        print(f"{out['song_id']}: {len(out['rows'])} rows ({nsw} swara), round trip {'exact' if same and not bad else 'DIFFERS'}"
              + (f' {bad[:3]}' if bad else ''))


if __name__ == '__main__':
    main()
