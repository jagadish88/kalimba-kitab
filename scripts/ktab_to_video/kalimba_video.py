#!/usr/bin/env python3
"""
Kalimba tab video maker — book style.

Reads a kalimba tab file where every syllable is written as (syllable: notes),
synthesises a kalimba recording of it, and renders a 1080p video showing two
lines at a time on a paper background. The word being played turns bold.

The tab is read by the ktab package (folder ktab/ next to this script), which
checks it against the kalimba tab grammar and reports mistakes with line:column.
Each stanza (lines separated by a blank line) starts a new slide.
A line ending in :| is played twice; a stanza whose last line ends in :|| is
played twice. Both end with a repeat barline (heavier for a stanza), drawn
faint until the repeat is playing. The last line ends with the end barline ||.
Lines are left-aligned on a common edge.
    (Ja: 1/)(na: 2/) (ga: 3/)(na: 3/) ...
    - groups with no space between them form one word; a space starts a new word
    - a note is: digit 0-7, octave marks (' up, , down), slashes, dot, dashes
      e.g. 5  1'  6,  3/  2'//  6/.  4--  7''//.   (0 = rest)
    - several notes on one syllable: (dha: 1/ 2/); a lone - holds the previous note
    - check a tab without making a video:  python3 -m ktab check song.ktab

Retuning: --retune "F4:F#4" (or "F4:F4#") retunes only the F4 tine (tab 4);
--retune "F:F#" makes every F tine (tab 4, all octaves) sound as F#;
--retune "B:Bb" turns the B tines (tab 7) into B flat. Combine with commas or repeat
the option: --retune "F:F#,C:C#". The tab is unchanged (you still play the same tine).

Requirements: Python 3, numpy, Pillow, antlr4-python3-runtime==4.13.2, ffmpeg on PATH,
the ktab/ folder next to this script, and three TeX Gyre font
files placed next to this script (or in a "fonts" folder beside it):
    texgyreheros-bold.otf, texgyrepagella-italic.otf, texgyrepagella-bolditalic.otf
(free, GUST Font License: https://www.gust.org.pl/projects/e-foundry/tex-gyre)

Example:
    python3 kalimba_video.py jana_kalimba_corrected.txt paper.png -o jana.mp4 --bpm 88
"""
import argparse, json, os, re, subprocess, sys, tempfile, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ktab

ap = argparse.ArgumentParser(description="Render a book-style kalimba tab video.")
ap.add_argument("tab", help="tab .txt file")
ap.add_argument("paper", help="background texture image")
ap.add_argument("-o", "--out", default="kalimba.mp4", help="output .mp4 (default kalimba.mp4)")
ap.add_argument("--bpm", type=float, default=88, help="tempo in beats per minute (default 88)")
ap.add_argument("--loudness", type=float, default=-14,
                help="target loudness in LUFS (default -14, the YouTube/Instagram standard)")
ap.add_argument("--model", default="synth",
                help="kalimba sound: 'synth' (built-in) or a sampled model such as 'k17cap' "
                     "(folder kalimbas/<model>/ next to this script)")
ap.add_argument("--reverb", type=float, default=0.25,
                help="reverb level: 0 = dry, 0.25 = light (default), 1 = heavy")
ap.add_argument("--retune", action="append", default=[], metavar='"F:F#"',
                help='retune all tines of one note, e.g. "F:F#" or "B:Bb"; '
                     'combine with commas or repeat the option')
ap.add_argument("--lines", type=int, default=None, help="only render the first N lines")
ap.add_argument("--fonts-dir", default=None,
                help="folder containing the TeX Gyre .otf files (default: next to this script)")
args = ap.parse_args()

# ---------------- retuning ----------------
LETTER_DEG = {"C": 1, "D": 2, "E": 3, "F": 4, "G": 5, "A": 6, "B": 7}
LETTER_SEMI = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
ACC = {"#": 1, "\u266f": 1, "b": -1, "\u266d": -1}

