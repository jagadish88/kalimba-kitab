#!/usr/bin/env python3
"""Opening slide for a kalimba video (1920x1080 PNG), in the style of
data/raw_data/image/ekla_chalo_re_intro_slide.png: title, author and year on the left, a
"Kalimba tab notation" card on the right (the symbols the tab uses, tempo, scale, the tines it
plays and how to retune them), on the paper texture.

    python scripts/ktab_to_video/make_slide.py --tab data/intermediate_data/ktab/rs000309/v3.ktab \
        "Amra Sobai Raja" --year 1910 --bpm 100 --scale "G Major" --taal dadra -o slide.png

With --tab, the card is read from the tab: the legend shows only the note lengths and signs it
uses (not the repeat signs), NOTES lists the tines it plays (lowest to highest), and an @retune header marks the retuned
tine in red and adds a "Tune ... up to ..." line. The notation is drawn with the same geometry
as kalimba_video.py (underlines, octave dots, dotted-note dot, hold dash, repeat signs).
Without --tab, the card shows one beat, half beat and rest, and the tines 1..1'.

Fonts: TeX Gyre Pagella (the lyrics' family) for the words, TeX Gyre Heros Bold for the digits
and labels, from scripts/ktab_to_video/fonts/. Use the same paper for add_intro.py so the slide
fades seamlessly into the video. Rendered with headless Chrome (google-chrome or chromium).
"""
import argparse
import html
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'src'))

INK, SOFT, ACCENT = '#1f1c17', '#6b645a', '#c4552d'
LETTERS = 'CDEFGAB'
DIGIT_W = 0.556          # width of a TeX Gyre Heros digit, x font size
CAP_H = 0.72             # height of its digits, x font size (kalimba_video.py: num_h)

