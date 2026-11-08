"""Turn a Song into a timeline at a given tempo.

    tl = ktab.timeline(song, bpm=88, start=1.5)
    for p in tl.plucks:  ...   # p.time, p.note, p.length  (seconds)
    for w in tl.words:   ...   # w.start, w.end, w.line, w.word

Lines are played in performance order: a line ending in :| twice in a row,
a stanza ending in :|| twice. Rests take time but make no pluck; a lone '-'
(Hold) lengthens the previous pluck. Bars take no time.
"""
from __future__ import annotations

from dataclasses import dataclass

from .model import Hold, Note, Song


@dataclass
class Pluck:
    time: float          # seconds from the start of the timeline
    note: Note
    length: float        # seconds until the next event (includes holds)


@dataclass
class WordSpan:
    start: float
    end: float           # when its last note's time runs out
    line: int            # index into song.lines
    word: int            # index into song.lines[line].words
    stanza: int = 0      # index into song.stanzas
    line_pass: int = 1   # 2 while a :| line is being repeated
    stanza_pass: int = 1 # 2 while a :|| stanza is being repeated


@dataclass
class Timeline:
    plucks: list[Pluck]
    words: list[WordSpan]
    end: float           # time after the last note

    def span_at(self, t: float, linger: float = 0.6):
        """The WordSpan being played at time t: a word stays current until
        the next word begins (the last one for `linger` seconds)."""
        for i, w in enumerate(self.words):
            nxt = self.words[i + 1].start if i + 1 < len(self.words) else w.end + linger
            if w.start <= t < nxt:
                return w
        return None

    def word_at(self, t: float, linger: float = 0.6):
        """(line, word) being played at time t, or None."""
        w = self.span_at(t, linger)
        return (w.line, w.word) if w else None


def timeline(song: Song, bpm: float, start: float = 0.0) -> Timeline:
    beat = 60.0 / bpm
    t = start
    plucks, words = [], []
    for played in song.performance():
        li, line = played.index, played.line
        for wi, word in enumerate(line.words):
            w_start = t
            for syl in word.syllables:
                for ev in syl.events:
                    dur = float(ev.beats) * beat
                    if isinstance(ev, Note):
                        if not ev.is_rest:
                            plucks.append(Pluck(t, ev, dur))
                    elif isinstance(ev, Hold) and plucks:
                        plucks[-1].length += dur
                    t += dur
            words.append(WordSpan(w_start, t, li, wi, played.stanza,
                                  played.line_pass, played.stanza_pass))
    return Timeline(plucks, words, t)
