#!/usr/bin/env python3
"""Download the third-party raw files that are not kept in git.

    python scripts/fetch_sources.py                 # fetch every missing file
    python scripts/fetch_sources.py --only midi     # just one folder (midi, swaralipi, text)
    python scripts/fetch_sources.py --dry-run       # list what would be fetched

Every row of sources/sources.csv whose local_path is in data/raw_data/midi,
data/raw_data/swaralipi or data/raw_data/text/lyrics is fetched from its url, unless
the file is already there. Files are saved as is, except the lyric .txt files: their
url is the Geetabitan lyric page, and the .txt is the "Transliteration in English"
block of that page.

Run from the repository root. Waits --delay seconds between requests (default 1).
"""
import argparse
import csv
import html
import re
import sys
import time
import urllib.request
from pathlib import Path

FOLDERS = {
    "midi": "data/raw_data/midi/",
    "swaralipi": "data/raw_data/swaralipi/",
    "text": "data/raw_data/text/lyrics/",
}
UA = {"User-Agent": "Mozilla/5.0 (kalimba-kitab fetch_sources)"}


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return r.read()


def lyric_text(page):
    """The transliteration from a Geetabitan lyric page: the <pre> inside <div id="copy">."""
    m = re.search(r'<div id="copy">\s*<pre[^>]*>(.*?)</pre>', page.decode("utf-8", "replace"), re.S)
    if not m:
        raise ValueError("no transliteration block on the page")
    text = html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip("\n")
    return ("\n".join(line.rstrip() for line in text.split("\n")) + "\n").encode("utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--only", choices=sorted(FOLDERS), action="append",
                    help="fetch only this folder (repeatable)")
    ap.add_argument("--dest", default=".", help="root to save under (default: current folder)")
    ap.add_argument("--delay", type=float, default=1.0, help="seconds between requests")
    ap.add_argument("--dry-run", action="store_true", help="list what would be fetched")
    a = ap.parse_args()

    prefixes = [FOLDERS[k] for k in (a.only or FOLDERS)]
    rows = [r for r in csv.DictReader(open("sources/sources.csv", encoding="utf-8"))
            if any(r["local_path"].startswith(p) for p in prefixes)]
    todo = [r for r in rows if not (Path(a.dest) / r["local_path"]).exists()]
    print(f"{len(rows)} files listed, {len(rows) - len(todo)} present, {len(todo)} to fetch",
          file=sys.stderr)

    failed = 0
    for r in todo:
        out = Path(a.dest) / r["local_path"]
        if a.dry_run:
            print(f"{r['source_id']}  {r['url']}  ->  {r['local_path']}")
            continue
        try:
            data = get(r["url"])
            if out.suffix == ".txt" and not r["url"].endswith(".txt"):
                data = lyric_text(data)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(data)
            print(f"ok    {r['local_path']}", file=sys.stderr)
        except Exception as e:
            failed += 1
            print(f"FAIL  {r['local_path']}  ({r['url']}): {e}", file=sys.stderr)
        time.sleep(a.delay)
    if failed:
        sys.exit(f"{failed} file(s) failed")


if __name__ == "__main__":
    main()
