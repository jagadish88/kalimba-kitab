#!/usr/bin/env python3
"""
piano_notes_from_audio.py

ABC sheet music, with the lyrics split into syllables under the notes, for
lines of song_lines.csv (the slow right-hand lines found by
extract_song_lines.py).

    python piano_notes_from_audio.py video.mp4 song_lines.csv --title "Ekla Cholo Re"

Writes one ABC file with one tune per stanza (no blank lines).

  --lines   only these rows of song_lines.csv, from one stanza ("1-2", "7-13")
  --key     key signature for the ABC (default E)
  --meter   4/4 (default), 6/8, or auto (picks per stanza)
  --tempo   quarter notes per minute for all stanzas (default: median played)
  --title   song title (default: the video's file name)
  --out     ABC file to write (default: <video name>.abc)

Needs notes_from_audio.py (the kalimba script) in the same folder.

What comes from where
  * WHICH notes: the note names shown on screen (the `notes` column of the
    CSV). They are taken as the truth.
  * WHEN each note starts, and its OCTAVE: the audio.
  * HOW LONG each note is: the audio of the same stanza played at normal speed
    (the "Fast" screens after the slow lines). The slow lines are played with
    rubato and don't round cleanly to note lengths; the normal-speed playing is
    steady.

How the audio is used (same ideas as notes_from_audio.py for the kalimba)
  1. Onsets: peaks of spectral flux (each key press has a sharp attack).
  2. A pitch guess per onset: for every pitch C2..B6, how much its fundamental
     and first three overtones rise at the onset; the pitch class with the
     largest rise summed over all octaves. (Summing over octaves matters: a
     piano's 3rd harmonic of G#4 is D#6.)
  3. Lining up: the onsets are matched to the screen notes in order (dynamic
     programming), so an extra onset (one key press detected twice, a knock) is
     dropped and a misheard pitch (typically a quick re-strike of a key still
     ringing) still gets the right note. Every disagreement is reported.
  4. Octave: for the screen note's pitch class, the lowest octave whose
     fundamental is within 12 dB of the strongest one.
  5. Note lengths: the gaps between the normal-speed notes, rounded to whole
     eighths of the length that explains all gaps best.
  6. Meter: 4/4 by default (--meter 6/8, or auto to pick 4/4 or 6/8). The bar
     lines go where the most note time falls on beats and the lines start on
     a bar line (or one eighth before it, as a pickup). The last note fills
     its bar.
  7. Lyrics: each word is split into syllables (romanised Bengali); a word's
     notes go one per syllable, extra notes held on its last syllable.
"""

import argparse
import csv
import re
import sys
from pathlib import Path

import numpy as np

import notes_from_audio as K      # read_audio, spectrogram, onsets, tuning_offset

NAMES = "C C# D D# E F F# G G# A A# B".split()
PC = {n: i for i, n in enumerate(NAMES)}
PC.update({"Cb": 11, "Db": 1, "Eb": 3, "Fb": 4, "Gb": 6, "Ab": 8, "Bb": 10})   # flats on screen
LETTERS = "CDEFGAB"
NATURAL = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
MAJOR = (0, 2, 4, 5, 7, 9, 11)


def parse_key(key):
    """'E' -> ('E', 4); 'Bb' -> ('B', 10); 'F#' -> ('F', 6): tonic letter and pitch class."""
    letter = key[0].upper()
    alt = {"": 0, "#": 1, "b": -1}[key[1:]]
    return letter, (NATURAL[letter] + alt) % 12


def key_signature(key):
    """Major key -> the alteration of each letter: E -> F,C,G,D sharp (+1); C -> none."""
    letter, tonic = parse_key(key)
    li = LETTERS.index(letter)
    sig = {}
    for i, step in enumerate(MAJOR):
        lt = LETTERS[(li + i) % 7]
        sig[lt] = ((tonic + step - NATURAL[lt] + 6) % 12) - 6
    return sig


def transposition(from_key, to_key):
    """(semitones, letter steps) taking from_key to to_key the shorter way:
    E -> C is down a major third: -4 semitones, -2 letters (E->C, D->B...)."""
    (fl, fp), (tl, tp) = parse_key(from_key), parse_key(to_key)
    semis = (tp - fp) % 12
    letters = (LETTERS.index(tl) - LETTERS.index(fl)) % 7
    if semis > 6:
        semis -= 12
        letters -= 7 if letters else 0
    return semis, letters


def midi_name(m):
    return f"{NAMES[m % 12]}{m // 12 - 1}"


def parse_lines(spec, n):
    rows = set()
    for part in spec.split(","):
        a, _, b = part.partition("-")
        rows.update(range(int(a), int(b or a) + 1))
    bad = [r for r in rows if not 1 <= r <= n]
    if bad:
        sys.exit(f"--lines out of range 1-{n}: {bad}")
    return sorted(rows)


def screen_notes(token_str):
    """'D#D# D# E' -> (['D#','D#','D#','E'], [2,1,1]): notes and notes per word."""
    notes, per_word = [], []
    for tok in token_str.split():
        parts = re.findall(r"[A-G][#b]?", tok)
        notes += parts
        per_word.append(len(parts))
    return notes, per_word


def mmss(s):
    m, sec = s.split(":")
    return 60 * int(m) + float(sec)


# ----------------------------------------------------------------------------
# Syllables (romanised Bengali)
# ----------------------------------------------------------------------------

VOWELS = set("aeiouAEIOU")
ONSETS = ("chh", "bh", "ch", "dh", "gh", "jh", "kh", "ph", "sh", "th")    # one sound each


