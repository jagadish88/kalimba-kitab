#!/usr/bin/env python3
"""Line breaks and stanzas of a ktab draft from the poem: a line starts only where a line of the poem starts.

    python scripts/ktab_to_video/fix_lyric_lines.py rs000842 [rs001248 ...] [--dry-run]
        (the song's latest draft in ktab_catalog.csv, changed in place)

1. Line starts: the Geetabitan lyrics (data/raw_data/text/lyrics/<song>.txt) give the poem's lines. A
   tab word starts a line when it and the next words spell the opening of a poem line (letters only,
   fuzzy: the drafts' syllables come from swaralipis and scores and are spelled differently). Those
   words get a capital; every other word is lowercased (the capitals the drafts had came from
   swaralipi rows and score layouts, not always from the poem).
2. Lines: a new line at every line start; a line longer than --max-words words or --max-syllables
   syllables is split as reflow_ktab.py splits it (balanced, at a held note if possible).
3. Stanzas: a stanza that ends in :|| (repeated) is kept as a stanza, and a line that ends in :| is
   kept whole. Elsewhere a new stanza starts when the song, having come back to its first poem line
   (the refrain), goes on to a poem line it has not sung yet.
Notes, syllables and holds are unchanged (an end hold is cut as in reflow_ktab.py). A song whose
lyrics match fewer than 3 line starts is left as it is (reported).
"""
import argparse
import csv
import difflib
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import reflow_ktab as R  # noqa: E402

WORD = re.compile(r'(?:\([^)]*\))+')


def key(s):
    return re.sub(r'[^a-z]', '', s.lower())


def poem_lines(song):
    lines = [l for l in open(f'data/raw_data/text/lyrics/{song}.txt', encoding='utf-8').read().split('\n') if key(l)]
    return [key(l) for l in lines]


def poem_phrases(song):
    """keys of the phrases that start inside a poem line: Gitabitan marks them with a wide gap"""
    out = []
    for l in open(f'data/raw_data/text/lyrics/{song}.txt', encoding='utf-8').read().split('\n'):
        parts = [key(p) for p in re.split(r'\s{2,}', l.strip()) if key(p)]
        out += [p for p in parts[1:] if len(p) >= 5]
    return out


def sections(song, poem):
    """poem lines where a section of the swaralipi ({ ... } groups) first starts, the first section aside;
    empty when the song has no SNLTR swaralipi"""
    path = f'data/intermediate_data/swaralipi/{song}.json'
    if not os.path.exists(path):
        return set()
    sys.path.insert(0, os.path.join(HERE, '..', 'swaralipi_player'))
    import swara_abc as S
    import match_snltr as M
    _, lines = S.TP.load(path)
    found = []
    for sw, ly in lines:
        j = next((k for k, c in enumerate(sw) if '{' in c), None)
        if j is None:
            continue
        q = key(M.translit(''.join(ly[j:j + 10]).replace('৹', '')))[:10]
        if len(q) < 5:
            continue
        best = max(((difflib.SequenceMatcher(None, q, p, autojunk=False).find_longest_match(0, len(q), 0, len(p)).size, -i, i)
                    for i, p in enumerate(poem)), default=None)
        if best and best[0] >= 5:
            found.append(best[2])
    return set(found[1:]) - {0, found[0] if found else 0}


def wkey(w):
    return key(''.join(s for s, _ in R.groups(w)))


def line_start(words, i, poem):
    """index of the poem line that begins at words[i], or None"""
    k0 = wkey(words[i])
    if not k0:
        return None
    s = ''
    for w in words[i:i + 8]:                      # about 12 letters, however the syllables are split
        s += wkey(w)
        if len(s) >= 12:
            break
    cands = []
    for j, p in enumerate(poem):
        if p[0] != k0[0]:
            continue
        n = min(len(s), len(p), 12)
        if n < 5:
            continue
        r = difflib.SequenceMatcher(None, s[:n], p[:n]).ratio()
        if r >= 0.75:
            cands.append((r, j))
    if not cands:
        return None
    top = max(c[0] for c in cands)
    near = sorted(j for r, j in cands if r >= top - 0.05)   # lines that open alike: the caller picks by order
    return (top, near[0], near)


def last_len(word):
    toks = R.groups(word)[-1][1].split() if R.groups(word) else []
    return R.note_beats(toks[-1]) if toks else 0


def split_long(words, max_words, max_syl):
    """as reflow_ktab.split_long, but a phrase end is a word whose last note is long (held or dotted)"""
    n_syl = [len(R.groups(w)) for w in words]
    if (len(words) <= max_words and sum(n_syl) <= max_syl) or len(words) < 2:
        return [words]
    best = None
    for k in range(1, len(words)):
        score = abs(sum(n_syl[:k]) - sum(n_syl) / 2) - 1.5 * min(float(last_len(words[k - 1])), 3)
        for part in (n_syl[:k], n_syl[k:]):
            if sum(part) < 3:
                score += 3
        if best is None or score < best[0]:
            best = (score, k)
    k = best[1]
    return split_long(words[:k], max_words, max_syl) + split_long(words[k:], max_words, max_syl)


