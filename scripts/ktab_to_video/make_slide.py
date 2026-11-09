#!/usr/bin/env python3
"""Opening slide for a kalimba video (1920x1080 PNG), in the style of
data/raw_data/image/jana_gana_mana_slide.png: title, author and year on the left, a
"Kalimba tab notation" card (beats, tempo, scale, notes) on the right, on the paper texture.

    python scripts/ktab_to_video/make_slide.py "Eso Eso He Boishakh" --year 1927 --bpm 200 \
        --scale "Sa on F" -o eso_slide.png

Use the same paper for add_intro.py so the slide fades seamlessly into the video.
Rendered with headless Chrome (google-chrome or chromium on PATH); fonts are the TeX Gyre
files in scripts/ktab_to_video/fonts/.
"""
import argparse
import html
import os
import shutil
import subprocess
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))

PAGE = """<!doctype html><html><head><meta charset="utf-8"><style>
@font-face {{ font-family: Serif; src: url("file://{fonts}/texgyrepagella-italic.otf"); font-style: italic; }}
@font-face {{ font-family: Serif; src: url("file://{fonts}/texgyrepagella-bolditalic.otf"); font-style: italic; font-weight: bold; }}
@font-face {{ font-family: SerifB; src: local("TeX Gyre Pagella Bold"), local("TeXGyrePagella-Bold"), url("file://{fonts}/texgyrepagella-bold.otf"); }}
@font-face {{ font-family: Sans; src: url("file://{fonts}/texgyreheros-bold.otf"); font-weight: bold; }}
:root {{ --ink: #1f1c17; --soft: #6b645a; --accent: #c4552d; --rule: #d9d1c3; }}
* {{ margin: 0; box-sizing: border-box; }}
body {{ width: 1920px; height: 1080px; overflow: hidden; color: var(--ink);
  background: url("file://{paper}") center / cover; font-family: Serif; }}
.left {{ position: absolute; left: 136px; top: 340px; width: 820px; }}
h1 {{ font: italic bold 112px/1.05 Serif; letter-spacing: -1px; white-space: nowrap; }}
.rule {{ position: relative; height: 2px; background: var(--accent); margin: 44px 0 56px; width: 806px; }}
.rule::after {{ content: ""; position: absolute; left: 395px; top: -7px; width: 13px; height: 13px;
  background: var(--accent); transform: rotate(45deg); box-shadow: 0 0 0 9px transparent; }}
.by {{ font: italic 36px Serif; color: var(--soft); }}
.who {{ font: 58px SerifB, serif; font-weight: bold; margin-top: 18px; }}
.year {{ font: bold 44px Sans; color: var(--accent); letter-spacing: 9px; margin-top: 22px; }}
.card {{ position: absolute; left: 1145px; top: 200px; width: 638px; height: 680px;
  background: rgba(250, 247, 238, .72); border: 2px solid #e6dfd2; outline: 1px solid #ebe5d9;
  outline-offset: -12px; box-shadow: 0 10px 28px rgba(80, 60, 30, .12); padding: 48px 60px 0; }}
.cap {{ font: bold 26px Sans; letter-spacing: 5px; color: var(--accent); text-align: center; }}
.beats {{ display: flex; justify-content: space-between; margin: 28px 22px 0; text-align: center; }}
.beats b {{ display: block; font: bold 66px/1 Sans; margin-bottom: 44px; }}
.beats .u {{ text-decoration: underline; text-decoration-thickness: 6px; text-underline-offset: 14px; }}
.beats span {{ font: 30px SerifB; font-weight: normal; }}
hr {{ border: 0; border-top: 2px solid var(--rule); margin: 30px 0 30px; }}
.row {{ display: flex; gap: 0; }}
.row div {{ flex: 1; }}
.lab {{ font: bold 21px Sans; letter-spacing: 4px; color: var(--soft); }}
.val {{ font: bold 40px Sans; margin-top: 8px; }}
.notes {{ display: flex; justify-content: space-between; margin-top: 18px; width: 480px; text-align: center; }}
.notes b {{ display: block; font: bold 40px Sans; position: relative; }}
.notes i {{ display: block; font: 30px Sans; font-style: normal; color: var(--soft); margin-top: 12px; }}
.hi::before, .hi::after {{ content: ""; position: absolute; left: 50%; width: 8px; height: 8px; margin-left: -4px;
  border-radius: 50%; background: var(--ink); }}
.hi::before {{ top: -10px; }}
.hi::after {{ bottom: -12px; display: none; }}
</style></head><body>
<div class="left">
  <h1>{title}</h1>
  <div class="rule"></div>
  <div class="by">Written &amp; composed by</div>
  <div class="who">{author}</div>
  <div class="year">{year}</div>
</div>
<div class="card">
  <div class="cap">KALIMBA TAB NOTATION</div>
  <div class="beats">
    <div><b>3</b><span>One beat</span></div>
    <div><b class="u">3</b><span>Half beat</span></div>
    <div><b>&ndash;</b><span>Rest</span></div>
  </div>
  <hr>
  <div class="row"><div><div class="lab">TEMPO</div><div class="val">{bpm} BPM</div></div>
    <div><div class="lab">SCALE</div><div class="val">{scale}</div></div></div>
  <hr>
  <div class="lab">NOTES</div>
  <div class="notes">
    <div><b>1</b><i>C</i></div><div><b>2</b><i>D</i></div><div><b>3</b><i>E</i></div><div><b>4</b><i>F</i></div>
    <div><b>5</b><i>G</i></div><div><b>6</b><i>A</i></div><div><b>7</b><i>B</i></div>
    <div><b class="hi">1</b><i>C</i></div>
  </div>
</div>
<script>  // shrink the title until it fits on one line beside the card
document.fonts.ready.then(() => {{
  const h = document.querySelector('h1'); let px = 112;
  while (h.scrollWidth > 900 && px > 60) {{ px -= 2; h.style.fontSize = px + 'px'; }}
}});
</script>
</body></html>"""


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('title')
    ap.add_argument('--author', default='Rabindranath Tagore')
    ap.add_argument('--year', default='')
    ap.add_argument('--bpm', required=True)
    ap.add_argument('--scale', default='C Major')
    ap.add_argument('--paper', default=os.path.join(ROOT, 'data/raw_data/image/paper_texture_brown.png'))
    ap.add_argument('-o', '--out', default='slide.png')
    a = ap.parse_args()
    chrome = next((c for c in ('google-chrome', 'chromium', 'chromium-browser') if shutil.which(c)), None)
    if not chrome:
        raise SystemExit('needs google-chrome or chromium on PATH')
    page = PAGE.format(fonts=os.path.join(HERE, 'fonts'), paper=os.path.abspath(a.paper),
                       title=html.escape(a.title), author=html.escape(a.author), year=html.escape(str(a.year)),
                       bpm=html.escape(str(a.bpm)), scale=html.escape(a.scale))
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, 'slide.html')
        open(src, 'w').write(page)
        subprocess.run([chrome, '--headless', '--disable-gpu', '--hide-scrollbars', '--allow-file-access-from-files',
                        '--force-device-scale-factor=1', '--virtual-time-budget=3000', '--window-size=1920,1080',
                        f'--screenshot={os.path.abspath(a.out)}', 'file://' + src],
                       check=True, capture_output=True)
    print('wrote', a.out)


if __name__ == '__main__':
    main()
