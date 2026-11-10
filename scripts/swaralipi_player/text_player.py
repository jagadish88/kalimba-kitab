#!/usr/bin/env python3
"""Swaralipi player from the swaralipi text alone: the notation is parsed, rendered as a page,
played, and a box follows the matra being played.

    python scripts/swaralipi_player/text_player.py rs002164
    python scripts/swaralipi_player/text_player.py rs002164 --matra 0.45 --sa 60

Input: data/intermediate_data/swaralipi/<song>.json, our transcription of the swaralipi (see
notation.py), made from SNLTR's Rabindra Rachanabali (rabindra-rachanabali.nltr.org). It is read back
into SNLTR's cell encoding, which the parser below works on (described here).
Output: data/intermediate_data/comparison/<song>_swaralipi_text.mp4 (git-ignored).

The encoding (from comparing with the printed swaralipi)
  s r g m k p q n   সা রা গা মা ক্ষা(tivra ma) পা ধা না
  v t d u           komal ঋ জ্ঞ দ ণ (re ga dha ni); a letter is followed by
  f / h             upper / lower octave (র্সা, ন্‌া)
  S R G ...         capitals: a grace note (kan) before the next swara; F / H its octave
  a                 closes the matra (the া); "-a" alone is a hold (-১)
  -                 at the start: the note continues the previous syllable
  i                 ঃ (ignored)
  l  ll  A  |       bar lines I, II, | ; "ll L" / "L" the end; w x y are marks (skipped)
  { } ( ) [ ]       repeat, first time only, an alternative (ignored)
A cell is one matra, shared equally by its swaras. A quoted lyric ("তু মি") at the end of a
section returns to the sthayi: its first line is sung (second-time path) before going on; at the
end of the song the whole repeated first section is sung (first and second time).
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import wave

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image, ImageDraw, ImageFont

SR = 44100
W, H, FPS = 1280, 720, 25
SEMI = dict(s=0, v=1, r=2, t=3, g=4, m=5, k=6, p=7, d=8, q=9, u=10, n=11)
BEN = dict(s='স', v='ঋ', r='র', t='জ্ঞ', g='গ', m='ম', k='ক্ষ', p='প', d='দ', q='ধ', u='ণ', n='ন')
BARS = {'l': 'I', 'll': 'II', 'A': '|', '|': '', 'll L': 'II', 'L': 'II', 'll ll': 'II II',
        'LL': 'II', 'L L': 'II', 'w': '', 'x': '', 'y': ''}   # w x y: marks at the start of a row, not notes
FONT = '/usr/share/fonts/google-noto-vf/NotoSansBengali[wght].ttf'
LATIN = '/usr/share/fonts/google-noto-vf/NotoSans[wght].ttf'          # for - | { } ( ) · :


def runs(text):
    """split text into runs of Bengali and of other characters (each drawn in its own font)"""
    out = []
    for ch in text:
        b = '\u0980' <= ch <= '\u09ff' or ch in '\u200c\u200d'
        if out and out[-1][0] == b: out[-1][1] += ch
        else: out.append([b, ch])
    return out


def tlen(d, text, fonts):
    return sum(d.textlength(t, font=fonts[b]) for b, t in runs(text))


def draw(d, xy, text, fonts, fill):
    x, y = xy
    for b, t in runs(text):
        d.text((x, y), t, font=fonts[b], fill=fill)
        x += d.textlength(t, font=fonts[b])


def parse_cell(c):
    """a matra cell -> dict(pre, post, cont, notes=[(semitones, octave, [grace (semitones, octave)])])"""
    c = c.replace(' ', '')
    if c.endswith('ah'):
        c = c[:-1]
    pre, post = [], []
    while c and c[0] in '{([':
        pre.append(c[0]); c = c[1:]
    while c and c[-1] in '})]':
        post.insert(0, c[-1]); c = c[:-1]
    cont = c.startswith('-')
    c = c.lstrip('-')
    notes, graces, i = [], [], 0
    while i < len(c):
        ch = c[i]
        if ch.lower() in SEMI and ch != 'a':
            octave = 0
            while i + 1 < len(c) and c[i + 1].lower() in 'fh':
                octave += 1 if c[i + 1].lower() == 'f' else -1
                i += 1
            if ch.islower():
                notes.append((SEMI[ch], octave, graces)); graces = []
            else:
                graces.append((SEMI[ch.lower()], octave))
        elif ch in 'ai':
            pass
        else:
            raise ValueError(f'unknown character {ch!r} in cell {c!r}')
        i += 1
    return dict(pre=pre, post=post, cont=cont, notes=notes)


def display(c):
    """a cell as Bengali notation text, and its grace notes as a small prefix"""
    if c in BARS:
        return BARS[c], ''
    head = ''.join(ch for ch in c if ch in '{([')
    tail = ''.join(ch for ch in c if ch in '})]')
    core = c.strip('{([})]')
    dash = '-' if core.startswith('-') else ''
    core = core.lstrip('-')
    main, grace, i = '', '', 0
    while i < len(core):
        ch = core[i]
        if ch.lower() in SEMI:
            o = 0
            while i + 1 < len(core) and core[i + 1].lower() in 'fh':
                o += 1 if core[i + 1].lower() == 'f' else -1
                i += 1
            g = BEN[ch.lower()]
            g = ('র্' + g) if o > 0 else (g + '্‌' if o < 0 else g)
            if ch.islower(): main += g
            else: grace += g
        i += 1
    body = (main + 'া') if main else '১'
    return head + dash + body + tail, grace


def is_swara_row(r):
    cells = [c for c in r if c]
    return bool(cells) and all(all(ord(ch) < 128 for ch in c) for c in cells)


def load(path):
    """(doc, [(swara cells, lyric cells)]): each swara row with the lyric row after it. `path` is our
    transcription (data/intermediate_data/swaralipi/<song>.json), read back into SNLTR's encoding."""
    import notation
    doc, rows = notation.load_snltr_rows(path)
    lines = []
    for k, r in enumerate(rows):
        if not is_swara_row(r) or any('[' in c for c in r):
            continue                             # a lyric row, or an alternative ([..])
        if all(c in ('', '|') or c in BARS for c in r):
            continue                             # only marks
        # the lyric row: the next row that is not a swara row, skipping rows of marks only
        # (<w> <x>: the ends of a slur under a melisma)
        lyr, j = [], k + 1
        while j < len(rows) and is_swara_row(rows[j]) and all(c in ('', '|') or c in BARS for c in rows[j]):
            j += 1
        if j < len(rows) and not is_swara_row(rows[j]):
            lyr = rows[j]
        lines.append((r, lyr))
    return doc, lines


