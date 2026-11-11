#!/bin/bash
# draft_from_midi.sh <song_id>: Geetabitan MIDI (notes) + SNLTR swaralipi (syllables) -> ABC v1/v2 -> ktab v1
# (no PDF or video). Checks: ABC notes = MIDI bars (0 errors), ktab check. Appends catalog rows.
set -e
cd "$(dirname "$0")/../.."
source ~/activate
S=$1; W=${TMPDIR:-/tmp}/midi_drafts; mkdir -p $W; A=data/intermediate_data/abc/$S; D=data/intermediate_data/ktab/$S
mkdir -p $A $D
python3 scripts/swaralipi_player/midi_swara_abc.py $S --out-dir $A 2>/dev/null | tail -1
python3 - $S > $W/$S.bars <<'PY'
import sys; sys.path.insert(0, 'scripts/swaralipi_player')
import midi_swara_abc as M
bars, *_ = M.midi_bars(sys.argv[1])
for k, b in enumerate(bars):
    print(k, ' '.join(t for t, _, _ in b))
PY
python3 scripts/swaralipi_player/check_midi_bars.py $A/v1.abc $W/$S.bars | tail -1
K=$(python3 scripts/piano_lesson_to_ktab/best_key.py $A/v2.abc | tail -1); T=$(echo $K | awk '{print $2}'); R=$(echo $K | awk '{print $3}')
python3 scripts/piano_lesson_to_ktab/abc_to_ktab.py $A/v2.abc --transpose $T --out $W/$S.ktab > $W/$S.conv.txt
sed -i -E '0,/\(([^:]*): 0[^ )]* /s//(\1: /' $W/$S.ktab
HDR=()
if [ -n "$R" ]; then
  TINES=$(grep "^retune tine" $W/$S.conv.txt | sed -E "s/retune tine ([^ ]+) .*/\1/" | paste -sd' ')
  HDR=("@subtitle: Kalimba tab -- retune $TINES" "@retune: $R")
fi
python3 scripts/ktab_to_video/fold_repeats.py $W/$S.ktab $D/v1.ktab "${HDR[@]}" > /dev/null
ktab check $D/v1.ktab | tail -1
SUBS=$(grep "no free tine" $W/$S.conv.txt | sed -E 's/: no free tine to retune, played as /->/; s/ \(tine.*//' | paste -sd' ')
SRC=$(grep -E "^data/raw_data/(midi/$S.mid|text/lyrics/$S.txt)," data/raw_data/source_provenance.csv | cut -d, -f2 | paste -sd';')
TEMPO=$(grep -m1 "^Q:" $A/v2.abc | cut -d= -f2)
echo "$S,v1,$A/v1.abc,midi_to_ktab,$SRC;snltr,,$(date +%F),\"notes from the MIDI melody track (check against the MIDI bars: 0 errors); syllables from the SNLTR swaralipi aligned by midi_swara_abc.py; Latin from Geetabitan\"" >> data/intermediate_data/abc/abc_catalog.csv
echo "$S,v2,$A/v2.abc,midi_to_ktab,$SRC;snltr,$A/v1.abc,$(date +%F),\"v1 with note values halved\"" >> data/intermediate_data/abc/abc_catalog.csv
echo "$S,v1,$D/v1.ktab,midi_to_ktab,$SRC;snltr,$A/v2.abc,$(date +%F),\"abc_to_ktab.py --transpose $T${R:+, retune $R}; played a semitone off: ${SUBS:-none}; repeats folded; for $TEMPO bpm; no PDF or video yet\"" >> data/intermediate_data/ktab/ktab_catalog.csv
echo "KEY $T retune ${R:-none} off: ${SUBS:-none}"