PAGE = """<!doctype html><html><head><meta charset="utf-8"><style>
@font-face {{ font-family: Pagella; src: url("file://{fonts}/texgyrepagella-regular.otf"); }}
@font-face {{ font-family: Pagella; src: url("file://{fonts}/texgyrepagella-bold.otf"); font-weight: bold; }}
@font-face {{ font-family: Pagella; src: url("file://{fonts}/texgyrepagella-italic.otf"); font-style: italic; }}
@font-face {{ font-family: Pagella; src: url("file://{fonts}/texgyrepagella-bolditalic.otf"); font-style: italic; font-weight: bold; }}
@font-face {{ font-family: Heros; src: url("file://{fonts}/texgyreheros-regular.otf"); }}
@font-face {{ font-family: Heros; src: url("file://{fonts}/texgyreheros-bold.otf"); font-weight: bold; }}
:root {{ --ink: {ink}; --soft: {soft}; --accent: {accent}; --rule: #ddd5c7; }}
* {{ margin: 0; box-sizing: border-box; }}
html {{ background: url("file://{paper}") center / cover; }}
body {{ width: 1920px; height: 1080px; overflow: hidden; color: var(--ink);
  background: url("file://{paper}") center / cover; font-family: Pagella; }}
.left {{ position: absolute; left: 136px; top: 0; bottom: 0; width: 820px;
  display: flex; flex-direction: column; justify-content: center; padding-bottom: 40px; }}
h1 {{ font: italic bold 112px/1.1 Pagella; letter-spacing: -1px; white-space: nowrap; width: max-content; }}
.rule {{ position: relative; height: 2px; background: var(--accent); margin: 40px 0 52px; width: {rule_w}px; }}
.rule::after {{ content: ""; position: absolute; left: 50%; top: -6px; width: 13px; height: 13px;
  margin-left: -6.5px; background: var(--accent); transform: rotate(45deg); }}
.by {{ font: italic 36px Pagella; color: var(--soft); }}
.who {{ font: bold 58px Pagella; margin-top: 14px; }}
.year {{ font: bold 44px Heros; color: var(--accent); letter-spacing: 9px; margin-top: 22px; }}
.wrap {{ position: absolute; right: 120px; top: 0; bottom: 0; display: flex; align-items: center; }}
.card {{ width: {card_w}px; background: rgba(250, 247, 238, .72); border: 2px solid #e6dfd2;
  outline: 1px solid #ebe5d9; outline-offset: -12px; box-shadow: 0 10px 28px rgba(80, 60, 30, .12);
  padding: 50px 58px 54px; }}
.cap {{ font: bold 26px Heros; letter-spacing: 5px; color: var(--accent); text-align: center; }}
.legend {{ display: flex; justify-content: space-between; margin-top: 30px; text-align: center; }}
.legend > div {{ width: {col_w}px; }}
.legend svg {{ display: block; margin: 0 auto 14px; overflow: visible; }}
.legend span {{ display: block; font: 29px/1.12 Pagella; }}
hr {{ border: 0; border-top: 2px solid var(--rule); margin: 34px 0 30px; }}
.row {{ display: flex; justify-content: space-between; gap: 40px; }}
.row > div {{ flex: none; }}
.row.two > div {{ flex: 1; }}
.lab {{ font: bold 21px Heros; letter-spacing: 4px; color: var(--soft); }}
.val {{ font: bold 40px Heros; margin-top: 8px; white-space: nowrap; }}
.sub {{ font: italic 26px Pagella; color: var(--soft); margin-top: 6px; white-space: nowrap; }}
.notes {{ display: flex; justify-content: space-between; margin-top: 16px; }}
.notes > div {{ width: {note_col}px; display: flex; flex-direction: column; align-items: center; }}
.notes > div:first-child {{ align-items: flex-start; }}
.notes > div:last-child {{ align-items: flex-end; }}
.notes svg {{ display: block; margin: 0 auto; overflow: visible; }}
.notes i {{ display: block; font: 30px Heros; font-style: normal; color: var(--soft); margin-top: 12px; }}
.notes i.re {{ color: var(--accent); font-weight: bold; position: relative; }}
.notes i.re sup {{ position: absolute; left: 100%; top: -.2em; }}
sup {{ font-size: 62%; vertical-align: 0; position: relative; top: -.62em; margin-left: 1px; }}
sub {{ font-size: 62%; vertical-align: 0; position: relative; top: .3em; }}
.tune {{ font: italic 30px Pagella; margin-top: 26px; color: var(--ink); }}
.tune b {{ font: bold 28px Heros; color: var(--accent); font-style: normal; }}
.tune b.k {{ color: var(--ink); }}
.tune .ti {{ white-space: nowrap; }}
.tune .sep {{ margin: 0 4px; color: var(--soft); }}
.tune {{ line-height: 1.5; }}
</style></head><body>
<div class="left">
  <h1>{title}</h1>
  <div class="rule"></div>
  <div class="by">Written &amp; composed by</div>
  <div class="who">{author}</div>
  <div class="year">{year}</div>
</div>
<div class="wrap"><div class="card">
  <div class="cap">KALIMBA TAB NOTATION</div>
  <div class="legend">{legend}</div>
  <hr>
  <div class="row{row_cls}"><div><div class="lab">TEMPO</div><div class="val">{bpm} BPM</div></div>
    <div><div class="lab">SCALE</div><div class="val">{scale}</div>{scale_sub}</div>{taal}</div>
  <hr>
  <div class="lab">NOTES</div>
  <div class="notes">{notes}</div>
  {tune}
</div></div>
<script>  // shrink the title until it fits on one line beside the card
document.fonts.ready.then(() => {{
  const h = document.querySelector('h1'); let px = 112;
  while (h.scrollWidth > {title_max} && px > 60) {{ px -= 2; h.style.fontSize = px + 'px'; }}
  document.querySelector('.rule').style.width = Math.max({rule_w}, h.scrollWidth) + 'px';
}});
</script>
</body></html>"""


