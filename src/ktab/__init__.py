"""ktab -- read kalimba tabs written as (syllable: notes).

    import ktab
    song = ktab.parse_file("ami_chini.ktab")      # raises ktab.KtabError on mistakes
    for line in song.lines:
        for word in line.words:
            print(word.text, [str(n) for s in word.syllables for n in s.notes])
    tl = ktab.timeline(song, bpm=88)              # follows :| and :|| repeats

Command line:
    python -m ktab check song.ktab [--tines 17]   syntax + range check, beats per line
    python -m ktab tree  song.ktab                print the parse tree
    python -m ktab fmt   song.ktab                print the song back in canonical form
    python -m ktab tex   song.ktab [-o x.tex]     printable sheet: .tex (+ .pdf with pdflatex)

The grammar lives in ktab/grammar/*.g4; the parser in ktab/_gen is generated
from it (see README) and needs:  pip install antlr4-python3-runtime==4.13.2
"""
from .model import LINE, STANZA, Bar, Hold, Line, Note, Played, Song, Stanza, Syllable, Word, SEMITONES
from .parser import KtabError, parse, parse_file, parse_tree
from .timing import Pluck, Timeline, WordSpan, timeline

__all__ = ["parse", "parse_file", "parse_tree", "KtabError", "timeline",
           "Song", "Stanza", "Line", "Word", "Bar", "Syllable", "Note", "Hold", "Played", "LINE", "STANZA",
           "Timeline", "Pluck", "WordSpan", "SEMITONES"]
