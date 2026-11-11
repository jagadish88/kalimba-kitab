#!/usr/bin/env python3
"""Sheet music of an ABC file with the notes the kalimba plays a semitone off in red.

    python scripts/piano_lesson_to_ktab/abc_offkey_score.py data/intermediate_data/abc/rs001381/v2.abc --transpose 8

The kalimba fit is the one abc_to_ktab.py makes (same --transpose): a note with no tine and no free
tine to retune is played on a neighbouring tine. Those notes are red, with the tine played above
them. The score stays in the ABC's own key; the ABC, lyrics and line breaks are kept.
Engraved with LilyPond. Writes data/intermediate_data/comparison/<song>_<abc name>_offkey.pdf
(and its .ly), git-ignored.
"""
import argparse
import os
import re
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
import abc_to_ktab as A  # noqa: E402

LY_NAMES = "c cis d dis e f fis g gis a ais b".split()
# length in eighths -> LilyPond duration
LY_DUR = {Fraction(1, 4): "32", Fraction(1, 2): "16", Fraction(3, 4): "16.", Fraction(1): "8",
          Fraction(3, 2): "8.", Fraction(2): "4", Fraction(3): "4.", Fraction(4): "2", Fraction(6): "2.",
          Fraction(8): "1", Fraction(12): "1."}
TOK = re.compile(r"([_=^]{0,2})([A-Ga-g])([',]*)([\d/]*)(-?)|([zx])([\d/]*)|(\|\]|\|+)")


def ly_pitch(m):
    octave = m // 12 - 1
    return LY_NAMES[m % 12] + ("'" * (octave - 3) if octave >= 3 else "," * (3 - octave))


def ly_durs(eighths, where):
    """LilyPond durations that add up to `eighths` (longest first; more than one = tied notes)."""
    left, out = Fraction(eighths), []
    for v in sorted(LY_DUR, reverse=True):
        while left >= v:
            out.append(LY_DUR[v]); left -= v
    if left:
        sys.exit(f"{where}: a note {eighths} eighths long can't be written in LilyPond durations")
    return out


def ly_dur(eighths, where):
    return "~ ".join(ly_durs(eighths, where))


def ly_text(s):
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'


