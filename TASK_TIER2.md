You are working in the repository jagadish88/kalimba-kitab (kalimba tabs for Rabindra Sangeet). Read README.md first. Your job: make draft transcriptions of 5 songs, verify them, and push them to the branch `tier2-drafts`. Never push to main. Work autonomously; nobody will answer questions.

## Songs (Tier 2: one tivra Ma, retune F -> F#)
| song_id | title | raag | Sa in the MIDI |
|---|---|---|---|
| rs000864 | Eso Eso He Boishakh | Iman-Kalyan | C |
| rs001848 | Sankocher Biwhalata | Iman-Kalyan | G# (not C! write real pitches with K:C and accidentals) |
| rs002064 | Tomar Holo Shuru Amar | - | C |
| rs000636 | Dariye Achho Tumi Amar | Iman | C |
| rs000616 | Chokher Aloy Dekhechhilem | Iman | C |
Their swaralipi uses only S R G M P D N (tivra Ma, no shuddha Ma); see data/raw_data/metadata/scale_catalog.csv.

## Setup
1. `pip install -e . mido` (ktab package + MIDI). Try `apt-get install -y abcmidi` for abc2midi; skip that check if it fails. Try installing pdflatex (texlive-latex-base/extra) only for the preview PDFs; if it is not possible, skip PDFs and say so.
2. The MIDI, swaralipi and lyrics files are git-ignored; download just these 5 songs:
```
python3 - <<'PY'
import csv, os
ids=('rs000864','rs001848','rs002064','rs000636','rs000616')
rows=[r for r in csv.DictReader(open('sources/sources.csv')) if any(f'/{i}' in r['local_path'] for i in ids)
      and r['local_path'].startswith(('data/raw_data/midi/','data/raw_data/swaralipi/','data/raw_data/text/lyrics/'))]
os.makedirs('/tmp/fs/sources',exist_ok=True)
w=csv.DictWriter(open('/tmp/fs/sources/sources.csv','w',newline=''),fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)
PY
cd /tmp/fs && python3 $OLDPWD/scripts/fetch_sources.py --dest $OLDPWD; cd -
```
3. Save the two helper scripts below as /tmp/midi_bars.py and /tmp/check_abc.py.

