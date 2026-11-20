"""Tabla theka under a kalimba tune, for kalimba_video.py --taal.

The tabla is built from single recorded strokes (data/raw_data/audio/tabla/sonic_pi/, CC0, Sonic Pi /
Freesound dio_333). A bol played with both hands is the two strokes together: Dha = Na + Ghe,
Dhin = Tin + Ghe. The bol sounds and their levels were checked by ear on 2026-11-19
(data/intermediate_data/taal/audition/).

    theka(name, sr, sam, matra, start, end)  ->  mono float array (len = end + ring-out)

`sam` is the time (s) of a sam, `matra` the length (s) of one matra. The theka plays in time with
that sam from `start` (a pickup before the first sam starts mid-cycle, on the right bol) up to `end`,
then lands one Dha on the next sam.
"""
import os
import subprocess

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLES = os.path.join(HERE, '..', '..', 'data', 'raw_data', 'audio', 'tabla', 'sonic_pi')

# bol -> strokes: (sample, gain, length in s; a longer ring is damped like a hand would)
BOLS = {
    'Dha':  [('na', 1.0, .6), ('ghe4', .8, .8)],
    'Dhin': [('tas2', .9, .6), ('ghe4', .8, .8)],
    'Na':   [('na', 1.0, .6)],
    'Tin':  [('tas2', .9, .6)],
    'Ta':   [('na_s', 1.0, .3)],
    'Ge':   [('ghe8', .8, .5)],
    'Ke':   [('ke3', .7, .1)],
    'Ti':   [('te1', .8, .2)],
    'Tun':  [('tun2', .9, .8)],
}
BOLS['Dhi'] = BOLS['Dhin']
BOLS['Ka'] = BOLS['Kat'] = BOLS['Ke']
BOLS['Ra'] = BOLS['Re'] = [('re', .7, .15)]
BOLS['Ki'] = [('ke2', .6, .08)]
BOLS['Tu'] = BOLS['Tun']

# taal -> vibhags (lists of bols, one bol per matra); the first vibhag starts on sam.
# The khali vibhag is the one whose bols have no bayan (no Dh-/Ge).
TAALS = {
    'dadra':    [['Dha', 'Dhin', 'Na'], ['Dha', 'Tin', 'Na']],
    'kaharwa':  [['Dha', 'Ge', 'Na', 'Tin'], ['Na', 'Ke', 'Dhin', 'Na']],
    'rupak':    [['Tin', 'Tin', 'Na'], ['Dhi', 'Na'], ['Dhi', 'Na']],
    'jhaptaal': [['Dhi', 'Na'], ['Dhi', 'Dhi', 'Na'], ['Ti', 'Na'], ['Dhi', 'Dhi', 'Na']],
    'teentaal': [['Dha', 'Dhin', 'Dhin', 'Dha'], ['Dha', 'Dhin', 'Dhin', 'Dha'],
                 ['Dha', 'Tin', 'Tin', 'Ta'], ['Ta', 'Dhin', 'Dhin', 'Dha']],
}
# Khemta: the light 6-matra (3 + 3) taal of Bengali folk and theatre songs, played with the Dadra theka
TAALS['khemta'] = TAALS['dadra']
# Ektaal (12 matras) as Rabindra Sangeet notation groups it, 3 + 3 + 3 + 3 (sam, 2, khali, 3).
# A bol written with dots is several strokes shared evenly inside one matra: Dha.Ge, Ti.Ra.Ki.Ta.
TAALS['ektaal'] = [['Dhin', 'Dhin', 'Dha.Ge'], ['Ti.Ra.Ki.Ta', 'Tu', 'Na'],
                   ['Kat', 'Ta', 'Dha.Ge'], ['Ti.Ra.Ki.Ta', 'Dhi', 'Na']]
ACCENT = {'sam': 1.0, 'vibhag': .85, 'other': .72}     # loudness of sam, other vibhag starts, the rest


def cycle(name):
    """bols of one cycle and the accent of each matra"""
    if name not in TAALS:
        raise SystemExit(f"unknown taal {name!r}; known: {', '.join(sorted(TAALS))}")
    bols, acc = [], []
    for vi, v in enumerate(TAALS[name]):
        for k, b in enumerate(v):
            bols.append(b)
            acc.append(ACCENT['sam'] if vi == 0 and k == 0 else ACCENT['vibhag'] if k == 0 else ACCENT['other'])
    return bols, acc


_cache = {}


def stroke(name, sr):
    if (name, sr) not in _cache:
        path = os.path.join(SAMPLES, f'tabla_{name}.flac')
        if not os.path.exists(path):
            raise SystemExit(f'tabla sample missing: {path} (see sources/sources.csv, src002164-src002189)')
        raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-f', 'f32le', '-ac', '1', '-ar', str(sr), '-'],
                             capture_output=True, check=True).stdout
        a = np.frombuffer(raw, np.float32).astype(np.float64)
        _cache[(name, sr)] = a / np.max(np.abs(a))
    return _cache[(name, sr)]


def bol_sound(bol, sr):
    parts = []
    for name, gain, length in BOLS[bol]:
        a = stroke(name, sr)[:int(length * sr)].copy()
        f = min(len(a), int(.05 * sr))
        a[-f:] *= np.linspace(1, 0, f)                      # damp the end
        parts.append(a * gain)
    out = np.zeros(max(len(p) for p in parts))
    for p in parts:
        out[:len(p)] += p
    return out


def theka(name, sr, sam, matra, start, end):
    """the theka from `start` to `end` (seconds), sam at time `sam`, one matra = `matra` seconds"""
    bols, acc = cycle(name)
    n = len(bols)
    first = int(np.ceil((start - sam) / matra - 1e-6))      # matra index (0 = that sam) of the first stroke
    last = int(np.ceil((end - sam) / matra - 1e-6))          # first matra at or after the end
    final = last + (-last) % n                                # the next sam: one Dha to close
    out = np.zeros(int((sam + final * matra + 2.0) * sr))
    events = [(k, bols[k % n], acc[k % n]) for k in range(first, last)] + [(final, 'Dha', ACCENT['sam'])]
    for k, bol, a in events:
        parts = bol.split('.')                                  # strokes shared inside one matra
        for j, b in enumerate(parts):
            i = int(round((sam + (k + j / len(parts)) * matra) * sr))
            s = bol_sound(b, sr) * (a if j == 0 else a * 0.8)
            out[i:i + len(s)] += s[:len(out) - i]
    return out
