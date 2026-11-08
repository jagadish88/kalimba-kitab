"""Parse .ktab text into a ktab.model.Song, using the ANTLR grammar in grammar/.

    song = ktab.parse_file("ami_chini.ktab")
    song = ktab.parse("(A: 5/)(mi: 6/) (chi: 7/)")

Syntax errors raise KtabError, which lists every problem with line:column
and a plain-language hint.
"""
from __future__ import annotations

from antlr4 import CommonTokenStream, InputStream
from antlr4.error.ErrorListener import ErrorListener

from ._gen.KalimbaLexer import KalimbaLexer
from ._gen.KalimbaParser import KalimbaParser
from .model import LINE, STANZA, Bar, Hold, Line, Note, Song, Stanza, Syllable, Word

# editors often swap in "smart" apostrophes/commas: treat them as plain ' and ,
SMART = str.maketrans({"’": "'", "‘": "'", "′": "'", "`": "'", "´": "'",
                       "ʼ": "'", "＇": "'", "，": ",", "‚": ","})


class KtabError(ValueError):
    def __init__(self, problems, source="<text>"):
        self.problems = problems            # [(line, col, message)]
        self.source = source
        lines = "\n".join(f"  line {l}:{c}: {m}" for l, c, m in problems)
        super().__init__(f"{source}: {len(problems)} problem(s)\n{lines}")


def _hint(tok, msg):
    t = tok.text if tok is not None else ""
    if t in ("8", "9"):
        return f"'{t}' is not a note: kalimba notes are 0-7 (the next octave is 1', 2', ...)"
    if tok is not None and tok.type == KalimbaLexer.NEWLINE:
        return "a group is not closed: missing ')' before the end of the line"
    if "expecting ':'" in msg or (t == ")" and "COLON" in msg):
        return "missing ':' between the lyric and its notes, e.g. (re: 6)"
    if t in ("/", ".", "'", ","):
        return (f"'{t}' is out of order: write a note as digit, octave marks, "
                "slashes, dot, dashes  (e.g. 7''//.-)")
    if tok is not None and tok.type in (KalimbaLexer.REPEAT_LINE, KalimbaLexer.REPEAT_STANZA):
        return f"'{t}' must come at the very end of a line"
    if t == ":":
        return "a repeat sign is ':|' (repeat the line) or ':||' (repeat the stanza), at the end of a line"
    if t.strip() and t not in "()|":
        return f"unexpected '{t}' here"
    return msg


class _Collect(ErrorListener):
    def __init__(self):
        self.problems = []

    def syntaxError(self, recognizer, offending, line, col, msg, e):
        if self.problems and self.problems[-1][0] == line:
            return                                   # one message per line is enough
        stream = recognizer.getInputStream() if hasattr(recognizer, "getTokenStream") else None
        if stream is not None:                       # a repeat sign followed by more music
            for k in (-1, -2):
                prev = stream.LT(k)
                if prev is None or prev.type != KalimbaLexer.SPACE:
                    break
            if prev is not None and prev.type in (KalimbaLexer.REPEAT_LINE, KalimbaLexer.REPEAT_STANZA):
                self.problems.append((prev.line, prev.column + 1,
                                      f"'{prev.text}' must come at the very end of a line"))
                return
        self.problems.append((line, col + 1, _hint(offending, msg)))


def _pos(ctx):
    return (ctx.start.line, ctx.start.column + 1)


def _note(ctx) -> Note:
    octave = 0
    if ctx.octave():
        marks = ctx.octave().getText()
        octave = len(marks) if marks[0] == "'" else -len(marks)
    return Note(degree=int(ctx.DEGREE().getText()),
                octave=octave,
                slashes=len(ctx.duration().SLASH()) if ctx.duration() else 0,
                dotted=ctx.DOT() is not None,
                dashes=len(ctx.DASH()),
                pos=_pos(ctx))


def _syllable(ctx) -> Syllable:
    text = ctx.LYRIC_TEXT().getText().strip() if ctx.LYRIC_TEXT() else ""
    events = []
    for ev in ctx.event():
        if ev.note():
            events.append(_note(ev.note()))
        else:
            events.append(Hold(len(ev.hold().DASH()), _pos(ev)))
    return Syllable(text, events, _pos(ctx))


def _build(tree) -> Song:
    song = Song()
    for h in tree.header():
        key, _, val = h.HEADER().getText()[1:].partition(":")
        song.headers[key.strip().lower()] = val.strip()
    for st in tree.stanza():
        stanza = Stanza(pos=_pos(st))
        for ln in st.line():
            line = Line(pos=_pos(ln))
            if ln.repeat():
                line.repeat = LINE if ln.repeat().REPEAT_LINE() else STANZA
                line.repeat_pos = _pos(ln.repeat())
            for ch in ln.chunk():
                if ch.BAR():
                    line.items.append(Bar(_pos(ch)))
                else:
                    w = ch.word()
                    line.items.append(Word([_syllable(s) for s in w.syllable()], _pos(w)))
            stanza.lines.append(line)
        song.stanzas.append(stanza)
    return song


def _check(song: Song, source: str):
    """Rules the grammar can't express."""
    problems = []
    for n in song.notes():
        if n.is_rest and n.octave:
            problems.append((*n.pos, "a rest (0) can't have octave marks"))
    for ln in song.lines:
        for w in ln.words:
            for s in w.syllables:
                if isinstance(s.events[0], Hold):
                    problems.append((*s.events[0].pos,
                                     "a group can't start with a lone '-': there is no note to hold"))
    for st in song.stanzas:
        for ln in st.lines[:-1]:
            if ln.repeat == STANZA:
                problems.append((*ln.repeat_pos,
                                 "':||' repeats the whole stanza, so it belongs at the end of the "
                                 "stanza's last line; use ':|' to repeat just this line"))
    if problems:
        problems.sort()
        raise KtabError(problems, source)


def parse(text: str, source: str = "<text>") -> Song:
    text = text.lstrip("﻿").translate(SMART)
    errors = _Collect()
    lexer = KalimbaLexer(InputStream(text))
    lexer.removeErrorListeners(); lexer.addErrorListener(errors)
    parser = KalimbaParser(CommonTokenStream(lexer))
    parser.removeErrorListeners(); parser.addErrorListener(errors)
    tree = parser.song()
    if errors.problems:
        raise KtabError(errors.problems, source)
    song = _build(tree)
    _check(song, source)
    return song


def parse_file(path: str) -> Song:
    with open(path, encoding="utf-8-sig") as f:
        return parse(f.read(), source=path)


def parse_tree(text: str):
    """The raw ANTLR tree and parser (for printing / debugging)."""
    lexer = KalimbaLexer(InputStream(text.lstrip("﻿").translate(SMART)))
    parser = KalimbaParser(CommonTokenStream(lexer))
    return parser.song(), parser