def read_abc(text):
    """-> header fields, and the body as items: ('part', name), ('line', events, lyric tokens or None).
    An event is ('note', midi, eighths, tie), ('rest', eighths) or ('bar', final)."""
    fields, items, unit, sig, in_body = {}, [], Fraction(1), {l: 0 for l in A.LETTERS}, False
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line or line.startswith("%"):
            continue
        f = re.match(r"([A-Za-z]):(.*)", line)
        if f and f.group(1) != "w":
            key, val = f.group(1), f.group(2).strip()
            fields.setdefault(key, val)
            if key == "L":
                a, b = val.split("/")
                unit = Fraction(int(a), int(b)) / Fraction(1, 8)
            elif key == "K":
                sig, in_body = A.key_signature(val), True
            elif key == "P" and in_body:
                items.append(("part", val))
            continue
        if line.startswith("w:"):
            if items and items[-1][0] == "line" and items[-1][2] is None:
                items[-1] = ("line", items[-1][1], A.lyric_tokens(line[2:]))
            continue
        if not in_body:
            continue
        line = re.sub(r'"[^"]*"|![^!]*!|\{[^}]*\}|\[[A-Za-z]:[^\]]*\]', "", line)
        events, bar_acc = [], {}
        for m in TOK.finditer(line):
            if m.group(8):
                bar_acc = {}
                events.append(("bar", m.group(8) == "|]"))
            elif m.group(6):
                events.append(("rest", A.length_of(m.group(7), unit)))
            else:
                midi = A.pitch(m.group(1), m.group(2), m.group(3), sig, bar_acc)
                events.append(("note", midi, A.length_of(m.group(4), unit), m.group(5) == "-"))
        items.append(("line", events, None))
    return fields, items


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument("abc")
    ap.add_argument("--transpose", type=int, help="as for abc_to_ktab.py (default: its best fit)")
    ap.add_argument("--out", help="output .pdf (default: comparison/<song>_<abc name>_offkey.pdf)")
    ap.add_argument("--mark", action="append", default=[], metavar="F4=4(F#)",
                    help="mark these written pitches red with this label instead of the converter's substitutions "
                         "(e.g. to show what a retuned tine does to the song's other notes)")
    ap.add_argument("--note", help="the explanation printed under the title (default: the substitutions)")
    a = ap.parse_args()

    text = Path(a.abc).read_text(encoding="utf-8")
    _, stanzas = A.parse_abc(text)
    pitches = [[e["midi"] for ln in st for e in ln if e["kind"] == "note"] for st in stanzas]
    stanza_shift, retune, play_as, report = A.plan(pitches, a.transpose)
    for r in report:
        print(r)
    fields, items = read_abc(text)
    marks = dict(m.split("=", 1) for m in a.mark)

    music, lyrics, si, n_off = [], [], -1, 0
    first_part = True
    for it in items:
        if it[0] == "part":
            if not first_part or si < 0:
                si += 1
            first_part = False
            music.append(f'\\mark \\markup \\small {ly_text(it[1])}')
            continue
        if si < 0:                                        # music before any P:
            si = 0
        first_part = False
        _, events, toks = it
        toks = list(toks or [])
        n_notes, parts = 0, []                            # LilyPond notes per ABC note
        for ev in events:
            if ev[0] == "bar":
                music.append('\\bar "|."' if ev[1] else "|")
            elif ev[0] == "rest":
                music.append(" ".join("r" + d for d in ly_durs(ev[1], "rest")))
            else:
                _, midi, eighths, tie = ev
                durs = ly_durs(eighths, A.name(midi))
                p = ly_pitch(midi)
                note = p + durs[0]
                played = play_as.get(midi + stanza_shift[si])
                label = A.tine(played) if played is not None else None
                if marks:
                    label = marks.get(A.name(midi))
                if label is not None:
                    n_off += 1
                    note = (f"\\override NoteHead.color = #red {note}"
                            f'^\\markup \\with-color #red \\small {ly_text(label)}')
                note += "".join(f"~ {p}{d}" for d in durs[1:]) + ("~" if tie else "")
                if label is not None:
                    note += " \\revert NoteHead.color"
                music.append(note)
                parts.append(len(durs))
                n_notes += 1
        music.append("\\break")
        # one lyric syllable per note (tied-on notes included, as in the ABC)
        toks = (toks + [("*",)] * n_notes)[:n_notes]
        for t, k in zip(toks, parts):
            if t[0] in ("_", "*"):
                lyrics.append("_")
            else:
                if not t[1] and lyrics and lyrics[-1] != "_":
                    lyrics.append("--")
                lyrics.append(ly_text(t[0]))
            lyrics += ["_"] * (k - 1)                     # a note split into tied notes: one syllable

    shifts = sorted(set(stanza_shift))
    subs = ", ".join(f"{A.name(m)} on tine {A.tine(q)} ({A.name(q)})" for m, q in play_as.items())
    note_line = (f"Red: no tine for the note (kalimba transposition {shifts[0]:+d}); "
                 f"played a semitone off on the tine shown above it. {subs}." if play_as else
                 "Every note has a tine (none played a semitone off).")
    if a.note:
        note_line = a.note
    meter = fields.get("M", "4/4")
    free = meter.strip().lower() == "none"          # no meter (drafts from the swaralipi): free bars
    if free:
        music = ['\\bar "|"' if m == "|" else m for m in music]
    ly = f"""\\version "2.24.0"
\\header {{
  title = {ly_text(fields.get("T", Path(a.abc).stem))}
  subtitle = {ly_text(os.path.relpath(os.path.abspath(a.abc), ROOT))}
  tagline = ##f
}}
\\paper {{ #(set-paper-size "a4") indent = 0 ragged-last = ##t }}
\\markup \\with-color #red \\small \\wordwrap-string {ly_text(note_line)}
\\score {{
  <<
    \\new Voice = "tune" {{
      \\key c \\major {'\\cadenzaOn' if free else '\\time ' + meter} \\autoBeamOn
      {' '.join(music)}
    }}
    \\new Lyrics \\lyricsto "tune" {{
      \\set ignoreMelismata = ##t
      {' '.join(lyrics)}
    }}
  >>
  \\layout {{ \\context {{ \\Score \\remove "Bar_number_engraver" }} }}
}}
"""
    song = os.path.basename(os.path.dirname(os.path.abspath(a.abc)))
    out = a.out or os.path.join(ROOT, "data/intermediate_data/comparison",
                                f"{song}_{Path(a.abc).stem}_offkey.pdf")
    base = os.path.splitext(out)[0]
    Path(base + ".ly").write_text(ly, encoding="utf-8")
    r = subprocess.run(["lilypond", "-l", "WARN", "-o", base, base + ".ly"], capture_output=True, text=True)
    if r.returncode:
        sys.exit(r.stderr[-3000:])
    for w in r.stderr.splitlines():
        print(w)
    print(f"{n_off} note(s) in red -> {out}")


if __name__ == "__main__":
    main()