def note_svg(S, deg='3', octave=0, slashes=0, dotted=False, dashes=0, top=1, low=0, uls=2, ink=INK, min_r=0):
    """One tab note drawn as in kalimba_video.py, at font size S.
    top / uls: room kept for octave dots above / underlines below, so a row of notes shares a baseline."""
    r = max(0.045 * S, min_r)         # min_r: keeps octave dots visible at small sizes
    ul_w = max(2, 0.045 * S)
    ul_step = ul_w + max(3, 0.075 * S)
    dw = DIGIT_W * S
    y0 = (0.15 + 0.13 * (top - 1)) * S + 2 * r + 2 if top else 0      # space for the dots above
    base = y0 + CAP_H * S                                              # digits' baseline
    y_ul = base + 0.16 * S
    h = y_ul + (uls * ul_step if uls else 0) + low * 0.13 * S
    parts, x = [], 0.0
    if deg is not None:
        parts.append(f'<text x="{x + dw / 2:.1f}" y="{base:.1f}" text-anchor="middle" '
                     f'font-family="Heros" font-weight="bold" font-size="{S}" fill="{ink}">{deg}</text>')
        cx = x + dw / 2
        for k in range(octave):
            cy = base - CAP_H * S - (0.15 + 0.13 * k) * S - (r - 0.045 * S)
            parts.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{ink}"/>')
        for k in range(-octave):
            cy = y_ul + slashes * ul_step + (0.10 + 0.13 * k) * S
            parts.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{ink}"/>')
        for k in range(slashes):
            yb = y_ul + k * ul_step
            parts.append(f'<rect x="{x - 0.04 * S:.1f}" y="{yb:.1f}" width="{dw + 0.08 * S:.1f}" '
                         f'height="{ul_w:.1f}" fill="{INK}"/>')
        x += dw
        if dotted:
            dx = x + 0.10 * S
            parts.append(f'<circle cx="{dx:.1f}" cy="{base - r:.1f}" r="{r:.1f}" fill="{INK}"/>')
            x += 0.16 * S + 2 * r
    for k in range(dashes):              # as kalimba_video.py: a note's pitch is 0.95 S, a dash 0.78 S
        x = (0.95 * S if deg is not None else 0) + 0.78 * S * k
        y = base - CAP_H * S * 0.45
        parts.append(f'<line x1="{x + dw * 0.15:.1f}" y1="{y:.1f}" x2="{x + dw * 0.85:.1f}" y2="{y:.1f}" '
                     f'stroke="{INK}" stroke-width="{max(2, 0.04 * S):.1f}"/>')
        x += dw
    return f'<svg width="{x:.1f}" height="{h:.1f}" viewBox="0 0 {x:.1f} {h:.1f}">{"".join(parts)}</svg>'


def repeat_svg(S, stanza, top=1, uls=2):
    """:|  or  :||  as in kalimba_video.py (dots, thin bar, thick bar), as tall as the digits."""
    r, thin, thick, gap = ((0.055, 0.070, 0.20, 0.10) if stanza else (0.045, 0.040, 0.14, 0.09))
    r, thin, thick, gap = (v * S for v in (r, thin, thick, gap))
    ul_w = max(2, 0.045 * S)
    y0 = (0.15 + 0.13 * (top - 1)) * S + 2 * 0.045 * S + 2 if top else 0     # as note_svg
    hd = CAP_H * S
    h = y0 + hd + 0.16 * S + uls * (ul_w + max(3, 0.075 * S))
    w = 2 * r + gap + thin + gap + thick
    p = [f'<circle cx="{r:.1f}" cy="{y0 + hd * f:.1f}" r="{r:.1f}" fill="{INK}"/>' for f in (0.32, 0.68)]
    x = 2 * r + gap
    p.append(f'<rect x="{x:.1f}" y="{y0:.1f}" width="{thin:.1f}" height="{hd:.1f}" fill="{INK}"/>')
    x += thin + gap
    p.append(f'<rect x="{x:.1f}" y="{y0:.1f}" width="{thick:.1f}" height="{hd:.1f}" fill="{INK}"/>')
    return f'<svg width="{w:.1f}" height="{h:.1f}" viewBox="0 0 {w:.1f} {h:.1f}">{"".join(p)}</svg>'


def pitch_name(deg, octave):
    """tine 1 = C4: (4, 1) -> ('F', 5)"""
    return LETTERS[deg - 1], 4 + octave


def note_html(letter, octave=None, sub=True):
    """'F#' , 5 -> F<sup>♯</sup><sub>5</sub>"""
    s = html.escape(letter[0])
    if letter[1:] == '#':
        s += '<sup>&#9839;</sup>'
    elif letter[1:] == 'b':
        s += '<sup>&#9837;</sup>'
    if octave is not None and sub:
        s += f'<sub>{octave}</sub>'
    return s


