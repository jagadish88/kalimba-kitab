"""Paper background (1920x1080) with a faint line-art figure on the right, multiplied into the
grain, e.g. a dancer for a dance song. The lines are thinned (MaxFilter) and drawn in a warm brown.

    python3 figure_paper.py paper.png figure.png out.png [opacity .16] [thin 3] [height 860] [right margin 40] [top: 'c' = centred] [ink: 'sat']

ink 'sat': coloured lines on a grey/white ground (e.g. a fake transparency checkerboard baked into the
pixels): the ink is taken from the colour saturation, so the grey ground drops out.

then: kalimba_video.py tab.ktab out.png ...
Mamo Chitte (approved 2026-11-20): dancing_girl.png .35 3 602 135 c
Mayabano Biharini: forest.png .35 1 602 135 c sat"""
import sys, numpy as np
from PIL import Image, ImageFilter, ImageOps
paper, fig, out = sys.argv[1:4]
op = float(sys.argv[4]) if len(sys.argv) > 4 else .16
thin = int(sys.argv[5]) if len(sys.argv) > 5 else 3
hgt = int(sys.argv[6]) if len(sys.argv) > 6 else 860
right = int(sys.argv[7]) if len(sys.argv) > 7 else 40         # px from the right edge
top = sys.argv[8] if len(sys.argv) > 8 else ''                  # 'c' centres it heightwise
sat = len(sys.argv) > 9 and sys.argv[9] == 'sat'
W, H = 1920, 1080
src = Image.open(paper).convert("RGB")
sc = max(W / src.width, H / src.height)
big = src.resize((round(src.width*sc), round(src.height*sc)), Image.LANCZOS)
l, t = (big.width - W)//2, (big.height - H)//2
pap = np.asarray(big.crop((l, t, l+W, t+H))).astype(np.float32)
if sat:
    rgb = np.asarray(Image.open(fig).convert("RGB")).astype(np.float32)
    s_ = rgb.max(2) - rgb.min(2)                             # saturation: the coloured lines
    g = Image.fromarray((255 - np.clip((s_ - 25) / 85, 0, 1) * 255).astype(np.uint8))
else:
    g = Image.open(fig).convert("L")
if thin > 1:
    g = g.filter(ImageFilter.MaxFilter(thin))          # lighten = thinner dark lines
ink = 255 - np.asarray(g).astype(np.float32)
ys, xs = np.where(ink > 40)
g = g.crop((max(xs.min()-10, 0), max(ys.min()-10, 0), min(xs.max()+10, g.width), min(ys.max()+10, g.height)))  # inside the image: a crop past the edge pads black = ink
w = round(g.width * hgt / g.height)
g = g.resize((w, hgt), Image.LANCZOS)
a = (255 - np.asarray(g).astype(np.float32)) / 255 * op   # line darkness -> alpha
x0 = W - w - right
y0 = (H - hgt) // 2 if top == 'c' else int(top) if top else H - hgt - 70
col = np.array([92, 58, 36], np.float32)                    # warm brown ink
reg = pap[y0:y0+hgt, x0:x0+w]
pap[y0:y0+hgt, x0:x0+w] = reg * (1 - a[..., None]) + (reg * col / 255) * a[..., None]
Image.fromarray(np.clip(pap, 0, 255).astype(np.uint8)).save(out)
print('figure', w, 'x', hgt, 'at', x0, y0)