def recase(w, upper):
    m = re.match(r'\(\s*([^:()]*)', w)
    syl = m.group(1)
    new = syl[:1].upper() + syl[1:] if upper else syl[:1].lower() + syl[1:]
    return w[:m.start(1)] + new + w[m.start(1) + len(syl):]


def parse(body):
    """-> stanzas: list of (lines, repeated); a line: (words, marker)"""
    out, cur = [], []
    for l in body.split('\n'):
        if not l.strip():
            if cur:
                out.append(cur); cur = []
            continue
        mk = re.search(r'\s*(:\|\|?)\s*$', l)
        cur.append((WORD.findall(l), mk.group(1) if mk else ''))
    if cur:
        out.append(cur)
    return [(st, st[-1][1] == ':||') for st in out]


def fix(text, poem, max_words, max_syl, max_hold, phrases=(), section_starts=()):
    head, body = text.split('\n\n', 1) if '\n\n' in text else ('', text)
    stanzas = parse(body)
    # units: a run of free words, or a fixed line (:| line); stanza groups keep :|| stanzas apart
    blocks = []                                   # (kind, payload): 'stream' [words], 'rep' stanza
    stream = []
    for st, rep in stanzas:
        if rep:
            if stream:
                blocks.append(('stream', stream)); stream = []
            blocks.append(('rep', st))
        else:
            for words, mk in st:
                stream.append((words, mk))
    if stream:
        blocks.append(('stream', stream))
    n_starts = 0
    cuts = []
    allwords = [w for _, payload in blocks for item in payload for w in (item[0] if isinstance(item, tuple) else [])]
    allwords += [w for kind, st in blocks if kind == 'rep' for ws, _ in st for w in ws]
    multi = sum(1 for w in allwords if len(R.groups(w)) > 1) / max(1, len(allwords))
    max_w = max_words if multi >= 0.2 else max_syl      # lyrics one syllable per word: count syllables only

    def lines_of(items):
        """items: [(words, marker)] -> [(line text, poem idx or None)]"""
        nonlocal n_starts
        flat = []                                 # (word, start idx, marker-after)
        for words, mk in items:
            for i, w in enumerate(words):
                flat.append([w, None, mk if i == len(words) - 1 else '', mk == ':|'])
        allw = [f[0] for f in flat]
        found = [line_start(allw, i, poem) for i in range(len(flat))]
        nsyl = [len(R.groups(w)) for w in allw]
        for i in range(len(flat)):                # starts closer than 3 syllables: the better match wins
            if not found[i]:
                continue
            j = i - 1
            gap = 0
            while j >= 0 and gap < 3:
                gap += nsyl[j]
                if found[j] and gap < 3:
                    if found[j][0] >= found[i][0]:
                        found[i] = None
                    else:
                        found[j] = None
                    break
                j -= 1
        prev = -1
        for i in range(len(flat)):                # of lines that open alike, the next one in the poem
            if found[i]:
                near = found[i][2]
                after = [j for j in near if j > prev]
                pick = (prev + 1) if (prev + 1) in near else (after[0] if after else near[0])
                if pick > prev + 2 and prev >= 0 and found[i][0] < 0.92:
                    flat[i][1] = None             # far ahead of the song's place in the poem: a look-alike phrase
                    continue
                flat[i][1] = pick
                prev = pick
            else:
                flat[i][1] = None
        keys = [wkey(w) for w in allw]
        for i in range(len(flat)):                # a sung repeat of a phrase inside a poem line: a new line, no capital
            if flat[i][1] is not None or i == 0 or flat[i - 1][1] is not None:
                continue
            win = keys[i:i + 3]
            if len(win) < 3 or len(''.join(win)) < 6:
                continue
            for j in range(max(0, i - 12), i - 2):
                if keys[j:j + 3] == win:
                    flat[i][1] = -2
                    break
        phr = [False] * len(flat)                 # a phrase of the poem line starts here (Gitabitan's gap)
        if phrases:
            for i in range(1, len(flat)):
                if flat[i][1] is not None:
                    continue
                k0 = keys[i]
                s = ''
                for w in keys[i:i + 8]:
                    s += w
                    if len(s) >= 10:
                        break
                for p in phrases:
                    n = min(len(s), len(p), 10)
                    if k0 and p[0] == k0[0] and n >= 5 and difflib.SequenceMatcher(None, s[:n], p[:n]).ratio() >= 0.8:
                        phr[i] = True
                        break
        if flat:
            if flat[0][1] is None:
                flat[0][1] = -1                   # a block starts a line anyway
        out, cur, cur_idx, fixed = [], [], None, False
        phrase_at = set()                         # ids of words where a poem phrase starts
        for (w, idx, mk, in_fixed), ph in zip(flat, phr):
            if cur and idx is not None and not (fixed and in_fixed):
                out.append((cur, cur_idx, fixed)); cur = []
            if not cur:
                cur_idx, fixed = idx, in_fixed
            cur.append(recase(w, idx is not None and idx >= 0 and not cur))
            if ph and len(cur) > 1:
                phrase_at.add((len(out), len(cur) - 1))
            if mk:
                cur[-1] = cur[-1] + ' ' + mk
                out.append((cur, cur_idx, fixed)); cur = []
        if cur:
            out.append((cur, cur_idx, fixed))
        res = []
        for li, (ws, idx, fx) in enumerate(out):
            if idx is not None and idx >= 0:
                n_starts += 1
            if fx or ws[-1].endswith(':|'):
                res.append((' '.join(ws), idx))
                continue
            nsy = [len(R.groups(w)) for w in ws]
            parts = [ws]
            if len(ws) > max_w or sum(nsy) > max_syl:  # too long: first at the poem's own phrase breaks
                cuts_at = sorted(k for (l2, k) in phrase_at if l2 == li)
                bounds = [0] + cuts_at + [len(ws)]
                pieces = [ws[a:b] for a, b in zip(bounds, bounds[1:]) if b > a]
                if len(pieces) > 1 and all(sum(len(R.groups(w)) for w in p) >= 3 for p in pieces):
                    parts = pieces
            parts = [q for p in parts for q in split_long(p, max_w, max_syl)]
            for k, p in enumerate(parts):
                res.append((R.cap_end_hold(' '.join(p), max_hold, cuts), idx if k == 0 else None))
        merged = []                               # a lone continuation word: back onto the line before
        for l, idx in res:
            w = WORD.findall(l)
            if (merged and idx is None and len(w) == 1 and not l.rstrip().endswith(':|')
                    and not merged[-1][0].rstrip().endswith(':|')):
                merged[-1] = (merged[-1][0] + ' ' + l, merged[-1][1])
            else:
                merged.append((l, idx))
        return merged

    out_stanzas = []
    for kind, payload in blocks:
        if kind == 'rep':
            ls = lines_of(payload)
            out_stanzas.append([l for l, _ in ls])
            continue
        ls = lines_of(payload)
        st, seen_max, returned = [], -1, False
        for l, idx in ls:
            if idx is not None and idx >= 0:
                if section_starts:                # the swaralipi's sections: a new one the first time it is sung
                    if idx in section_starts and idx > seen_max and st:
                        out_stanzas.append(st); st = []
                elif idx == 0 and seen_max > 1:
                    returned = True
                elif returned and idx > seen_max and st:
                    out_stanzas.append(st); st = []; returned = False
                seen_max = max(seen_max, idx)
            st.append(l)
        if st:
            out_stanzas.append(st)
    new = head.rstrip('\n') + '\n\n' + '\n\n'.join('\n'.join(s) for s in out_stanzas) + '\n'
    return new, n_starts, cuts


