#!/usr/bin/env python3
"""
swara_to_ktab.py

Kalimba tab (.ktab) from a swaralipi written out as text (.swara):

    python swara_to_ktab.py ekla_cholo_re.swara --title "Ekla Cholo Re"

The .swara format (see ekla_cholo_re.swara):
  - one ktab line per text line, a blank line between stanzas, '#' comments;
  - each syllable is  text:cells ; a text ending in '-' joins the next
    syllable into the same word (Jo-:N_ di:N_  ->  (Jo: ..)(di: ..));
  - cells are separated by ',' and each is one matra. In a cell
    S R G M P D N = sa re ga ma pa dha ni, n = komal ni, r g m d = komal re,
    komal ga, tivra ma, komal dha; ^ = upper octave, _ = lower octave;
    '-' = the note before goes on. Two signs in a cell share the matra
    equally, three are taken as 1/2 1/4 1/4 (ktab has no triplets).

Lengths: two matras make one ktab beat (--matras-per-beat 2, the default,
like the lesson tabs at ~110 bpm): a matra is written 5/, two are 5,
three 5. ; with --matras-per-beat 1 a matra is one beat.

Fitting a C kalimba (1 = C4 .. 3'' = E6) - transposition, a stanza moved by
an octave, a retuned tine or a substituted note - is done as in
abc_to_ktab.py, and every choice is printed. --sa places Sa yourself
(e.g. --sa G4).
"""

import argparse
import re
import sys
from fractions import Fraction
from pathlib import Path

from abc_to_ktab import HEADER, marks, plan, written

SEMI = {"S": 0, "r": 1, "R": 2, "g": 3, "G": 4, "M": 5, "m": 6, "P": 7, "d": 8, "D": 9, "n": 10, "N": 11}
NOTE_NAMES = "C C# D D# E F F# G G# A A# B".split()
TOKEN = re.compile(r"-|[SrRgGMmPdDnN][\^_]*")


def midi_of_name(s):
    m = re.fullmatch(r"([A-Ga-g]#?)(-?\d)", s)
    if not m:
        sys.exit(f"--sa: give a note like G4 or E4, not {s!r}")
    return 12 * (int(m.group(2)) + 1) + NOTE_NAMES.index(m.group(1).upper())


def parse_cell(cell, where):
    toks = TOKEN.findall(cell)
    if "".join(toks) != cell or not toks:
        sys.exit(f"{where}: can't read the cell {cell!r}")
    shares = {1: [1], 2: [Fraction(1, 2)] * 2, 3: [Fraction(1, 2), Fraction(1, 4), Fraction(1, 4)]}.get(len(toks))
    if shares is None:
        sys.exit(f"{where}: more than three signs in one matra: {cell!r}")
    return list(zip(toks, shares))


def parse(path):
    """-> stanzas: list of lines; a line is a list of (text, joins_next, notes);
    notes = [[semitones from Sa, matras], ...]."""
    stanzas, cur = [], []
    for no, raw in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        line = raw.split("#")[0].strip()
        if not line:
            if cur:
                stanzas.append(cur)
                cur = []
            continue
        sylls, last_note = [], None
        for item in line.split():
            if ":" not in item:
                sys.exit(f"line {no}: {item!r} has no ':'")
            text, cells = item.split(":", 1)
            notes = []
            for cell in cells.split(","):
                for tok, share in parse_cell(cell, f"line {no}"):
                    if tok == "-":
                        target = notes[-1] if notes else last_note
                        if target is None:
                            sys.exit(f"line {no}: '-' with no note before it")
                        target[1] += share
                    else:
                        semis = SEMI[tok[0]] + 12 * (tok.count("^") - tok.count("_"))
                        notes.append([semis, Fraction(share)])
            if not notes:                            # only holds: belongs to the syllable before
                continue
            last_note = notes[-1]
            sylls.append((text.rstrip("-"), text.endswith("-"), notes))
        cur.append(sylls)
    if cur:
        stanzas.append(cur)
    return stanzas


def main():
    ap = argparse.ArgumentParser(description="Swaralipi written out as .swara -> kalimba tab (.ktab).")
    ap.add_argument("swara")
    ap.add_argument("--title", help="title (default: the file name)")
    ap.add_argument("--out", help="ktab file (default: next to the .swara)")
    ap.add_argument("--sa", help="the note Sa is played as, e.g. G4 (default: the best fit for the kalimba)")
    ap.add_argument("--matras-per-beat", type=int, default=2, choices=[1, 2])
    args = ap.parse_args()

    stanzas = parse(args.swara)
    base = 64                                        # Sa = E4 to start from; plan() transposes
    transpose = None
    if args.sa:
        transpose = midi_of_name(args.sa) - base
    pitches = [[base + s for ln in st for _, _, ns in ln for s, _ in ns] for st in stanzas]
    stanza_shift, retune, play_as, report = plan(pitches, transpose)
    shift = stanza_shift[0] if transpose is None else transpose
    sa = base + (transpose if transpose is not None else 0)
    for r in report:
        print(r)

    beat = "quarter" if args.matras_per_beat == 2 else "eighth"
    out = [f"@title: {args.title or Path(args.swara).stem}"] + HEADER + [""]
    for si, st in enumerate(stanzas):
        if si:
            out.append("")
        for sylls in st:
            words, word = [], ""
            for text, joins, notes in sylls:
                evs = [written(base + s + stanza_shift[si], retune, play_as) + marks(m, beat) for s, m in notes]
                word += f"({text}: {' '.join(evs)})"
                if not joins:
                    words.append(word)
                    word = ""
            if word:
                words.append(word)
            out.append(" ".join(words))
    path = Path(args.out) if args.out else Path(args.swara).with_suffix(".ktab")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    n = sum(len(ns) for st in stanzas for ln in st for _, _, ns in ln)
    print(f"ktab: {path}  ({len(stanzas)} stanzas, {n} notes)")


if __name__ == "__main__":
    main()