def parse_note(txt, natural_only=False):
    """'F', 'F#', 'Bb', 'F4', 'F#4' or 'F4#' -> (letter, semitones above C, octave or None)."""
    txt = txt.strip()
    m = re.fullmatch(r"([A-Ga-g])([#b\u266f\u266d]*)(\d?)([#b\u266f\u266d]*)", txt)
    if not m:
        return None
    letter, acc1, octave, acc2 = m.groups()
    acc = acc1 + acc2
    if natural_only and acc:
        return None
    letter = letter.upper()
    return letter, LETTER_SEMI[letter] + sum(ACC[c] for c in acc), (int(octave) if octave else None)

RETUNE = {}                                    # tab degree -> semitone shift (every octave)
RETUNE_TINE = {}                               # (tab degree, octave mark) -> shift, one tine only
for spec in ",".join(args.retune).split(","):
    if not spec.strip():
        continue
    parts = spec.split(":")
    src = parse_note(parts[0], natural_only=True) if len(parts) == 2 else None
    dst = parse_note(parts[1]) if len(parts) == 2 else None
    if not src or not dst:
        sys.exit(f'Can\'t read --retune "{spec.strip()}". Use "F:F#" (every F tine) or '
                 f'"F4:F#4" (only the F4 tine): a tine letter A-G with an optional octave, '
                 f'a colon, then the new note.')
    if src[2] is None and dst[2] is not None:
        sys.exit(f'--retune "{spec.strip()}": give the octave on the left too (e.g. "F4:F#4"), '
                 f'or leave it out on both sides to retune every F tine.')
    if dst[2] is not None:                               # octave given on both sides: exact
        shift = (dst[1] + 12 * dst[2]) - (src[1] + 12 * src[2])
    else:                                                # nearest way: e.g. B->Bb is -1, not +11
        shift = (dst[1] - src[1] + 6) % 12 - 6
    if abs(shift) > 2:
        sys.exit(f'--retune "{spec.strip()}" moves the tine by {shift:+d} semitones; '
                 f'only up to 2 semitones is allowed.')
    if src[2] is None:
        RETUNE[LETTER_DEG[src[0]]] = shift
    else:
        RETUNE_TINE[(LETTER_DEG[src[0]], src[2] - 4)] = shift   # 1 = C4, so octave 4 is the middle row
if RETUNE or RETUNE_TINE:
    names = {v: k for k, v in LETTER_DEG.items()}
    done = [f"{names[d]} tines {s:+d} semitone" for d, s in sorted(RETUNE.items())]
    done += [f"{names[d]}{o + 4} tine {s:+d} semitone" for (d, o), s in sorted(RETUNE_TINE.items())]
    print("retuned: " + ", ".join(done))

PER_PAGE = 2              # at most this many lines per slide; each stanza starts a new slide
FADE = 0.3                # page cross-fade, seconds (ends exactly on the next page's first note)
BEAT = 60.0 / args.bpm
SR, FPS = 44100, 30
W, H = 1920, 1080
INTRO, OUTRO = 1.5, 2.5   # silence before / ring-out after, seconds

# ---------------- parse the tab ----------------
try:
    song = ktab.parse_file(args.tab)
except ktab.KtabError as e:
    sys.exit(str(e))
if args.lines:
    song = song.truncated(args.lines)
lines = song.lines                    # ktab.Line objects; line.words -> ktab.Word

# ---------------- timing ----------------
tl = ktab.timeline(song, args.bpm, start=INTRO)
TOTAL = tl.end + OUTRO

# ---------------- audio ----------------
SEMI = {1: 0, 2: 2, 3: 4, 4: 5, 5: 7, 6: 9, 7: 11}
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def synth_voice(deg, hi):
    """Built-in synthesised kalimba, 1 = middle C."""
    L = int(3.0 * SR); tt = np.arange(L) / SR
    f = 261.63 * 2 ** ((SEMI[deg] + 12 * hi) / 12)
    return 0.32 * (np.sin(2*np.pi*f*tt) * np.exp(-tt*1.9) * np.minimum(1, tt/0.002)
            + 0.30*np.sin(2*np.pi*2*f*tt) * np.exp(-tt*3.5)
            + 0.12*np.sin(2*np.pi*3*f*tt) * np.exp(-tt*6)
            + 0.18*np.sin(2*np.pi*5.4*f*tt) * np.exp(-tt*12)
            + 0.06*np.sin(2*np.pi*12.1*f*tt) * np.exp(-tt*40))