def syllables(word):
    """'shune' -> ['shu','ne'], 'ekla' -> ['ek','la'], 'firaaye' -> ['fi','raa','ye'].
    A run of vowels is one syllable (aa, ai, eu, ui, oi); a single consonant or
    one sound written with several letters (bh, ch, chh, kh ...) starts the next
    syllable, together with an r after it (bhr, pr, tr); other consonants
    before it close the syllable before ('anchalchhaya' -> an-chal-chha-ya,
    'nibhrito' -> ni-bhri-to)."""
    nuclei = [(m.start(), m.end()) for m in re.finditer(r"[aeiouAEIOU]+", word)]
    if len(nuclei) <= 1:
        return [word]
    cuts = []
    for (_, e1), (s2, _) in zip(nuclei, nuclei[1:]):
        cons = word[e1:s2].lower()
        onset = next((o for o in ONSETS if cons.endswith(o)), cons[-1:])
        if cons.endswith("r") and len(cons) > len(onset):     # bhr, pr, tr: start together
            onset = next((o + "r" for o in ONSETS if cons.endswith(o + "r")), cons[-2:])
        cuts.append(s2 - len(onset))
    bounds = [0] + cuts + [len(word)]
    return [word[a:b] for a, b in zip(bounds, bounds[1:])]


def lyric_items(words, per_word):
    """One (text, ends_word) per note: a syllable, or '_' to hold the one before."""
    items = []
    for w, n in zip(words, per_word):
        syl = syllables(w)
        while len(syl) > n:                  # fewer notes than syllables: sing two on one
            syl[-2:] = [syl[-2] + syl[-1]]
        items += [(s, i == len(syl) - 1) for i, s in enumerate(syl)]
        items += [("_", True)] * (n - len(syl))    # more notes: hold the last syllable
    return items


def place_syllables(per_line, first_pos, beat):
    """Which of a word's notes start its syllables. The screen gives notes per
    word only, so when a word has more notes than syllables this is a guess:
    the syllables share the word's time evenly. The first starts on its first
    note; each other one on the note nearest its share of the word's length
    (two syllables over 12 eighths: the second at the 6th eighth), avoiding a
    quick ornament note (one eighth between two notes of the same other pitch:
    the F# of G F# G). The notes in between hold the syllable before."""
    for pl in per_line:
        k = 0
        for w, n in zip(pl["row"]["line"].split(), pl["per_word"]):
            ns = pl["notes"][k:k + n]
            syl = syllables(w)
            while len(syl) > n:                      # fewer notes than syllables
                syl[-2:] = [syl[-2] + syl[-1]]
            s_ = len(syl)
            at, p = [], 0
            for nt in ns:
                at.append(p)
                p += nt["units"] or 2
            total = p

            def orn(i):
                return (ns[i]["units"] or 2) == 1 and 0 < i < n - 1 \
                    and ns[i - 1]["midi"] == ns[i + 1]["midi"] != ns[i]["midi"]
            starts = [0]
            for j in range(1, s_):
                lo, hi = starts[-1] + 1, n - (s_ - j)        # leave a note for each syllable after
                target = total * j / s_
                starts.append(min(range(lo, hi + 1), key=lambda i: (abs(at[i] - target) + 1.5 * orn(i), i)))
            for i, nt in enumerate(ns):
                jj = sum(1 for st in starts if st <= i) - 1
                nt["lyric"] = (syl[jj] if i in starts else "_", jj == s_ - 1)
            k += n


def render_lyrics(items):
    """ABC w: text: '-' between syllables of a word, '_' holds a syllable for one
    more note (inside a word written 'syll-a-_ble', as in the ABC standard)."""
    out = ""
    for text, ends in items:
        out += text + (" " if ends else ("" if text == "_" else "-"))
    return out.strip()


# ----------------------------------------------------------------------------
# Audio
# ----------------------------------------------------------------------------

def onsets_with_pitch(video, t0, t1, lo=36, hi=96):
    """Onsets between t0 and t1 with, for each, the guessed pitch class and the
    octave each pitch class would have there. Returns (list, tuning_cents)."""
    pre = 0.3
    start = max(t0 - pre, 0)
    a, sr = K.read_audio(video, sr=22050, start=start, end=t1 + 0.5)
    S, f = K.spectrogram(a, sr, 4096, 256, 16384)
    dt = 256 / sr
    cents = K.tuning_offset(S, f)
    hz = lambda m: 440 * 2 ** ((m - 69) / 12) * 2 ** (cents / 1200)

    def band(spec, fr):
        sel = (f >= fr * 2 ** (-40 / 1200)) & (f <= fr * 2 ** (40 / 1200))
        return spec[sel].max() if sel.any() else 0.0

    # sharper in time (half the window) for following one pitch's level
    S2, f2 = K.spectrogram(a, sr, 2048, 256, 8192)
    _lev = {}

    def lev(midi):
        """dB level over time of one pitch's fundamental (+-40 cents)."""
        if midi not in _lev:
            sel = (f2 >= hz(midi) * 2 ** (-40 / 1200)) & (f2 <= hz(midi) * 2 ** (40 / 1200))
            _lev[midi] = 20 * np.log10(S2[:, sel].max(1) + 1e-9)
        return _lev[midi]

    def jumps_at(t, octave, jump_db=4.0, leak_db=6.0):
        """Pitch classes whose key could have been struck at t even if another
        pitch sounded louder: the fundamental jumps >= jump_db within 80 ms
        (kalimba script's re-pluck rule), and no key a semitone or tone away
        is more than leak_db louder (that would be leakage, not a key press)."""
        i0 = int(t / dt)
        b0, b1, a1 = max(i0 - int(0.03 / dt), 0), max(i0 - int(0.01 / dt), 1), i0 + int(0.08 / dt) + 1
        ok = set()
        for c, m in octave.items():
            x = lev(m)
            if a1 > len(x) or b1 <= b0:
                continue
            peak = x[i0:a1].max()
            if peak - x[b0:b1].mean() < jump_db:
                continue
            if any(lev(m + d)[i0:a1].max() > peak + leak_db for d in (-2, -1, 1, 2)):
                continue
            ok.add(c)
        return ok

    on = [t for t in K.onsets(a, sr) if t0 - 0.05 <= t + start < t1]
    out = []
    for k, t in enumerate(on):
        t_next = on[k + 1] if k + 1 < len(on) else t + 0.6
        steady = S[int((t + 0.06) / dt):int(max(min(t + 0.3, t_next - 0.01), t + 0.1) / dt) + 1].mean(0)
        before = S[max(int((t - 0.08) / dt), 0):int((t - 0.01) / dt) + 1].mean(0)
        rise = {m: sum(w * (np.log1p(band(steady, h * hz(m)) * 50) - np.log1p(band(before, h * hz(m)) * 50))
                       for h, w in ((1, 1.0), (2, 0.6), (3, 0.4), (4, 0.3)))
                for m in range(lo, hi)}
        scores = {c: sum(v for m, v in rise.items() if m % 12 == c) for c in range(12)}
        guess = max(scores, key=scores.get)
        octave = {}
        for c in range(12):
            level = {m: band(steady, hz(m)) for m in range(lo, hi) if m % 12 == c}
            top = max(level.values())
            octave[c] = min(m for m in level if level[m] >= top * 10 ** (-12 / 20))
        if out and out[-1]["guess"] == guess and t + start - out[-1]["time"] < 0.12:
            continue                     # one key press detected twice: keep the first
        out.append(dict(time=t + start, guess=guess, scores=scores, midi_for=octave, struck=jumps_at(t, octave)))

    def find_quiet_note(midi, t_lo, t_hi, min_jump=6.0):
        """A key pressed without a sharp attack (soft, or struck again while
        still ringing): the time its fundamental jumps the most between t_lo
        and t_hi, if by at least min_jump dB within ~50 ms (as the kalimba
        script's re-pluck and gentle-pluck rules)."""
        i0, i1 = int((t_lo - start) / dt), int((t_hi - start) / dt)
        if i1 - i0 < 4:
            return None
        x = lev(midi)
        w = max(1, int(0.05 / dt))
        best, best_i = 0.0, None
        for i in range(max(i0, w), min(i1, len(x) - w)):
            jump = x[i:i + w].max() - x[i - w:i].min()
            if jump > best:
                best, best_i = jump, i
        return (best_i * dt + start) if best_i is not None and best >= min_jump else None

    return out, cents, find_quiet_note


