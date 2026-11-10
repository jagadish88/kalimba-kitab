#!/usr/bin/env python3
"""Write repeated music once, with ktab repeat marks.

    python scripts/ktab_to_video/fold_repeats.py in.ktab out.ktab ["@header: value" ...]

1. A block of two or more lines played twice in a row inside a stanza becomes a stanza of its
   own ending in ' :||' (the lines before and after it become stanzas too).
2. Two identical stanzas in a row become one, ending in ' :||'.
3. Two identical lines in a row become one, ending in ' :|'.
Extra arguments are header lines added after @title. The played notes and timing are unchanged.
"""
import sys


def fold(text):
    head, *st = text.strip('\n').split('\n\n')
    st = [s.split('\n') for s in st if s.strip()]
    blocks = []                                # (lines, repeated?)
    for s in st:
        i, cur = 0, []
        while i < len(s):
            k = next((k for k in range(len(s) // 2, 1, -1) if s[i:i + k] == s[i + k:i + 2 * k]), 0)
            if k:
                if cur:
                    blocks.append((cur, False)); cur = []
                blocks.append((s[i:i + k], True)); i += 2 * k
            else:
                cur.append(s[i]); i += 1
        if cur:
            blocks.append((cur, False))
    merged, i = [], 0
    while i < len(blocks):
        if i + 1 < len(blocks) and not blocks[i][1] and blocks[i] == blocks[i + 1]:
            merged.append((blocks[i][0], True)); i += 2
        else:
            merged.append(blocks[i]); i += 1
    out = []
    for lines, rep in merged:
        res, j = [], 0
        while j < len(lines):
            if j + 1 < len(lines) and lines[j] == lines[j + 1]:
                res.append(lines[j] + ' :|'); j += 2
            else:
                res.append(lines[j]); j += 1
        if rep:
            res[-1] += ' :||'
        out.append('\n'.join(res))
    return head, out, len(st)


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    head, stanzas, n = fold(open(sys.argv[1], encoding='utf-8').read())
    h = head.split('\n')
    h[1:1] = sys.argv[3:]
    with open(sys.argv[2], 'w', encoding='utf-8') as f:
        f.write('\n'.join(h) + '\n\n' + '\n\n'.join(stanzas) + '\n')
    print(f'{n} stanzas -> {len(stanzas)}')


if __name__ == '__main__':
    main()