def from_tab(path):
    """What the card needs from a tab: legend items, tines played, retunes."""
    import ktab
    song = ktab.parse_file(path)
    text = open(path, encoding='utf-8').read()
    body = '\n'.join(l for l in text.splitlines() if not l.startswith('@'))
    notes = list(song.notes())
    sl = {n.slashes for n in notes}
    S = 66
    legend = [(note_svg(S, '3'), 'One<br>beat')]
    if 1 in sl:
        legend.append((note_svg(S, '3', slashes=1), 'Half<br>beat'))
    if 2 in sl:
        legend.append((note_svg(S, '3', slashes=2), 'Quarter<br>beat'))
    if 3 in sl:
        legend.append((note_svg(S, '3', slashes=3), 'Eighth<br>beat'))
    if any(n.dotted for n in notes):
        legend.append((note_svg(S, '3', dotted=True), 'Dotted<br>&times;1&frac12;'))
    if any(n.dashes for n in notes) or re.search(r'\(\S*:[^)]*\s-[\s)]', body):
        legend.append((note_svg(S, None, dashes=1), 'Hold<br>+1 beat'))
    if any(n.degree == 0 for n in notes):
        legend.append((note_svg(S, '0'), 'Rest'))
    # repeat signs (:| :||) are left out: the user asked not to explain them on the slide
    tines = sorted({(n.octave, n.degree) for n in notes if n.degree})
    retune = {}
    for pair in (song.headers.get('retune') or '').split(','):
        if ':' in pair:
            a, b = (x.strip() for x in pair.split(':'))
            retune[a] = b
    return legend, [(d, o) for o, d in tines], retune


