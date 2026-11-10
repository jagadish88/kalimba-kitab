#!/usr/bin/env python3
"""Short tab lines for videos and PDFs: break at the poem's lines, split long ones, cut long end holds.

    python scripts/ktab_to_video/reflow_ktab.py in.ktab out.ktab [--max-words 6] [--max-syllables 10] [--max-hold 3]

1. Within each stanza (blank-line separated), a line starts at every word whose first syllable is
   capitalized: the drafts capitalize the first word of each line of the poem.
2. A poem line of more than --max-words words or --max-syllables syllables is split at the word
   boundary that balances its syllables, preferring the end of a word whose last note is held (a
   phrase end); repeated until every part is short.
3. The last note of every line keeps at most --max-hold extra beats ("1'-------" -> "1'---").
Notes and syllables are otherwise unchanged: only line breaks and those end holds change.
"""
import argparse
import re
from fractions import Fraction

NOTE = re.compile(r"([0-7])([',]*)(/*)(\.?)(-*)$")


def note_beats(tok):
    if set(tok) == {'-'}:
        return Fraction(len(tok))
    m = NOTE.match(tok)
    if not m:
        return Fraction(0)
    b = Fraction(1, 2 ** len(m.group(3)))
    if m.group(4):
        b *= Fraction(3, 2)
    return b + len(m.group(5))


def groups(word):
    return re.findall(r'\(([^:()]*):([^()]*)\)', word)


def word_beats(word):
    return sum(note_beats(t) for _, notes in groups(word) for t in notes.split())


def last_hold(word):
    toks = groups(word)[-1][1].split() if groups(word) else []
    if not toks:
        return 0
    m = NOTE.match(toks[-1])
    return len(m.group(5)) if m else 0


def split_long(words, max_words, max_syl):
    """a poem line of more than max_words words or max_syl syllables: split at the word boundary that
    balances its syllables best, preferring a phrase end (a word whose last note is held) and
    avoiding a short word alone on a line"""
    n_syl = [len(groups(w)) for w in words]
    if (len(words) <= max_words and sum(n_syl) <= max_syl) or len(words) < 2:
        return [words]
    best = None
    for k in range(1, len(words)):
        score = abs(sum(n_syl[:k]) - sum(n_syl) / 2) - 0.75 * min(last_hold(words[k - 1]), 4)
        for part in (n_syl[:k], n_syl[k:]):      # a short word alone on a line: avoid
            if len(part) == 1 and part[0] < 4:
                score += 3
        if best is None or score < best[0]:
            best = (score, k)
    k = best[1]
    return split_long(words[:k], max_words, max_syl) + split_long(words[k:], max_words, max_syl)


def cap_end_hold(line, max_hold, cuts):
    m = re.search(r'\(([^:()]*):([^()]*)\)\s*$', line)
    if not m:
        return line
    toks = m.group(2).split()
    nm = NOTE.match(toks[-1]) if toks else None
    if nm and len(nm.group(5)) > max_hold:
        cuts.append((m.group(1), len(nm.group(5)), max_hold))
        toks[-1] = toks[-1][:len(toks[-1]) - len(nm.group(5))] + '-' * max_hold
        return line[:m.start()] + f'({m.group(1)}: {" ".join(toks)})' + line[m.end():]
    return line


def reflow(text, max_words=6, max_syl=10, max_hold=3):
    head, body = [], []
    lines = text.split('\n')
    k = 0
    while k < len(lines) and (lines[k].startswith('@') or not lines[k].strip()):
        head.append(lines[k]); k += 1
    stanzas, cur = [], []
    for l in lines[k:]:
        if l.strip():
            cur.append(l)
        elif cur:
            stanzas.append(cur); cur = []
    if cur: stanzas.append(cur)
    cuts, out = [], []
    for st in stanzas:
        words = [w for l in st for w in re.findall(r'(?:\([^)]*\))+', l)]
        poem, cur = [], []
        for w in words:
            syl = groups(w)[0][0].strip() if groups(w) else ''
            if cur and syl[:1].isupper():
                poem.append(cur); cur = []
            cur.append(w)
        if cur: poem.append(cur)
        new = []
        for pl in poem:
            new += split_long(pl, max_words, max_syl)
        out.append([cap_end_hold(' '.join(ws), max_hold, cuts) for ws in new])
    while head and not head[-1].strip():
        head.pop()
    text = '\n'.join(head) + '\n\n' + '\n\n'.join('\n'.join(st) for st in out) + '\n'
    return text, cuts


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('src'); ap.add_argument('dst')
    ap.add_argument('--max-words', type=int, default=6)
    ap.add_argument('--max-syllables', type=int, default=10)
    ap.add_argument('--max-hold', type=int, default=3)
    a = ap.parse_args()
    text, cuts = reflow(open(a.src).read(), a.max_words, a.max_syllables, a.max_hold)
    open(a.dst, 'w').write(text)
    print(f'{a.dst}: {text.count(chr(10) + "(")} lines; {len(cuts)} end holds cut to {a.max_hold}: '
          + ', '.join(f'{s.strip()} {n}->{m}' for s, n, m in cuts[:12]) + (' ...' if len(cuts) > 12 else ''))


if __name__ == '__main__':
    main()
