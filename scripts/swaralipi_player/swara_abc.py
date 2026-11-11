#!/usr/bin/env python3
"""ABC draft straight from the swaralipi text (no MIDI): notes, matras and syllables from SNLTR's
table, Latin lyrics from the Geetabitan transliteration.

    python scripts/swaralipi_player/swara_abc.py rs002122 [--bpm 55] [--out FILE]

Input: data/intermediate_data/swaralipi/<song>.json (notation.py's transcription) and
data/raw_data/text/lyrics/<song>.txt. Output: data/intermediate_data/abc/<song>/v1.abc.

How
  * Singing order, cells and notes come from text_player.py: { } twice, ( ) first time only, a
    quoted return sings the sthayi's first line; alternatives [ ] are left out.
  * One matra = one eighth note (L:1/32, a matra is 4 units), as in the halved MIDI drafts, so the tab
    plays at the swaralipi's speed in eighths. Swaras sharing a matra share it: 2 -> 2+2, 3 -> 2+1+1,
    4 -> 1+1+1+1. A hold (-১) lengthens the note before it. Grace notes are left out.
  * Sa = C4; the kalimba transposition is chosen later by abc_to_ktab.py.
  * One ABC line per swaralipi row as sung; P: marks each { } section.
  * Lyrics: a syllable starts where the lyric row has one (not on cells that continue with "-").
    Each sung line's syllables are transliterated roughly and aligned to the best-matching line of
    the Geetabitan transliteration, which gives each syllable its Latin spelling and where the
    words end. Without a good match the rough transliteration is kept, one word per syllable.
"""
import argparse
import difflib
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import text_player as TP  # noqa: E402
from match_snltr import translit, key  # noqa: E402

NAMES = ['C', '^C', 'D', '^D', 'E', 'F', '^F', 'G', '^G', 'A', '^A', 'B']
SPLIT = {1: [4], 2: [2, 2], 3: [2, 1, 1], 4: [1, 1, 1, 1]}
SKIP_LYR = {'', '৹', '০', '•', '·'}


def abc_note(midi, units):
    pc, octave = midi % 12, midi // 12 - 1
    n = NAMES[pc]
    acc, letter = (n[0], n[1]) if n[0] == '^' else ('=', n)
    if octave >= 5:
        letter = letter.lower() + "'" * (octave - 5)
    else:
        letter = letter + ',' * (4 - octave)
    return f"{acc}{letter}{units if units != 1 else ''}"


def clean_syl(s):
    s = s.replace('"', '').replace('“', '').replace('”', '').replace('৹', '').strip()
    return '' if s in SKIP_LYR else s


def singing_order(lines):
    """[(line, col)] in singing order"""
    items = []
    for li, (sw, ly) in enumerate(lines):
        for ci, c in enumerate(sw):
            if not c or c in TP.BARS:
                continue
            try:
                p = TP.parse_cell(c)
            except ValueError as e:
                print('skipped:', e, file=sys.stderr); continue
            items += [x for x in p['pre'] if x in '{(']
            items.append((li, ci))
            items += [x for x in p['post'] if x in ')}']
        if any(x.startswith('"') or x.endswith('"') for x in ly):
            items.append('return')
    # the sthayi's first line, second-time path, for the returns: the first line inside the first
    # { } when the song opens with it, else the song's first line (here the antara has the braces)
    first = items.index('{') if '{' in items else 0
    if '{' not in items or (first and isinstance(items[0], tuple) and items[0][0] != items[first + 1][0]):
        first = -1
    # a first row that is only a pickup (a few matras) is sung with the row after it
    l0 = items[0][0] if items and isinstance(items[0], tuple) else 0
    head_lines = {l0} | ({l0 + 1} if sum(1 for it in items if isinstance(it, tuple) and it[0] == l0) <= 3 else set())
    line1, skip, depth = [], 0, 0
    for it in items[max(first, -1) + 1:]:
        if it == '(':
            skip += 1
        elif it == ')':
            skip -= 1
        elif it == '}':
            break
        elif isinstance(it, tuple) and not skip:
            if first == -1 and it[0] not in head_lines:
                break
            line1.append(it)
    order, opens = [], []
    for i, it in enumerate(items):
        if it == '{':
            opens.append(i)
        elif it == '}' and opens:
            s0 = opens.pop(); skip = 0
            for it2 in items[s0 + 1:i]:
                if it2 == '(': skip += 1
                elif it2 == ')': skip -= 1
                elif isinstance(it2, tuple) and not skip: order.append(it2)
        elif it == 'return':
            if i == len(items) - 1 and '{' in items:   # the song's end: the whole repeated first section, both times
                s0 = items.index('{') if '{' in items else 0
                e0 = items.index('}', s0) if '}' in items[s0:] else len(items)
                body = items[s0 + 1:e0]
                order += [x for x in body if isinstance(x, tuple)]
                skip = 0
                for x in body:
                    if x == '(': skip += 1
                    elif x == ')': skip -= 1
                    elif isinstance(x, tuple) and not skip: order.append(x)
            else:
                order += line1
        elif isinstance(it, tuple):
            order.append(it)
    return order


