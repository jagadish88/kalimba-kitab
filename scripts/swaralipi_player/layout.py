"""Swaralipi pages (rendered at 130 dpi): matras, bar lines, holds, syllable starts, { } repeats and ( ) first-time parts."""
import numpy as np
from PIL import Image

def lines_of(dark):
    on = dark.sum(1) > 3; L = []; y = 0
    while y < len(on):
        if on[y]:
            s = y
            while y < len(on) and on[y]: y += 1
            if y - s > 4: L.append((s, y))
        else: y += 1
    return L

def tokens_of(dark, y0, y1):
    top = dark[y0:y0 + 18].any(0); xs = []; x = 0
    while x < len(top):
        if top[x]:
            s = x; last = x
            while x < len(top) and (top[x] or x - last <= 6):
                if top[x]: last = x
                x += 1
            ys = np.flatnonzero(dark[y0 - 8:y1 + 10, s:last + 1].any(1))
            h = ys.max() - ys.min() + 1 if len(ys) else 0
            xs.append(dict(x0=s, x1=last, w=last - s + 1, h=h))
        else: x += 1
    out = []
    for t in xs:                                 # a lone dash joins the stroke after it: "-।" (a hold)
        if out and out[-1]['h'] < 10 and out[-1]['w'] >= 5 and t['x0'] - out[-1]['x1'] <= 14:
            d = out.pop()
            t = dict(x0=d['x0'], x1=t['x1'], w=t['x1'] - d['x0'] + 1, h=t['h'])
        out.append(t)
    return [t for t in out if t['h'] >= 10]


