#!/usr/bin/env python3
"""ABC draft from the Geetabitan MIDI (notes, rhythm) and the SNLTR swaralipi text (syllables).

    python scripts/swaralipi_player/midi_swara_abc.py rs001397 [--out-dir data/intermediate_data/abc/rs001397]

Writes v1.abc (L:1/8, the MIDI's meter and tempo) and v2.abc (the same with note values halved,
L:1/16, so the tab plays at half the MIDI's beat count per minute), both with w: lyrics.

How
  1. Melody: the MIDI's violin/melody track, quantized to 16ths, as ABC bars with ties across bar
     lines (the same tokens as midi_bars.py in TASK_TIER2.md, so check_abc.py can compare them).
  2. Swaralipi: the notes in singing order with their syllables (swara_abc.py), Sa = C4.
  3. Alignment: the MIDI's tied notes are joined; both note sequences are compared by pitch class,
     the MIDI shifted by its Sa (the shift with the longest common subsequence), with an exact LCS.
     A swaralipi syllable goes on its matched MIDI note; if its note is not matched, on the next
     matched MIDI note.
  4. Lyrics: each syllable's Latin spelling and word ends come from the Geetabitan transliteration
     (swara_abc.align_song); MIDI notes between syllables hold the syllable before ('_'); a stretch
     of MIDI notes the swaralipi doesn't sing (an introduction or interlude) gets '*'.
  5. Lines: a new ABC line starts at the bar where a sung swaralipi row's first syllable falls.
"""
import argparse
import re
import os
import sys
from fractions import Fraction as F

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import mido  # noqa: E402
import midi_to_ktab as MK  # noqa: E402
import swara_abc as SA  # noqa: E402
import note_align as NA  # noqa: E402

N = 'C ^C D ^D E F ^F G ^G A ^A B'.split()


def split_channels(mid):
    """A type-0 MIDI (everything in one track) -> type 1 with one track per channel, so the melody
    can be picked like a melody track. Meta messages go to every track; other files are unchanged."""
    if mid.type != 0 or len(mid.tracks) != 1:
        return mid
    chans = sorted({m.channel for m in mid.tracks[0] if hasattr(m, 'channel')})
    out = mido.MidiFile(type=1, ticks_per_beat=mid.ticks_per_beat)
    for ch in chans:
        t, tick, last = mido.MidiTrack(), 0, 0
        for m in mid.tracks[0]:
            tick += m.time
            if m.is_meta or getattr(m, 'channel', None) == ch:
                t.append(m.copy(time=tick - last))
                last = tick
        out.tracks.append(t)
    return out