def singing_order(lines):
    """[(line, col)] in singing order"""
    items = []
    for li, (sw, ly) in enumerate(lines):
        for ci, c in enumerate(sw):
            if not c or c in BARS:
                continue
            try:
                p = parse_cell(c)
            except ValueError as e:
                print('skipped:', e, file=sys.stderr); continue
            items += [x for x in p['pre'] if x in '{(']
            items.append((li, ci))
            items += [x for x in p['post'] if x in ')}']
        if any(x.startswith('"') or x.endswith('"') for x in ly):
            items.append('return')
    # the sthayi's first line, second-time path, for the returns
    first = items.index('{') if '{' in items else 0
    line1, skip, depth = [], 0, 0
    for it in items[first + 1:]:
        if it == '(':
            skip += 1
        elif it == ')':
            skip -= 1
        elif it == '}':
            break
        elif isinstance(it, tuple) and not skip:
            line1.append(it)
    order, opens = [], []
    for i, it in enumerate(items):
        if it == '{':
            opens.append(i)
        elif it == '}' and opens:
            s0 = opens.pop(); skip = 0
            for it2 in items[s0 + 1:i]:
                if it2 == '(': skip += 1
                elif it2 == ')': skip -= 1
                elif isinstance(it2, tuple) and not skip: order.append(it2)
        elif it == 'return':
            if i == len(items) - 1:              # the song's end: the whole repeated first section, both times
                s0 = items.index('{') if '{' in items else 0
                e0 = items.index('}', s0) if '}' in items[s0:] else len(items)
                body = items[s0 + 1:e0]
                order += [x for x in body if isinstance(x, tuple)]
                skip = 0
                for x in body:
                    if x == '(': skip += 1
                    elif x == ')': skip -= 1
                    elif isinstance(x, tuple) and not skip: order.append(x)
            else:
                order += line1
        elif isinstance(it, tuple):
            order.append(it)
    return order