def song_events(song):
    doc, lines = TP.load(f'data/intermediate_data/swaralipi/{song}.json')
    # swaralipis with two tunes mark each row "1:" (main tune) or "2:" (the tune for the repeat,
    # printed above it): keep the main tune only
    kept = []
    for sw, ly in lines:
        head = next((c for c in sw if c), '')
        if head.startswith('2:'):
            continue
        sw = [c[2:] if c.startswith('1:') else c for c in sw]
        kept.append((sw, ly))
    lines = kept
    order = singing_order(lines)
    events, prev_li = [], None          # event: dict(midi, units, syl, line)
    for li, ci in order:
        sw, ly = lines[li]
        p = TP.parse_cell(sw[ci])
        lyr = clean_syl(ly[ci]) if ci < len(ly) else ''
        newline = li != prev_li
        prev_li = li
        if not p['notes']:
            if events:
                events[-1]['units'] += 4
            continue
        n = len(p['notes'])
        parts = SPLIT.get(n, [1] * n)
        for k, (semi, octv, _grace) in enumerate(p['notes']):
            syl = lyr if k == 0 and lyr and not p['cont'] else ''
            events.append(dict(midi=60 + semi + 12 * octv, units=parts[min(k, len(parts) - 1)],
                               syl=syl, line=li, newline=newline and k == 0))
    return doc, lines, events


def letters(s):
    return re.sub(r'[^a-z]', '', s.lower())


class Lyrics:
    """the Geetabitan transliteration as one letter string, with where each letter sits in the text"""
    def __init__(self, glines):
        self.text = ' '.join(glines)
        self.pos = [i for i, ch in enumerate(self.text) if ch.isalpha()]
        self.gl = ''.join(self.text[i].lower() for i in self.pos)
        # letter indices where a word starts
        self.starts = [k for k in range(len(self.pos)) if k == 0 or self.pos[k] != self.pos[k - 1] + 1]

    def word_end(self, k):
        """letter index after the end of the word containing letter k"""
        while k + 1 < len(self.pos) and self.pos[k + 1] == self.pos[k] + 1:
            k += 1
        return k + 1


