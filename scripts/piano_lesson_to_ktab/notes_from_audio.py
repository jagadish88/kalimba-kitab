"""Kalimba notes from the sound of a recording (video or audio file).

  python notes_from_audio.py student.mp4

Writes next to the input (or to --out):
  <name>_notes.abc  the notes as ABC sheet music, kalimba numbers under the
                    staff, to play back and check by ear
  <name>_notes.csv  one row per note: time, note(s), tine(s), strength,
                    certain or not, and what a less certain note could also be
  <name>_notes.png  spectrogram with every detected note marked - a quick
                    way to see whether a note was missed or misread
  <name>_played.wav the notes with exactly the timing they were played,
                    with a kalimba sound measured from a real instrument: to
                    compare by ear with the recording
                    (the ABC has to round the timing to whole note lengths)

How it works
  1. Tuning: the strongest pitches over the whole recording show how far the
     instrument is from A=440; the note frequencies follow it.
  2. Onsets: each pluck starts with a sharp attack (spectral flux peaks).
  3. Which note: at each onset, the kalimba note whose pitch rises most - from
     its lowest point around the onset to its steady level once the attack
     click has passed (60 ms on). Comparing with the lowest point also catches
     a tine that was still ringing and got re-plucked.
  4. Re-plucks: a tine plucked again while still ringing barely dips first,
     so step 3 sees only a small rise. Its level still JUMPS at the onset
     (typically 5-7 dB within 50 ms) while a tine that only rings just
     decays, so such an onset is kept as a re-pluck of that tine. Neighbour
     tines a semitone or tone away that only 'jump' because the louder tine
     leaks into their band are ignored, and the note just played is
     preferred (repeated notes are far commoner than steps).
     Onsets where no kalimba pitch rises (nail clicks, knocks, handling noise)
     are dropped; one pluck detected twice (same note within 0.12 s) is
     counted once. A gentle pluck with too soft an attack for step 2 is still
     caught: a pitch jumping 20 dB or more from near silence to about the
     loudness of the other notes.
  5. Two notes at once: the second must rise at least 45% as much as the
     first, not be the first note's overtone or its neighbour a semitone
     away, and get about as loud as a real pluck of its tine (within 15 dB
     of its level after the sure notes on it). Tines ring along faintly when
     others are plucked; that ringing is not a note. The same test decides
     which other notes a less certain note could have been (CSV column
     or_maybe, used by check_with_video.py).
  6. ABC rhythm from the gaps between notes. Played with swing (the two
     notes of most beats clearly unequal): 6/8, with all notes placed on the
     grid together so repeated passages come out the same. Otherwise 4/4 or
     6/8, whichever fits the repetition of beats and bars; pauses between
     phrases are rounded so each phrase sits on the beat.

Options:
  --layout "2'' 7' 5' 3' 1' 6 4 2 1 3 5 7 2' 4' 6' 1'' 3''"
                 notes of the tines from left to right (default: standard
                 17-key kalimba). Only used for the tine numbers in the CSV.
  --key C        the kalimba's key: the note that "1" stands for (C, D, G ...)
  --start / --end  only this part of the recording (seconds)
"""
import argparse
import csv
import shutil
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

STANDARD_17 = "2'' 7' 5' 3' 1' 6 4 2 1 3 5 7 2' 4' 6' 1'' 3''"
SEMITONES = {"1": 0, "2": 2, "3": 4, "4": 5, "5": 7, "6": 9, "7": 11}
KEYS = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5, "F#": 6, "Gb": 6,
        "G": 7, "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11}


# ------------------------------------------------------------------ notes
def parse_note(nm):
    """'1' -> (1, 0); "1'" -> (1, +1 octave); "5," -> (5, -1 octave)."""
    return int(nm.strip("',")), nm.count("'") - nm.count(",")


def note_midi(nm, key=0):
    deg, octv = parse_note(nm)
    return 60 + key + SEMITONES[str(deg)] + 12 * octv


def note_to_abc(nm):
    """Numbered note -> ABC pitch, with 1 = middle C (C4): 1 -> C, 1' -> c, 1'' -> c'.
    (Written in C; for another key the ABC is transposed - same numbers.)"""
    deg, octv = parse_note(nm)
    letter = "CDEFGAB"[deg - 1]
    return letter + "," * (-octv) if octv <= 0 else letter.lower() + "'" * (octv - 1)


# ------------------------------------------------------------------ audio
def ffmpeg_exe():
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        sys.exit("needs ffmpeg (or: pip install imageio-ffmpeg)")


def read_audio(path, sr=22050, start=None, end=None):
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "a.wav"
        cmd = [ffmpeg_exe(), "-y", "-loglevel", "error"]
        if start:
            cmd += ["-ss", str(start)]
        cmd += ["-i", str(path)]
        if end:
            cmd += ["-t", str(end - (start or 0))]
        cmd += ["-vn", "-ac", "1", "-ar", str(sr), "-acodec", "pcm_s16le", str(wav)]
        subprocess.run(cmd, check=True)
        with wave.open(str(wav)) as w:
            a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(float) / 32768
    return a, sr


