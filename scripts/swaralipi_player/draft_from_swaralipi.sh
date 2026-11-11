#!/bin/bash
# draft.sh <song_id> [bpm]: swaralipi text -> ABC -> ktab, with catalog rows (no PDF or video)
set -e
cd /home/jagadish/Desktop/kalimba_video/kalimba-kitab
source ~/activate
S=$1; BPM=${2:-60}; W=${TMPDIR:-/tmp}/swaralipi_drafts; mkdir -p $W; A=data/intermediate_data/abc/$S; D=data/intermediate_data/ktab/$S
mkdir -p $A $D
python3 scripts/swaralipi_player/swara_abc.py $S --bpm $BPM --out $A/v1.abc 2>/dev/null | tail -1
K=$(python3 scripts/piano_lesson_to_ktab/best_key.py $A/v1.abc | tail -1); T=$(echo $K | awk '{print $2}'); R=$(echo $K | awk '{print $3}')
python3 scripts/piano_lesson_to_ktab/abc_to_ktab.py $A/v1.abc --transpose $T --out $W/$S.ktab > $W/$S.conv.txt
sed -i -E '0,/\(([^:]*): 0[^ )]* /s//(\1: /' $W/$S.ktab        # no leading rest
HDR=()
if [ -n "$R" ]; then
  TINES=$(grep "^retune tine" $W/$S.conv.txt | sed -E "s/retune tine ([^ ]+) .*/\1/" | paste -sd' ')
  HDR=("@subtitle: Kalimba tab -- retune $TINES" "@retune: $R")
fi
python3 scripts/ktab_to_video/fold_repeats.py $W/$S.ktab $D/v1.ktab "${HDR[@]}" > /dev/null
ktab check $D/v1.ktab | tail -1
OFF=$(grep -c "no free tine" $W/$S.conv.txt || true)
SUBS=$(grep "no free tine" $W/$S.conv.txt | sed -E 's/: no free tine to retune, played as /->/; s/ \(tine.*//' | paste -sd' ')
SRC=$(grep -E ",data/raw_data/text/lyrics/$S.txt" data/raw_data/source_provenance.csv | cut -d, -f2 | head -1)
echo "$S,v1,$A/v1.abc,swaralipi_to_ktab,snltr;$SRC,,$(date +%F),\"from the SNLTR swaralipi text by swara_abc.py (one matra = one eighth, main tune only, grace notes left out); Latin lyrics aligned from Geetabitan\"" >> data/intermediate_data/abc/abc_catalog.csv
echo "$S,v1,$D/v1.ktab,swaralipi_to_ktab,snltr;$SRC,$A/v1.abc,$(date +%F),\"abc_to_ktab.py --transpose $T${R:+, retune $R}; played a semitone off: ${SUBS:-none}; repeats folded; meant for $BPM bpm; no PDF or video yet\"" >> data/intermediate_data/ktab/ktab_catalog.csv
echo "KEY $T retune ${R:-none} off: ${SUBS:-none}"