# Notes of the song's key: a pitch outside it is not a believable other
# reading of a note (unless the screen shows it there); set from --key.
SCALE = set(range(12))


MAJOR_KEY_NAMES = ["C", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]


def key_from_titles(video):
    """The key the video states on its title card: "Scale/Key - C Major" ->
    ('C', 'C major'); "Scale/Key - B Minor" -> ('D', 'B minor'): a minor key
    is worked with as its relative major (same notes and key signature).
    None if no such card is found."""
    from extract_chapter_titles import scan
    for ch in scan(video):
        m = re.search(r"key\W*([A-G])\s*(#|b|sharp|flat)?\s*(major|minor)", ch["title"], re.I)
        if m:
            tonic = PC[m.group(1).upper()] + {"#": 1, "sharp": 1, "b": -1, "flat": -1}.get((m.group(2) or "").lower(), 0)
            name = MAJOR_KEY_NAMES[tonic % 12]
            if m.group(3).lower() == "minor":
                return MAJOR_KEY_NAMES[(tonic + 3) % 12], f"{name} minor"     # relative major
            return name, f"{name} major"
    return None


def guess_key(rows):
    """Major key of the song from the screen notes: among the keys whose scale
    holds nearly as many of the notes as the best one (within 10%), the one
    whose home note most often ends a stanza. (Coverage alone can mislead: a
    song in E with many D naturals fits A major's scale best, but its stanzas
    end on E.)"""
    notes = [PC[n] for r in rows for n in screen_notes(r["notes"])[0]]
    cover = {k: sum((n - k) % 12 in (0, 2, 4, 5, 7, 9, 11) for n in notes) for k in range(12)}
    best = max(cover.values())
    near = [k for k in range(12) if cover[k] >= 0.9 * best]
    finals = {}
    stanzas = {}
    for r in rows:
        stanzas.setdefault(r["chapter_no"], []).append(r)
    for st in stanzas.values():
        last = PC[screen_notes(st[-1]["notes"])[0][-1]]
        finals[last] = finals.get(last, 0) + 1
    k = max(near, key=lambda k: (finals.get(k, 0), cover[k]))
    return MAJOR_KEY_NAMES[k]


def key_scale(key):
    tonic = PC.get(key[0].upper() + key[1:], PC[key[0].upper()])
    return {(tonic + s) % 12 for s in (0, 2, 4, 5, 7, 9, 11)}


ALLOWED = set(range(12))                        # set per stanza: key + notes on its screens


def heard(o, e=None):
    """The pitch class onset o sounded like, among the notes this stanza can
    have: the key's notes plus any others its screens show (D natural in an
    E major song, say). A louder pitch outside them (noise of a re-strike, an
    overtone) does not count as another reading. The same set is used for
    every onset, so it cannot make one note look like its neighbour."""
    if "scores" not in o:
        return o["guess"]
    return max(ALLOWED, key=lambda c: o["scores"][c])


def line_up(onsets, expected):
    """Match onsets to the expected pitch classes in order. Returns, per
    expected note, the matched onset (or None), plus the onsets left over."""
    n, m = len(onsets), len(expected)
    EXTRA, MISSING = 1.0, 1.5

    def cost(o, e):
        if heard(o, e) == e:
            return 0.0                       # heard as the screen note
        if e in o.get("struck", ()):
            return 0.3                       # its key was struck too (re-strike under a louder note)
        return 0.9

    D = np.full((n + 1, m + 1), np.inf)
    D[0, :] = np.arange(m + 1) * MISSING
    D[:, 0] = np.arange(n + 1) * EXTRA
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            D[i, j] = min(D[i - 1, j - 1] + cost(onsets[i - 1], expected[j - 1]),
                          D[i - 1, j] + EXTRA, D[i, j - 1] + MISSING)
    match, extra = [None] * m, []
    i, j = n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0 and D[i, j] == D[i - 1, j - 1] + cost(onsets[i - 1], expected[j - 1]):
            match[j - 1] = onsets[i - 1]
            i, j = i - 1, j - 1
        elif i > 0 and D[i, j] == D[i - 1, j] + EXTRA:
            extra.append(onsets[i - 1])
            i -= 1
        else:
            j -= 1
    return match, extra[::-1]