def midi_bars(song):
    """-> (bars: [[(token, midi or None, tied_on)]], meter (num, den), tempo bpm, track name)"""
    mid = split_channels(mido.MidiFile(os.path.join(ROOT, f'data/raw_data/midi/{song}.mid')))
    tpb = mid.ticks_per_beat
    tr, meta = MK.read_tracks(mid)
    c = []
    for i, (nm, n) in enumerate(tr):
        if len(n) < 50:
            continue
        ov = sum(1 for a, b in zip(n, n[1:]) if b[0] < a[1]) / len(n)
        c.append((ov, sum(x[2] for x in n) / len(n), i))
    i = max([x for x in c if x[0] < 0.5], key=lambda x: x[1])[2]
    notes = MK.quantize(tr[i][1], tpb // 4)
    num, den = meta['timesig']
    bar = tpb * 4 // den * num
    tempo = next((mido.tempo2bpm(m.tempo) for t in mid.tracks for m in t if m.type == 'set_tempo'), 120)

    def nm(p):
        o = p // 12 - 1
        n_ = N[p % 12]
        return n_.lower() + "'" * (o - 5) if o >= 5 else n_ + "," * (4 - o)

    def ln(t):
        f = F(t, tpb // 2)
        if f == 1:
            return ""
        if f.denominator == 1:
            return str(f.numerator)
        if f.numerator == 1 and f.denominator in (2, 4):
            return "/" * {2: 1, 4: 2}[f.denominator]
        return f"{f.numerator}/{f.denominator}"

    ev, prev = [], 0
    for a, b, p in notes:
        if a > prev:
            ev.append((prev, a, None))
        ev.append((a, b, p))
        prev = b
    bars, acc = {}, {}

    def spell(k, p):
        s = nm(p)
        base = s.lstrip('^')
        if s.startswith('^'):
            acc[(k, base)] = '^'
            return s
        if acc.get((k, base)) == '^':
            acc[(k, base)] = '='
            return '=' + base
        return s

    for a, b, p in ev:
        t, first = a, True
        while t < b:
            k = t // bar
            e = min(b, (k + 1) * bar)
            tok = ("z" if p is None else spell(k, p)) + ln(e - t)
            if p is not None and e < b:
                tok += "-"
            bars.setdefault(k, []).append((tok, p, p is not None and not first))
            t, first = e, False
    out = [bars.get(k, [(f"z{ln(bar)}", None, False)]) for k in range(max(bars) + 1)]
    return out, (num, den), tempo, tr[i][0]


def tok_len(tok):
    """length of an ABC note token in eighths ('c2' 2, 'd/' 1/2, 'e3/2' 3/2, 'f' 1)"""
    m = re.search(r'(\d*)(/*)(\d*)-?$', tok)
    num = int(m.group(1) or 1)
    if m.group(2):
        den = int(m.group(3)) if m.group(3) else 2 ** len(m.group(2))
        return num / den
    return float(num)


def lcs_pairs(a, b):
    """index pairs of an exact longest common subsequence of a and b"""
    n, m = len(a), len(b)
    L = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        Li, Li1, ai = L[i], L[i + 1], a[i]
        for j in range(m - 1, -1, -1):
            Li[j] = Li1[j + 1] + 1 if ai == b[j] else max(Li1[j], Li[j + 1])
    i = j = 0
    out = []
    while i < n and j < m:
        if a[i] == b[j]:
            out.append((i, j)); i += 1; j += 1
        elif L[i + 1][j] >= L[i][j + 1]:
            i += 1
        else:
            j += 1
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('song')
    ap.add_argument('--out-dir')
    a = ap.parse_args()
    s = a.song
    bars, (num, den), tempo, track = midi_bars(s)
    # MIDI notes (tied notes joined): (bar, index in bar, midi)
    mnotes, mlen = [], []
    for bi, b in enumerate(bars):
        for k, (tok, p, tied_on) in enumerate(b):
            if p is None:
                continue
            if not tied_on:
                mnotes.append((bi, k, p)); mlen.append(0.0)
            if mlen:
                mlen[-1] += tok_len(tok)
    doc, lines, sev = SA.song_events(s)
    # swaralipi notes paired with MIDI notes by pitch class and length (note_align: where a pitch
    # repeats, the note of the right length is taken); only pairs of equal pitch class count
    pair, sh = NA.align([e['midi'] for e in sev], [p for _, _, p in mnotes], [e['units'] for e in sev], mlen)
    s2m = {j: mi for j, mi in enumerate(pair)
           if mi is not None and sev[j]['midi'] % 12 == (mnotes[mi][2] + sh) % 12}
    pairs = sorted(s2m.items())
    sa_shift = (-sh) % 12                          # MIDI pitch - sa_shift = the swaralipi's (Sa = C)
    # Latin for every swaralipi syllable, sung line by sung line
    lyr_path = os.path.join(ROOT, f'data/raw_data/text/lyrics/{s}.txt')
    glines = [l.strip() for l in open(lyr_path, encoding='utf-8') if l.strip()] if os.path.exists(lyr_path) else []
    Ly = SA.Lyrics(glines)
    Ly.last = 0
    idx = [j for j, e in enumerate(sev) if e['syl']]          # the whole song at once (swara_abc.align_song)
    latin = dict(zip(idx, SA.align_song([sev[j]['syl'] for j in idx], Ly)))
    # syllables onto MIDI notes. A syllable whose swaralipi note is paired with a MIDI note goes there.
    # The others, between two such anchors, go on the free MIDI notes between them in order. If one
    # or two are left without a note, they join the syllable before; if three or more are, the MIDI
    # does not play that passage (a repeat the swaralipi sings and the MIDI does not): they are left
    # out rather than packed onto one note.
    syl_at = {}                                    # MIDI note index -> (text, end_word, starts a sung row)
    syl_js = [j for j, e in enumerate(sev) if e['syl'] and j in latin]
    item = {j: (latin[j][0], latin[j][1], sev[j]['newline']) for j in syl_js}
    anchors, last_m = [], -1
    for j in syl_js:                               # paired syllables, in order on both sides
        if j in s2m and s2m[j] > last_m:
            anchors.append(j); last_m = s2m[j]
    anchor_set = set(anchors)
    for j in anchors:
        syl_at[s2m[j]] = item[j]
    bounds = [(-1, -1)] + [(j, s2m[j]) for j in anchors] + [(len(sev), len(mnotes))]
    for (j0, m0), (j1, m1) in zip(bounds, bounds[1:]):
        between = [j for j in syl_js if j0 < j < j1 and j not in anchor_set]
        if not between:
            continue
        free = [mi for mi in range(m0 + 1, m1) if mi not in syl_at]
        if len(free) >= len(between):
            # spread in order: each at about its own distance from the anchor before, never backwards
            k = 0
            for j in between:
                want = m0 + (j - j0)
                while k < len(free) - (len(between) - between.index(j) - 1) - 1 and free[k] < want:
                    k += 1
                syl_at[free[k]] = item[j]; k += 1
            continue
        missing = len(between) - len(free)
        for mi, j in zip(free, between):
            syl_at[mi] = item[j]
        if missing >= 3:
            continue                               # a passage the MIDI does not play: left out
        for j in between[len(free):]:              # one or two short: join the syllable before
            prev_m = max((mi for mi in syl_at if mi < m1), default=None)
            if prev_m is not None:
                p0 = syl_at[prev_m]
                syl_at[prev_m] = (p0[0] + item[j][0], item[j][1], p0[2])
    sung = set(s2m.values())
    # tokens per MIDI note: syllable, hold, or '*' (in a long stretch the swaralipi doesn't sing)
    toks = []
    first_syl = min(syl_at) if syl_at else len(mnotes)
    last_syl = max(syl_at) if syl_at else -1
    run_unsung = 0
    for mi in range(len(mnotes)):
        if mi in syl_at:
            toks.append(syl_at[mi])
        elif mi < first_syl:
            toks.append('*')
        else:
            # count unsung notes around: a stretch of 8+ MIDI notes with no swaralipi match is instrumental
            lo = mi
            while lo > 0 and (lo - 1) not in sung and (lo - 1) not in syl_at:
                lo -= 1
            hi = mi
            while hi + 1 < len(mnotes) and (hi + 1) not in sung and (hi + 1) not in syl_at:
                hi += 1
            toks.append('*' if hi - lo + 1 >= 8 and mi not in sung else '_')
    # render bars into lines; a line starts at the bar of a syllable that starts a sung row
    note_at = {(bi, k): mi for mi, (bi, k, _) in enumerate(mnotes)}
    line_starts = {0}
    for mi, t in enumerate(toks):
        if isinstance(t, tuple) and t[2]:
            line_starts.add(mnotes[mi][0])
    music, words = [], []
    in_word = False
    cur_m, cur_w = [], ''
    for bi, b in enumerate(bars):
        if bi in line_starts and cur_m:
            music.append(' | '.join(cur_m) + ' |'); words.append(cur_w.strip() + ' |')
            cur_m, cur_w = [], ''
        cur_m.append(' '.join(tok for tok, _, _ in b))
        piece = ''
        for k, (tok, p, tied_on) in enumerate(b):
            if p is None:
                continue
            if tied_on:
                t = '_-' if in_word else '_'
            else:
                t = toks[note_at[(bi, k)]]
                if isinstance(t, tuple):
                    txt = ''.join(ch for ch in t[0] if ch.isalpha() or ch == "'") or 'a'
                    if t[2]:
                        txt = txt[0].upper() + txt[1:]
                    in_word = not t[1]
                    t = txt + ('-' if in_word else '')
                elif t == '*':
                    in_word = False
                else:
                    t = '_-' if in_word else '_'
            sep = '' if (piece.endswith('-') or not piece) else ' '
            piece += sep + t
        if cur_w:
            cur_w += '|' if cur_w.endswith('-') else ' | '
        cur_w += piece
    if cur_m:
        music.append(' | '.join(cur_m) + ' |]'); words.append(cur_w.strip() + ' |')
    title = doc.get('title', s)
    head = ['X:1', f'T:{s}', 'C:Rabindranath Tagore',
            f'S:notes: data/raw_data/midi/{s}.mid (Geetabitan, arranged by Anjan Ganguly), {track} track',
            f"S:syllables: SNLTR Rabindra Rachanabali swaralipi ({title}), aligned to the MIDI by midi_swara_abc.py",
            f'S:lyrics: data/raw_data/text/lyrics/{s}.txt (Geetabitan transliteration)',
            f'N:Swaralipi notes matched to MIDI notes: {len(pairs)} of {len(sev)} (MIDI has {len(mnotes)}); '
            f'Sa of the MIDI = {N[sa_shift].replace("^", "")}. Notes quantized to 16ths. "*" = notes the swaralipi does not sing.']
    body = []
    for mline, wline in zip(music, words):
        body += [mline, 'w: ' + wline]
    out = a.out_dir or os.path.join(ROOT, f'data/intermediate_data/abc/{s}')
    os.makedirs(out, exist_ok=True)
    v1 = head + [f'M:{num}/{den}', 'L:1/8', f'Q:1/4={tempo:g}', 'K:C'] + body
    m2 = f'{num}/{den * 2}'
    v2 = head + ['N:v2: v1 with note values halved, so the tab plays at half the beats per minute.',
                 f'M:{m2}', 'L:1/16', f'Q:1/4={tempo / 2:g}', 'K:C'] + body
    open(os.path.join(out, 'v1.abc'), 'w', encoding='utf-8').write('\n'.join(v1) + '\n')
    open(os.path.join(out, 'v2.abc'), 'w', encoding='utf-8').write('\n'.join(v2) + '\n')
    nsyl = sum(1 for t in toks if isinstance(t, tuple))
    print(f'{s}: {len(mnotes)} MIDI notes, swaralipi {len(sev)} notes, {len(pairs)} matched '
          f'({100 * len(pairs) / max(1, len(sev)):.0f}%), {nsyl} syllables placed, {len(music)} lines -> {out}')


if __name__ == '__main__':
    main()
