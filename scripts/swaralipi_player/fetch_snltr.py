#!/usr/bin/env python3
"""Download every song swaralipi from SNLTR's Rabindra Rachanabali as text (no browser needed).

    python scripts/swaralipi_player/fetch_snltr.py index     # crawl the song pages -> snltr_index.csv
    python scripts/swaralipi_player/fetch_snltr.py notation  # fetch each song's notation table -> <node>.json

The songs section (node 6585, "গান (স্বরলিপি সহ)") links to its categories (পূজা, প্রেম, ...); a
category page links to its sub-sections and songs; a song page that has a swaralipi links to
/node/16053?gaan=<title>.xml, whose page holds the notation table as plain HTML (cells with
id=row.col). The table is saved row by row, empty rows dropped, trailing empty cells trimmed and
runs of spaces collapsed - the same as the rows saved earlier through the browser.

Everything goes to data/raw_data/swaralipi_text/snltr/ (git-ignored: SNLTR does not allow
re-hosting). Requests are one at a time with a pause; pages already saved are skipped, so the
script can be stopped and restarted.
"""
import csv
import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

BASE = 'https://rabindra-rachanabali.nltr.org'
OUT = 'data/raw_data/swaralipi_text/snltr'
START = [6594, 6598, 6599, 8871, 6601, 6603, 6604, 6605, 6606, 6610, 6614, 6619]
EXTRA = ['/node/4?subcatid=13&catId=2', '/node/4?subcatid=15&catId=2']
MENU = {2, 3, 9, 6582, 6583, 6584, 6585, 8347, 10609, 14752, 15185, 16054, 16140, 16141, 16171, 16433, 3619, 6624}
PAUSE = 0.4


def get(path):
    url = path if path.startswith('http') else BASE + urllib.parse.quote(path, safe='/?=&%')
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=60) as r:
                time.sleep(PAUSE)
                return r.read().decode('utf-8', 'replace')
        except Exception as e:
            print('  retry', path, e, file=sys.stderr)
            time.sleep(5 * (attempt + 1))
    return ''


def title_of(t):
    m = re.search(r'<title>(.*?)</title>', t, re.S)
    return m.group(1).split('|')[0].strip() if m else ''


def crawl():
    os.makedirs(OUT, exist_ok=True)
    seen, queue, songs = set(), [f'/node/{n}' for n in START] + EXTRA, {}
    while queue:
        p = queue.pop(0)
        if p in seen:
            continue
        seen.add(p)
        t = get(p)
        if not t:
            continue
        g = re.findall(r'16053\?gaan=([^"\'<>]+?\.xml)', t)
        if g:
            songs[p] = (title_of(t), urllib.parse.unquote(g[0]))
        for n in re.findall(r'href=["\']?/node/(\d+)["\' >]', t):
            if int(n) not in MENU and f'/node/{n}' not in seen:
                queue.append(f'/node/{n}')
        for q in re.findall(r'href=["\']?(/node/4\?subcatid=\d+&(?:amp;)?catId=\d+)', t):
            queue.append(html.unescape(q))
        if len(seen) % 50 == 0:
            print(f'{len(seen)} pages, {len(songs)} with swaralipi, {len(queue)} queued', flush=True)
    with open(f'{OUT}/snltr_index.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['song_page', 'page_title', 'gaan'])
        for p, (ti, g) in sorted(songs.items()):
            w.writerow([p, ti, g])
    print(f'{len(seen)} pages crawled, {len(songs)} songs with a swaralipi -> {OUT}/snltr_index.csv')


def parse(t):
    rows = {}
    for m in re.finditer(r"<td[^>]*id=(\d+)\.(\d+)>\s*<span[^>]*>\s*<div[^>]*>(.*?)</div>", t, re.S):
        r, c = int(m.group(1)), int(m.group(2))
        v = re.sub(r'\s+', ' ', html.unescape(m.group(3)).replace('\xa0', ' ')).strip()
        rows.setdefault(r, {})[c] = v
    R = []
    for r in sorted(rows):
        x = [rows[r][c] for c in sorted(rows[r])]
        while x and x[-1] == '':
            x.pop()
        if x:
            R.append(x)
    head = {}
    for k, key in (('নাম', 'title'), ('তাল', 'tala'), ('আবর্তন', 'abartan')):
        m = re.search(k + r"\s*(?:<[^>]+>|\s)*:\s*(?:<[^>]+>|\s)*([^<]*)", t)
        head[key] = m.group(1).strip() if m else ''
    return head, R


def notation():
    rows = list(csv.DictReader(open(f'{OUT}/snltr_index.csv', encoding='utf-8')))
    done = 0
    for i, r in enumerate(rows):
        node = r['song_page'].rsplit('/', 1)[-1]
        path = f'{OUT}/{node}.json'
        if os.path.exists(path):
            continue
        src = f"/node/16053?gaan={r['gaan']}"
        t = get(src)
        head, R = parse(t)
        if not R:
            print('  no table', node, r['gaan'], file=sys.stderr)
            continue
        d = dict(head, page_title=r['page_title'], source=BASE + urllib.parse.quote(src, safe='/?='),
                 song_page=BASE + r['song_page'], publisher='SNLTR, Rabindra Rachanabali (not for re-hosting)',
                 accessed=time.strftime('%Y-%m-%d'), rows=R)
        json.dump(d, open(path, 'w', encoding='utf-8'), ensure_ascii=False)
        done += 1
        if done % 50 == 0:
            print(f'{i + 1}/{len(rows)} fetched', flush=True)
    print(f'notation tables saved: {done} new, {len(os.listdir(OUT)) - 1} in {OUT}')


if __name__ == '__main__':
    {'index': crawl, 'notation': notation}[sys.argv[1] if len(sys.argv) > 1 else 'index']()
