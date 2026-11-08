#!/usr/bin/env python3
"""Sung melody from a recording: voice separation (Demucs) + pitch tracking (CREPE).

    python scripts/vocal_melody/extract_vocal_melody.py data/raw_data/audio/rs000864_src001749.m4a
    python scripts/vocal_melody/extract_vocal_melody.py song.m4a --out-dir DIR --sa 57

Writes, into --out-dir (default data/intermediate_data/vocal_melody/<song_id>/):
  <name>_pitch.csv   every 10 ms: time, f0 (Hz), midi (fractional), periodicity (0-1, how sure
                     CREPE is that there is a pitch); unvoiced frames have empty f0
  <name>_notes.csv   the contour cut into notes: start, end, midi (rounded), cents off, degree
                     relative to Sa (S r R g G m M P d D n N, with octave ' or ,)
  <name>_vocals.wav  the separated voice, 16 kHz mono (large: keep it out of git)
and prints the singer's Sa, found from the pitch histogram (or given with --sa as a MIDI number).

How it works
  1. Demucs (htdemucs) splits the mix into vocals / drums / bass / other; only vocals are kept.
  2. CREPE (torchcrepe, 'full' model) gives f0 and periodicity every 10 ms. Frames with
     periodicity below --min-periodicity or very quiet are treated as unvoiced.
  3. Sa: with --scale (the song's notes, e.g. from scale_catalog.csv), the pitch class whose
     degrees best cover the sung frames; without it, a guess from the histogram that can be a
     semitone off. The singer's tuning need not be A=440, so Sa is reported in cents too.
  4. Notes: the contour is median-filtered, rounded to the nearest semitone relative to Sa, and
     runs of the same semitone longer than --min-note seconds become notes. Short wobbles
     (meend, gamak) are absorbed into the neighbouring notes.

Needs: ffmpeg, torch, demucs, torchcrepe, librosa, soundfile (pip install demucs torchcrepe). torchaudio
is not needed: audio is decoded with ffmpeg, and a stub stands in for torchaudio at import time.
"""
import argparse
import csv
import os
import sys
import types

import numpy as np

sys.modules.setdefault('torchaudio', types.ModuleType('torchaudio'))   # demucs/torchcrepe import it for file I/O only
import librosa  # noqa: E402
import soundfile as sf  # noqa: E402
import torch  # noqa: E402

DEG = 'S r R g G m M P d D n N'.split()


def load_audio(path, sr, mono):
    """Any format ffmpeg can read -> float32 array (channels, samples) or (samples,)."""
    import subprocess
    ch = 1 if mono else 2
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-f', 'f32le', '-ac', str(ch), '-ar', str(sr), '-'],
                         capture_output=True, check=True).stdout
    y = np.frombuffer(raw, dtype=np.float32)
    return y if mono else y.reshape(-1, 2).T.copy()


def separate_vocals(path):
    from demucs.apply import apply_model
    from demucs.pretrained import get_model
    model = get_model('htdemucs')
    model.eval()
    y = load_audio(path, model.samplerate, mono=False)
    if y.ndim == 1:
        y = np.stack([y, y])
    mix = torch.tensor(y, dtype=torch.float32)
    ref = mix.mean(0)
    mix = (mix - ref.mean()) / ref.std()
    with torch.no_grad():
        out = apply_model(model, mix[None], device='cpu', shifts=1, split=True, overlap=0.25, progress=True)[0]
    vocals = out[model.sources.index('vocals')] * ref.std() + ref.mean()
    v = vocals.mean(0).numpy()
    return librosa.resample(v, orig_sr=model.samplerate, target_sr=16000), 16000


def track_pitch(v, sr, hop=0.01):
    import torchcrepe
    audio = torch.tensor(v, dtype=torch.float32)[None]
    f0, per = torchcrepe.predict(audio, sr, hop_length=int(sr * hop), fmin=65, fmax=1000, model='full',
                                 batch_size=512, device='cpu', return_periodicity=True)
    per = torchcrepe.filter.median(per, 3)
    f0 = torchcrepe.filter.mean(f0, 3)
    rms = librosa.feature.rms(y=v, frame_length=int(sr * 0.04), hop_length=int(sr * hop))[0]
    n = min(f0.shape[1], len(rms))
    return f0[0, :n].numpy(), per[0, :n].numpy(), rms[:n]


def find_sa(midi, weight):
    """Sa as a fractional MIDI pitch class: the tonic whose S/P/(G or g)/(m or M) etc. best explain the notes."""
    pc = np.mod(midi, 12.0)
    best = None
    for cand in np.arange(0, 12, 0.01):
        d = np.mod(pc - cand + 0.5, 1.0) - 0.5            # distance to the nearest semitone above cand
        on_grid = np.exp(-(d / 0.2) ** 2)                 # how well each frame sits on a semitone of this Sa
        deg = np.mod(np.round(pc - cand), 12).astype(int)
        hist = np.bincount(deg, weights=weight * on_grid, minlength=12)
        score = hist[0] * 1.5 + hist[7] + hist.sum() * 0.2 - hist[1] * 0.5 - hist[6] * 0.2   # Sa, Pa strong; r rare
        if best is None or score > best[0]:
            best = (score, cand)
    return best[1]


