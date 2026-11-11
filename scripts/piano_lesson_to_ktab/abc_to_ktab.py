#!/usr/bin/env python3
"""
abc_to_ktab.py

ABC sheet music (one tune, with w: lyrics) -> kalimba tab (.ktab):

    (A: 5/)(mi: 6/) (chi: 7/)(ni: 7/)       one group per syllable, its notes
                                             after the colon; groups with no
                                             space between them make one word

    python abc_to_ktab.py song.abc                    -> song.ktab
    python abc_to_ktab.py song.abc --out tab.ktab --transpose -2 --beat quarter

What it does
  * Notes: the ABC's pitches (with its key signature and bar accidentals) are
    written as the tines of a kalimba tuned in C: 1 = C4 ... 7 = B4,
    1' = C5, 1'' = C6, 5, = G3. ktab has no sharps or flats, so:
      - the song is transposed to fit the kalimba best (fewest notes it can't
        play, then its middle nearest 1'..2'), unless --transpose is given;
      - a stanza outside the kalimba's range moves an octave as a whole;
      - a note the kalimba doesn't have goes on a neighbouring tine the song
        doesn't otherwise use, which the player retunes; if both neighbours are
        in use, a note the kalimba has is played instead (the same for the
        whole song, keeping the melody's direction).
    Every such choice is printed.
  * Lengths: one beat = a quarter note (--beat quarter, the default) or an
    eighth (--beat eighth). '/' halves, '.' is half as long again, each '-' adds
    a beat: an eighth is 5/, a dotted quarter 5., two and a half beats 5.-.
    Tied notes become one note; a rest (z) becomes 0 in the group before it.
  * Lyrics: the w: line under each music line. A '-' joins syllables of one
    word, a space starts a new word, '_' holds the syllable over one more note,
    '*' skips a note. '?' marks of uncertainty are dropped (--keep-marks keeps
    them). A note with no syllable gets an empty one: ( : 5).
  * Layout: one ktab line per ABC music line, a blank line between the parts
    (P:) of the tune, so each stanza is a ktab stanza.
"""

import argparse
import re
import sys
from fractions import Fraction
from pathlib import Path

LETTERS = "CDEFGAB"
NATURAL = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
MAJOR = (0, 2, 4, 5, 7, 9, 11)
NAMES = "C C# D D# E F F# G G# A A# B".split()
# mode -> (letters, semitones) from its relative major's tonic
MODES = {"": (0, 0), "maj": (0, 0), "ion": (0, 0), "dor": (1, 2), "phr": (2, 4), "lyd": (3, 5),
         "mix": (4, 7), "m": (5, 9), "min": (5, 9), "aeo": (5, 9), "loc": (6, 11)}
HEADER = ["@margin: 1.2cm", "@beat: 1.8em", "@wordgap: .55em", "@linegap: .6em", "@stanzagap: .9em"]
LOW, HIGH = 60, 88                         # 17-key kalimba in C: 1 (C4) .. 3'' (E6)
TINES_17 = set("1 2 3 4 5 6 7 1' 2' 3' 4' 5' 6' 7' 1'' 2'' 3''".split())


def name(m):
    return f"{NAMES[m % 12]}{m // 12 - 1}"


# ----------------------------------------------------------------------------
# ABC
# ----------------------------------------------------------------------------

def key_signature(k):
    """K: field -> alteration per letter, e.g. 'Bm' -> F and C sharp."""
    k = k.split("%")[0].strip()
    m = re.match(r"([A-G])([#b]?)\s*([A-Za-z]*)", k)
    if not m or k.lower().startswith("none"):
        return {l: 0 for l in LETTERS}
    letter, acc, mode = m.group(1), m.group(2), m.group(3).lower()
    mode = next((x for x in sorted(MODES, key=len, reverse=True) if x and mode.startswith(x)), "")
    dl, ds = MODES[mode]
    tonic = (NATURAL[letter] + {"#": 1, "b": -1, "": 0}[acc]) % 12
    li = (LETTERS.index(letter) - dl) % 7           # relative major
    tp = (tonic - ds) % 12
    sig = {}
    for i, step in enumerate(MAJOR):
        lt = LETTERS[(li + i) % 7]
        sig[lt] = ((tp + step - NATURAL[lt] + 6) % 12) - 6
    return sig


def length_of(s, unit):
    """ABC length suffix ('', '2', '/2', '3/2', '/') in eighths, given L:."""
    if not s:
        return unit
    m = re.fullmatch(r"(\d*)(/*)(\d*)", s)
    num = int(m.group(1)) if m.group(1) else 1
    if m.group(2):
        den = int(m.group(3)) if m.group(3) else 2 ** len(m.group(2))
    else:
        den = 1
    return unit * num / den