def spectrogram(a, sr, win, hop, nfft):
    w = np.hanning(win)
    pad = np.concatenate([np.zeros(win // 2), a, np.zeros(win // 2)])
    frames = np.lib.stride_tricks.sliding_window_view(pad, win)[::hop]
    return np.abs(np.fft.rfft(frames * w, n=nfft, axis=1)), np.fft.rfftfreq(nfft, 1 / sr)


def tuning_offset(S, f):
    """How far (cents) the instrument sits from A=440: strongest pitches of the
    whole recording against the nearest semitone."""
    spec = S.mean(0)
    sel = np.where((f > 200) & (f < 1600))[0]
    x = spec[sel]
    peaks = [i for i in range(1, len(x) - 1) if x[i] > x[i - 1] and x[i] >= x[i + 1] and x[i] > 0.05 * x.max()]
    peaks = sorted(peaks, key=lambda i: -x[i])[:8]
    cents, wts = [], []
    for i in peaks:
        y0, y1, y2 = np.log(x[i - 1] + 1e-12), np.log(x[i] + 1e-12), np.log(x[i + 1] + 1e-12)
        di = 0.5 * (y0 - y2) / (y0 - 2 * y1 + y2) if (y0 - 2 * y1 + y2) != 0 else 0.0
        hz = f[sel[i]] + di * (f[1] - f[0])
        m = 69 + 12 * np.log2(hz / 440)
        cents.append(100 * (m - round(m)))
        wts.append(x[i])
    if not cents:
        return 0.0
    o = np.argsort(cents)
    cw = np.cumsum(np.array(wts)[o]) / np.sum(wts)
    return float(np.array(cents)[o][np.searchsorted(cw, 0.5)])        # weighted median


def onsets(a, sr, hop=256, n=1024):
    """Note onsets: peaks of spectral flux (sharp rises in any frequency band)."""
    S, _ = spectrogram(a, sr, n, hop, n)
    win = np.hanning(n)
    M = np.log1p(S / win.sum() * 100)
    flux = np.maximum(np.diff(M, axis=0), 0).sum(1)
    t = np.arange(1, len(M)) * hop / sr
    flux = (flux - np.median(flux)) / (np.percentile(flux, 95) - np.median(flux) + 1e-9)
    cand = [k for k in range(1, len(flux) - 1)
            if flux[k] >= 1.0 and flux[k] > flux[k - 1] and flux[k] >= flux[k + 1]]
    keep, dist = [], int(0.08 * sr / hop)
    for k in sorted(cand, key=lambda k: -flux[k]):
        if all(abs(k - j) >= dist for j in keep):
            keep.append(k)
    return np.sort(t[keep])


def band_levels(a, sr, freqs, hop=256):
    """Level of each kalimba pitch over time (+-35 cents band of a fine spectrum)."""
    S, f = spectrogram(a, sr, 2048, hop, 8192)
    E = np.zeros((len(S), len(freqs)))
    for j, f0 in enumerate(freqs):
        m = (f >= f0 * 2 ** (-35 / 1200)) & (f <= f0 * 2 ** (35 / 1200))
        E[:, j] = S[:, m].max(1)
    return E, hop / sr


def rises(E, dt, t0, t_next):
    """Per pitch: steady level after the attack minus the lowest level around it."""
    lo = slice(max(int((t0 - 0.04) / dt), 0), int((t0 + 0.05) / dt) + 1)
    end = max(min(t0 + 0.20, t_next - 0.01), t0 + 0.11)
    st = slice(int((t0 + 0.06) / dt), int(end / dt) + 1)
    if st.start >= len(E):
        return np.zeros(E.shape[1]), np.zeros(E.shape[1])
    steady = np.median(E[st], axis=0)
    low = E[lo].min(axis=0)
    return steady - low, 20 * np.log10((steady + 1e-9) / (low + 1e-9))


def repluck(X, dt, t0, loud_db, freqs, prev=None, jump_db=2.5, near_db=15.0, leak_db=6.0):
    """The tine that was plucked again while still ringing, or None.

    jump = highest level in the 80 ms after the onset minus the level just
    before it (30-10 ms before). Only tines already sounding near the
    loudness of a real pluck qualify (within near_db), and the jump must be at
    least jump_db and clearly the biggest one."""
    i0 = int(t0 / dt)
    b0, b1 = max(i0 - int(0.03 / dt), 0), max(i0 - int(0.01 / dt), 1)
    a1 = min(i0 + int(0.08 / dt) + 1, len(X))
    if b1 <= b0 or a1 <= i0:
        return None
    before = X[b0:b1].mean(axis=0)
    peak = X[i0:a1].max(axis=0)
    jump = peak - before
    ok = peak >= loud_db - near_db
    if not ok.any():
        return None
    # leakage: a ringing tine also shows up, weaker, in the band of a tine a
    # semitone or tone away and 'jumps' with it - only the louder one is real
    semis = 12 * np.log2(np.asarray(freqs)[:, None] / np.asarray(freqs)[None, :])
    near = (np.abs(semis) > 0.5) & (np.abs(semis) < 2.5)
    for a in range(len(freqs)):
        if ok[a] and any(peak[b] > peak[a] + leak_db for b in np.where(near[a])[0]):
            ok[a] = False
    jump = np.where(ok, jump, -99)
    o = np.argsort(-jump)
    j = int(o[0])
    if jump[j] < jump_db:
        return None
    # the same tine as the note just before is by far the likeliest re-pluck
    if prev is not None and prev != j and ok[prev] and jump[prev] >= max(jump_db, 0.7 * jump[j]):
        return int(prev)
    if len(o) > 1 and jump[o[1]] > 0.8 * jump[j] and jump[o[1]] > jump_db:
        return None                                          # no clear single re-plucked tine
    return j


# ------------------------------------------------------------------ transcription
def transcribe(a, sr, names, key=0):
    S, f = spectrogram(a, sr, 2048, 256, 8192)
    cents = tuning_offset(S, f)
    freqs = [440 * 2 ** ((note_midi(nm, key) - 69) / 12) * 2 ** (cents / 1200) for nm in names]
    E, dt = band_levels(a, sr, freqs)
    on = list(onsets(a, sr))

    notes, dropped = [], []
    raw = []
    for k, t0 in enumerate(on):
        t_next = on[k + 1] if k + 1 < len(on) else t0 + 1.0
        r_lin, r_db = rises(E, dt, t0, t_next)
        raw.append((t0, r_lin, r_db))
    top = np.array([r[1].max() for r in raw]) if raw else np.zeros(0)
    typical = float(np.median(top)) if len(top) else 0.0
    X = 20 * np.log10(E + 1e-9)
    loud_db = float(np.percentile(X.max(axis=1), 90))      # level of a solid pluck, any tine
    for t0, r_lin, r_db in raw:
        o = np.argsort(-r_lin)
        j1 = int(o[0])
        if r_lin[j1] < 0.08 * typical or r_db[j1] < 4:
            # A tine that is still ringing and gets plucked again barely dips
            # first, so its rise from the lowest point is small (2-5 dB). But
            # its level JUMPS at the onset (5-7 dB within 50 ms), while a tine
            # that only rings never jumps up - it just decays.
            prev = notes[-1]["main"] if notes else None
            j_re = repluck(X, dt, t0, loud_db, freqs, prev)
            if j_re is None:
                dropped.append(t0)                           # no kalimba pitch rose: not a pluck
                continue
            j1 = j_re
            notes.append(dict(time_s=float(t0), idx=[j1], strength_db=float(r_db[j1]), margin=99.0,
                              rise=float(max(r_lin[j1], 0.25 * typical)), main=j1, r_lin=r_lin,
                              r_db=r_db, cands=[j1], repluck=True))
            continue
        chord = [j1]
        for j2 in o[1:3]:
            j2 = int(j2)
            if r_lin[j2] < 0.45 * r_lin[j1] or r_db[j2] < 6:
                break
            ratio = freqs[j2] / freqs[j1]
            semis = 12 * np.log2(max(ratio, 1 / ratio))
            overtone = any(abs(12 * np.log2(ratio) - 12 * np.log2(h)) < 0.4 for h in (2, 3, 4))
            if semis < 1.5 or overtone:
                continue                                     # leakage or overtone, not a second note
            chord.append(j2)
        second = float(r_lin[o[1]]) if len(o) > 1 else 0.0
        notes.append(dict(time_s=float(t0), idx=sorted(chord, key=lambda j: freqs[j]),
                          strength_db=float(r_db[j1]), margin=float(r_lin[j1] / (second + 1e-9)),
                          rise=float(r_lin[j1]), main=j1, r_lin=r_lin, r_db=r_db, cands=list(chord)))
    # gentle plucks: a pitch that jumps >= 20 dB from near silence to about the
    # loudness of the other notes, with no attack big enough to be caught as
    # an onset (a soft thumb)
    X = 20 * np.log10(E + 1e-9)
    levels = [float(np.median(seg)) for n in notes
              for seg in [X[int((n["time_s"] + 0.06) / dt):int((n["time_s"] + 0.2) / dt), n["idx"][0]]]
              if len(seg)]                                 # a note at the very end has no level yet
    if levels:
        typical_db = float(np.median(levels))
        lead = 0.5 * 2048 / sr                             # the level starts rising half a window early
        w6, w20 = int(0.06 / dt), int(0.2 / dt)
        added = []
        for j in range(len(names)):
            x = X[:, j]
            for i in range(w6, len(x) - w20):
                before, after = x[i - w6:i].min(), np.median(x[i + w6:i + w20])
                if after - before >= 20 and after >= typical_db - 10 and x[i + 1] - x[i - 1] >= 6:
                    ti = i * dt + lead
                    if all(abs(ti - o) > 0.15 for o in on) and \
                            all(abs(ti - g["time_s"]) > 0.3 or g["idx"] != [j] for g in added):
                        added.append(dict(time_s=float(ti), idx=[j], strength_db=float(after - before), margin=99.0,
                                          rise=float(10 ** (after / 20) - 10 ** (before / 20))))
        notes = sorted(notes + added, key=lambda n: n["time_s"])

    # one pluck can trigger two onsets a few frames apart: the same note twice
    # within 0.12 s is one note (a real re-pluck is never that fast)
    merged = []
    for n in notes:
        if merged and n["idx"] == merged[-1]["idx"] and n["time_s"] - merged[-1]["time_s"] < 0.12:
            if n["rise"] > merged[-1]["rise"]:
                merged[-1] = n
            continue
        merged.append(n)
    notes = merged
    for n in notes:
        n["sure"] = n["margin"] >= 2.5 and n["rise"] >= 0.25 * typical
    real_pluck_check(notes, X, dt, typical)
    return notes, dropped, cents, freqs, S, f


def real_pluck_check(notes, X, dt, typical, softer_db=15.0):
    """A second note of a chord, or a rival pitch, only counts if it gets
    about as loud as a real pluck of that tine (within softer_db). Tines ring
    along faintly when others are plucked, and that ringing can rise a little
    at a neighbour's pluck without the tine being touched.
    Real-pluck loudness of a tine = its level after the sure single notes on
    it (or of all tines, for a tine with none yet); done twice so notes made
    sure in the first round count in the second. Adds n["maybe"]: the other
    notes (tine indexes) a less certain note could also be."""
    for n in notes:
        n["maybe"] = []
    if not notes:
        return
    nxt = [n["time_s"] for n in notes[1:]] + [notes[-1]["time_s"] + 1.0]

    def level(t, t_next, j):
        end = max(min(t + 0.20, t_next - 0.01), t + 0.11)
        return float(np.median(X[int((t + 0.06) / dt):int(end / dt) + 1, j]))
    for _ in range(2):
        real = {}
        for n, tn in zip(notes, nxt):
            if n["sure"] and len(n["idx"]) == 1:
                real.setdefault(n["idx"][0], []).append(level(n["time_s"], tn, n["idx"][0]))
        if not real:
            return
        every = float(np.median([v for vs in real.values() for v in vs]))
        ref = {j: float(np.median(real[j])) if j in real else every for j in range(X.shape[1])}
        for n, tn in zip(notes, nxt):
            if "r_lin" not in n:                              # gentle pluck: one clear pitch
                continue
            r_lin, r_db = n["r_lin"], n["r_db"]

            def plausible(j):
                return level(n["time_s"], tn, j) >= ref[j] - softer_db
            keep = [j for j in n["cands"] if plausible(j)]
            if not keep:                                      # a soft note: the pitch that rose most from quiet
                keep = [max(n["cands"], key=lambda j: r_db[j])]
            main = max(keep, key=lambda j: r_lin[j])
            rivals = [int(j) for j in np.argsort(-r_lin)
                      if int(j) not in keep and r_lin[j] > 0 and plausible(int(j))]
            n["idx"], n["main"] = sorted(keep), main
            n["rise"], n["strength_db"] = float(r_lin[main]), float(r_db[main])
            n["margin"] = float(r_lin[main] / r_lin[rivals[0]]) if rivals else 99.0
            n["sure"] = n["margin"] >= 2.5 and n["rise"] >= 0.25 * typical
            n["maybe"] = [] if n["sure"] else [j for j in rivals[:2] if r_lin[j] >= 0.2 * r_lin[main]]


# ------------------------------------------------------------------ ABC
def swing_units(x, bar=6):
    """Whole eighths for each gap between notes (x = gap / eighth), chosen
    together (Viterbi): each gap close to its own length, and every two
    consecutive gaps together close to theirs, because players keep the beat
    steadier than its two halves. So an evenly played pair inside a swung
    piece still fills exactly one beat. Pauses (about a bar or longer) are
    just rounded."""
    long_ = x >= bar - 1
    cand = [[max(1, int(round(v)))] if lg else sorted({max(1, int(np.floor(v))), max(1, int(np.ceil(v)))})
            for v, lg in zip(x, long_)]
    cost = {u: (np.log(x[0] / u) / 0.2) ** 2 for u in cand[0]}
    back = []
    for i in range(1, len(x)):
        new, bp = {}, {}
        for u in cand[i]:
            own = (np.log(x[i] / u) / 0.2) ** 2
            opts = [(c + own + (0.0 if long_[i] or long_[i - 1]
                                else (np.log((x[i - 1] + x[i]) / (up + u)) / 0.12) ** 2), up)
                    for up, c in cost.items()]
            new[u], bp[u] = min(opts)
        cost = new
        back.append(bp)
    u = min(cost, key=cost.get)
    units = [u]
    for bp in reversed(back):
        u = bp[u]
        units.append(u)
    return np.array(units[::-1], int)


def write_abc(path, results, title, key_name="C"):
    """results: dicts with time_s, notes (list of numbered notes), sure."""
    t = np.array([r["time_s"] for r in results])
    if len(t) < 2:
        return None
    ioi = np.diff(t)
    # Swing: when the two notes of most beats are clearly unequal (long-short),
    # the beat is the time two consecutive notes take together, the piece is
    # written in 6/8 (three eighths per beat) and swing_units rounds the gaps.
    med = float(np.median(ioi))
    pairs = [(ioi[i], ioi[i + 1]) for i in range(len(ioi) - 1) if ioi[i] < 1.8 * med and ioi[i + 1] < 1.8 * med]
    swing = float(np.mean([abs(np.log(x / y)) > np.log(1.25) for x, y in pairs])) if len(pairs) >= 4 else 0.0
    if swing > 0.6:
        bar, beat = 6, 3
        p = float(np.median([x + y for x, y in pairs])) / beat
        for _ in range(2):                                # refine on the whole piece
            units = swing_units(ioi / p, bar)
            k = np.r_[0, np.cumsum(units)]
            p = float(np.sum(k * (t - t[0])) / np.sum(k * k))
        # bar lines where phrases (notes after long gaps) start and notes fall on beats
        starts = [k[i + 1] for i in range(len(units)) if units[i] >= 3]
        phase = max(range(bar), key=lambda ph: (np.mean([(x - ph) % beat == 0 for x in k]) +
                                                (np.mean([(x - ph) % bar == 0 for x in starts]) if starts else 0),
                                                ph == 0))
    else:
        # unit = the note length that best explains all the gaps, searched
        # around the typical short gap; then refined on the whole piece
        short = float(np.median(np.sort(ioi)[:max(2, len(ioi) // 3)]))
        body = ioi[ioi < 6 * short]
        cands = np.arange(0.75 * short, 1.05 * short, 0.002)
        err = [np.mean(np.abs(body / q - np.maximum(1, np.round(body / q)))) for q in cands]
        p = float(cands[int(np.argmin(err))])
        for _ in range(2):
            units = np.maximum(1, np.round(ioi / p)).astype(int)
            k = np.r_[0, np.cumsum(units)]
            p = float(np.sum(k * (t - t[0])) / np.sum(k * k))
        # meter: 4/4 (beat = 2 eighths) or 6/8 (beat = 3 eighths), whichever
        # explains the repetition of beats and bars better; bar lines where
        # phrases (notes after long gaps) start and notes fall on beats
        pos = set(int(x) for x in k)
        starts = [k[i + 1] for i in range(len(units)) if units[i] >= 3]
        best = None
        for bar_, beat_ in ((8, 2), (6, 3)):
            repeat = np.mean([(x + beat_) in pos for x in k]) + np.mean([(x + bar_) in pos for x in k])
            for ph in range(bar_):
                on_beat = np.mean([(x - ph) % beat_ == 0 for x in k])
                on_bar = np.mean([(x - ph) % bar_ == 0 for x in starts]) if starts else 0
                score = 2 * repeat + on_beat + on_bar + (0.01 if bar_ == 8 else 0) + (0.005 if ph == 0 else 0)
                if best is None or score > best[0]:
                    best = (score, bar_, beat_, ph)
        _, bar, beat, phase = best
    # pauses between phrases are arbitrary: a phrase that fits the grid
    # clearly worse than it could is moved by adjusting the pause before it,
    # preferably to where the well-placed phrases start in the bar (so
    # repeated phrases are written the same way)
    dur = np.minimum(np.r_[units, bar], bar).astype(float)
    cuts = [0] + [i + 1 for i in range(len(units)) if units[i] >= bar - 1] + [len(t)]
    phrases = list(zip(cuts[:-1], cuts[1:]))
    k = k.copy()

    def fit_of(a_, b_):
        rel, w = k[a_:b_] - k[a_], dur[a_:b_]
        return lambda ph: (np.sum(w * ((rel + ph) % beat == 0)) + 0.5 * np.sum(w * ((rel + ph) % bar == 0))) / w.sum()
    fits = [fit_of(a_, b_) for a_, b_ in phrases]
    placed = [int((k[a_] - phase) % bar) for a_, _ in phrases]
    ok = [c for c, fit in zip(placed, fits) if fit(c) >= max(fit(x) for x in range(bar)) - 0.15]
    ref = max(set(ok), key=ok.count) if ok else None
    shift = 0
    for (a_, b_), fit in zip(phrases, fits):
        cur = int((k[a_] + shift - phase) % bar)
        top = max(fit(x) for x in range(bar))
        if fit(cur) < top - 0.15:
            if ref is not None and fit(ref) >= top - 0.1:
                target = ref
            else:
                target = max(range(bar), key=lambda x: (fit(x), -abs(((x - cur + bar // 2) % bar) - bar // 2)))
            delta = ((target - cur + bar // 2) % bar) - bar // 2
            if a_ > 0 and k[a_] + shift + delta <= k[a_ - 1]:
                delta += bar
            shift += delta
        k[a_:b_] = k[a_:b_] + shift
    meter = "4/4" if bar == 8 else "6/8"
    bpm = int(round(60 / (beat * p)))
    first_bar = phase - bar if phase > 0 else 0
    ends = np.r_[k[1:], (k[-1] - first_bar) // bar * bar + first_bar + bar]
    std = [8, 6, 4, 3, 2, 1] if bar == 8 else [6, 3, 2, 1]
    bars = {}
    for i, r in enumerate(results):
        pos_, end = int(k[i]), int(ends[i])
        # a note still ringing at the bar line is tied over (a kalimba tine keeps
        # sounding; a rest would cut it off in playback), for up to two bars
        bar_end = first_bar + bar * ((pos_ - first_bar) // bar + 1)
        ring = min(end, pos_ + 2 * bar) if end > bar_end else pos_
        segs = []
        while pos_ < end:
            b = (pos_ - first_bar) // bar
            stop = min(end, first_bar + bar * (b + 1))
            if pos_ < ring:
                stop = min(stop, ring)
            seg = stop - pos_
            while seg > 0:
                d_ = next(x for x in std if x <= seg)
                kind = "note" if not segs else ("tie" if pos_ < ring else "rest")
                if kind == "tie":
                    segs[-1]["tied"] = True
                segs.append(dict(pos=pos_, d=d_, r=r, kind=kind, tied=False, bar=b))
                pos_, seg = pos_ + d_, seg - d_
        for sg in segs:
            bars.setdefault(sg["bar"], []).append(sg)
    lines, lyr, row_n, row_w = [], [], [], []
    for b in sorted(bars):
        toks, words, prev_beat = [], [], None
        for sg in bars[b]:
            pos_, d_, r = sg["pos"], sg["d"], sg["r"]
            if sg["kind"] == "rest":
                toks.append(" z" + (str(d_) if d_ > 1 else ""))
                prev_beat = None
                continue
            pitches = [note_to_abc(nm) for nm in r["notes"]]
            body_ = pitches[0] if len(pitches) == 1 else "[" + "".join(pitches) + "]"
            mark = '"^?"' if sg["kind"] == "note" and not r["sure"] else ""
            tok = mark + body_ + (str(d_) if d_ > 1 else "") + ("-" if sg["tied"] else "")
            bt = (pos_ - first_bar) // beat
            joined = prev_beat == bt and d_ <= 2 and (d_ == 1 or beat == 3)
            toks.append(tok if joined else " " + tok)
            prev_beat = bt if (d_ == 1 or (beat == 3 and d_ <= 2)) else None
            words.append("+".join(r["notes"]) if sg["kind"] == "note" else "_")
        row_n.append("".join(toks).strip())
        row_w.append(" ".join(words))
        if len(row_n) == 2:
            lines.append(" | ".join(row_n) + " |")
            lyr.append("w: " + " | ".join(row_w) + " |")
            row_n, row_w = [], []
    if row_n:
        lines.append(" | ".join(row_n) + " |")
        lyr.append("w: " + " | ".join(row_w) + " |")
    lines[-1] = lines[-1] + "]"
    lyr[-1] = lyr[-1][:-2]
    body = []
    for a_, w_ in zip(lines, lyr):
        body += [a_, w_]
    head = ["X:1", f"T:{title}",
            "Z:notes read from the audio by notes_from_audio.py (kalimba numbers under the notes)",
            "N:? above a note = less certain; notes joined with + were played together",
            f"M:{meter}", "L:1/8", f"Q:{'1/4' if bar == 8 else '3/8'}={bpm}", "%%MIDI program 108",
            "K:C" if key_name == "C" else f"K:C % kalimba in {key_name}: written in C, numbers are the same"]
    table = ["", "% note  time_s  kalimba  abc"]
    for j, r in enumerate(results, 1):
        table.append(f"% {j:4d}  {r['time_s']:6.2f}  {'+'.join(r['notes']):7s}  "
                     f"{'+'.join(note_to_abc(x) for x in r['notes'])}{'' if r['sure'] else '   (less certain)'}"
                     f"{'   ' + r['remark'] if r.get('remark') else ''}")
    # Duration is the interval from this pluck to the next pluck, quantized
    # using the same rhythmic grid as the ABC transcription.
    for i, r in enumerate(results):
        u = int(units[i]) if i < len(units) else int(round(np.median(units)))
        r["duration_beats"] = u / beat
        r["duration_s"] = u * p
    Path(path).write_text("\n".join(head + body + table) + "\n")
    return f"{meter}, {'quarter' if bar == 8 else 'dotted quarter'} = {bpm}"


def kalimba_note(f0, n, sr, rng):
    """One kalimba pluck, n samples long. Measured on a real 17-key kalimba
    recording:
      - attack: full level within ~7 ms
      - body: nearly a pure tone - the overtones a pluck adds are 35-40 dB
        below the fundamental (2nd harmonic ~-35 dB, a faint inharmonic
        partial near 2.8x ~-39 dB that dies fast)
      - fade: higher tines fade much faster: ~25 dB/s at 500 Hz, ~41 dB/s at
        750 Hz (about dB/s = 24.5 * (f0/500)^1.3), never slower than 9 dB/s
      - pluck click: a soft broadband tick (1.5-12 kHz, 19-37 dB below the
        note) gone within ~40 ms
    """
    t = np.arange(n) / sr
    db_per_s = max(9.0, 24.5 * (f0 / 500.0) ** 1.3)
    tau = 8.686 / db_per_s                                   # amplitude time constant (s)
    y = np.sin(2 * np.pi * f0 * t) * np.exp(-t / tau)
    y += 10 ** (-35 / 20) * np.sin(2 * np.pi * 2 * f0 * t) * np.exp(-t / (0.6 * tau))
    y += 10 ** (-39 / 20) * np.sin(2 * np.pi * 2.8 * f0 * t + 1.0) * np.exp(-t / 0.06)
    y *= 1 - np.exp(-t / CLICK["rise"])                      # ~7 ms to full level
    # pluck click: a short noise burst shaped like the measured one - strongest
    # around 2 kHz, falling ~14 dB per octave above it, little below 1.5 kHz
    m = min(n, int(0.04 * sr))
    if m > 16:
        spec = np.fft.rfft(rng.standard_normal(m))
        ff = np.fft.rfftfreq(m, 1 / sr)
        shape = np.where(ff < 2000, (ff / 2000) ** 2, (ff / 2000) ** -2.4)
        burst = np.fft.irfft(spec * shape, m)
        burst /= np.sqrt(np.mean(burst ** 2)) + 1e-12
        y[:m] += CLICK["gain"] * burst * np.exp(-np.arange(m) / (CLICK["decay"] * sr))
    return y


CLICK = dict(rise=0.0006, gain=10 ** (-15 / 20), decay=0.004)   # tuned against the recording


def render_played(path, results, key=0, sr=22050):
    """The notes at exactly the times they were played, with a kalimba sound
    measured from a real instrument (see kalimba_note), as a WAV file: the
    player's own timing, which ABC can only write rounded to whole note
    lengths. A tine plucked again stops its previous ring (with a 10 ms
    fade, so there is no click)."""
    if not results:
        return
    sr = 44100                                               # the click needs the high frequencies
    rng = np.random.default_rng(0)
    hits = sorted((r["time_s"], nm, 1.0 / len(r["notes"]) ** 0.5) for r in results for nm in r["notes"])
    end = hits[-1][0] + 3.0
    out = np.zeros(int(end * sr) + 1)
    for j, (t0, nm, gain) in enumerate(hits):
        f0 = 440.0 * 2 ** ((note_midi(nm, key) - 69) / 12)
        db_per_s = max(9.0, 24.5 * (f0 / 500.0) ** 1.3)
        life = min(60.0 / db_per_s, 4.0)                     # until it has faded by 60 dB
        stop = next((t for t, n2, _ in hits[j + 1:] if n2 == nm), end)    # re-plucked: old ring stops
        n = int((min(stop, t0 + life) - t0) * sr)
        if n <= 0:
            continue
        y = gain * kalimba_note(f0, n, sr, rng)
        fade = min(n, int(0.01 * sr))
        y[-fade:] *= np.linspace(1, 0, fade)
        i0 = int(t0 * sr)
        out[i0:i0 + n] += y[:len(out) - i0]
    out *= 0.5 / (np.abs(out).max() + 1e-9)                  # headroom, like a real recording
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((out * 32767).astype("<i2").tobytes())


# ------------------------------------------------------------------ check picture
def check_picture(path, S, f, sr, freqs, names, notes, dropped, hop=256, px_per_s=80, row_s=20):
    """Spectrogram (kalimba pitch range) with the detected notes marked."""
    import cv2
    lo, hi = min(freqs) * 0.9, max(freqs) * 1.12
    H = 300
    logf = np.exp(np.linspace(np.log(lo), np.log(hi), H))
    cols = np.array([np.interp(logf, f, s) for s in S])                # time x H
    db = 20 * np.log10(cols + 1e-9)
    top = np.percentile(db, 99.5)
    img = np.clip((db - (top - 60)) / 60 * 255, 0, 255).astype(np.uint8).T[::-1]
    dt = hop / sr
    T = S.shape[0] * dt
    rows = []
    for r0 in np.arange(0, T, row_s):
        i0, i1 = int(r0 / dt), min(int((r0 + row_s) / dt), S.shape[0])
        width = int(min(row_s, T - r0) * px_per_s) + 10        # last row: only as long as the recording
        tile = cv2.resize(img[:, i0:i1], (max(int((i1 - i0) * dt * px_per_s), 1), H), interpolation=cv2.INTER_AREA)
        tile = cv2.applyColorMap(tile, cv2.COLORMAP_MAGMA)
        canvas = np.zeros((H + 40, width + 50, 3), np.uint8)
        canvas[20:20 + H, 50:50 + tile.shape[1]] = tile

        def y_of(hz):
            return int(20 + H - 1 - (np.log(hz) - np.log(lo)) / (np.log(hi) - np.log(lo)) * (H - 1))
        for nm, hz in zip(names, freqs):
            y = y_of(hz)
            cv2.line(canvas, (50, y), (50 + width, y), (70, 70, 70), 1)
            cv2.putText(canvas, nm, (4, y + 4), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (220, 220, 220), 1, cv2.LINE_AA)
        for s in range(int(r0), int(r0 + row_s) + 1):
            x = 50 + int((s - r0) * px_per_s)
            cv2.line(canvas, (x, 20 + H), (x, 26 + H), (200, 200, 200), 1)
            cv2.putText(canvas, f"{s}s", (x - 8, 38 + H), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (200, 200, 200), 1, cv2.LINE_AA)
        for t0 in dropped:
            if r0 <= t0 < r0 + row_s:
                x = 50 + int((t0 - r0) * px_per_s)
                cv2.line(canvas, (x, 20), (x, 32), (150, 150, 150), 1)          # onset with no note
        for n in notes:
            if r0 <= n["time_s"] < r0 + row_s:
                x = 50 + int((n["time_s"] - r0) * px_per_s)
                for j in n["idx"]:
                    y = y_of(freqs[j])
                    col = (255, 255, 0) if n["sure"] else (0, 165, 255)
                    cv2.circle(canvas, (x, y), 5, col, 1, cv2.LINE_AA)
                    cv2.putText(canvas, names[j], (x + 6, y - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.4, col, 1, cv2.LINE_AA)
        rows.append(canvas)
    wmax = max(r.shape[1] for r in rows)
    rows = [np.pad(r, ((0, 0), (0, wmax - r.shape[1]), (0, 0))) for r in rows]
    cv2.imwrite(str(path), np.vstack(rows))


def format_numbered_notes(results):
    """Format notes with duration suffixes and break lines after long gaps.

    One beat has no suffix, half a beat uses '/', a quarter beat uses '//'.
    Durations longer than one beat are shown explicitly as (n).
    """
    lines, current = [], []
    for r in results:
        duration = max(float(r.get("duration_beats", 1.0)), 0.125)
        if duration > 1.0:
            suffix = f"({duration:g})"
        else:
            subdivisions = max(0, int(round(-np.log2(duration))))
            suffix = "/" * min(subdivisions, 4)
        current.append("+".join(r["notes"]) + suffix)
        if duration > 1.0:
            lines.append(" ".join(current))
            current = []
    if current:
        lines.append(" ".join(current))
    return "\\n".join(lines)


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("recording")
    ap.add_argument("--layout", default=STANDARD_17)
    ap.add_argument("--key", default="C")
    ap.add_argument("--start", type=float, default=None)
    ap.add_argument("--end", type=float, default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    src = Path(args.recording)
    out_dir = Path(args.out) if args.out else src.resolve().parent
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = src.stem
    layout = args.layout.split()
    key = KEYS.get(args.key)
    if key is None:
        sys.exit(f"unknown key {args.key}")
    names = sorted(set(layout), key=lambda nm: note_midi(nm))
    tine_of = {nm: i + 1 for i, nm in enumerate(layout)}

    a, sr = read_audio(src, start=args.start, end=args.end)
    notes, dropped, cents, freqs, S, f = transcribe(a, sr, names, key)
    t_off = args.start or 0.0
    print(f"tuning: {cents:+.0f} cents from A=440; {len(notes)} notes "
          f"({sum(not n['sure'] for n in notes)} less certain), "
          f"{len(dropped)} onsets with no note ignored (clicks/handling)")

    results = [dict(time_s=n["time_s"] + t_off, notes=[names[j] for j in n["idx"]], sure=n["sure"],
                    strength_db=n["strength_db"], margin=n["margin"],
                    maybe=[names[j] for j in n.get("maybe", [])]) for n in notes]
    with open(out_dir / f"{stem}_notes.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["time_s", "note", "tine", "abc", "duration_s", "duration_beats",
                    "strength_db", "certain", "or_maybe"])
        for r in results:
            w.writerow([f"{r['time_s']:.3f}", "+".join(r["notes"]),
                        "+".join(str(tine_of.get(x, "")) for x in r["notes"]),
                        "+".join(note_to_abc(x) for x in r["notes"]),
                        f"{r.get('duration_s', 0):.3f}", f"{r.get('duration_beats', 0):.3f}",
                        f"{r['strength_db']:.1f}", "yes" if r["sure"] else "less",
                        " ".join(r["maybe"])])
    rhythm = write_abc(out_dir / f"{stem}_notes.abc", results, f"{stem} - notes heard in the audio", args.key)
    render_played(out_dir / f"{stem}_played.wav", results, key)
    try:
        check_picture(out_dir / f"{stem}_notes.png", S, f, sr, freqs, names, notes, dropped)
    except ImportError:
        pass                                              # picture needs opencv
    print("notes:")
    print(format_numbered_notes(results))
    print(f"abc:   {out_dir / (stem + '_notes.abc')}  ({rhythm})")
    print(f"csv:   {out_dir / (stem + '_notes.csv')}\npng:   {out_dir / (stem + '_notes.png')}")
    print(f"wav:   {out_dir / (stem + '_played.wav')}  (the notes with the exact timing played)")


if __name__ == "__main__":
    main()