def latin_line(syls, L, after=0):
    """syllables (Bengali) of one sung line -> [(latin text, word ends after it)], by aligning their
    rough transliteration to the best-matching stretch of the Geetabitan lyrics"""
    rough = [letters(translit(s, final_o=True)) or 'a' for s in syls]
    joined = ''.join(rough)
    if not L.gl or not joined:
        return [(r, True) for r in rough]
    n = len(joined)
    cands = []
    for s in L.starts:
        for m in (n - n // 4, n, n + n // 4):
            win = L.gl[s:s + m]
            cands.append((difflib.SequenceMatcher(None, joined, win, autojunk=False).ratio(), s, len(win)))
    top = max(c[0] for c in cands)
    # among the near-best matches prefer the one closest after the previous line's match
    # (short lines like "tu-mi" or "mo-mo" match in many places)
    near = [c for c in cands if c[0] >= top - 0.08]
    r, s, m = min(near, key=lambda c: (c[1] < after, abs(c[1] - after), -c[0]))
    L.last = s + m
    if r < 0.5:
        return [(x, True) for x in rough]
    win = L.gl[s:s + m]
    sm = difflib.SequenceMatcher(None, joined, win, autojunk=False)
    amap = [0] * (n + 1)                      # joined index -> window index
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        for k in range(i1, i2):
            amap[k] = j1 + (min(k - i1, j2 - j1 - 1) if j2 > j1 else 0)
        amap[i2] = j2
    out, pos = [], 0
    starts = []
    for x in rough:
        starts.append(s + amap[pos]); pos += len(x)
    for k, a in enumerate(starts):
        we = L.word_end(a)
        nxt = starts[k + 1] if k + 1 < len(starts) else None
        if nxt is not None and a < nxt <= we:
            b = nxt                                    # the next syllable continues this word
        else:
            # the word ends here, or continues on the next line: about the syllable's own length
            b = min(we, a + len(rough[k]))
            if we - b <= 2:
                b = we
        piece = ''.join(L.text[L.pos[i]] for i in range(a, min(b, len(L.pos))))
        end_word = b >= we
        # a spelling that looks nothing like the syllable itself came from a wrong match: keep the
        # syllable's own transliteration (and let it end its word)
        if not piece or difflib.SequenceMatcher(None, key(rough[k]), key(letters(piece))).ratio() < 0.6:
            piece, end_word = rough[k], True
        out.append((piece, end_word))
    return out


_ED = {}


def edit(a, b):
    """Levenshtein distance (cached; syllables are short)"""
    k = (a, b)
    if k not in _ED:
        prev = list(range(len(b) + 1))
        for i, ca in enumerate(a, 1):
            cur = [i]
            for j, cb in enumerate(b, 1):
                cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
            prev = cur
        _ED[k] = prev[-1]
    return _ED[k]


def align_song(syls, L, jump=2.0, insert=1.6, per_letter=1.0):
    """Latin for every swaralipi syllable of the song at once -> [(latin text, word ends after it)].

    The syllables (in singing order) walk through the Geetabitan lyrics letter by letter: each one
    covers the next few letters of the poem (about as many as its rough transliteration has), with a
    cost for the letters that differ. The walk may jump to any word start (a sung repeat, a return to
    the refrain, a skipped word) at a fixed cost, and a syllable may match nothing (a sung 'o' or
    'aa' that the poem does not spell) at a fixed cost; it then keeps its own transliteration.
    Replaces latin_line's line-by-line window match, which drifted when a sung line repeated words or
    crossed the poem's line ends."""
    rough = [letters(translit(s, final_o=True)) or 'a' for s in syls]
    gl, P = L.gl, len(L.gl)
    if not P or not syls:
        return [(r, True) for r in rough]
    INF = float('inf')
    is_start = [False] * (P + 1)
    for s in L.starts:
        is_start[s] = True
    nxt_start = [P] * (P + 1)                     # a syllable never runs into the next word
    for s in range(P - 1, -1, -1):
        nxt_start[s] = s + 1 if is_start[s + 1] else nxt_start[s + 1] if s + 1 <= P - 1 else P
    D = [0.0 if is_start[s] else INF for s in range(P + 1)]   # before the first syllable
    D[0] = 0.0
    back = []                                     # per syllable: e -> (kind, s)
    argbest = []                                  # per syllable: the best end before it (where a jump comes from)
    for r in rough:
        # a jump leaves from the end of a word; leaving in the middle of one costs more
        bi = min(range(P + 1), key=lambda k: D[k] + (0 if (k == P or is_start[k]) else 1.5))
        best_prev = D[bi] + (0 if (bi == P or is_start[bi]) else 1.5)
        argbest.append(bi)
        N = [INF] * (P + 1)
        B = [None] * (P + 1)
        lr = len(r)
        for e in range(P + 1):                    # nothing matched: stay at e
            c = D[e] + insert + 0.2 * lr
            if c < N[e]:
                N[e], B[e] = c, ('ins', e)
        for l in range(max(1, lr - 2), lr + 3):
            for s in range(0, P - l + 1):
                if s + l > nxt_start[s]:
                    continue
                base = D[s]
                kind = 'go'
                if is_start[s] and best_prev + jump < base:
                    base, kind = best_prev + jump, 'jump'
                if base == INF:
                    continue
                e = s + l
                c = base + per_letter * edit(r, gl[s:e])
                if c < N[e]:
                    N[e], B[e] = c, (kind, s)
        back.append(B)
        D = N
    # back-track
    e = min(range(P + 1), key=lambda k: D[k])
    spans = []
    for i in range(len(rough) - 1, -1, -1):
        kind, s = back[i][e]
        spans.append(None if kind == 'ins' else (s, e))
        e = argbest[i] if kind == 'jump' else s
    spans.reverse()
    out = []
    for i, sp in enumerate(spans):
        if sp is None:
            out.append((rough[i], True))
            continue
        s, e = sp
        piece = ''.join(L.text[L.pos[k]] for k in range(s, e))
        if edit(rough[i], gl[s:e]) > max(2, round(0.75 * len(rough[i]))):
            out.append((rough[i], True))          # too unlike the syllable: its own spelling
            continue
        nxt = spans[i + 1] if i + 1 < len(spans) else None
        end_word = e >= L.word_end(e - 1) or nxt is None or nxt[0] != e
        out.append((piece, end_word))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('song')
    ap.add_argument('--bpm', type=float, default=60, help='quarter notes per minute (two matras)')
    ap.add_argument('--out')
    a = ap.parse_args()
    doc, lines, events = song_events(a.song)
    lyr_path = f'data/raw_data/text/lyrics/{a.song}.txt'
    glines = [l.strip() for l in open(lyr_path, encoding='utf-8')] if os.path.exists(lyr_path) else []
    glines = [l for l in glines if l]
    L = Lyrics(glines)
    L.last = 0

    # group events into sung lines
    groups = []
    for e in events:
        if e['newline'] or not groups:
            groups.append([])
        groups[-1].append(e)
    body = []
    every = [e for g in groups for e in g if e['syl']]
    aligned = dict(zip(map(id, every), align_song([e['syl'] for e in every], L)))
    for g in groups:
        syl_idx = [i for i, e in enumerate(g) if e['syl']]
        latin = [aligned[id(g[i])] for i in syl_idx]
        toks = ['_'] * len(g)
        first = True
        for (i, (txt, end)) in zip(syl_idx, latin):
            t = re.sub(r'[^A-Za-z\']', '', txt) or 'a'
            if first and t:
                t = t[0].upper() + t[1:]
            first = False
            toks[i] = t + ('' if end else '-')
        # a word held over notes stays one word: "aa-_-pon", not "aa-_ pon" (a space starts a new word)
        line_w, join = '', False
        for t in toks:
            if not line_w:
                line_w = t
            elif line_w.endswith('-'):
                line_w += t
            else:
                line_w += ('-' if join else ' ') + t
            if t != '_':
                join = t.endswith('-')
        notes = ' '.join(abc_note(e['midi'], e['units']) for e in g)
        if g[0].get('newline') and g[0]['line'] == groups[0][0]['line'] and body:
            body.append('P:Sthayi')
        body.append(notes + ' |')
        body.append('w: ' + line_w)
    title = doc.get('title', a.song)
    head = [
        'X:1', f'T:{a.song}', 'C:Rabindranath Tagore',
        f"S:notes and syllables: SNLTR Rabindra Rachanabali swaralipi ({doc.get('song_page', '')}), "
        f"title {title}, tala {doc.get('tala', '')}",
        f'S:lyrics: {lyr_path} (Geetabitan transliteration), aligned to the swaralipi syllables',
        'N:Made by scripts/swaralipi_player/swara_abc.py: one matra = one eighth note; Sa = C; grace notes left out.',
        'M:none', 'L:1/32', f'Q:1/4={a.bpm:g}', 'K:C']
    out = a.out or f'data/intermediate_data/abc/{a.song}/v1.abc'
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, 'w', encoding='utf-8').write('\n'.join(head + ['P:Sthayi'] + body) + '\n')
    print(f'{len(events)} notes, {len(groups)} lines, {sum(1 for e in events if e["syl"])} syllables -> {out}')


if __name__ == '__main__':
    main()
