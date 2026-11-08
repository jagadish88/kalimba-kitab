# Kalimba-Kitab

Kalimba tabs for public-domain songs, starting with Rabindra Sangeet. Each song is
written as `(syllable: notes)` tabs (`.ktab`), turned into printable sheets (PDF) and
book-style videos with sound, and can be practised in the browser.

```
data/
  raw_data/            everything collected, untouched; one song = one id (rs000001 ...)
    text/              catalog.csv (song_id, title), lyrics/ (transliteration .txt, Bengali .png)
    midi/              Geetabitan staff-notation MIDI files
    swaralipi/         Geetabitan swaralipi (Bengali notation), PDF + image
    video/             video_catalog.csv (+ downloaded videos)
    image/             slides and the paper background for videos
    audio/             recordings
    metadata/          scale_catalog.csv (raag, key, notes per source)
    source_provenance.csv   local file -> source_id
  intermediate_data/   drafts made by the scripts, one folder per pipeline
  dataset/             finished output: ktab/, pdf/, video/
sources/sources.csv    every source: source_id, title, url, local_path, date accessed
scripts/               pipelines that turn sources into tabs, and tabs into videos
src/ktab/              the ktab package: grammar, parser, timing, LaTeX sheet
index.html             Kalimba Tab Trainer, the practice page, served by GitHub Pages
```

## Catalogs

Every file in `raw_data` is listed in `source_provenance.csv`, and every source in
`sources/sources.csv`, so each fact can be traced back to where it came from.

- **text/catalog.csv**: `song_id, title`.
- **video/video_catalog.csv**: `song_id, source_id, local_path, type`. The type is one of
  `piano_lesson` (hands on a keyboard, chords + melody), `piano_roll` (falling notes),
  `piano_staff` (scrolling sheet music), `kalimba` (kalimba covers) or `vocal_melody`
  (a clear sung rendition, up to 3 per song). An empty `local_path` means not downloaded.
- **metadata/scale_catalog.csv**: one row per song and source:
  `song_id, source_id, method, raag, key, sa, S r R g G m M P d D n N`.
  `method` is `stated` (the source says it), `read` (read from the swaralipi) or
  `derived` (worked out). Swaralipi rows mark each note used with `1`; MIDI rows give
  Sa and the number of melody notes on each swara. Capitals are shuddha, lowercase
  `r g d n` komal, `M` tivra ma.

## The tab format

```
@title: Ami Chini Go Chini Tomare           optional header lines
(A: 5/)(mi: 6/) (chi: 7/)(ni: 7/) :|        no space = same word; ends with :| -> play twice
(Tu: 7/)(mi: 1'/) (pa: 3'.)(re: 2') :||     last line of a stanza ends with :|| -> stanza twice

(O: 5/)(go: 6// 7//) | (bi: 1'/)            blank line = new stanza; | = bar line
```

A note is written as: digit `0`–`7` (0 = rest), octave marks (`'` up, `,` down), slashes
(`/` half beat, `//` quarter, `///` eighth), a dot (x1.5), dashes (+1 beat each), e.g.
`5`, `1'`, `6,`, `2'//`, `6/.`, `4--`, `7''//.`. A lone `-` inside a group holds the
previous note: `(cha: 5'' - 1'///)`. `1` is C, so a tab is in C major; there are no
sharps or flats.

## Install

    pip install -e .                 # the ktab command; or pip install -e ".[video]" for numpy + pillow

Videos also need `ffmpeg` on PATH; PDFs need `pdflatex` (TeX Live or MiKTeX).

The third-party files (MIDI, swaralipi, lyrics) and downloaded videos are not kept in git.
Get the files back from their sources after cloning:

    python scripts/fetch_sources.py        # --only midi|swaralipi|text, --dry-run

## Check a tab and make the PDF

    ktab check data/dataset/ktab/ami_chini.ktab        # errors come with line:column and a hint
    ktab fmt   data/dataset/ktab/ami_chini.ktab        # print it back in canonical form
    ktab tex   data/dataset/ktab/ami_chini.ktab -o data/dataset/pdf/ami_chini.tex

`ktab tex` writes the `.tex`, the PDF and `jianpu.sty` next to it, and writes nothing if
the tab has mistakes. Optional header lines set the layout: `@subtitle`, `@paper` (a4 |
letter), `@margin`, `@beat`, `@wordgap`, `@linegap`, `@stanzagap`, `@align` (left |
centre). If a song runs onto an extra page, lower `@beat`, `@linegap` or `@margin`.

The grammar is in `src/ktab/grammar/*.g4` (ANTLR 4); see `src/ktab/README.md`.

## Make a video

    python3 scripts/ktab_to_video/kalimba_video.py data/dataset/ktab/ami_chini.ktab \
        data/raw_data/image/paper_texture_brown.png -o ami.mp4 --bpm 88
    python3 scripts/ktab_to_video/add_intro.py slide.png \
        data/raw_data/image/paper_texture_brown.png ami.mp4        # -> ami_with_intro.mp4

`kalimba_video.py` synthesises the kalimba and shows two lines at a time; the word being
played turns bold (`-h` lists tempo, loudness, sampled kalimba and retuning options).
`add_intro.py` opens with a slide that fades to plain paper before the video starts.
Use the same paper for both so the cut is seamless. Fonts are TeX Gyre, in
`scripts/ktab_to_video/fonts/` (GUST Font License).

## From sources to tabs

| Script | From | To |
|---|---|---|
| `scripts/midi_to_ktab.py` | MIDI melody | notes-only `.ktab` draft |
| `scripts/piano_lesson_to_ktab/video_to_abc.py` | piano-lesson video | ABC with lyrics (chapters, on-screen notes, audio) |
| `scripts/piano_lesson_to_ktab/abc_to_ktab.py` | ABC with `w:` lyrics | `.ktab`, transposed to fit a kalimba in C |
| `scripts/piano_lesson_to_ktab/swara_to_ktab.py` | swaralipi typed as `.swara` text | `.ktab` |
| `scripts/kalimba_cover_to_abc/notes_from_audio.py` | kalimba recording | ABC, notes CSV, spectrogram, replay WAV |

Drafts go to `data/intermediate_data/<pipeline>/`; a corrected tab goes to
`data/dataset/ktab/`.

## Practice

`index.html` (the Kalimba Tab Trainer) loads a `.ktab`, plays it, and listens through the
microphone to check the notes you pluck. It is published with GitHub Pages.