def notes_of(text):
    body = text.split('\n\n', 1)[-1]
    return [(s.strip().lower(), n.split()) for s, n in R.groups(body)]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('songs', nargs='*')
    ap.add_argument('--all-drafts', action='store_true', help='every draft not in data/dataset/')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--max-words', type=int, default=6)
    ap.add_argument('--max-syllables', type=int, default=10)
    ap.add_argument('--max-hold', type=int, default=3)
    a = ap.parse_args()
    rows = list(csv.reader(open('data/intermediate_data/ktab/ktab_catalog.csv', encoding='utf-8')))
    last = {}
    for r in rows[1:]:
        if r and r[0].startswith('rs'):
            last[r[0]] = r[2]
    songs = a.songs
    if a.all_drafts:
        ds = {r[0] for r in csv.reader(open('data/dataset/dataset_catalog.csv', encoding='utf-8')) if r}
        songs = sorted(s for s in last if s not in ds)
    for s in songs:
        p = last[s]
        text = open(p, encoding='utf-8').read()
        poem = poem_lines(s)
        new, n, cuts = fix(text, poem, a.max_words, a.max_syllables, a.max_hold, poem_phrases(s), sections(s, poem))
        if n < 3:
            print(f'{s}: only {n} line starts found in the lyrics; left as it is')
            continue
        old_n = [(x, [t.rstrip('-') for t in y]) for x, y in notes_of(text)]
        new_n = [(x, [t.rstrip('-') for t in y]) for x, y in notes_of(new)]
        assert old_n == new_n, f'{s}: syllables or notes changed'
        nl = new.split('\n\n', 1)[1].count('\n') + 1
        ns = new.split('\n\n', 1)[1].strip().count('\n\n') + 1
        print(f'{s}: {p}: {n} line starts, {nl} lines, {ns} stanzas, {len(cuts)} end holds cut')
        if not a.dry_run:
            open(p, 'w', encoding='utf-8').write(new)


if __name__ == '__main__':
    main()
