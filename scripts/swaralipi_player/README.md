# Swaralipi player

Plays a song's ABC draft while a box moves over the original Bengali swaralipi (Akarmatrik
notation from Geetabitan), matra by matra. It is a way to read along with Tagore's notation and to
check a draft by eye and ear.

    source ~/activate
    python3 scripts/swaralipi_player/player.py rs000864

Output: `data/intermediate_data/comparison/<song>_swaralipi_ticker.mp4` (git-ignored).
Inputs: `data/intermediate_data/abc/<song>/v1.abc` (or `--abc`) and
`data/raw_data/swaralipi/<song>.pdf` (or `--pdf`; re-download with `scripts/fetch_sources.py`).
Needs `pdftoppm` (poppler) and `ffmpeg`.

## Files

| File | What it does |
|---|---|
| `layout.py` | Reads the rendered swaralipi pages (130 dpi): finds the swara rows, splits each into matras between its bar lines, marks holds (`-।`), syllables in the lyric row under each matra, and `{ }` repeats |
| `player.py` | Builds the singing order, aligns the draft with it, synthesizes the draft and renders the video |

## How it works

1. **Rows.** Text lines are found by horizontal projection. A line with a `।` (narrow, about
   15 px tall) is a swara row; the lines below it, up to the next swara row, are its lyrics.
2. **Matras.** A swara row is split into tokens by vertical projection of its top 18 px (above
   the slur arcs, low enough to keep the hyphen of `-।`). Bar lines are the `।`s, the `I`s at
   the ends and the one between the two `।`s; braces are narrow and taller than 23 px. Between bar
   lines come 4 matras; extra tokens before the first bar line are a pickup and a double bar.
3. **Holds and syllables.** A matra is a hold when it is a short dash followed by one thin tall
   stroke. A syllable starts under a matra when a lyric token at least 12 px tall sits below it
   (smaller ones are the `•` and `০` placeholders).
4. **Singing order.** `{ ... }` sections are sung twice; when the draft's last section has the
   same name as its first, the first row is appended (the return to the sthayi).
5. **Alignment.** One matra = one quarter note. The draft and the swaralipi are aligned matra by
   matra with dynamic time warping on two marks, "a new note starts" and "a syllable starts".
   Matras only one side has are skipped, so the draft's longer holds (from the MIDI arrangement)
   just keep the box on that swara.
6. **Video.** The draft is synthesized at its own pitch and tempo (`Q:`); the page scrolls to keep
   the sung row a third of the way down.

## Status

Tested on Eso Eso He Boishakh (rs000864): 0.23 alignment mismatches per matra; the box lands on the
right swara at every section start.

## Ideas to improve

- Test on more songs; the bar-line and brace rules are tuned to Geetabitan's layout of Eso Eso.
- Read the swara glyphs themselves (template matching) and check each note's pitch against them.
- Smoother scrolling; show the sargam and lyrics in Latin letters beside the page.
- Play the piano roll's melody or a sung rendition instead of the synthesized draft.

## From the swaralipi text (SNLTR)

Better than reading scans: SNLTR's Rabindra Rachanabali (rabindra-rachanabali.nltr.org) has each
song's swaralipi as a table of text. It was saved from the site through the browser (Claude in
Chrome) into `data/raw_data/swaralipi_text/<song>.json` (git-ignored: SNLTR does not allow
re-hosting their digitization), and transcribed into our own notation:

| File | What it does |
|---|---|
| `notation.py` | Our transcription format, `data/intermediate_data/swaralipi/<song>.json` (committed): every row of the printed swaralipi on its column grid, swara rows in our notation (S r R g G m M P d D n N, `'` `,` octaves, `^X` grace notes, `-` holds and melismas, bar lines, `{ } ( ) [ ]`), lyric rows unchanged. Converting back gives SNLTR's table exactly (checked for every cell). |
| `text_player.py` | Plays a song from the transcription alone and renders its notation page with a box on the matra being played; sound and box come from the same cells. `{ }` are sung twice, `( )` the first time only, a quoted "তুমি" returns to the sthayi. |
| `check_abc.py` | Checks an ABC draft against the transcription note by note: pitch, place in the matra, syllables; grace notes may be played as notes. Reports in `data/intermediate_data/comparison/<song>_<version>_swaralipi_check.md`. |

SNLTR's cell encoding (what `notation.py` translates): `s v r t g m k p d q u n` = S r R g G m M P
d D n N; `f` / `h` after a swara = upper / lower octave; capitals = grace notes; `a` closes the
matra; `-a` = hold; `i` = ঃ; `l ll A L` = bar lines and the end mark; `w x y` = marks at row starts
(not yet understood). The komal codes (`v t d u`) were worked out from which songs use which komal
notes; they agree with Dariye Achho's komal Re and Katobaro's komal Ni.
