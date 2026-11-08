#!/usr/bin/env python3
"""Convert a MIDI melody into a notes-only .ktab draft (empty lyrics).

    python scripts/midi_to_ktab.py data/raw_data/midi/rs002164.mid \
        -o data/intermediate_data/rs002164.ktab --title "Tumi Robe Nirobe"

Steps:
  1. Pick the melody track: the one with the most notes that never sound together
     (or pass --track N).
  2. Apply pitch bends. Some arrangers slide into the next note by bending
     (meend), so a single MIDI note can hold several melody notes. The bend range
     is read from the RPN 0 messages (default 2 semitones).
  3. Quantize to a grid (default a 16th note). Bend steps shorter than half a
     grid cell are slides between notes and are dropped.
  4. Write scale degrees in the given key (default: the key signature, else C).
     Middle octave = MIDI 60-71 relative to the tonic.
     Notes outside the major scale have no ktab spelling. They are written as the
     scale note one semitone below and reported on stderr, so check them by hand.

Every note becomes its own empty-lyric group "( : 3)", every bar is one word,
bars are separated by " | ", and --bars-per-line bars go on each line.
"""
import argparse
import sys
from fractions import Fraction

import mido

MAJOR = {0: 1, 2: 2, 4: 3, 5: 4, 7: 5, 9: 6, 11: 7}
KEYS = {k: i for i, k in enumerate("C C# D D# E F F# G G# A A# B".split())}
KEYS.update({"Db": 1, "Eb": 3, "Gb": 6, "Ab": 8, "Bb": 10})
NAMES = "C C# D D# E F F# G G# A A# B".split()


def drop_passing(segs, end, slide):
    """Remove the in-between steps of a bend slide (D -> D# -> E keeps D and E).

    A step is passing when its pitch lies strictly between its neighbours and it
    lasts less than `slide` ticks; its time goes to the step before it."""
    segs = [list(s) for s in segs]
    changed = True
    while changed and len(segs) > 2:
        changed = False
        for i in range(1, len(segs) - 1):
            lo, hi = sorted((segs[i - 1][1], segs[i + 1][1]))
            dur = segs[i + 1][0] - segs[i][0]
            if lo < segs[i][1] < hi and dur < slide:
                del segs[i]
                changed = True
                break
    merged = [segs[0]]
    for s in segs[1:]:
        if s[1] != merged[-1][1]:
            merged.append(s)
    return merged


def read_tracks(mid):
    """Per track: list of (start, end, pitch) after pitch bends; plus meta info."""
    slide = mid.ticks_per_beat // 2       # bend steps shorter than an 8th can be slides
    meta = {"timesig": (4, 4), "key": None}
    tracks = []
    for tr in mid.tracks:
        tick = 0
        bend = {}          # channel -> semitones (float)
        brange = {}        # channel -> semitones
        rpn = {}           # channel -> (msb, lsb)
        sounding = {}      # (channel, note) -> list of [start, pitch]
        out = []

        def close(ch, note, t):
            segs = sounding.pop((ch, note), None)
            if not segs:
                return
            segs = drop_passing(segs, t, slide)
            for (s, p), nxt in zip(segs, segs[1:] + [[t, None]]):
                out.append((s, nxt[0], p))

        for msg in tr:
            tick += msg.time
            if msg.type == "time_signature" and tick == 0:
                meta["timesig"] = (msg.numerator, msg.denominator)
            elif msg.type == "key_signature" and meta["key"] is None:
                meta["key"] = msg.key
            elif msg.type == "control_change":
                ch = msg.channel
                if msg.control == 101:
                    rpn[ch] = (msg.value, rpn.get(ch, (127, 127))[1])
                elif msg.control == 100:
                    rpn[ch] = (rpn.get(ch, (127, 127))[0], msg.value)
                elif msg.control == 6 and rpn.get(ch) == (0, 0):
                    brange[ch] = msg.value
            elif msg.type == "pitchwheel":
                ch = msg.channel
                bend[ch] = msg.pitch / 8192 * brange.get(ch, 2)
                for (c, n), segs in sounding.items():
                    if c == ch:
                        p = n + round(bend[ch])
                        if p != segs[-1][1]:
                            if segs[-1][0] == tick:
                                segs[-1][1] = p
                            else:
                                segs.append([tick, p])
            elif msg.type == "note_on" and msg.velocity > 0:
                close(msg.channel, msg.note, tick)
                sounding[(msg.channel, msg.note)] = [[tick, msg.note + round(bend.get(msg.channel, 0))]]
            elif msg.type in ("note_off", "note_on"):
                close(msg.channel, msg.note, tick)
        out.sort()
        tracks.append((tr.name, out))
    return tracks, meta


