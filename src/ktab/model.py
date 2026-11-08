"""Data model for a parsed kalimba tab.

    Song
     ├─ headers            {"title": "...", ...}   from "@title: ..." lines
     └─ stanzas: [Stanza]                         separated by blank lines
          └─ lines: [Line]                        one text line each;
                                                  "... :|" repeats the line,
                                                  "... :||" (last line) the stanza
               └─ items: [Word | Bar]
                    └─ Word.syllables: [Syllable] "(ma: 5)(lik: 5/ 6/)"
                         └─ events: [Note | Hold]

Every node keeps `pos` = (line, column) in the source file, 1-based.
Lengths are exact fractions of a beat (`beats`).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from typing import Iterator, Union

Pos = tuple  # (line, column)

# semitones above "1" for each scale degree (C major: 1 = C)
SEMITONES = {1: 0, 2: 2, 3: 4, 4: 5, 5: 7, 6: 9, 7: 11}


@dataclass
class Note:
    degree: int                 # 0 = rest, 1..7
    octave: int = 0             # +1 per ', -1 per ,
    slashes: int = 0            # underlines: / = 1/2 beat, // = 1/4, /// = 1/8
    dotted: bool = False        # x 1.5
    dashes: int = 0             # each adds one beat
    pos: Pos = (0, 0)

    @property
    def is_rest(self) -> bool:
        return self.degree == 0

    @property
    def beats(self) -> Fraction:
        b = Fraction(1, 2 ** self.slashes)
        if self.dotted:
            b *= Fraction(3, 2)
        return b + self.dashes

    @property
    def semitone(self) -> int | None:
        """Semitones above middle "1" (None for a rest)."""
        return None if self.is_rest else SEMITONES[self.degree] + 12 * self.octave

    @property
    def scale_index(self) -> int | None:
        """Position on the 7-note scale, 0 = "1" (None for a rest)."""
        return None if self.is_rest else 7 * self.octave + self.degree - 1

    def __str__(self) -> str:
        marks = "'" * self.octave if self.octave > 0 else "," * -self.octave
        return (f"{self.degree}{marks}{'/' * self.slashes}"
                f"{'.' if self.dotted else ''}{'-' * self.dashes}")


@dataclass
class Hold:
    """A lone '-' inside a group: the previous note rings one more beat per dash."""
    dashes: int = 1
    pos: Pos = (0, 0)

    @property
    def beats(self) -> Fraction:
        return Fraction(self.dashes)

    def __str__(self) -> str:
        return "-" * self.dashes


Event = Union[Note, Hold]


@dataclass
class Syllable:
    text: str
    events: list[Event] = field(default_factory=list)
    pos: Pos = (0, 0)

    @property
    def notes(self) -> list[Note]:
        return [e for e in self.events if isinstance(e, Note)]

    @property
    def beats(self) -> Fraction:
        return sum((e.beats for e in self.events), Fraction(0))

    def __str__(self) -> str:
        return f"({self.text}: {' '.join(map(str, self.events))})"


@dataclass
class Word:
    syllables: list[Syllable] = field(default_factory=list)
    pos: Pos = (0, 0)

    @property
    def text(self) -> str:
        """The lyric as printed: syllables joined with a middle dot."""
        return "·".join(s.text for s in self.syllables)

    @property
    def beats(self) -> Fraction:
        return sum((s.beats for s in self.syllables), Fraction(0))

    def __str__(self) -> str:
        return "".join(map(str, self.syllables))


@dataclass
class Bar:
    pos: Pos = (0, 0)

    def __str__(self) -> str:
        return "|"


LINE, STANZA = "line", "stanza"      # values of Line.repeat


@dataclass
class Line:
    items: list[Union[Word, Bar]] = field(default_factory=list)
    pos: Pos = (0, 0)
    repeat: str | None = None          # None, "line" (:|) or "stanza" (:||)
    repeat_pos: Pos = (0, 0)           # where the repeat sign is written

    @property
    def words(self) -> list[Word]:
        return [i for i in self.items if isinstance(i, Word)]

    @property
    def beats(self) -> Fraction:
        return sum((w.beats for w in self.words), Fraction(0))

    def notes(self) -> Iterator[Note]:
        for w in self.words:
            for s in w.syllables:
                yield from s.notes

    def __str__(self) -> str:
        mark = {LINE: " :|", STANZA: " :||"}.get(self.repeat, "")
        return " ".join(map(str, self.items)) + mark


@dataclass
class Stanza:
    lines: list[Line] = field(default_factory=list)
    pos: Pos = (0, 0)

    @property
    def repeat(self) -> bool:
        """True when the stanza ends with :|| (play it twice)."""
        return bool(self.lines) and self.lines[-1].repeat == STANZA

    def __str__(self) -> str:
        return "\n".join(map(str, self.lines))


@dataclass
class Song:
    headers: dict[str, str] = field(default_factory=dict)
    stanzas: list[Stanza] = field(default_factory=list)

    @property
    def title(self) -> str | None:
        return self.headers.get("title")

    @property
    def lines(self) -> list[Line]:
        return [ln for st in self.stanzas for ln in st.lines]

    def notes(self) -> Iterator[Note]:
        for ln in self.lines:
            yield from ln.notes()

    def performance(self) -> Iterator["Played"]:
        """The lines in playing order, with repeats unfolded.

        A line ending in :| is played twice in a row; a stanza ending in :||
        is played twice (and its :| lines twice within each pass)."""
        first = 0
        for si, st in enumerate(self.stanzas):
            for spass in range(1, 3 if st.repeat else 2):
                for k, ln in enumerate(st.lines):
                    for lpass in range(1, 3 if ln.repeat == LINE else 2):
                        yield Played(first + k, ln, si, lpass, spass)
            first += len(st.lines)

    def truncated(self, n_lines: int) -> "Song":
        """The same song keeping only the first n lines (stanzas preserved)."""
        out, left = Song(dict(self.headers)), n_lines
        for st in self.stanzas:
            if left <= 0:
                break
            out.stanzas.append(Stanza(st.lines[:left], st.pos))
            left -= len(st.lines)
        return out

    def __str__(self) -> str:
        head = "".join(f"@{k}: {v}\n" for k, v in self.headers.items())
        return head + "\n\n".join(map(str, self.stanzas)) + "\n"


@dataclass
class Played:
    """One line as it is played: `index` into song.lines, plus which pass."""
    index: int
    line: Line
    stanza: int            # index into song.stanzas
    line_pass: int = 1     # 2 = the repeat of a :| line
    stanza_pass: int = 1   # 2 = the repeat of a :|| stanza