def find_sa_for_scale(midi, weight, scale):
    """Sa (fractional pitch class) whose scale degrees best cover the sung frames, e.g. scale='S R G M P D N'."""
    rel = {DEG.index(x) for x in scale.split()}
    pc = np.mod(midi, 12.0)
    best = None
    for cand in np.arange(0, 12, 0.01):
        d = np.mod(pc - cand + 0.5, 1.0) - 0.5
        deg = np.mod(np.round(pc - cand), 12).astype(int)
        w = weight * np.exp(-(d / 0.25) ** 2)
        score = w[np.isin(deg, list(rel))].sum() - w[~np.isin(deg, list(rel))].sum()
        if best is None or score > best[0]:
            best = (score, cand)
    return best[1]


def notes_from_contour(t, midi, voiced, sa, min_note=0.08):
    from scipy.ndimage import median_filter
    m = np.where(voiced, midi, np.nan)
    sm = median_filter(np.nan_to_num(m, nan=-1000), size=7)
    sm = np.where(voiced, sm, np.nan)
    rel = np.round(sm - sa)                                  # semitones above Sa (Sa at its own octave)
    notes, i, n = [], 0, len(t)
    while i < n:
        if np.isnan(rel[i]):
            i += 1
            continue
        j = i
        while j + 1 < n and rel[j + 1] == rel[i]:
            j += 1
        if t[j] - t[i] + (t[1] - t[0]) >= min_note:
            seg = sm[i:j + 1]
            notes.append([t[i], t[j] + (t[1] - t[0]), int(rel[i]), float(np.nanmedian(seg - sa - rel[i]) * 100)])
        i = j + 1
    merged = []                                              # join same-degree notes split by a short gap
    for nt in notes:
        if merged and merged[-1][2] == nt[2] and nt[0] - merged[-1][1] < 0.06:
            merged[-1][1] = nt[1]
        else:
            merged.append(nt)
    return merged


def deg_name(r):
    o, d = divmod(r, 12)
    return DEG[d] + ("'" * o if o > 0 else "," * -o)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('audio')
    ap.add_argument('--out-dir')
    ap.add_argument('--sa', type=float, help="Sa as a MIDI number (e.g. 57 = A3); default: worked out")
    ap.add_argument('--min-periodicity', type=float, default=0.5)
    ap.add_argument('--min-note', type=float, default=0.08, help='shortest note in seconds')
    ap.add_argument('--vocals', help='use an already separated vocals file instead of running Demucs')
    ap.add_argument('--scale', help="notes the song uses, e.g. 'S R G M P D N' (from scale_catalog.csv): picks Sa by fit")
    ap.add_argument('--from-pitch', action='store_true', help='reuse <name>_pitch.csv (skip Demucs and CREPE)')
    a = ap.parse_args()

    name = os.path.splitext(os.path.basename(a.audio))[0]
    song = name.split('_')[0]
    out = a.out_dir or f'data/intermediate_data/vocal_melody/{song}'
    os.makedirs(out, exist_ok=True)

    pitch_csv = os.path.join(out, f'{name}_pitch.csv')
    if a.from_pitch:
        rows = list(csv.DictReader(open(pitch_csv)))
        t = np.array([float(r['time']) for r in rows])
        f0 = np.array([float(r['f0']) if r['f0'] else 0.0 for r in rows])
        per = np.array([float(r['periodicity']) for r in rows])
        voiced = f0 > 0
        midi = 69 + 12 * np.log2(np.maximum(f0, 1e-6) / 440.0)
    elif a.vocals:
        v, sr = load_audio(a.vocals, 16000, mono=True), 16000
    else:
        print('separating the voice (Demucs, CPU: a few minutes)...', file=sys.stderr)
        v, sr = separate_vocals(a.audio)
        sf.write(os.path.join(out, f'{name}_vocals.wav'), v, sr)
    if not a.from_pitch:
        print('tracking pitch (CREPE)...', file=sys.stderr)
        f0, per, rms = track_pitch(v, sr)
        t = np.arange(len(f0)) * 0.01
        voiced = (per >= a.min_periodicity) & (rms > np.percentile(rms, 30) * 0.5) & (f0 > 0)
        midi = 69 + 12 * np.log2(np.maximum(f0, 1e-6) / 440.0)

    if a.sa is not None:
        sa = a.sa
    else:
        sa_pc = (find_sa_for_scale(midi[voiced], per[voiced], a.scale) if a.scale
                 else find_sa(midi[voiced], per[voiced]))
        oct_base = np.median(midi[voiced]) - 6                    # put Sa's octave near the bottom of the singing range
        sa = sa_pc + 12 * np.round((oct_base - sa_pc) / 12)
    names = 'C C# D D# E F F# G G# A A# B'.split()
    sa_note = names[int(np.round(sa)) % 12] + str(int(np.round(sa)) // 12 - 1)
    print(f'Sa = MIDI {sa:.2f} ({sa_note}, {100 * (sa - np.round(sa)):+.0f} cents)', file=sys.stderr)

    if not a.from_pitch:
      with open(pitch_csv, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['time', 'f0', 'midi', 'periodicity'])
        for i in range(len(t)):
            w.writerow([f'{t[i]:.2f}', f'{f0[i]:.1f}' if voiced[i] else '', f'{midi[i]:.2f}' if voiced[i] else '',
                        f'{per[i]:.2f}'])
    notes = notes_from_contour(t, midi, voiced, sa, a.min_note)
    with open(os.path.join(out, f'{name}_notes.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['start', 'end', 'semitones_from_sa', 'degree', 'cents_off', 'sa_midi'])
        for s, e, r, c in notes:
            w.writerow([f'{s:.2f}', f'{e:.2f}', r, deg_name(r), f'{c:+.0f}', f'{sa:.2f}'])
    print(f'{voiced.mean():.0%} of frames voiced; {len(notes)} notes -> {out}', file=sys.stderr)


if __name__ == '__main__':
    main()