def shape(dark, t, y0, y1):
    """'bar' (a straight stroke: I | ।, or a double bar II), 'curve' ({ ( ) }), or None (a matra)"""
    sub = dark[y0 - 8:y1 + 10, t['x0']:t['x1'] + 1]
    rows = [np.flatnonzero(r) for r in sub if r.any()]
    if t['h'] < 12 or not rows:
        return None
    colh = sub.sum(0)
    tall = colh >= 0.7 * t['h']
    runs, x = [], 0
    while x < len(tall):                         # runs of nearly full-height columns
        if tall[x]:
            s0 = x
            while x < len(tall) and tall[x]: x += 1
            runs.append((s0, x))
        else: x += 1
    if t['w'] <= 22 and len(runs) == 2 and all(e - s0 <= 5 for s0, e in runs) and \
            sum(colh[s0:e].sum() for s0, e in runs) >= 0.6 * colh.sum():
        return 'bar'                                                  # II
    if t['w'] > 11:
        return None
    c = np.array([r.mean() for r in rows])
    n = len(c); e = max(2, n // 6)
    ends = (c[:e].mean() + c[-e:].mean()) / 2
    same_side = np.sign(c[:e].mean() - c[n // 2]) == np.sign(c[-e:].mean() - c[n // 2])
    t['bend'] = abs(c[n // 3:n - n // 3].mean() - ends) if same_side else 0.0
    if (t['bend'] >= 1.5 and t['h'] >= 21) or (5 <= t['w'] <= 9 and t['h'] >= 22 and t['bend'] >= 0.5):
        return 'curve'
    if c.max() - c.min() <= 3.5 and (t['w'] <= 6 or len(runs) == 1):
        return 'bar'
    return None


def page_rows(path):
    """swara rows: [(y0, y1, [matra boxes], [events])]; events: ('open'|'close', index of the matra
    after it). A swara row is a text line with at least three bar lines."""
    dark = np.asarray(Image.open(path).convert('L')) < 110
    lines = []
    for y0, y1 in lines_of(dark):
        tk = tokens_of(dark, y0, y1)
        kinds = [shape(dark, t, y0, y1) for t in tk]
        if kinds.count('bar') >= 3:
            lines.append((y0, y1, tk, kinds))
    # Some pages draw { } ( ) nearly straight: a thin stroke much taller than the page's thin bar
    # lines (।, |) is a curve.
    thin = sorted(t['h'] for _, _, tk, ks in lines for t, k in zip(tk, ks) if k == 'bar' and t['w'] <= 4)
    med = thin[len(thin) // 2] if thin else 99
    for _, _, tk, kinds in lines:
        for i, (t, k) in enumerate(zip(tk, kinds)):
            if k == 'bar' and t['w'] <= 6 and t['h'] >= 22 and t['h'] >= 1.3 * med:
                kinds[i] = 'curve'
    # a lone stroke that leaves a bar segment one matra short is a hold ("-।" with its dash apart)
    sizes = []
    for _, _, tk, kinds in lines:
        n = 0
        for k in kinds:
            if k == 'bar':
                if n: sizes.append(n)
                n = 0
            elif k is None:
                n += 1
    mode = max(set(sizes), key=sizes.count) if sizes else 4
    rows = []
    for y0, y1, tk, kinds in lines:
        n = 0
        for i, k in enumerate(kinds):
            if k == 'bar':
                t = tk[i]                        # "১" alone: thin, I-high, inside an unfinished segment
                if 1 <= n < mode and t['w'] <= 7 and 17 <= t['h'] <= 21 and \
                        (n == mode - 1 and i + 1 < len(kinds) and kinds[i + 1] == 'bar' or n < mode - 1):
                    kinds[i] = None; n += 1; continue
                n = 0
            elif k is None:
                n += 1
        matras, events = [], []
        for i, (t, k) in enumerate(zip(tk, kinds)):
            if k is None:
                matras.append((t['x0'], t['x1']))
            elif k == 'curve':                   # opens if a note follows it, closes if a bar line does
                nxt = next((kk for kk in kinds[i + 1:] if kk != 'curve'), 'bar')
                events.append(('open' if nxt is None else 'close', len(matras)))
        rows.append((y0, y1, matras, events))
    return rows


def singing_order(rows_by_page):
    """[(page, row, matra)] in singing order. A curve that opens while a { } section is open is a
    '(' (sung the first time only); otherwise '{'. A curve that closes an open '(' is ')', else '}'.
    { ... } is sung twice; the second time its ( ... ) parts are left out."""
    items, braces, parens = [], 0, 0
    for p, rows in enumerate(rows_by_page):
        for r, row in enumerate(rows):
            ev = sorted(row['ev'], key=lambda e: e[1])
            k = 0
            for m in range(len(row['boxes']) + 1):
                while k < len(ev) and ev[k][1] == m:
                    kind = ev[k][0]
                    if kind == 'open':
                        if braces and not parens: items.append('('); parens += 1
                        else: items.append('{'); braces += 1
                    else:
                        if parens: items.append(')'); parens -= 1
                        elif braces: items.append('}'); braces -= 1
                    k += 1
                if m < len(row['boxes']):
                    items.append((p, r, m))
    order, opens = [], []
    for i, it in enumerate(items):
        if it == '{':
            opens.append(i)
        elif it == '}' and opens:
            s0 = opens.pop(); skip = 0
            for it2 in items[s0 + 1:i]:                  # the second time through
                if it2 == '(': skip += 1
                elif it2 == ')': skip -= 1
                elif isinstance(it2, tuple) and not skip: order.append(it2)
        elif isinstance(it, tuple):
            order.append(it)
    return order


def page_layout(path):
    """swara rows with, for each matra, its box, whether a syllable starts under it, and whether it is a hold"""
    dark = np.asarray(Image.open(path).convert('L')) < 110
    rows = page_rows(path)
    ys = [r[0] for r in rows] + [dark.shape[0]]
    out = []
    for k, (y0, y1, boxes, ev) in enumerate(rows):
        # lyric tokens: everything between this swara row's bottom and the next swara row
        ly0, ly1 = y1 + 2, ys[k + 1] - 4
        band = dark[ly0:ly1]
        colon = band.any(0); toks = []; x = 0
        while x < len(colon):
            if colon[x]:
                s = x; last = x
                while x < len(colon) and (colon[x] or x - last <= 4):
                    if colon[x]: last = x
                    x += 1
                yy = np.flatnonzero(band[:, s:last + 1].any(1))
                toks.append((s, last, yy.max() - yy.min() + 1 if len(yy) else 0))
            else: x += 1
        syl = [False] * len(boxes)
        for s, e, h in toks:
            if h < 12 or e - s + 1 < 6:
                continue                                              # a placeholder dot or a stray mark
            c = (s + e) / 2
            j = min(range(len(boxes)), key=lambda j: abs((boxes[j][0] + boxes[j][1]) / 2 - c))
            if abs((boxes[j][0] + boxes[j][1]) / 2 - c) < 30:
                syl[j] = True
        hold = []
        for x0, x1 in boxes:                     # "-।": a short dash, then one tall thin stroke on the right
            colh = dark[y0 - 2:y0 + 24, x0:x1 + 1].sum(0)
            tall = np.flatnonzero(colh >= 12)
            hold.append(bool((x1 - x0 + 1) <= 18 and len(tall) and tall.max() - tall.min() <= 5
                             and tall.min() >= (x1 - x0) * 0.45))
        out.append(dict(y0=y0, y1=y1, boxes=boxes, syl=syl, hold=hold, ev=ev))
    return out
