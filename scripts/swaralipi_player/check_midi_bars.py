"""python check_midi_bars.py song.abc song.bars : ABC notes vs the MIDI bars (midi_bars), and one lyric token per note in every bar"""
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
