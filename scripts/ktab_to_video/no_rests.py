#!/usr/bin/env python3
"""No rests in a ktab: a rest after a note becomes that note's hold (same total length, when ktab can
write it), any other rest is dropped. The layout rule for kalimba tabs (no 0s).

    python scripts/ktab_to_video/no_rests.py tab.ktab [...]     (in place)
"""
import re
import sys
from fractions import Fraction as Fr

NOTE = re.compile(r"^([0-7][',]*)(/*)(\.?)(-*)$")


def beats(t):
    m = NOTE.match(t)
    b = Fr(1, 2 ** len(m.group(2))) * (Fr(3, 2) if m.group(3) else 1)
    return b + len(m.group(4))


def write(pitch, d):
    for s in range(0, 5):
        for dot in (0, 1):
            base = Fr(1, 2 ** s) * (Fr(3, 2) if dot else 1)
            k = d - base
            if k >= 0 and k.denominator == 1:
                return pitch + '/' * s + ('.' if dot else '') + '-' * int(k)
    return None


def fix_group(notes):
    out = []
    for t in notes.split():
        if t.startswith('0'):
            if out and NOTE.match(out[-1]) and not out[-1].startswith('0'):
                m = NOTE.match(out[-1])
                nt = write(m.group(1), beats(out[-1]) + beats(t))
                if nt:
                    out[-1] = nt
            continue
        out.append(t)
    return ' '.join(out)


def no_rests(text):
    head, body = text.split('\n\n', 1)
    body = re.sub(r'\(([^:()]*):([^()]*)\)',
                  lambda m: (lambda new: f'({m.group(1)}: {new})' if new else '')(fix_group(m.group(2)))
                  if re.search(r'(^|\s)0', m.group(2)) else m.group(0), body)
    body = re.sub(r'[ \t]+\n', '\n', body)
    return head + '\n\n' + body


if __name__ == '__main__':
    for p in sys.argv[1:]:
        open(p, 'w', encoding='utf-8').write(no_rests(open(p, encoding='utf-8').read()))
