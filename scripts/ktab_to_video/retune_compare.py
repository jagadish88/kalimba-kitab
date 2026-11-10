#!/usr/bin/env python3
"""Tab lines played without and with the retuned tines, in turn, to hear what retuning changes.

    python scripts/ktab_to_video/retune_compare.py data/intermediate_data/ktab/rs001381/v5.ktab --lines 1-6

Lines are chosen in playing order (a ':|' line counts twice). For every stanza among them: its chosen
lines as the kalimba sounds in standard tuning, then the same lines with the tines retuned. With
--whole, all the chosen lines without retuning, then all of them with it. The retuning comes from --retune, or else from the tab's
@retune header (same syntax as kalimba_video.py --retune, e.g. "G4:G#4,A4:A#4").

Writes data/intermediate_data/comparison/<tab dir>_<tab name>_retune_compare_lines<a-b>.mp4 (git-ignored).
"""
import argparse
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'src'))
import ktab  # noqa: E402

FONT_DIR = os.path.join(HERE, 'fonts')
INTRO = 1.5                                     # kalimba_video.py's silence before the first note
ENC = ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '23', '-r', '30', '-pix_fmt', 'yuv420p',
       '-c:a', 'aac', '-ar', '44100', '-ac', '2']


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('ktab')
    ap.add_argument('--lines', required=True, help='tab lines in playing order, 1-based: 3 or 1-6')
    ap.add_argument('--bpm', type=float, default=100, help='tempo (default 100)')
    ap.add_argument('--retune', help='e.g. "G4:G#4,A4:A#4" (default: the tab\'s @retune header)')
    ap.add_argument('--whole', action='store_true',
                    help='play all chosen lines without retuning, then all with it (default: stanza by stanza)')
    ap.add_argument('--out', help='output .mp4')
    a = ap.parse_args()

    song = ktab.parse_file(a.ktab)
    retune = a.retune or song.headers.get('retune')
    if not retune:
        sys.exit('no retuning: give --retune or put an @retune: header in the tab')

    tl = ktab.timeline(song, a.bpm, start=INTRO)
    played = []                                 # [stanza, line index, start, end] in playing order
    for w in tl.words:
        if not played or played[-1][1] != w.line or w.word == 0:
            played.append([w.stanza, w.line, w.start, w.end])
        played[-1][3] = w.end
    lo, _, hi = a.lines.partition('-')
    lo, hi = int(lo), int(hi or lo)
    if not 1 <= lo <= hi <= len(played):
        sys.exit(f'--lines {a.lines}: the tab has {len(played)} lines in playing order')
    sel = played[lo - 1:hi]

    name = os.path.splitext(os.path.basename(a.ktab))[0]
    song_dir = os.path.basename(os.path.dirname(os.path.abspath(a.ktab)))
    out = a.out or os.path.join(ROOT, 'data/intermediate_data/comparison',
                                f'{song_dir}_{name}_retune_compare_lines{lo}-{hi}.mp4')

    with tempfile.TemporaryDirectory() as tmp:
        videos = {}
        for tag, extra in (('plain', []), ('retuned', ['--retune', retune])):
            videos[tag] = os.path.join(tmp, f'{tag}.mp4')
            print(f'rendering the tab {"with" if extra else "without"} retuning ...', flush=True)
            subprocess.run([sys.executable, os.path.join(HERE, 'kalimba_video.py'), a.ktab,
                            os.path.join(ROOT, 'data/raw_data/image/paper_texture_brown.png'),
                            '-o', videos[tag], '--bpm', str(a.bpm)] + extra, check=True, capture_output=True)

        def clip(tag, t0, t1, path):
            label = ('Standard tuning' if tag == 'plain' else f'Retuned  ({retune})').replace(':', '\\:')
            # from the first note to the next word's pluck (no earlier tail, no later word), short fades
            s0, dur = t0, t1 - t0
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{s0:.3f}', '-t', f'{dur:.3f}',
                            '-i', videos[tag],
                            '-vf', f"scale=1280:720,drawtext=fontfile={FONT_DIR}/texgyreheros-bold.otf:"
                            f"text='{label}':x=20:y=20:fontsize=28:fontcolor=white:box=1:boxcolor=black@0.6",
                            '-af', f'afade=t=in:d=0.02,afade=t=out:st={max(0, dur - 0.12):.3f}:d=0.12'] + ENC + [path], check=True)

        groups = []                             # runs of chosen lines in one stanza (or all of them)
        for p in sel:
            if groups and (a.whole or groups[-1][-1][0] == p[0]):
                groups[-1].append(p)
            else:
                groups.append([p])
        parts = []
        for k, g in enumerate(groups):
            for tag in ('plain', 'retuned'):
                parts.append(os.path.join(tmp, f'{tag}_{k}.mp4'))
                clip(tag, g[0][2], g[-1][3], parts[-1])
        lst = os.path.join(tmp, 'list.txt')
        with open(lst, 'w') as f:
            f.write(''.join(f"file '{p}'\n" for p in parts))
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', lst, '-c', 'copy', out],
                       check=True)
    print(f'lines {lo}-{hi} in {len(groups)} part(s), each plain then retuned -> {out}')


if __name__ == '__main__':
    main()