def load_sample_model(name):
    """A sampled kalimba: kalimbas/<name>/ holds one .wav per tine, lowest first
    (01_C4.wav, 02_D4.wav ...). Tab '1' is the lowest tine; notes beyond the
    tines are pitch-shifted from the nearest one."""
    folder = next((d for d in (os.path.join(SCRIPT_DIR, "kalimbas", name),
                               os.path.join(os.getcwd(), "kalimbas", name)) if os.path.isdir(d)), None)
    if not folder:
        sys.exit(f"Kalimba model '{name}' not found: put its folder at kalimbas/{name}/ next to this script.")
    tines = []
    for fn in sorted(f for f in os.listdir(folder) if f.lower().endswith(".wav")):
        with wave.open(os.path.join(folder, fn)) as w:
            ch, sw, fr = w.getnchannels(), w.getsampwidth(), w.getframerate()
            a = np.frombuffer(w.readframes(w.getnframes()), {2: np.int16, 4: np.int32}[sw]).astype(np.float64)
            a = a.reshape(-1, ch).mean(1) / (2 ** (8 * sw - 1))
            if fr != SR:
                a = np.interp(np.arange(0, len(a), fr / SR), np.arange(len(a)), a)
            tines.append(a)
    if not tines:
        sys.exit(f"No .wav files in {folder}")
    def voice(deg, hi):
        idx = 7 * hi + deg - 1                       # position on the scale, 0 = lowest tine
        near = min(max(idx, 0), len(tines) - 1)
        a = tines[near]
        if near != idx:                               # outside the tines: shift the nearest one
            semis = (12 * (idx // 7) + SEMI[idx % 7 + 1]) - (12 * (near // 7) + SEMI[near % 7 + 1])
            r = 2 ** (semis / 12)
            a = np.interp(np.arange(0, len(a) - 1, r), np.arange(len(a)), a)
        return a
    return voice, len(tines)

if args.model == "synth":
    base_voice, n_tines = synth_voice, None
else:
    base_voice, n_tines = load_sample_model(args.model)

def voice(deg, hi):
    a = base_voice(deg, hi)
    shift = RETUNE_TINE.get((deg, hi), RETUNE.get(deg, 0))   # one-tine retune wins over all-octave
    if shift:                                         # retuned tine: re-pitch its sound
        r = 2 ** (shift / 12)
        a = np.interp(np.arange(0, len(a) - 1, r), np.arange(len(a)), a)
    return a

audio = np.zeros(int((TOTAL + 8) * SR))
ringing = {}                                         # tine -> start sample of its current note
DAMP = int(0.03 * SR)
for p in tl.plucks:
    st, deg, hi = p.time, p.note.degree, p.note.octave
    i = int(st * SR)
    key = (deg, hi)
    if n_tines and key in ringing:                    # re-plucking a tine stops its old ring
        a = ringing[key][1]
        tail = a[i - ringing[key][0]:]
        if len(tail):
            ramp = np.ones(len(tail)); k = min(DAMP, len(tail))
            ramp[:k] = np.linspace(1, 0, k); ramp[k:] = 0
            audio[i:i + len(tail)] -= tail[:len(audio) - i] * (1 - ramp)[:len(audio) - i]
    tone = voice(deg, hi)
    seg = audio[i:i + len(tone)]
    seg += tone[:len(seg)]
    ringing[key] = (i, tone)
audio = audio[:int((TOTAL + 1.5) * SR)]
# light stereo reverb (different tails left/right, dry sound in the centre)
# --reverb sets the reverb level relative to the dry kalimba: 0.25 = 12 dB quieter, 0 = none
irt = np.arange(int(1.2*SR)) / SR
nfft = 1 << (len(audio) + len(irt)).bit_length()
spec = np.fft.rfft(audio, nfft)
chans = []
for seed in (1, 2):
    tail = np.random.default_rng(seed).standard_normal(len(irt)) * np.exp(-irt*5.0)
    tail[:int(0.012*SR)] = 0                                  # 12 ms pre-delay keeps the pluck clear
    tail *= args.reverb / np.sqrt(np.sum(tail**2))            # wet energy = reverb^2 x dry
    ir = tail; ir[0] = 1
    chans.append(np.fft.irfft(spec * np.fft.rfft(ir, nfft), nfft)[:len(audio)])
stereo = np.stack(chans, axis=1)
fade = np.ones(len(audio)); fe = int(TOTAL*SR); fs = int((TOTAL-1.0)*SR)
fade[fs:fe] = np.linspace(1, 0, fe-fs); fade[fe:] = 0
stereo *= fade[:, None]
stereo = stereo / np.max(np.abs(stereo)) * 0.9
tmpdir = tempfile.mkdtemp()
raw_wav = os.path.join(tmpdir, "raw.wav")
with wave.open(raw_wav, "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((stereo * 32767).astype(np.int16).tobytes())
del stereo, spec, chans, audio, fade            # free audio buffers before rendering video

# gentle compression + two-pass loudness normalisation to the upload standard
COMP = "acompressor=threshold=-24dB:ratio=3:attack=5:release=250:makeup=2"
def loudnorm(extra):
    return f"{COMP},loudnorm=I={args.loudness}:TP=-1.0:LRA=11{extra}"
meas = subprocess.run(["ffmpeg", "-hide_banner", "-i", raw_wav, "-af", loudnorm(":print_format=json"),
                       "-f", "null", "-"], capture_output=True, text=True).stderr
m = json.loads(meas[meas.rindex("{"):meas.rindex("}") + 1])
wav_path = os.path.join(tmpdir, "kalimba.wav")
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw_wav, "-af",
                loudnorm(f":measured_I={m['input_i']}:measured_TP={m['input_tp']}"
                         f":measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}"
                         f":offset={m['target_offset']}:linear=true"),
                "-ar", str(SR), wav_path], check=True)
os.remove(raw_wav)

# ---------------- book-style drawing ----------------
NUM_INK = (34, 34, 36)
LYR_INK = (92, 84, 80)      # warm grey lyrics
LYR_ACT = (20, 18, 18)      # bold word being played
RULE = (190, 186, 184)
UP_INK = (0, 0, 0)          # a tine tuned up: a shade darker than the other numbers
DOWN_INK = (96, 92, 90)     # a tine tuned down: a shade lighter

def tine_ink(n, S):
    """colour of note n's number: darker if its tine is tuned up, lighter if down."""
    shift = RETUNE_TINE.get((n.degree, n.octave), RETUNE.get(n.degree, 0))
    return UP_INK if shift > 0 else DOWN_INK if shift < 0 else NUM_INK

def make_paper():
    src = Image.open(args.paper).convert("RGB")
    sc = max(W / src.width, H / src.height)
    big = src.resize((round(src.width*sc), round(src.height*sc)), Image.LANCZOS)
    l, t = (big.width - W)//2, (big.height - H)//2
    arr = np.asarray(big.crop((l, t, l+W, t+H))).astype(np.float32)
    g = np.random.default_rng(7).normal(0, 2.2, (H, W, 1))     # fine grain lost in upscaling
    return Image.fromarray(np.clip(arr + g, 0, 255).astype(np.uint8))
PAPER = make_paper()

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIRS = [args.fonts_dir] if args.fonts_dir else [
    HERE, os.path.join(HERE, "fonts"), os.getcwd(),
    os.path.expanduser("~/Library/Fonts"), "/Library/Fonts",                        # macOS
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Windows", "Fonts"),
    os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts"),               # Windows
    os.path.expanduser("~/.local/share/fonts"), os.path.expanduser("~/.fonts"),     # Linux
    "/usr/share/fonts/opentype/tex-gyre", "/usr/share/texmf/fonts/opentype/public/tex-gyre",
]

def font(name, size):
    for d in FONT_DIRS:
        path = os.path.join(d, name)
        if d and os.path.exists(path):
            return ImageFont.truetype(path, size)
    sys.exit(f"Font {name} not found. Put the .otf files next to this script, or use --fonts-dir.")

def fonts(S):
    return dict(num=font("texgyreheros-bold.otf", S),
                lyr=font("texgyrepagella-italic.otf", int(S * 0.78)),
                lyrb=font("texgyrepagella-bolditalic.otf", int(S * 0.78)))

REP_GAP = 0.40          # space before a repeat sign, x font size
REP_DIM = 0.45          # opacity of the sign until its repeat is playing
# repeat barline  : ||  as (dot radius, thin bar, thick bar, gap), x font size.
# The thick bar matches the digits' stems (0.14) so the sign reads as part of the tab.
END = "end"
REP_STYLE = {ktab.LINE: (0.045, 0.040, 0.14, 0.09),      # :|   repeat this line
             ktab.STANZA: (0.055, 0.070, 0.20, 0.10),     # :||  repeat the stanza (a little heavier)
             END: (0, 0.040, 0.14, 0.09)}                 # ||   end of the song (no dots)

def repeat_sign(S, kind, active):
    """End-repeat barline (dots, thin bar, thick bar) exactly as tall as the digits.
    Returns (RGBA image, height); paste its bottom on the digits' baseline.
    Drawn 4x larger and scaled down for smooth edges."""
    key = (S, kind, active)
    if key not in _sign_cache:
        digit_h = -fonts(S)["num"].getbbox("7", anchor="ls")[1]      # cap height of the digits
        r, thin, thick, gap = (v * S * 4 for v in REP_STYLE[kind])
        h = digit_h * 4
        lead = 2 * r + gap if r else 0               # the dots and their gap (none for the end bar)
        w = lead + thin + gap + thick
        im = Image.new("RGBA", (int(w) + 4, int(h) + 4), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        ink = NUM_INK + (255 if active else int(255 * REP_DIM),)
        for f in ((0.32, 0.68) if r else ()):        # dots at a third and two thirds of the height
            cy = h * f
            d.ellipse([0, cy - r, 2 * r, cy + r], fill=ink)
        x = lead
        d.rectangle([x, 0, x + thin, h], fill=ink)
        x += thin + gap
        d.rectangle([x, 0, x + thick, h], fill=ink)
        small = im.resize((max(1, round(im.width / 4)), max(1, round(im.height / 4))), Image.LANCZOS)
        _sign_cache[key] = (small, digit_h)
    return _sign_cache[key]
_sign_cache = {}

def word_text(wd):
    return wd.text                     # syllables joined with a middle dot

def layout_line(ln, S, F):
    """Word positions (relative to line start) and total line width."""
    pitch, pair, dash_w, word_gap, pad = 0.95*S, 0.70*S, 0.78*S, 0.85*S, 0.16*S
    x, out = 0.0, []
    for wd in ln.words:
        items = []
        cx = x + pad
        for si, s in enumerate(wd.syllables):
            for ni, ev in enumerate(s.events):
                if isinstance(ev, ktab.Hold):          # a lone '-' inside the group
                    for _ in range(ev.dashes):
                        items.append(("dash", cx, None)); cx += dash_w
                    continue
                items.append(("num", cx, (ev, si, ni)))
                cx += pair if ni + 1 < len(s.events) else pitch
                if ev.dotted:
                    cx += 0.16 * S
                for _ in range(ev.dashes):
                    items.append(("dash", cx, None)); cx += dash_w
        notes_end = cx - (pitch - F["num"].getlength("0")) + pad
        tw = F["lyrb"].getlength(word_text(wd))
        end = max(notes_end, x + tw + pad * 0.5)
        out.append(dict(x0=x, x1=end, items=items, wd=wd))
        x = end + word_gap
    return out, x - word_gap

def render(S, page_idx, active_word, rep_line=None, rep_stanza=None):
    """page_idx: indexes into `lines`; rep_line / rep_stanza: the line / stanza
    whose repeat is playing now (its sign is drawn dark)."""
    page_lines = [lines[i] for i in page_idx]
    F = fonts(S)
    img = PAPER.copy()
    d = ImageDraw.Draw(img)
    num_h, lyr_h = S * 0.72, S * 0.78
    ul_w = max(2, int(S * 0.045)); ul_step = ul_w + max(3, int(S * 0.075))
    block = lyr_h + 0.66*S + num_h + 0.30*S + (MAX_UL - 1) * ul_step + MAX_LOW * 0.13*S
    line_gap = 0.95 * S
    y = (H - (block * len(page_lines) + line_gap * (len(page_lines) - 1))) / 2
    digit_w = F["num"].getlength("0")
    for li, ln in enumerate(page_lines):
        gi = page_idx[li]
        words, width = layout_line(ln, S, F)
        ox = LEFT
        y_rule = y + lyr_h + 0.30*S
        y_num = y_rule + 0.36*S
        y_ul = y_num + num_h + 0.16*S
        for wi, wdl in enumerate(words):
            on = active_word == (li, wi)
            d.text((ox + wdl["x0"], y + lyr_h), word_text(wdl["wd"]),
                   font=F["lyrb"] if on else F["lyr"], fill=LYR_ACT if on else LYR_INK, anchor="ls")
            d.line([ox + wdl["x0"], y_rule, ox + wdl["x1"], y_rule], fill=RULE, width=max(1, int(S*0.018)))
            beams = {}
            for kind, x, p in wdl["items"]:
                X = ox + x
                if kind == "dash":
                    d.line([X + digit_w*0.15, y_num + num_h*0.55, X + digit_w*0.85, y_num + num_h*0.55],
                           fill=NUM_INK, width=max(2, int(S*0.04)))
                    continue
                n, si, ni = p
                ink = tine_ink(n, S)
                d.text((X, y_num + num_h), str(n.degree), font=F["num"], fill=ink, anchor="ls")
                for k in range(-n.octave):                    # one dot per octave below, under the underlines
                    r, cx = S * 0.045, X + digit_w/2
                    syl_ul = max(m.slashes for m in wdl["wd"].syllables[si].notes)
                    cy = y_ul + syl_ul * ul_step + (0.10 + 0.13*k)*S
                    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=ink)
                for k in range(n.octave):                     # one dot per octave above
                    r, cx, cy = S * 0.045, X + digit_w/2, y_num - (0.15 + 0.13*k)*S
                    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=ink)
                if n.dotted:                                  # dotted note
                    r, dx = S * 0.045, X + digit_w + 0.10*S        # small dot, same size as the octave dots
                    d.ellipse([dx - r, y_num + num_h - 2*r, dx + r, y_num + num_h], fill=NUM_INK)
                beams.setdefault(si, []).append((X, n.slashes))
            # underlines: one per slash; within a syllable, neighbouring notes at the same level share a line
            for notes_x in beams.values():
                for lvl in range(1, max(u for _, u in notes_x) + 1):
                    run = []
                    for X, u in notes_x + [(None, 0)]:
                        if u >= lvl:
                            run.append(X)
                        elif run:
                            yb = y_ul + (lvl - 1) * ul_step
                            d.rectangle([min(run) - 0.04*S, yb, max(run) + digit_w + 0.04*S, yb + ul_w], fill=NUM_INK)
                            run = []
        kind = line_end(gi)
        if kind:                                      # :| / :|| at the end of the line, || at the song's end
            on = (rep_line == gi if kind == ktab.LINE else
                  rep_stanza == LINE_STANZA[gi] if kind == ktab.STANZA else True)
            sign, digit_h = repeat_sign(S, kind, on)
            img.paste(sign, (round(ox + width + REP_GAP * S), round(y_num + num_h - digit_h)), sign)
        y += block + line_gap
    return img