def tone(midi, dur):
    f = 440.0 * 2 ** ((midi - 69) / 12)
    t = np.arange(int(SR * dur)) / SR
    y = sum(a * np.sin(2 * np.pi * f * h * t) for h, a in ((1, 1.0), (2, 0.45), (3, 0.2), (4, 0.1)))
    return y * np.exp(-t * 2.0) * np.minimum(1, t / 0.005) * np.minimum(1, (dur - t) / 0.03)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('song')
    ap.add_argument('--matra', type=float, default=0.5, help='seconds per matra (default 0.5)')
    ap.add_argument('--sa', type=int, default=60, help='Sa as a MIDI note (default 60 = C4)')
    a = ap.parse_args()
    doc, lines = load(f'data/intermediate_data/swaralipi/{a.song}.json')
    order = singing_order(lines)

    # notes in time: (start s, duration s, midi); a hold lengthens the note before it
    notes, cell_t = [], []
    t = 0.6
    for li, ci in order:
        p = parse_cell(lines[li][0][ci])
        cell_t.append((t, li, ci))
        if not p['notes']:
            if notes: notes[-1][1] += a.matra
        else:
            share = a.matra / len(p['notes'])
            for k, (semi, octv, graces) in enumerate(p['notes']):
                s0 = t + k * share
                gd = min(0.09, share * 0.25)
                for gi, (gs, go) in enumerate(graces):
                    notes.append([s0, gd, a.sa + gs + 12 * go])
                    s0 += gd
                notes.append([s0, t + (k + 1) * share - s0, a.sa + semi + 12 * octv])
        t += a.matra
    total = t + 1.5
    y = np.zeros(int(total * SR) + SR)
    for s0, d, m in notes:
        tt = tone(m, max(0.08, d) + 0.15)
        k = int(s0 * SR); y[k:k + len(tt)] += tt
    y *= 0.6 / max(1e-9, np.abs(y).max())

    # the page: a grid like the original table, swara row over lyric row
    def fonts(size):
        f = {True: ImageFont.truetype(FONT, size), False: ImageFont.truetype(LATIN, size)}
        for v in f.values():
            try: v.set_variation_by_axes([600])
            except Exception: pass
        return f
    fs, fl, fg = fonts(30), fonts(22), fonts(15)
    ncol = max(len(sw) for sw, _ in lines)
    colw = [24] * ncol
    tmp_img = ImageDraw.Draw(Image.new('RGB', (10, 10)))
    for sw, ly in lines:
        for ci in range(ncol):
            c = sw[ci] if ci < len(sw) else ''
            l = ly[ci] if ci < len(ly) else ''
            txt, gr = display(c) if c else ('', '')
            w = max(tlen(tmp_img, txt, fs) + tlen(tmp_img, gr, fg), tlen(tmp_img, l.replace('৹', '·'), fl))
            colw[ci] = max(colw[ci], int(w) + 18)
    xs = np.concatenate([[40], 40 + np.cumsum(colw)])
    page_w = int(xs[-1] + 40)
    line_h = 112
    page = Image.new('RGB', (page_w, 80 + line_h * len(lines) + 200), (250, 247, 238))
    d = ImageDraw.Draw(page)
    draw(d, (40, 20), f"{doc['title']}   ·   তাল {doc.get('tala', '')}", fl, (90, 70, 50))
    boxes = {}
    for li, (sw, ly) in enumerate(lines):
        y0 = 80 + li * line_h
        for ci in range(ncol):
            c = sw[ci] if ci < len(sw) else ''
            l = ly[ci] if ci < len(ly) else ''
            x0, x1 = xs[ci], xs[ci + 1]
            if c:
                txt, gr = display(c)
                tw = tlen(d, txt, fs) + tlen(d, gr, fg)
                xx = (x0 + x1 - tw) / 2
                if gr:
                    draw(d, (xx, y0 - 2), gr, fg, (60, 60, 60)); xx += tlen(d, gr, fg)
                draw(d, (xx, y0 + 8), txt, fs, (20, 20, 20))
                if c not in BARS:
                    boxes[(li, ci)] = (x0 + 3, y0, x1 - 3, y0 + 92)
            if l:
                l2 = l.replace('৹', '·')
                draw(d, ((x0 + x1 - tlen(d, l2, fl)) / 2, y0 + 52), l2, fl, (70, 70, 140))

    with tempfile.TemporaryDirectory() as tmp:
        wav = os.path.join(tmp, 'a.wav')
        with wave.open(wav, 'wb') as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
            w.writeframes((y * 32767).astype(np.int16).tobytes())
        scale = min(1.0, W / page.width)
        win = int(H / scale)
        out = f'data/intermediate_data/comparison/{a.song}_swaralipi_text.mp4'
        ff = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}',
                               '-r', str(FPS), '-i', '-', '-i', wav, '-c:v', 'libx264', '-preset', 'veryfast',
                               '-crf', '23', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest', out],
                              stdin=subprocess.PIPE)
        starts = np.array([c[0] for c in cell_t])
        top = 0.0
        for f in range(int(total * FPS)):
            tt = f / FPS
            k = max(0, int(np.searchsorted(starts, tt, side='right')) - 1)
            _, li, ci = cell_t[k]
            x0, y0, x1, y1 = boxes[(li, ci)]
            want = float(np.clip(y0 - win / 3, 0, max(0, page.height - win)))
            top += (want - top) * 0.15                                # smooth scrolling
            frame = page.crop((0, int(top), page.width, int(top) + win)).copy()
            dd = ImageDraw.Draw(frame, 'RGBA')
            dd.rectangle((x0, y0 - int(top), x1, y1 - int(top)), fill=(255, 200, 0, 80), outline=(220, 120, 0, 255), width=3)
            fr = frame.resize((int(frame.width * scale), H))
            canvas = Image.new('RGB', (W, H), (250, 247, 238)); canvas.paste(fr, ((W - fr.width) // 2, 0))
            ff.stdin.write(np.asarray(canvas).tobytes())
        ff.stdin.close(); ff.wait()
    print(f'{len(lines)} lines, {len(order)} matras sung, {len(notes)} notes, {total:.0f} s -> {out}')


if __name__ == '__main__':
    main()