def is_monophonic(notes):
    return all(b[0] >= a[1] for a, b in zip(notes, notes[1:]))


def quantize(notes, grid):
    q = []
    for s, e, p in notes:
        s2, e2 = round(s / grid) * grid, round(e / grid) * grid
        if e2 - s2 < grid:          # shorter than half a cell: a slide, drop it
            continue
        if q and s2 < q[-1][1]:     # rounding overlap: trim the previous note
            q[-1] = (q[-1][0], s2, q[-1][2])
        q.append((s2, e2, p))
    return [n for n in q if n[1] > n[0]]


def degree(pitch, tonic):
    """MIDI pitch -> (ktab text, exact?) in the major key on `tonic` (0-11)."""
    rel = pitch - (60 + tonic)
    octave, pc = divmod(rel, 12)
    exact = pc in MAJOR
    deg = MAJOR.get(pc) or MAJOR[pc - 1]
    marks = "'" * octave if octave > 0 else "," * -octave
    return f"{deg}{marks}", exact


def length(beats: Fraction) -> str:
    """Beats -> slashes/dot/dashes suffix, e.g. 0.75 -> '/.', 3.75 -> '/.---'."""
    for whole in range(int(beats) + 1):          # fewest dashes first: 1.5 -> '.', not '/-'
        rest = beats - whole
        for s in range(4):
            base = Fraction(1, 2 ** s)
            for dot, mark in ((base, ""), (base * Fraction(3, 2), ".")):
                if rest == dot:
                    return "/" * s + mark + "-" * whole
    raise ValueError(f"can't write a length of {beats} beats")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("midi")
    ap.add_argument("-o", "--out", help="output .ktab (default: stdout)")
    ap.add_argument("--title", help="@title header")
    ap.add_argument("--track", type=int, help="melody track index (default: auto)")
    ap.add_argument("--key", help="tonic, e.g. C, G, Bb (default: key signature or C)")
    ap.add_argument("--grid", type=int, default=16, help="quantize to 1/N notes (default 16)")
    ap.add_argument("--bars-per-line", type=int, default=4)
    a = ap.parse_args()

    mid = mido.MidiFile(a.midi)
    tracks, meta = read_tracks(mid)
    if a.track is None:
        cands = [(len(n), i) for i, (_, n) in enumerate(tracks) if n and is_monophonic(n)]
        if not cands:
            sys.exit("no monophonic track found; pick one with --track")
        a.track = max(cands)[1]
    name, notes = tracks[a.track]

    key = a.key or (meta["key"] or "C").rstrip("m")
    if key not in KEYS:
        sys.exit(f"unknown key {key!r}")
    tonic = KEYS[key]
    num, den = meta["timesig"]
    beat = mid.ticks_per_beat * 4 // den         # one beat = the time signature's unit
    bar = beat * num
    notes = quantize(notes, mid.ticks_per_beat * 4 // a.grid)

    print(f"track {a.track} ({name or 'unnamed'}): {len(notes)} notes, key {key}, "
          f"{num}/{den}", file=sys.stderr)

    # split into bars; a note keeps the bar it starts in
    bars, prev = {}, notes[0][0] if notes else 0
    warnings = 0
    for s, e, p in notes:
        if s > prev:
            bars.setdefault(prev // bar, []).append(f"( : 0{length(Fraction(s - prev, beat))})")
        txt, exact = degree(p, tonic)
        if not exact:
            warnings += 1
            print(f"warning: bar {s // bar + 1}: {NAMES[p % 12]}{p // 12 - 1} is not in {key} major,"
                  f" written as {txt}", file=sys.stderr)
        bars.setdefault(s // bar, []).append(f"( : {txt}{length(Fraction(e - s, beat))})")
        prev = e

    first, last = min(bars), max(bars)
    words = ["".join(bars.get(b, [f"( : 0{length(Fraction(bar, beat))})"])) for b in range(first, last + 1)]
    lines = [" | ".join(words[i:i + a.bars_per_line]) for i in range(0, len(words), a.bars_per_line)]

    head = [f"@title: {a.title}"] if a.title else []
    text = "\n".join(head + ([""] if head else []) + lines) + "\n"
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"wrote {a.out}: {len(words)} bars, {len(lines)} lines, {warnings} warning(s)",
              file=sys.stderr)
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