def parse_abc(text):
    """-> title, stanzas; a stanza is a list of lines; a line is a list of
    events dict(kind='note'|'rest', midi, eighths, tok). Each note gets its
    lyric token (syllable, '_' or '*') in ABC order, where a tied-on note has
    its own token; then tied notes are joined into one (also across lines)."""
    title, unit, sig = "", Fraction(1), {l: 0 for l in LETTERS}
    stanzas, cur, last = [], [], None
    in_body = False
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line or line.startswith("%"):
            continue
        f = re.match(r"([A-Za-z]):(.*)", line)
        if f and f.group(1) != "w":
            key, val = f.group(1), f.group(2).strip()
            if key == "T" and not title:
                title = val
            elif key == "L":
                a, b = val.split("/")
                unit = Fraction(int(a), int(b)) / Fraction(1, 8)       # in eighths
            elif key == "K":
                sig = key_signature(val)
                in_body = True
            elif key == "P" and in_body:
                if cur:
                    stanzas.append(cur)
                cur = []
            continue
        if line.startswith("w:"):
            if last is not None:
                notes = [e for e in last if e["kind"] == "note" and "tok" not in e]
                for e, t in zip(notes, lyric_tokens(line[2:])):
                    e["tok"] = t
            continue
        if not in_body:
            continue
        last = music_line(line, unit, sig)
        cur.append(last)
    if cur:
        stanzas.append(cur)
    # join tied notes: the tied-on note (and its '_' token) merges into the one before
    for st in stanzas:
        prev = None
        for ln in st:
            keep = []
            for e in ln:
                if e["kind"] == "note" and prev is not None and prev.get("tie") and prev["midi"] == e["midi"]:
                    prev["eighths"] += e["eighths"]
                    prev["tie"] = e.get("tie")
                    continue
                keep.append(e)
                prev = e if e["kind"] == "note" else None
            ln[:] = keep
    return title, stanzas


def music_line(line, unit, sig):
    """One line of ABC music -> events (ties marked, not yet joined)."""
    line = re.sub(r'"[^"]*"', "", line)              # annotations ("^?") and chord names
    line = re.sub(r"![^!]*!", "", line)              # decorations
    line = re.sub(r"\{[^}]*\}", "", line)          # grace notes
    line = re.sub(r"\[[A-Za-z]:[^\]]*\]", "", line)  # inline fields
    events, bar_acc = [], {}
    tok = re.compile(r"(\[[^\]]*\])([\d/]*)(-?)|([_=^]{0,2})([A-Ga-g])([',]*)([\d/]*)(-?)|([zx])([\d/]*)|(\|+\]?|\]|:\||\|:)")
    pos = 0
    while pos < len(line):
        m = tok.match(line, pos)
        if not m:
            pos += 1
            continue
        pos = m.end()
        if m.group(11):                              # bar line
            bar_acc = {}
        elif m.group(9):                             # rest
            events.append(dict(kind="rest", midi=None, eighths=length_of(m.group(10), unit)))
        elif m.group(1):                             # chord: its top note is the melody
            notes = re.findall(r"([_=^]{0,2})([A-Ga-g])([',]*)", m.group(1))
            mids = [pitch(a, l, o, sig, bar_acc) for a, l, o in notes]
            events.append(dict(kind="note", midi=max(mids), eighths=length_of(m.group(2), unit),
                               tie=m.group(3) == "-"))
        else:
            events.append(dict(kind="note", midi=pitch(m.group(4), m.group(5), m.group(6), sig, bar_acc),
                               eighths=length_of(m.group(7), unit), tie=m.group(8) == "-"))
    return events


def pitch(acc, letter, octs, sig, bar_acc):
    up = letter.islower()
    L = letter.upper()
    octave = 5 if up else 4
    octave += octs.count("'") - octs.count(",")
    if acc:
        alt = {"^": 1, "^^": 2, "_": -1, "__": -2, "=": 0}[acc]
        bar_acc[(L, octave)] = alt
    else:
        alt = bar_acc.get((L, octave), sig[L])
    return 12 * (octave + 1) + NATURAL[L] + alt