def fill_quiet(match, expected, find_quiet_note):
    """Screen notes with no onset: look for the key being pressed quietly
    between the neighbouring notes (in the octave of the nearest neighbour)."""
    for j, o in enumerate(match):
        if o is not None:
            continue
        kp = next((k for k in range(j - 1, -1, -1) if match[k] is not None), None)
        kn = next((k for k in range(j + 1, len(match)) if match[k] is not None), None)
        if kp is None or kn is None:
            continue
        prev, nxt = match[kp], match[kn]
        ref = prev["midi_for"][expected[kp]]
        midi = min((ref // 12 * 12 + expected[j] + 12 * d for d in (-1, 0, 1)), key=lambda m: abs(m - ref))
        # stop 0.1 s before the next onset: its attack starts rising a little early
        t = find_quiet_note(midi, prev["time"] + 0.08, nxt["time"] - 0.1)
        if t is not None:
            match[j] = dict(time=t, guess=expected[j], midi_for={expected[j]: midi}, quiet=True)
    return match


def report(label, expected, match, extra):
    """Print disagreements between screen and audio; return their count."""
    issues = 0
    for j, (e, o) in enumerate(zip(expected, match)):
        if o is not None and o.get("quiet"):
            print(f"    {label} note {j + 1} ({NAMES[e]}): no sharp attack (soft or re-struck), "
                  f"found by its pitch rising at {o['time']:.2f}s")
        if o is None:
            print(f"    {label} note {j + 1} ({NAMES[e]}): not heard")
            issues += 1
        elif heard(o, e) != e and e in o.get("struck", ()):
            pass                             # its key was struck; another pitch just sounded louder
        elif heard(o, e) != e:
            print(f"    {label} note {j + 1} ({NAMES[e]}) at {o['time']:.2f}s: sounded more like {NAMES[heard(o, e)]}")
            issues += 1
    for o in extra:
        print(f"    {label}: extra onset at {o['time']:.2f}s ignored (sounded like {NAMES[o['guess']]})")
    return issues


# ----------------------------------------------------------------------------
# Rhythm and meter
# ----------------------------------------------------------------------------

def quantize(times, hint=None):
    """Whole eighths for each gap, with the eighth length that fits all gaps
    (as in notes_from_audio.write_abc). Returns (units, eighth_seconds).
    hint: the song's usual eighth; a stanza with few short notes can look as
    if its eighth were twice as long (or half), so of p/2, p and 2p the one
    nearest the hint is used."""
    ioi = np.diff(times)
    real = ioi[ioi > 0.05]                          # ignore two notes at (almost) the same time
    if len(real) < 2:
        return [max(1, int(round(x / 0.25))) for x in ioi], 0.25
    short = float(np.median(np.sort(real)[:max(2, len(real) // 3)]))
    body = real[real < 6 * short]
    cands = np.arange(0.75 * short, 1.05 * short, 0.002)
    err = [np.mean(np.abs(body / q - np.maximum(1, np.round(body / q)))) for q in cands]
    p = float(cands[int(np.argmin(err))])
    if hint:
        p = min((p / 2, p, 2 * p), key=lambda q: abs(np.log(q / hint)))
    for _ in range(2):
        units = np.maximum(1, np.round(ioi / p)).astype(int)
        k = np.r_[0, np.cumsum(units)]
        p = float(np.sum(k * (np.asarray(times) - times[0])) / np.sum(k * k))
    return [int(u) for u in units], p


METERS = {"4/4": (8, 2), "6/8": (6, 3)}


def choose_meter(units, line_starts, meter="4/4"):
    """(bar, beat, first_pos): first_pos = where the first note sits in its bar.
    meter '4/4' or '6/8' fixes the meter (only the bar lines are chosen);
    'auto' also picks the meter."""
    k = np.r_[0, np.cumsum(units)[:-1]]
    d = np.asarray(units, float)
    best = None
    for bar, beat in (METERS.values() if meter == "auto" else [METERS[meter]]):
        for ph in range(bar):                       # bar lines at positions = ph (mod bar)
            on_beat = d[(k - ph) % beat == 0].sum() / d.sum()
            starts = np.mean([((s - ph) % bar) in (0, bar - 1) for s in line_starts])
            score = on_beat + starts + (0.01 if bar == 8 else 0) + (0.005 if ph == 0 else 0)
            if best is None or score > best[0]:
                best = (score, bar, beat, (-ph) % bar)
    return best[1:]


# ----------------------------------------------------------------------------
# ABC
# ----------------------------------------------------------------------------

def abc_pitch(letter, midi, bar_acc, keysig):
    """ABC for a note spelled with this letter (the letter fixes the name: Bb,
    not A#), tracking accidentals within the bar against the key signature."""
    octave = next(o for o in range(-1, 10) if abs(midi - (12 * (o + 1) + NATURAL[letter])) <= 2)
    alt = midi - (12 * (octave + 1) + NATURAL[letter])
    current = bar_acc.get((letter, octave), keysig[letter])
    acc = ""
    if alt != current:
        acc = {2: "^^", 1: "^", 0: "=", -1: "_", -2: "__"}[alt]
        bar_acc[(letter, octave)] = alt
    body = letter.lower() + "'" * (octave - 5) if octave >= 5 else letter + "," * (4 - octave)
    return acc + body


def split_len(n, bar):
    std = (8, 6, 4, 3, 2, 1) if bar == 8 else (6, 3, 2, 1)
    out = []
    for d in std:
        while n >= d:
            out.append(d)
            n -= d
    return out


def doubt(o, e):
    """Why a note matched to onset o (screen pitch class e) is uncertain, or None."""
    if o is None:
        return "not heard"
    if o.get("quiet"):
        return "no clear attack, found by its pitch rising"
    if heard(o, e) != e and e not in o.get("struck", ()):
        return f"sounded more like {NAMES[heard(o, e)]}"
    return None


def strict_substitutes(stanzas, key, shift):
    """--strict: replace every note outside the key by a note of the key.
    One substitute per pitch class for the whole song (so repeated phrases stay
    the same), chosen over all its occurrences: keep the melody's direction
    into and out of the note, don't create a repeated note the original
    didn't have, prefer a semitone over a tone; on a tie, raise.
    Returns [(old name, new name, count)]."""
    semis, letters = shift
    sig = key_signature(key)
    tonic_letter, tonic = parse_key(key)
    li = LETTERS.index(tonic_letter)
    letter_of = {(tonic + MAJOR[i]) % 12: LETTERS[(li + i) % 7] for i in range(7)}
    in_key = set(letter_of)
    lines = [[nt for nt in pl["notes"]] for s in stanzas for pl in s["lines"]]
    pitch = lambda nt: nt["midi"] + semis
    out_pcs = sorted({pitch(nt) % 12 for ln in lines for nt in ln} - in_key)
    sign = lambda x: (x > 0) - (x < 0)
    result = []
    for pc in out_pcs:
        occ = [(ln, i) for ln in lines for i, nt in enumerate(ln) if pitch(nt) % 12 == pc]
        best = None
        for step in (1, -1, 2, -2):                 # raise first: wins ties
            if (pc + step) % 12 not in in_key:
                continue
            cost = 0.0
            for ln, i in occ:
                p, q = pitch(ln[i]), pitch(ln[i]) + step
                for j in (i - 1, i + 1):
                    if 0 <= j < len(ln):
                        r = pitch(ln[j])
                        cost += 2 * (sign(p - r) != sign(q - r))      # direction changed
                        cost += 3 * (q == r and p != r)               # new repeated note
                cost += 0.5 * abs(step)
            if best is None or cost < best[0]:
                best = (cost, step)
        step = best[1]
        new_pc = (pc + step) % 12
        for ln, i in occ:
            nt = ln[i]
            nt["sub"] = (letter_of[new_pc], pitch(nt) + step)
        old = LETTERS[(LETTERS.index(occ[0][0][occ[0][1]]["letter"]) + letters) % 7]
        alt = (pc - NATURAL[old] + 6) % 12 - 6
        result.append((old + {-1: "b", 0: "", 1: "#"}.get(alt, ""), letter_of[new_pc], len(occ)))
    return result


def song_body(stanzas, key, shift=(0, 0)):
    """ABC body of the whole song as one tune: P: per stanza, bars continuous.
    Each stanza's last note lasts until the next stanza's lead-in completes
    the bar (its length is not measured: it is marked uncertain)."""
    keysig = key_signature(key)
    semis, letters = shift                           # transposition (0, 0 = as played)
    out, pos, prev_bar = [], None, None
    for si, s in enumerate(stanzas):
        bar = s["bar"]
        if prev_bar is not None and bar != prev_bar:
            out.append(f"M:{'4/4' if bar == 8 else '6/8'}")
        out.append(f"P:Stanza {s['stanza_no']}")
        if pos is None:
            pos = s["first_pos"]
        prev_bar = bar
        for li, ln in enumerate(s["lines"]):
            toks, bar_acc, lyr = [], {}, []
            for ni, nt in enumerate(ln["notes"]):
                units = nt["units"]
                last_of_stanza = li == len(s["lines"]) - 1 and ni == len(ln["notes"]) - 1
                rest = 0
                if last_of_stanza:
                    if si + 1 < len(stanzas):        # where the next stanza's lead-in starts
                        nxt = stanzas[si + 1]
                        room = (nxt["first_pos"] - pos) % nxt["bar"]
                        while room < (units or 2):          # a long ending can span bars
                            room += nxt["bar"]
                    else:                            # the very end: to the end of the bar
                        room = (-pos) % bar or bar
                        while room < (units or 1):
                            room += bar
                    if units is None:                # not known: hold it until then
                        units = room
                    # known: a rest fills the gap to the next lead-in (none at the very end)
                    rest = room - units if si + 1 < len(stanzas) else 0
                    nt["units"] = units
                remaining, first = units, True
                while remaining > 0:
                    seg = min(remaining, bar - pos % bar)
                    pieces = split_len(seg, bar)
                    for i, d in enumerate(pieces):
                        tie = i < len(pieces) - 1 or remaining > seg
                        if "sub" in nt:              # --strict: a note of the key instead
                            letter, midi_out = nt["sub"]
                        else:
                            letter = LETTERS[(LETTERS.index(nt["letter"]) + letters) % 7]
                            midi_out = nt["midi"] + semis
                        toks.append(abc_pitch(letter, midi_out, bar_acc, keysig) + (str(d) if d > 1 else "") + ("-" if tie else ""))
                        text, ends = nt["lyric"]
                        if not first:
                            text = "_"                   # a tied-on note: hold the syllable
                        elif nt["doubt"]:
                            text = "?" if text == "_" else text + "?"
                        lyr.append((text, ends))
                        first = False
                    pos += seg
                    remaining -= seg
                    if pos % bar == 0:
                        toks.append("|")
                        bar_acc = {}
                while rest > 0:                      # rests take no syllable
                    seg = min(rest, bar - pos % bar)
                    for d in split_len(seg, bar):
                        toks.append("z" + (str(d) if d > 1 else ""))
                    pos += seg
                    rest -= seg
                    if pos % bar == 0:
                        toks.append("|")
                        bar_acc = {}
            out.append(" ".join(toks))
            out.append("w: " + render_lyrics(lyr))
    for j in range(len(out) - 1, -1, -1):           # final bar line
        if not out[j].startswith(("w:", "P:", "M:")):
            out[j] = (out[j][:-1].rstrip() if out[j].endswith("|") else out[j]) + " |]"
            break
    return out


# ----------------------------------------------------------------------------
# One stanza
# ----------------------------------------------------------------------------

def process_stanza(video, rows, sel, meter, hint=None):
    """Notes, octaves, times and lengths for the selected lines of one stanza."""
    global ALLOWED
    stanza_rows = [r for r in rows if r["chapter_no"] == sel[0]["chapter_no"]]
    ALLOWED = SCALE | {PC[n] for r in stanza_rows for n in screen_notes(r["notes"])[0]}
    # slow lines: when each screen note starts, and its octave
    per_line = []
    for r in sel:
        t0, t1 = float(r["line_timestamp_start_slow"]), float(r["line_timestamp_end_slow"])
        exp_names, per_word = screen_notes(r["notes"])
        expected = [PC[n] for n in exp_names]
        ons, _, finder = onsets_with_pitch(video, t0, t1)
        match, extra = line_up(ons, expected)
        match = fill_quiet(match, expected, finder)
        print(f"line {r['line_no']} of stanza {r['stanza_no']}: {r['line']}  ({t0:.2f}-{t1:.2f}s)")
        if not report("slow", expected, match, extra):
            print("    audio agrees with the screen")
        items = lyric_items(r["line"].split(), per_word)
        notes = [dict(pc=e, letter=nm[0], midi=o["midi_for"][e] if o else None, slow_time=o["time"] if o else None,
                      lyric=item, doubt=[f"slow: {d}"] if (d := doubt(o, e)) else [])
                 for e, o, item, nm in zip(expected, match, items, exp_names)]
        ref = next((x["midi"] for x in notes if x["midi"] is not None), 60)
        for nt in notes:                            # not heard: nearest octave to the line's notes
            if nt["midi"] is None:
                nt["midi"] = min((ref // 12 * 12 + nt["pc"] + 12 * d for d in (-1, 0, 1)), key=lambda m: abs(m - ref))
                nt["doubt"].append("octave guessed")
        per_line.append(dict(row=r, notes=notes, per_word=per_word))
    flat = [nt for pl in per_line for nt in pl["notes"]]
    # The same note again on screen (same pitch class, next note) is the same
    # key struck again: it keeps the previous note's octave. (Re-struck while
    # still ringing, its own fundamental barely rises, so the octave test can
    # pick a faint lower or higher one.)
    for a_, b_ in zip(flat, flat[1:]):
        if b_["pc"] == a_["pc"] and b_["midi"] != a_["midi"]:
            b_["midi"] = a_["midi"]

    # normal-speed playing of the whole stanza: the note lengths
    ch = sel[0]["chapter_no"]
    stanza = [r for r in rows if r["chapter_no"] == ch]
    stanza_expected = [PC[n] for r in stanza for n in screen_notes(r["notes"])[0]]
    first = sum(len(screen_notes(r["notes"])[0]) for r in stanza if int(r["line_no"]) < int(sel[0]["line_no"]))
    fast_t0 = max(float(r["line_timestamp_end_slow"]) for r in stanza)
    fast_t1 = mmss(sel[0]["chapter_time_interval"].split("-")[1])
    fast_ons, _, ffinder = onsets_with_pitch(video, fast_t0, fast_t1)
    fmatch, fextra = line_up(fast_ons, stanza_expected)
    fmatch = fill_quiet(fmatch, stanza_expected, ffinder)
    print(f"normal-speed playing of stanza {sel[0]['stanza_no']} ({fast_t0:.2f}-{fast_t1:.2f}s):")
    if not report("normal-speed", stanza_expected, fmatch, fextra):
        print("    audio agrees with the screen")
    times = [o["time"] if o else None for o in fmatch]
    slow_t = {first + j: nt["slow_time"] for j, nt in enumerate(flat)}
    placed_by_slow = set()
    for k, t in enumerate(times):                   # not heard at normal speed
        if t is None:
            kp = next((j for j in range(k - 1, -1, -1) if times[j] is not None), None)
            kn = next((j for j in range(k + 1, len(times)) if times[j] is not None), None)
            if kp is None or kn is None:
                times[k] = times[kp] if kp is not None else times[kn]
            elif all(slow_t.get(j) is not None for j in (kp, k, kn)) and slow_t[kn] > slow_t[kp]:
                # where it falls between its neighbours in the slow playing
                frac = (slow_t[k] - slow_t[kp]) / (slow_t[kn] - slow_t[kp])
                times[k] = times[kp] + frac * (times[kn] - times[kp])
                placed_by_slow.add(k)
            else:
                times[k] = (times[kp] + times[kn]) / 2
    all_units, eighth = quantize(times, hint)
    off_grid = np.abs(np.diff(times) / eighth - np.array(all_units))   # how far each gap is from whole eighths
    for j, nt in enumerate(flat):
        k = first + j
        nt["fast_time"] = times[k]
        d = doubt(fmatch[k], stanza_expected[k])
        # The same key struck again while still ringing (sustain pedal) barely
        # rises, so another pitch can sound louder. The pitch comes from the
        # screen anyway; only the onset time is used, so if the screen repeats
        # the previous note and the onset sits on the rhythm grid on both
        # sides, the mismatch is expected and the note is not uncertain.
        if d and d.startswith("sounded") and k > 0 and stanza_expected[k] == stanza_expected[k - 1] \
                and off_grid[k - 1] <= 0.3 and (k >= len(off_grid) or off_grid[k] <= 0.3):
            d = None
        # A key pressed softly (no sharp attack) at normal speed: the slow
        # playing already shows the same note with a clear onset, so the note
        # is there; its time only has to fit the rhythm on both sides.
        if d and fmatch[k] is not None and fmatch[k].get("quiet") and not nt["doubt"] and k > 0 \
                and off_grid[k - 1] <= 0.3 and (k >= len(off_grid) or off_grid[k] <= 0.3):
            d = None
        # Not heard at normal speed at all, but clear in the slow playing, and
        # placed between its neighbours as the slow playing places it: if that
        # time fits the rhythm on both sides, the note is settled.
        if d == "not heard" and k in placed_by_slow and not nt["doubt"] and k > 0 \
                and off_grid[k - 1] <= 0.3 and (k >= len(off_grid) or off_grid[k] <= 0.3):
            d = None
        if d:
            nt["doubt"].append(f"normal speed: {d}")
        if k < len(all_units) and j < len(flat) - 1:
            nt["units"] = all_units[k]
            if off_grid[k] > 0.3:
                nt["doubt"].append(f"length: gap of {np.diff(times)[k] / eighth:.2f} eighths rounded to {all_units[k]}")
        else:
            nt["units"] = None                      # last note: no next note in either playing;
            nt["last"] = True                       # its length comes from the same phrase elsewhere

    units = [nt["units"] or 1 for nt in flat]
    line_starts = list(np.cumsum([0] + [len(pl["notes"]) for pl in per_line])[:-1])
    k_start = [int(sum(units[:i])) for i in line_starts]
    bar, beat, first_pos = choose_meter(units, k_start, meter)
    place_syllables(per_line, first_pos, beat)
    print(f"  lengths: eighth = {eighth:.3f}s; {'4/4' if bar == 8 else '6/8'}"
          f"{f', lead-in of {bar - first_pos} eighth(s)' if first_pos else ''}")
    return dict(lines=per_line, eighth=eighth, bar=bar, beat=beat, first_pos=first_pos,
                stanza_no=sel[0]["stanza_no"])


def apply_lengths(stanzas, path):
    """Note lengths known from elsewhere - the song's swaralipi, say - replace
    the ones from the audio. Each row names a note by stanza, line and its
    number in the line, and gives its name as a check."""
    by = {(s["stanza_no"], pl["row"]["line_no"]): pl for s in stanzas for pl in s["lines"]}
    changed = same = 0
    for r in csv.DictReader(open(path, encoding="utf-8")):
        pl = by.get((r["stanza_no"], r["line_no"]))
        i = int(r["note_no"]) - 1
        if pl is None or not 0 <= i < len(pl["notes"]):
            print(f"  --lengths: no note {r['note_no']} in stanza {r['stanza_no']} line {r['line_no']}; skipped")
            continue
        nt = pl["notes"][i]
        if nt["pc"] != PC[r["note"]]:
            print(f"  --lengths: stanza {r['stanza_no']} line {r['line_no']} note {r['note_no']} is "
                  f"{NAMES[nt['pc']]}, not {r['note']}; skipped")
            continue
        new = int(r["eighths"])
        if nt["units"] == new:
            same += 1
        else:
            changed += 1
            print(f"  stanza {r['stanza_no']} line {r['line_no']} note {r['note_no']} ({r['note']}): "
                  f"{nt['units']} -> {new} eighths ({r.get('source', '').strip()})")
        nt["units"] = new
        nt["doubt"] = []
        nt["length_from"] = r.get("source", "").strip() or path
    print(f"--lengths: {changed} lengths changed, {same} confirmed")


def last_note_lengths(stanzas, k=4):
    """A stanza's last note has no next note in either playing (and the video
    cuts its sound), so its length is not measured. The same closing phrase
    usually also ends a line inside a stanza, where it is: a line ending with
    the same last k pitches and the same lengths before the last note. Take the length from there;
    without such a phrase the note stays uncertain and is held to the next
    stanza's lead-in."""
    lines = [(s, pl) for s in stanzas for pl in s["lines"]]
    for s in stanzas:
        pl = s["lines"][-1]
        nt = pl["notes"][-1]
        if not nt.get("last"):
            continue
        tail = pl["notes"][-k:]
        key_ = ([x["midi"] for x in tail], [x["units"] for x in tail[:-1]])
        found = None
        for s2, pl2 in lines:
            ns = pl2["notes"]
            for i in [len(ns)] if len(ns) >= k else []:   # a line ending, like the note itself
                cand = ns[i - k:i]
                if cand[-1].get("last") or cand[-1]["doubt"]:   # only measured, certain endings
                    continue
                if ([x["midi"] for x in cand], [x["units"] for x in cand[:-1]]) == key_:
                    found = (cand[-1]["units"], s2["stanza_no"], pl2["row"]["line_no"])
                    break
            if found:
                break
        if found:
            nt["units"] = found[0]
            print(f"stanza {s['stanza_no']}: last note ({pl['row']['line']}) = {found[0]} eighths, "
                  f"as the same phrase in stanza {found[1]} line {found[2]}")
        else:
            nt["doubt"].append("length: last note of the stanza, not measured")


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="ABC with syllables for the lines of song_lines.csv.")
    ap.add_argument("video")
    ap.add_argument("lines_csv")
    ap.add_argument("--lines", help="rows of the CSV from one stanza, 1-based (e.g. 1-2); default: every stanza")
    ap.add_argument("--key", default="auto",
                    help="major key the song is played in, e.g. E (default: worked out from the screen notes)")
    ap.add_argument("--to-key", help="transpose the ABC to this major key, e.g. C (default: as played)")
    ap.add_argument("--strict", action="store_true",
                    help="no accidentals: notes outside the key are replaced by notes of the key")
    ap.set_defaults(minor=None)                      # set when the title card says minor
    ap.add_argument("--meter", default="4/4", choices=["4/4", "6/8", "auto"],
                    help="time signature (default 4/4; auto picks 4/4 or 6/8 per stanza)")
    ap.add_argument("--tempo", type=int, help="quarter notes per minute "
                                              "(default: the median of the tempos played)")
    ap.add_argument("--title", help="song title (default: the video's file name)")
    ap.add_argument("--lengths", help="CSV of note lengths known from elsewhere (e.g. the song's swaralipi): "
                                      "stanza_no,line_no,note_no,note,eighths,source; they replace the "
                                      "lengths from the audio")
    ap.add_argument("--out", help="ABC file to write (default: <video name>.abc)")
    args = ap.parse_args()

    global SCALE
    rows = list(csv.DictReader(open(args.lines_csv, encoding="utf-8")))
    if not rows:
        sys.exit(f"{args.lines_csv} has no lines: nothing to transcribe "
                 "(were the lyrics/notes screens of the Right Hand chapters read?)")
    if args.key == "auto":
        stated = key_from_titles(args.video)
        if stated:
            args.key, said = stated
            if said.endswith("minor"):
                args.minor = said.split()[0]
            print(f"key: {said} (from the video's Scale/Key title card)"
                  + (f"; worked with as {args.key} major, the same notes" if args.minor else ""))
        else:
            args.key = guess_key(rows)
            print(f"key: {args.key} major (no Scale/Key card found; worked out from the notes on screen)")
    SCALE = key_scale(args.key)                     # major key, e.g. E: E F# G# A B C# D#
    if args.lines:
        sel = [rows[i - 1] for i in parse_lines(args.lines, len(rows))]
        if len({r["chapter_no"] for r in sel}) != 1:
            sys.exit("--lines must all come from one stanza")
        groups = [sel]
    else:
        order = list(dict.fromkeys(r["chapter_no"] for r in rows))
        groups = [[r for r in rows if r["chapter_no"] == ch] for ch in order]

    stanzas = [process_stanza(args.video, rows, g, args.meter) for g in groups]
    # One song, one beat: a stanza whose eighth came out about twice (or half)
    # the song's usual one has few short notes and was counted in quarters (or
    # sixteenths); count it again with the song's eighth.
    if len(stanzas) > 2:
        usual = float(np.median([s_["eighth"] for s_ in stanzas]))
        for i, (g, s_) in enumerate(zip(groups, stanzas)):
            if not 0.7 < s_["eighth"] / usual < 1.4:
                print(f"stanza {s_['stanza_no']}: eighth {s_['eighth']:.3f}s is about "
                      f"{s_['eighth'] / usual:.1f}x the song's {usual:.3f}s; counting it again")
                stanzas[i] = process_stanza(args.video, rows, g, args.meter, hint=usual)
    last_note_lengths(stanzas)
    if args.lengths:
        apply_lengths(stanzas, args.lengths)

    tempo = args.tempo or int(round(float(np.median([60 / (2 * s["eighth"]) for s in stanzas]))))
    title = args.title or Path(args.video).stem
    s0 = stanzas[0]
    head = [f"X:1", f"T:{title}",
            "C:notes from the screen; octave and lengths from the audio of the normal-speed playing",
            "N:? after a syllable = that note is less certain (see the notes CSV for why)",
            f"M:{'4/4' if s0['bar'] == 8 else '6/8'}", "L:1/8",
            f"Q:{'1/4=' + str(tempo) if s0['beat'] == 2 else '3/8=' + str(int(round(tempo * 2 / 3)))}",
            "%%MIDI program 0",
            f"K:{args.minor + 'm' if args.minor and not args.to_key else args.to_key or args.key}"]
    if args.to_key:
        head.insert(3, f"N:transposed from {args.key} major to {args.to_key} major")
    if args.lengths:
        n_from = sum(1 for s_ in stanzas for pl in s_["lines"] for nt in pl["notes"] if nt.get("length_from"))
        head.insert(3, f"N:{n_from} note lengths taken from {Path(args.lengths).name} (e.g. the song's swaralipi)")
    out_key = args.to_key or args.key
    shift = transposition(args.key, args.to_key) if args.to_key else (0, 0)
    if args.strict:
        subs = strict_substitutes(stanzas, out_key, shift)
        for old, new, n in subs:
            print(f"--strict: {old} -> {new} ({n} notes)")
        if subs:
            head.insert(3, "N:strictly in " + out_key + " major: " +
                        ", ".join(f"{old} played as {new} ({n} notes)" for old, new, n in subs))
    body = song_body(stanzas, out_key, shift)
    path = Path(args.out or f"{Path(args.video).stem}.abc")
    path.write_text("\n".join(head + body) + "\n")       # one header, no blank lines

    # every note with its time in the video goes to the CSV; only the
    # uncertain ones are printed, to check by hand
    def clock(t):
        return f"{int(t // 60)}:{t % 60:05.2f}" if t is not None else "-"

    notes_csv = path.with_name(path.stem + "_notes.csv")
    uncertain = []
    with open(notes_csv, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["stanza_no", "line_no", "syllable", "note", "time_slow_s", "time_normal_speed_s",
                    "length_eighths", "certain", "why_uncertain", "length_from"])
        for s in stanzas:
            for pl in s["lines"]:
                held = ""
                for nt in pl["notes"]:
                    syl = nt["lyric"][0]
                    if syl == "_":
                        syl = f"({held})"           # the syllable before, held over this note
                    else:
                        held = syl
                    ts = f"{nt['slow_time']:.2f}" if nt["slow_time"] is not None else ""
                    tf = f"{nt['fast_time']:.2f}" if nt["fast_time"] is not None else ""
                    why = "; ".join(nt["doubt"])
                    w.writerow([s["stanza_no"], pl["row"]["line_no"], syl, midi_name(nt["midi"]), ts, tf,
                                nt["units"], "no" if why else "yes", why,
                                nt.get("length_from", "audio")])
                    if why:
                        uncertain.append((s["stanza_no"], pl["row"]["line_no"], syl, midi_name(nt["midi"]),
                                          clock(nt["slow_time"]), clock(nt["fast_time"]), nt["units"], why))

    n_all = sum(len(pl["notes"]) for s in stanzas for pl in s["lines"])
    print(f"\n{len(uncertain)} of {n_all} notes are uncertain (marked ? in the ABC); times in the video:")
    if uncertain:
        print(f"{'stanza':>6} {'line':>4}  {'syllable':10} {'note':4} {'slow':>8} {'normal':>8} {'eighths':>7}  why")
        for st, ln, syl, nm, ts, tf, u, why in uncertain:
            print(f"{st:>6} {ln:>4}  {syl:10} {nm:4} {ts:>8} {tf:>8} {u:>7}  {why}")
    print(f"\nabc:   {path}  ({len(stanzas)} stanza(s), quarter = {tempo})")
    print(f"notes: {notes_csv}")


if __name__ == "__main__":
    main()
