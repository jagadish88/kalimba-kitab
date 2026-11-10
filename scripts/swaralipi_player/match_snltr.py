#!/usr/bin/env python3
"""Match SNLTR swaralipi pages (Bengali titles) to our song ids (Geetabitan transliterated lyrics).

    python scripts/swaralipi_player/match_snltr.py

Reads data/raw_data/swaralipi_text/snltr/<node>.json and data/raw_data/text/lyrics/rs*.txt.
The Bengali title is transliterated roughly (consonant + inherent 'o', vowel signs, no
diacritics) and compared with the first line of each song's lyrics, letters only; the best match
wins if it is clearly ahead. Writes data/raw_data/swaralipi_text/snltr/snltr_match.csv
(node, title, song_id, score, runner-up) and copies each matched table to
data/raw_data/swaralipi_text/<song_id>.json (only when no file is there yet).
"""
import csv
import difflib
import glob
import json
import os
import re

V = {'অ': 'o', 'আ': 'aa', 'ই': 'i', 'ঈ': 'ee', 'উ': 'u', 'ঊ': 'u', 'ঋ': 'ri', 'এ': 'e', 'ঐ': 'oi', 'ও': 'o', 'ঔ': 'ou'}
S = {'া': 'aa', 'ি': 'i', 'ী': 'ee', 'ু': 'u', 'ূ': 'u', 'ৃ': 'ri', 'ে': 'e', 'ৈ': 'oi', 'ো': 'o', 'ৌ': 'ou'}
C = {'ক': 'k', 'খ': 'kh', 'গ': 'g', 'ঘ': 'gh', 'ঙ': 'ng', 'চ': 'ch', 'ছ': 'chh', 'জ': 'j', 'ঝ': 'jh', 'ঞ': 'n',
     'ট': 't', 'ঠ': 'th', 'ড': 'd', 'ঢ': 'dh', 'ণ': 'n', 'ত': 't', 'থ': 'th', 'দ': 'd', 'ধ': 'dh', 'ন': 'n',
     'প': 'p', 'ফ': 'ph', 'ব': 'b', 'ভ': 'bh', 'ম': 'm', 'য': 'j', 'র': 'r', 'ল': 'l', 'শ': 'sh', 'ষ': 'sh',
     'স': 's', 'হ': 'h', 'ড়': 'r', 'ঢ়': 'rh', 'য়': 'y', 'ৎ': 't', 'ং': 'ng', 'ঃ': '', 'ঁ': 'n'}


def translit(s):
    s = s.replace('ড়', 'ড়').replace('ঢ়', 'ঢ়').replace('য়', 'য়')
    out, i = [], 0
    while i < len(s):
        ch = s[i]
        if ch in C:
            out.append(C[ch])
            nxt = s[i + 1] if i + 1 < len(s) else ''
            if ch in 'ংঃঁৎ':
                pass
            elif nxt in S:
                out.append(S[nxt]); i += 1
            elif nxt == '্':
                i += 1
            elif nxt and (nxt in C or nxt in V):
                out.append('o')
        elif ch in V:
            out.append(V[ch])
        elif ch in S:
            out.append(S[ch])
        elif ch == '্':
            pass
        else:
            out.append(' ' if not ch.isalnum() else '')
        i += 1
    return ''.join(out)


def key(s):
    s = s.lower().replace('aa', 'a').replace('ee', 'i').replace('oo', 'u').replace('w', 'o')
    s = re.sub(r'[^a-z]', '', s)
    s = s.replace('o', 'a')          # inherent vowel o/a varies across transliterations
    return s


def main():
    lyr = {}
    for p in glob.glob('data/raw_data/text/lyrics/rs*.txt'):
        sid = os.path.basename(p)[:8]
        first = open(p, encoding='utf-8').readline()
        if first.strip():
            lyr[sid] = key(first)
    keys = list(lyr.items())
    out = []
    for p in sorted(glob.glob('data/raw_data/swaralipi_text/snltr/*.json')):
        d = json.load(open(p, encoding='utf-8'))
        t = d.get('title') or ''
        k = key(translit(t))
        sc = sorted(((difflib.SequenceMatcher(None, k, v[:len(k) + 6]).ratio(), sid) for sid, v in keys), reverse=True)[:2]
        (s1, id1), (s2, id2) = sc
        ok = s1 >= 0.72 and s1 - s2 >= 0.05
        out.append([os.path.basename(p)[:-5], t, id1 if ok else '', f'{s1:.2f}', f'{id2} {s2:.2f}'])
        if ok and not os.path.exists(f'data/raw_data/swaralipi_text/{id1}.json'):
            json.dump(dict(d, song_id=id1), open(f'data/raw_data/swaralipi_text/{id1}.json', 'w', encoding='utf-8'),
                      ensure_ascii=False)
    with open('data/raw_data/swaralipi_text/snltr/snltr_match.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['node', 'title', 'song_id', 'score', 'runner_up'])
        w.writerows(out)
    print(f'{len(out)} SNLTR swaralipis, {sum(1 for o in out if o[2])} matched to a song id')


if __name__ == '__main__':
    main()