def lyric_tokens(w):
    """ABC w: text -> per-note tokens: (syllable, starts_word) or ('_',),
    ('*',). '-' joins syllables of a word, a space starts a new word."""
    out, buf, new_word = [], "", True
    w = w.replace("\\-", "\x00")
    i = 0
    def flush():
        nonlocal buf, new_word
        if buf:
            out.append((buf.replace("\x00", "-").replace("~", " "), new_word))
            buf, new_word = "", False
    while i < len(w):
        c = w[i]
        if c == " ":
            flush()
            new_word = True
        elif c == "-":
            if buf:
                flush()
            else:
                pass                                  # '- -' or '_-': nothing to end
        elif c == "_":
            flush()
            out.append(("_",))
        elif c == "*":
            flush()
            out.append(("*",))
            new_word = True
        elif c == "|":
            flush()
        else:
            buf += c
        i += 1
    flush()
    return out


# ----------------------------------------------------------------------------
# Kalimba
# ----------------------------------------------------------------------------

TINE = {0: "1", 2: "2", 4: "3", 5: "4", 7: "5", 9: "6", 11: "7"}


def tine(m):
    pc, octave = m % 12, m // 12 - 1
    if pc not in TINE:
        return None
    return TINE[pc] + ("'" * (octave - 4) if octave >= 4 else "," * (4 - octave))


