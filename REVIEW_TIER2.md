# Tier 2 review

The cloud run on 2026-11-08 could not download the sources: the cloud environment blocks
`www.geetabitan.com`. The 5 songs were then transcribed locally on the same day, using the same
method as Tier 1. Everything below is draft work for review; nothing is in `data/dataset/` yet.

## Results

| Song | ID | Bars | Melody notes | Form (as in the swaralipi and the MIDI) | ktab | Preview |
|---|---|---|---|---|---|---|
| Eso Eso He Boishakh | rs000864 | 101 | 295 | sthayi (2nd line repeated), antara, sanchari x2, abhog, sthayi | +5, no retune, 0 substituted | 2 pages |
| Sankocher Biwhalata | rs001848 | 100 | 210 | sthayi, antara, sanchari, abhog, each closing on "aa...haa" | +9, no retune, 0 substituted | 2 pages |
| Tomar Holo Shuru Amar | rs002064 | 88 | 170 | sthayi; first two lines return after antara, sanchari, abhog | +5, no retune, 0 substituted | 2 pages |
| Dariye Achho Tumi Amar | rs000636 | 118 | 437 | sthayi, antara (lines 1-2 x2), sanchari, abhog x2, sthayi | +5, no retune, 2 substituted | 3 pages |
| Chokher Aloy Dekhechhilem | rs000616 | 136 | 380 | sthayi, antara x2, sanchari x2, abhog x2, sthayi | +5, no retune, 2 substituted | 3 pages |

Files: `data/intermediate_data/abc/<id>/v1.abc`, `data/intermediate_data/ktab/<id>/v1.ktab`
and `v1.pdf`, with rows in `abc_catalog.csv` and `ktab_catalog.csv`.

Checks passed for every song: the notes match the MIDI bar for bar; one lyric token per note in
every bar; `abc2midi` reports no errors; `ktab check` passes with 0 warnings; each line reads
back as the right words.

## Key and retune
`abc_to_ktab.py` placed Sa on the F tine, so tivra Ma falls on the B tine and no tine needs
retuning. In kalimba numbers these tabs read in "F" (Sa = 4). The alternative, Sa on C with the
F tines retuned to F# as for Ekla Cholo Re, has the same substitutions:
`abc_to_ktab.py ... --transpose 0` (or `12`).

## Corrections found on the way
- **Dariye Achho is not a single-accidental song.** Its sanchari ("Be-do-na-te") has komal Re
  (C#) in the upper octave, in both the swaralipi and the MIDI; scale_catalog.csv is fixed. The
  2 komal Re notes are played as the natural neighbour in the ktab.
- **An ABC accidental bug, now fixed.** In ABC a sharp lasts to the end of the bar, so a natural
  after it needs `=`. The bar-dump script did not write it. Katobaro (rs001194 v1) had 3 bars
  where the abhog's A naturals read as A#; they are fixed and its ktab and PDF rebuilt (6 komal
  Ni notes, not 7). The fixed script is in TASK_TIER2.md.
- **The same bug is in the piano-lesson pipeline output** (`piano_notes_from_audio.py`): the
  drafts rs000206 v1, rs001619 v1 and rs002164 v1 have naturals after sharps without `=`. They
  were left unchanged.

## Where to look first
- **Sankocher:** written at the MIDI's real pitch (Sa = G#). The "aa...haa" vocalise after each
  section comes from the swaralipi; the lyrics file does not have it.
- **Eso Eso:** "daao" and "jaa(o)" each sit on one held note, where the swaralipi gives the
  vowel its own matra. "puraton" is sung "to-n" over two notes.
- **Chokher Aloy:** the G# in "jho-re" (bars 69 and 85) is the arranger's passing note, not in
  the swaralipi.
- **Tomar Holo Shuru:** the swaralipi gives the final "r" of "tomar"/"aamar" its own matra; it is
  held on the syllable.

## Not done
- **No piano lesson for any of these songs.** They were cross-checked against Arup Paul's piano rolls instead (see below). The Arup
  Paul "Arrangement" video for Sankocher (lyrics above the staff) was not downloaded in this
  run.
- **Not checked by ear** against the catalogued vocal renditions.

## Cross-check against Arup Paul's piano rolls (added 2026-11-09)
Each draft was compared, word by word, with the melody read from Arup Paul's falling-notes
video (`scripts/piano_roll/extract_piano_roll.py`, tables made by
`scripts/vocal_melody/word_table.py` in `data/intermediate_data/comparison/<id>_words.md`).
"Same" means the roll plays exactly the draft's notes over that word.

| Song | Words the same | Where they differ |
|---|---|---|
| Eso Eso (rs000864) | 95 / 99 | single repeated notes |
| Dariye Achho (rs000636) | 95 / 108 | single repeated notes; every stanza otherwise note for note |
| Tomar Holo Shuru (rs002064) | 54 / 65 | the arranger's quick re-strikes (an extra repeated note), no other notes |
| Chokher Aloy (rs000616) | 81 / 113 | extra repeated notes; "baa-hi-re" S R G R G (draft S R G G R G); the roll has no final return of the sthayi |
| Sankocher (rs001848) | 15 / 65 | the video covers only the sthayi and antara: there 15 / 20 are the same; the rest are a repeated Ma in "aa-haa", "ni-je-re" D S' N (draft D N S'), and a few komal Ga that are probably misreads of a letter-labelled bar |

No word differs in its notes' pitches beyond these, so the five drafts are confirmed by an
independent arrangement (Arup Paul seems to work from the same staff notation, so this checks the
reading of the MIDI, not how the songs are sung).

Reader fixes made on the way: keys found from the keyboard itself (cropped keyboards, title
cards, photo overlays), each bar assigned to the key under its centre (Sankocher's wide bars had
read a semitone high), white keys placed on a least-squares grid of the black keys, and the
falling area cropped to an even height for ffmpeg.
