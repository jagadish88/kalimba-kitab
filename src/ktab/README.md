# ktab — kalimba tab parser

    pip install antlr4-python3-runtime==4.13.2

    import ktab
    song = ktab.parse_file("song.ktab")        # ktab.KtabError lists mistakes with line:column
    song.headers, song.stanzas, song.lines      # Song -> Stanza -> Line -> Word -> Syllable -> Note/Hold
    tl = ktab.timeline(song, bpm=88)            # plucks (time, note, length) and word spans
    list(song.performance())                    # lines in playing order, repeats unfolded

Repeats: end a line with ` :|` to play it twice, or end a stanza's last line
with ` :||` to play the whole stanza twice. Both may be combined.

    python3 -m ktab check song.ktab [--tines 17]   # check + beats per line
    python3 -m ktab tree  song.ktab                # parse tree
    python3 -m ktab fmt   song.ktab                # print back in canonical form

Files: model.py (data classes), parser.py (grammar -> model, error hints),
timing.py (beats -> seconds), grammar/*.g4 (the grammar), _gen/ (generated, don't edit).

After editing the grammar, regenerate _gen/ from inside this folder:

    antlr4 -v 4.13.2 -Dlanguage=Python3 -no-listener -o _gen grammar/KalimbaLexer.g4 grammar/KalimbaParser.g4
    # or, without Java:
    npx antlr-ng -Dlanguage=Python3 --generate-listener=false -o _gen grammar/KalimbaLexer.g4 grammar/KalimbaParser.g4

The runtime version must match the generator (4.13.x).