## Method (per song) - the same method already used for rs002164, rs000451, rs000920, rs001194, rs000011, rs000262
Study data/intermediate_data/abc/rs000451/v1.abc and rs001194/v1.abc first: copy their header style (X, T, C, S: sources, N: notes, M, L:1/8, Q, K:C, P: section labels) and w: conventions exactly.
1. `cd <repo> && python3 /tmp/midi_bars.py <id> > /tmp/<id>.bars` prints the MIDI melody (violin track) bar by bar as ABC tokens with real pitches, L:1/8, ties across bars. The ABC music lines must reproduce these bars exactly (same tokens, same order, every bar, including rests and tied notes).
2. Read the swaralipi (Read data/raw_data/swaralipi/<id>.pdf; it is Bengali Akarmatrik notation). Learn the notation: swaras সা রা গা মা পা ধা না; ক্ষা = tivra Ma (F#); hyphenated cells (-পা) continue the previous syllable's melisma; -1 holds; a dot below = mandra, above = taar; small superscript = grace note; { } = repeat; ( ) = only the first time. Under each note row is the lyric row: each syllable sits under the matra where it starts; • means the previous syllable continues.
3. Work out the time mapping: usually one swaralipi matra = one quarter note, so a 3-matra half-bar = one 3/4 bar (check the MIDI time signature in the first stderr line of midi_bars.py). Then map the whole MIDI form (sthayi, antara, sanchari, abhog, repeats, refrains, returns of the first line) onto the swaralipi lines, matching melodies. The MIDI is Anjan Ganguly's arrangement; it may repeat sections or drop a pickup.
4. Write data/intermediate_data/abc/<id>/v1.abc: one music line per sung phrase, with a `w:` line under it. One lyric token per note INCLUDING tied-on continuation notes; rests get no token. `-` joins syllables of one word, `_` holds the previous syllable over a note, `*` for a note with no lyric (instrumental). Bar lines `|` in w: help, but tokens must still be exactly one per note; a word continuing across a bar line must be written `syl-|syl` (no space before |) or it splits into two words. Lyrics: data/raw_data/text/lyrics/<id>.txt, syllabified; where the swaralipi's words differ from the lyrics file (refrains, extra words), follow the swaralipi and add an N: line saying so. Put each syllable on the note where the swaralipi starts it.
5. Verify, and fix until clean:
   - `python3 /tmp/check_abc.py data/intermediate_data/abc/<id>/v1.abc /tmp/<id>.bars` must print `errors: 0` (notes identical to the MIDI and one lyric token per note in every bar).
   - abc2midi (if installed) must report no errors.
   - `python3 scripts/piano_lesson_to_ktab/abc_to_ktab.py data/intermediate_data/abc/<id>/v1.abc --out data/intermediate_data/ktab/<id>/v1.ktab` then `ktab check data/intermediate_data/ktab/<id>/v1.ktab` must say OK with 0 warnings; read its per-line output and make sure each line reads as correct words (no words split or wrongly joined).
   - abc_to_ktab picks a transposition and may retune a tine (e.g. F4 -> F#4). Prefer a result in C with F tines retuned to F#; if its best fit substitutes notes in the main melody, try `--transpose 0` or `--transpose 12` (or for rs001848 the value that puts Sa on C) and keep the one with fewest wrong notes. Record the choice.
   - Preview: copy the .ktab to a temp dir, run `ktab tex <copy>.ktab`, copy only the PDF to data/intermediate_data/ktab/<id>/v1.pdf.
6. Optional cross-check (rs001848 only): its Arup Paul arrangement video https://www.youtube.com/watch?v=KvvV9WTnb7Y shows Bengali lyrics above the staff. If yt-dlp works in your environment, download it to /tmp (NOT into the repo), grab frames with ffmpeg and compare the syllable placement with your draft; report agreements and differences. If YouTube blocks the download, skip it and say so.

## Record keeping
- Append rows to data/intermediate_data/abc/abc_catalog.csv and data/intermediate_data/ktab/ktab_catalog.csv in the existing format (song_id, version v1, path, pipeline `midi_to_ktab`, source_ids = MIDI;swaralipi;lyrics source ids from data/raw_data/source_provenance.csv, made_from, date, note).
- If your reading of a swaralipi disagrees with its row in scale_catalog.csv (method `read`), fix that row and say so.
- Do NOT touch data/dataset/ (those are the user's finished songs), and do not commit the downloaded MIDI/swaralipi/lyrics files (.gitignore already excludes them).

## Deliver
- You are on branch `tier2-drafts` (this file is on it). Commit there (message ending with a Co-Authored-By line for Claude) and `git push origin tier2-drafts`. Commit and push after each finished song, so work is saved even if the session ends early.
- Write REVIEW_TIER2.md at the repo root (commit it too) with, per song: form found, bars, notes, checks passed, transposition/retune chosen, any notes substituted, and a list of the specific bars where you are least sure (blurry swaralipi, MIDI merging notes the swaralipi gives separate syllables, words that differ from the lyrics file). Be honest about anything not done.

## /tmp/midi_bars.py
```python
"""Melody of a MIDI as ABC bars (L:1/8, real pitches, ties across bars): python midi_bars.py rsNNNNNN"""
import sys, collections
sys.path.insert(0, 'scripts')
from fractions import Fraction as F
import mido, midi_to_ktab as m
s = sys.argv[1]
mid = mido.MidiFile(f'data/raw_data/midi/{s}.mid'); tpb = mid.ticks_per_beat
tr, meta = m.read_tracks(mid)
c = []
for i, (nm, n) in enumerate(tr):
    if len(n) < 50: continue
    ov = sum(1 for a, b in zip(n, n[1:]) if b[0] < a[1]) / len(n); c.append((ov, sum(x[2] for x in n) / len(n), i))
i = max([x for x in c if x[0] < 0.5], key=lambda x: x[1])[2]
notes = m.quantize(tr[i][1], tpb // 4)
num, den = meta['timesig']; bar = tpb * 4 // den * num
N = 'C ^C D ^D E F ^F G ^G A ^A B'.split()
def nm(p):
    o = p // 12 - 1; n = N[p % 12]
    return n.lower() + "'" * (o - 5) if o >= 5 else n + "," * (4 - o)
def ln(t):
    f = F(t, tpb // 2)
    if f == 1: return ""
    if f.denominator == 1: return str(f.numerator)
    if f.numerator == 1 and f.denominator in (2, 4): return "/" * {2: 1, 4: 2}[f.denominator]
    return f"{f.numerator}/{f.denominator}"
ev = []; prev = 0
for a, b, p in notes:
    if a > prev: ev.append((prev, a, None))
    ev.append((a, b, p)); prev = b
bars = {}
for a, b, p in ev:
    t = a
    while t < b:
        k = t // bar; e = min(b, (k + 1) * bar)
        tok = ("z" if p is None else nm(p)) + ln(e - t)
        if p is not None and e < b: tok += "-"
        bars.setdefault(k, []).append(tok); t = e
print(f"# track {i} ({tr[i][0]}), {num}/{den}, {len(notes)} notes, {max(bars)+1} bars", file=sys.stderr)
for k in range(max(bars) + 1):
    print(k, " ".join(bars.get(k, [f"z{ln(bar)}"])))
```

## /tmp/check_abc.py
```python
"""python check_abc.py song.abc song.bars : ABC notes vs MIDI bars, and lyric tokens per bar"""
import re, sys
sys.path.insert(0, 'scripts/piano_lesson_to_ktab')
from abc_to_ktab import lyric_tokens
abc = open(sys.argv[1]).read().splitlines()
midi = [l.split(' ', 1)[1] for l in open(sys.argv[2]).read().splitlines() if l and not l.startswith('#')]
body = False; bars = []; errs = 0; prev = []
note = re.compile(r"[_=^]{0,2}[A-Ga-g][',]*[\d/]*-?|z[\d/]*")
for i, l in enumerate(abc):
    if l.startswith('K:'): body = True; continue
    if not body or not l.strip() or l[0] == '%' or re.match(r'[A-Z]:', l): continue
    if l.startswith('w:'):
        wb = l[2:].split('|')
        if len(wb) < len(prev): wb += [''] * (len(prev) - len(wb))
        for k, (mb, w) in enumerate(zip(prev, wb)):
            n = len([x for x in note.findall(mb) if not x.startswith('z')]); t = len(lyric_tokens(w))
            if n != t: errs += 1; print(f'line {i+1} bar {k+1}: {n} notes, {t} tokens: {mb.strip()!r} / {w.strip()!r}')
        continue
    prev = [b for b in re.split(r'\|\]?', l) if b.strip()]
    bars += [' '.join(note.findall(b)) for b in prev]
print(len(bars), 'abc bars,', len(midi), 'midi bars')
for k, (a, b) in enumerate(zip(bars, midi)):
    if a != b: errs += 1; print('bar', k, 'abc', a, '| midi', b)
if len(bars) != len(midi): errs += 1
print('errors:', errs)
```
