#!/usr/bin/env python3
"""YouTube thumbnail (1280x720 PNG) in the series style of
data/raw_data/image/ekla_chalo_re_thumbnail.png: "KALIMBA TABS" in spaced capitals, a rule with five
hanging kalimba tines, and the song title in two lines on brushed brown wood.

    python scripts/ktab_to_video/make_thumbnail.py "Amra Sobai Raja" -o thumbnail.png
    python scripts/ktab_to_video/make_thumbnail.py "Purano Sei | Diner Kotha" -o thumbnail.png

The title is split into two lines where the line widths are closest (a tie gives the shorter
first line, as "Ekla / Chalo Re"); write " | " to choose the break yourself.
Geometry and colours were measured from the Ekla Chalo Re thumbnail. Fonts (SIL OFL, in
scripts/ktab_to_video/fonts/): Josefin Sans for "KALIMBA TABS", Crimson Pro Bold Italic for the
title. Rendered with headless Chrome (google-chrome or chromium).
"""
import argparse
import html
import os
import shutil
import subprocess
import tempfile

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
W, H = 1280, 720
TITLE_PX = 196       # title size: ascender to baseline 136 px, as the Ekla Chalo Re thumbnail
KT_DY = 2            # fine shift of "KALIMBA TABS" so its caps span y 78..156 as in the reference

PAGE = """<!doctype html><html><head><meta charset="utf-8"><style>
@font-face {{ font-family: Josefin; src: url("file://{fonts}/JosefinSans[wght].ttf"); font-weight: 100 700; }}
@font-face {{ font-family: Crimson; src: url("file://{fonts}/CrimsonPro-Italic[wght].ttf"); font-weight: 200 900; font-style: italic; }}
* {{ margin: 0; box-sizing: border-box; }}
html, body {{ width: {W}px; height: {H}px; overflow: hidden; background: url("file://{bg}"); }}
#kt {{ position: absolute; left: 0; width: {W}px; text-align: center; color: rgb(244,211,188);
  font: 500 104px Josefin; white-space: nowrap; }}
#rule {{ position: absolute; left: 360px; top: 208px; width: 560px; height: 6px; border-radius: 3px;
  background: rgb(244,211,188); }}
.tine {{ position: absolute; width: 6px; top: 210px; border-radius: 0 0 3px 3px; background: rgb(244,211,188); opacity: .82; }}
.title {{ position: absolute; left: 0; width: {W}px; text-align: center; white-space: nowrap;
  font: italic 700 {title_px}px/1 Crimson; color: rgb(243,236,222);
  text-shadow: 0 4px 10px rgba(40,15,5,.45), 0 1px 2px rgba(40,15,5,.35); }}
</style></head><body>
<div id="kt">KALIMBA TABS</div>
<div id="rule"></div>
{tines}
<div class="title" id="l1">{line1}</div>
<div class="title" id="l2">{line2}</div>
<script>
const KT_DY = {kt_dy}, TITLE_PX = {title_px};
document.fonts.ready.then(() => {{
  const cv = document.createElement('canvas').getContext('2d');
  // "KALIMBA TABS": cap height 78 px with its top at y 78, ink spanning x 201..1083
  const kt = document.getElementById('kt');
  cv.font = '500 100px Josefin';
  const size = 78 / (cv.measureText('K').actualBoundingBoxAscent / 100);
  cv.font = `500 ${{size}}px Josefin`;
  const text = 'KALIMBA TABS', m0 = cv.measureText(text);
  const ink = m0.actualBoundingBoxLeft + m0.actualBoundingBoxRight;
  const ls = (882 - ink) / (text.length - 1);
  kt.style.font = `500 ${{size}}px/${{size}}px Josefin`;
  kt.style.letterSpacing = ls + 'px'; kt.style.textIndent = ls + 'px';
  const mk = cv.measureText('K');
  const capTop = (size - (mk.fontBoundingBoxAscent + mk.fontBoundingBoxDescent)) / 2
                 + mk.fontBoundingBoxAscent - mk.actualBoundingBoxAscent;
  kt.style.top = (78 + KT_DY - capTop) + 'px';
  // title lines: ascender tops at y 304 and 484 (as "Ekla" / "Chalo Re"); shrink if too wide
  let ts = TITLE_PX;
  cv.font = `italic 700 ${{ts}}px Crimson`;
  const widest = Math.max(...['l1', 'l2'].map(id => cv.measureText(document.getElementById(id).textContent).width));
  if (widest > 1180) ts = ts * 1180 / widest;
  for (const [id, top] of [['l1', 304], ['l2', 484]]) {{
    const el = document.getElementById(id); el.style.fontSize = ts + 'px'; el.style.lineHeight = ts + 'px';
    cv.font = `italic 700 ${{ts}}px Crimson`;
    const t = cv.measureText('Ekl'), lead = (ts - (t.fontBoundingBoxAscent + t.fontBoundingBoxDescent)) / 2;
    const ascTop = lead + t.fontBoundingBoxAscent - t.actualBoundingBoxAscent;
    el.style.top = (top + (TITLE_PX - ts) * 0.4 - ascTop) + 'px';
  }}
}});
</script></body></html>"""