def plan(pitches_by_stanza, transpose):
    """Choose how the song goes on the kalimba. Returns (shift per stanza,
    retune {midi: tine}, play_as {midi: midi}, report lines)."""
    def fit(shift):
        stanza_shift, report = [], []
        for i, ps in enumerate(pitches_by_stanza):
            s = shift
            lo, hi = min(ps) + s, max(ps) + s
            if lo < LOW or hi > HIGH:
                move = 12 if lo < LOW else -12
                if LOW <= lo + move and hi + move <= HIGH:
                    s += move
                    report.append(f"stanza {i + 1}: {name(lo)}..{name(hi)} doesn't fit the kalimba, "
                                  f"played an octave {'higher' if move > 0 else 'lower'}")
            stanza_shift.append(s)
        allp = [p + s for ps, s in zip(pitches_by_stanza, stanza_shift) for p in ps]
        out_range = sum(1 for p in allp if not LOW <= p <= HIGH)
        used = {tine(p) for p in allp if tine(p)}
        retune, play_as = {}, {}
        sign = lambda x: (x > 0) - (x < 0)
        for m in sorted({p for p in allp if tine(p) is None}):
            free = [tine(m + d) for d in (-1, 1) if tine(m + d) in TINES_17
                    and tine(m + d) not in used and tine(m + d) not in retune.values()]
            if free:
                retune[m] = free[0]
                continue
            occ = [i for i, p in enumerate(allp) if p == m]
            best = None
            for step in (-1, 1, -2, 2):
                q = m + step
                if tine(q) not in TINES_17 or tine(q) in retune.values():
                    continue                              # a retuned tine no longer sounds q
                cost = 0.5 * abs(step)
                for i in occ:
                    for j in (i - 1, i + 1):
                        if 0 <= j < len(allp):
                            r = allp[j]
                            cost += 2 * (sign(m - r) != sign(q - r)) + 3 * (q == r != m)
                if best is None or cost < best[0]:
                    best = (cost, q)
            if best:
                play_as[m] = best[1]
        n_sub = sum(1 for p in allp if p in play_as)
        mid = sorted(allp)[len(allp) // 2]
        moved = sum(1 for s_ in stanza_shift if s_ != shift)
        # 73 ~ between 1' and 2'; moving a stanza by an octave costs a little
        score = 100 * out_range + 3 * n_sub + 2 * len(retune) + 1.5 * moved + 0.3 * abs(mid - 73)
        return score, stanza_shift, retune, play_as, report, out_range, n_sub
    if transpose is not None:
        tried = [(transpose,) + fit(transpose)]
    else:
        tried = sorted(((s,) + fit(s) for s in range(-12, 13)), key=lambda t: t[1])
    shift, score, stanza_shift, retune, play_as, report, out_range, n_sub = tried[0]
    lines = []
    if transpose is None:
        lines.append(f"transposed {shift:+d} semitones (best fit; --transpose to choose)")
        for t in tried[1:4]:
            sh, _, ss, rt, pa, _, outr, nsub = t
            moved = sum(1 for x in ss if x != sh)
            lines.append(f"  also possible: --transpose {sh:+d}: {len(rt)} tine(s) to retune, "
                         f"{nsub} note(s) substituted, {moved} stanza(s) moved an octave"
                         + (f", {outr} out of range" if outr else ""))
    lines += report
    for m, t in retune.items():
        near = m + (1 if tine(m + 1) == t else -1)
        lines.append(f"retune tine {t} ({name(near)}) to {name(m)}; it is written {t}")
    for m, q in play_as.items():
        lines.append(f"{name(m)}: no free tine to retune, played as {name(q)} (tine {tine(q)})")
    if out_range:
        lines.append(f"{out_range} note(s) outside the kalimba's range even so")
    return stanza_shift, retune, play_as, lines


def written(m, retune, play_as):
    if m in retune:
        return retune[m]
    t = tine(play_as.get(m, m))
    if t is None:
        sys.exit(f"{name(m)} can't be written on the kalimba")
    return t


# ----------------------------------------------------------------------------
# Lengths
# ----------------------------------------------------------------------------

def marks(eighths, beat):
    """Length in eighths -> ktab marks after the tine: '/' halves, '.' x1.5,
    '-' one more beat. Uses the fewest marks; e.g. (quarter beat) 1 -> '/',
    2 -> '', 3 -> '.', 4 -> '-', 5 -> '.-', 1/2 -> '//'."""
    beats = Fraction(eighths) / (2 if beat == "quarter" else 1)
    best = None
    for slashes in range(0, 5):
        base = Fraction(1, 2 ** slashes)
        for dot in (False, True):
            b = base * (Fraction(3, 2) if dot else 1)
            rest = beats - b
            if rest < 0 or rest.denominator != 1:
                continue
            m = "/" * slashes + ("." if dot else "") + "-" * int(rest)
            if best is None or len(m) < len(best):
                best = m
    if best is None:                                   # not writable: nearest
        q = round(beats * 4) / Fraction(4)
        return marks(q * (2 if beat == "quarter" else 1), beat) if q > 0 else "//"
    return best


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="ABC (with w: lyrics) -> kalimba tab (.ktab).")
    ap.add_argument("abc")
    ap.add_argument("--out", help="ktab file (default: next to the ABC, .ktab)")
    ap.add_argument("--transpose", type=int, help="semitones (default: the best fit for the kalimba)")
    ap.add_argument("--beat", default="quarter", choices=["quarter", "eighth"],
                    help="what one beat is (default quarter: an eighth is written 5/)")
    ap.add_argument("--title", help="title (default: the ABC's T:)")
    ap.add_argument("--keep-marks", action="store_true", help="keep '?' marks on syllables")
    args = ap.parse_args()

    title, stanzas = parse_abc(Path(args.abc).read_text(encoding="utf-8"))
    if not stanzas:
        sys.exit("no music found in the ABC")
    pitches = [[e["midi"] for ln in st for e in ln if e["kind"] == "note"] for st in stanzas]
    stanza_shift, retune, play_as, report = plan(pitches, args.transpose)
    for r in report:
        print(r)

    out = [f"@title: {args.title or title or Path(args.abc).stem}"] + HEADER + [""]
    for si, st in enumerate(stanzas):
        if si:
            out.append("")
        # Every note belongs to a syllable. A note with no syllable text of its own
        # (an ABC hold '_', a skipped note '*', a lone '?' mark, a rest) goes on
        # with the syllable before it - also across a line break - so nothing
        # is left as an empty group; only notes before the stanza's first
        # syllable are held until it.
        rendered, last, waiting = [], None, []
        for events in st:
            words, groups = [], None                     # groups of the current word
            for e in events:
                if e["kind"] == "rest":
                    ev, text, new_word = "0" + marks(e["eighths"], args.beat), "", False
                else:
                    ev = written(e["midi"] + stanza_shift[si], retune, play_as) + marks(e["eighths"], args.beat)
                    tokv = e.get("tok", ("*",))
                    text, new_word = (tokv if tokv[0] not in ("_", "*") else ("", False))
                    if not args.keep_marks:
                        text = text.replace("?", "")
                    text = re.sub(r"[:()\r\n]", "", text).strip()
                if not text:                              # no syllable of its own
                    if last is not None:
                        last[1].append(ev)
                    else:
                        waiting.append(ev)
                    continue
                if new_word or groups is None:
                    groups = []
                    words.append(groups)
                last = [text, waiting + [ev]]
                waiting = []
                groups.append(last)
            rendered.append(words)
        for words in rendered:
            if words:
                out.append(" ".join("".join(f"({t}: {' '.join(ns)})" for t, ns in w) for w in words))
    path = Path(args.out) if args.out else Path(args.abc).with_suffix(".ktab")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"ktab: {path}  ({sum(1 for st in stanzas for ln in st for e in ln if e['kind'] == 'note')} notes)")


if __name__ == "__main__":
    main()