MAX_UL = max([1] + [n.slashes for n in song.notes()])
MAX_LOW = max([0] + [-n.octave for n in song.notes()])
pages, first = [], 0                 # each stanza starts a new page; at most PER_PAGE lines each
for stanza in song.stanzas:
    for k in range(0, len(stanza.lines), PER_PAGE):
        pages.append(list(range(first + k, first + min(k + PER_PAGE, len(stanza.lines)))))
    first += len(stanza.lines)
LINE_STANZA = [si for si, st in enumerate(song.stanzas) for _ in st.lines]
PAGE_OF = {i: pi for pi, pg in enumerate(pages) for i in pg}
# pages in the order they are seen: a repeated stanza goes back to its first page
visits = []                          # [page, time it starts]
for w in tl.words:
    if not visits or visits[-1][0] != PAGE_OF[w.line]:
        visits.append([PAGE_OF[w.line], w.start])

def line_end(i):
    """Sign after line i: its repeat sign, the end barline after the song's last line, or None."""
    if lines[i].repeat:
        return lines[i].repeat
    return END if i == len(lines) - 1 else None

def fit_width(i, S, F):
    """Room a line needs, including its repeat sign / end barline."""
    width = layout_line(lines[i], S, F)[1]
    if line_end(i):
        width += REP_GAP * S + repeat_sign(S, line_end(i), False)[0].width
    return width