def default_card():
    S = 66
    legend = [(note_svg(S, '3'), 'One<br>beat'), (note_svg(S, '3', slashes=1), 'Half<br>beat'),
              (note_svg(S, None, dashes=1), 'Rest')]
    return legend, [(d, 0) for d in range(1, 8)] + [(1, 1)], {}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('title', nargs='?', help="song title (default: the tab's @title)")
    ap.add_argument('--tab', help='the .ktab file the card is read from')
    ap.add_argument('--author', default='Rabindranath Tagore')
    ap.add_argument('--year', default='')
    ap.add_argument('--bpm', required=True)
    ap.add_argument('--scale', default='C Major',
                    help='e.g. "G Major"; a | adds a smaller second line: "Kafi | Sa = G#"')
    ap.add_argument('--taal', help='taal of the tabla accompaniment (kalimba_video.py --taal), e.g. dadra')
    ap.add_argument('--paper', default=os.path.join(ROOT, 'data/raw_data/image/paper_texture_brown.png'))
    ap.add_argument('--html', help='also save the page here (for checking the layout)')
    ap.add_argument('-o', '--out', default='slide.png')
    a = ap.parse_args()
    chrome = next((c for c in ('google-chrome', 'chromium', 'chromium-browser') if shutil.which(c)), None)
    if not chrome:
        raise SystemExit('needs google-chrome or chromium on PATH')

    if a.tab:
        legend, tines, retune = from_tab(a.tab)
        if not a.title:
            import ktab
            a.title = ktab.parse_file(a.tab).headers.get('title', '')
    else:
        legend, tines, retune = default_card()
    if not a.title:
        raise SystemExit('give a title (or a tab with @title)')

    # NOTES: every tine the tab plays, its digit with octave dots, and the note it sounds
    S = 40
    top = max([1] + [o for _, o in tines])
    note_col = 24                     # a digit's width; the columns spread across the card
    cells, re_used = [], []
    for d, o in tines:
        letter, octv = pitch_name(d, o)
        new = retune.get(f'{letter}{octv}')
        if new:
            re_used.append((f'{letter}{octv}', new))
            lab = f'<i class="re">{note_html(new[:-1])}</i>'
        else:
            lab = f'<i>{letter}</i>'
        cells.append(f'<div>{note_svg(S, str(d), octave=max(o, 0), top=top, uls=0, min_r=3.6)}{lab}</div>')

    tune = ''
    if retune:
        bits = []
        for old, new in retune.items():
            bits.append(f'Tune <b>{note_html(old[:-1], old[-1])}</b> up to <b>{note_html(new[:-1], new[-1])}</b>'
                        if (LETTERS.index(new[0]) * 2 + (new[1:2] == '#')) >= LETTERS.index(old[0]) * 2
                        else f'Tune <b>{note_html(old[:-1], old[-1])}</b> down to <b>{note_html(new[:-1], new[-1])}</b>')
        # the other tines with the same letter stay as they are (a 17-tine kalimba, C4..E6)
        keep = sorted({f'{old[0]}{o}' for old in retune for o in (4, 5, 6)
                       if f'{old[0]}{o}' not in retune and (o < 6 or old[0] in 'CDE')})
        if len(retune) == 1:
            if keep:
                bits.append('keep ' + ', '.join(f'<b class="k">{note_html(k[0], k[1])}</b>' for k in keep))
            tune = '<div class="tune">' + ' &middot; '.join(bits) + '</div>'
        else:
            # several retunes: a compact list, no item split across lines; the NOTES row shows them in red
            items = [f'<span class="ti"><b>{note_html(o[:-1], o[-1])}</b> &rarr; <b>{note_html(n[:-1], n[-1])}</b></span>'
                     for o, n in retune.items()]
            tune = (f'<div class="tune">Retune {len(retune)} tines: '
                    + ' <span class="sep">&middot;</span> '.join(items) + '</div>')

    taal_html = ''
    if a.taal:
        import taal as T
        v = T.TAALS.get(a.taal.lower())
        if v is None:
            raise SystemExit(f"unknown taal {a.taal!r}; known: {', '.join(sorted(T.TAALS))}")
        parts = (' + ' if len(v) <= 2 else '+').join(str(len(x)) for x in v)   # 3 + 3, but 3+3+3+3
        taal_html = (f'<div><div class="lab">TAAL</div><div class="val">{html.escape(a.taal.title())}</div>'
                     f'<div class="sub">{sum(len(x) for x in v)} matras &middot; {parts}</div></div>')
    col_w = 126 if len(legend) >= 6 else 136 if len(legend) == 5 else 150
    card_w = max(760, 116 + len(tines) * 58, 116 + len(legend) * col_w)
    page = PAGE.format(
        fonts=os.path.join(HERE, 'fonts'), paper=os.path.abspath(a.paper), ink=INK, soft=SOFT, accent=ACCENT,
        title=html.escape(a.title), author=html.escape(a.author), year=html.escape(str(a.year)),
        bpm=html.escape(str(a.bpm)), scale=html.escape(a.scale.split('|')[0].strip()).replace('#', '<sup>&#9839;</sup>'),
        scale_sub=(f'<div class="sub">{html.escape(a.scale.split("|", 1)[1].strip()).replace("#", "&#9839;")}</div>'
                   if '|' in a.scale else ''),
        legend=''.join(f'<div>{svg}<span>{cap}</span></div>' for svg, cap in legend),
        notes=''.join(cells), n_notes=len(tines), note_col=note_col, tune=tune, taal=taal_html, row_cls='' if taal_html else ' two',
        card_w=card_w, col_w=col_w, title_max=1920 - 120 - card_w - 136 - 70, rule_w=646)
    if a.html:
        open(a.html, 'w').write(page)
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, 'slide.html')
        open(src, 'w').write(page)
        subprocess.run([chrome, '--headless', '--disable-gpu', '--hide-scrollbars', '--allow-file-access-from-files',
                        '--force-device-scale-factor=1', '--virtual-time-budget=3000', '--window-size=1920,1080',
                        f'--screenshot={os.path.abspath(a.out)}', 'file://' + src],
                       check=True, capture_output=True)
    from PIL import Image
    im = Image.open(a.out).convert('RGB')
    if im.size != (1920, 1080) or min(im.getpixel((x, 1075)) for x in (10, 960, 1910)) > (250, 250, 250):
        raise SystemExit(f'{a.out}: the capture came out short (white at the bottom); run again')
    print('wrote', a.out)


if __name__ == '__main__':
    main()