def wood(seed=3):
    """brushed brown wood: a warm glow just above the centre, darker edges, fine horizontal streaks"""
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:H, 0:W].astype(np.float64)
    r = np.sqrt(((x - 640) / 640) ** 2 + ((y - 350) / 390) ** 2)
    knots = [0, .5, .75, 1.0, 1.42]
    cols = np.array([(169, 109, 75), (158, 97, 67), (136, 74, 47), (104, 52, 29), (90, 44, 24)], float)
    img = np.stack([np.interp(r, knots, cols[:, c]) for c in range(3)], -1)
    # streaks: noise stretched along x (long box blur), a little smoothed across rows
    n = rng.standard_normal((H, W))
    k = 161
    n = np.cumsum(np.pad(n, ((0, 0), (k, 0)), mode='wrap'), 1)
    n = (n[:, k:] - n[:, :-k]) / np.sqrt(k)
    n = (n + np.roll(n, 1, 0) * .6 + np.roll(n, -1, 0) * .6) / 1.5
    n2 = rng.standard_normal((H, W))
    k2 = 15
    n2 = np.cumsum(np.pad(n2, ((0, 0), (k2, 0)), mode='wrap'), 1)
    n2 = (n2[:, k2:] - n2[:, :-k2]) / np.sqrt(k2)
    shade = 4.0 * n / n.std() + 2.0 * n2 / n2.std()
    img = img * (1 + shade[..., None] / 140)
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))


def split_title(title):
    if '|' in title:
        a, b = (s.strip() for s in title.split('|', 1))
        return a, b
    words = title.split()
    if len(words) == 1:
        return title, ''
    best = min(range(1, len(words)), key=lambda i: (abs(len(' '.join(words[:i])) - len(' '.join(words[i:]))),
                                                   len(' '.join(words[:i]))))
    return ' '.join(words[:best]), ' '.join(words[best:])


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('title', help='song title; " | " marks the line break')
    ap.add_argument('-o', '--out', default='thumbnail.png')
    a = ap.parse_args()
    chrome = next((c for c in ('google-chrome', 'chromium', 'chromium-browser') if shutil.which(c)), None)
    if not chrome:
        raise SystemExit('needs google-chrome or chromium on PATH')
    l1, l2 = split_title(a.title)
    tines = ''.join(f'<div class="tine" style="left:{593 + 22 * i}px;height:{h}px"></div>'
                    for i, h in enumerate((29, 37, 45, 37, 29)))     # bottoms at y 239, 247, 255
    with tempfile.TemporaryDirectory() as d:
        bg = os.path.join(d, 'wood.png')
        wood().save(bg)
        page = PAGE.format(fonts=os.path.join(HERE, 'fonts'), bg=bg, W=W, H=H, tines=tines,
                           line1=html.escape(l1), line2=html.escape(l2), kt_dy=KT_DY, title_px=TITLE_PX)
        src = os.path.join(d, 'thumb.html')
        open(src, 'w').write(page)
        subprocess.run([chrome, '--headless', '--disable-gpu', '--hide-scrollbars', '--allow-file-access-from-files',
                        '--force-device-scale-factor=1', '--virtual-time-budget=3000', f'--window-size={W},{H}',
                        f'--screenshot={os.path.abspath(a.out)}', 'file://' + src], check=True, capture_output=True)
    im = Image.open(a.out).convert('RGB')
    if im.size != (W, H) or min(im.getpixel((x, H - 4)) for x in (10, W // 2, W - 10)) > (250, 250, 250):
        raise SystemExit(f'{a.out}: the capture came out short (white at the bottom); run again')
    im.save(a.out)
    print('wrote', a.out, f'({l1} / {l2})')


if __name__ == '__main__':
    main()