# largest font size where the widest line fits 90% of the frame (same size on every page)
S = 200
while S > 20:
    F = fonts(S)
    if max(fit_width(i, S, F) for i in range(len(lines))) <= W * 0.70:
        break
    S -= 2
# lines start at one left edge; the block is centred on the widest line of the song,
# so the edge stays put from page to page
LEFT = (W - max(fit_width(i, S, fonts(S)) for i in range(len(lines)))) / 2
print(f"lines: {len(lines)}  font size: {S}  duration: {TOTAL:.1f}s")

def state(now):
    """(line, word, line being repeated, stanza being repeated) at time `now`."""
    w = tl.span_at(now)
    if w is None:
        return None
    return (w.line, w.word, w.line if w.line_pass == 2 else None,
            w.stanza if w.stanza_pass == 2 else None)

# Frames are needed in time order, so keep only a few recent ones (each is a full-size
# image; caching all of them used gigabytes of RAM on long songs).
from collections import OrderedDict
CACHE_MAX = 6
cache = OrderedDict()
def frame(pi, st):
    key = (pi, st)
    if key in cache:
        cache.move_to_end(key)
        return cache[key]
    pg = pages[pi]
    local = (st[0] - pg[0], st[1]) if st and st[0] in pg else None
    cache[key] = render(S, pg, local, *(st[2:] if st else (None, None)))
    while len(cache) > CACHE_MAX:
        cache.popitem(last=False)
    return cache[key]

ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                       "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", wav_path,
                       "-c:v", "libx264", "-threads", "2", "-preset", "slow", "-crf", "18", "-tune", "stillimage",
                       "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "256k", "-shortest", args.out],
                      stdin=subprocess.PIPE)
for fi in range(int(TOTAL * FPS)):
    now = fi / FPS
    st = state(now)
    vi = max(i for i in range(len(visits)) if i == 0 or visits[i][1] - FADE <= now)
    pi, start = visits[vi]
    img = frame(pi, st)
    if vi > 0 and now < start:                        # cross-fade into the next page
        a = (now - (start - FADE)) / FADE
        img = Image.blend(frame(visits[vi - 1][0], st), frame(pi, None), a * a * (3 - 2 * a))
    ff.stdin.write(img.tobytes())
ff.stdin.close()
if ff.wait() != 0:
    sys.exit("ffmpeg failed")
os.remove(wav_path)
print("wrote", args.out)
