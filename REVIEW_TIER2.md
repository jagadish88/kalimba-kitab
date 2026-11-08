# Tier 2 review: run of 2026-11-08 (blocked, no drafts made)

**Status: not done.** None of the 5 Tier 2 songs (rs000864, rs001848, rs002064, rs000636,
rs000616) was transcribed. No `v1.abc`, `.ktab` or PDF files were written, and no catalog rows
were added. `data/dataset/` and `main` were not touched.

## Why
Step 2 of TASK_TIER2.md (`scripts/fetch_sources.py` on the 25 source rows) failed for **all
25 files**: the MIDI (5), swaralipi PDF/GIF (10), lyrics .txt (5) and Bengali lyric PNG (5).
Every one of them is hosted on `www.geetabitan.com`, and this cloud session's egress proxy
refuses that host:

    <urlopen error Tunnel connection failed: 403 Forbidden>
    proxy status: connect_rejected, "gateway answered 403 to CONNECT (policy denial ...)",
    host www.geetabitan.com:443

That is a network-policy denial for this environment, not a temporary error, so I did not keep
retrying it or look for a way around it. The method needs the exact MIDI bars
(`midi_bars.py`) and the swaralipi for every bar, so with neither file available I could not
write drafts that pass `check_abc.py`. I chose not to make up melodies or lyric placement
from memory.

## What did work
- `pip install -e . mido`: OK.
- `abcmidi` installed after an `apt-get update`.
- `ffmpeg` is present. TeX Live install was started; it does not matter for this run.

## Not attempted
- Per-song form, bars, notes, checks, transposition/retune choices: no input files.
- rs001848 YouTube cross-check: optional, and only useful against a draft, so skipped.
- scale_catalog.csv `read` rows: not checked (no swaralipi).

## To unblock
Pick one:
1. Allow `www.geetabitan.com` in this cloud environment's network policy
   (https://code.claude.com/docs/en/claude-code-on-the-web), then run the routine again; or
2. Run the task locally, where `fetch_sources.py` can reach geetabitan.com; or
3. Put the 25 files somewhere this environment can reach, for example a private repo or
   release that the session can read. They are git-ignored here for copyright reasons, so
   do not commit them to this public repo.
