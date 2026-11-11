"""Pair the notes of two versions of a tune (a draft and a swaralipi, a MIDI and a swaralipi).

align(a, b, a_len=None, b_len=None) -> (pair, shift)
    a, b      MIDI pitches; b is transposed by `shift` (the pitch-class shift that lines up best)
    a_len...  note lengths (any units; their scale is found from the pairs), optional
    pair[i] = index in b paired with a[i], or None (a gap: an ornament or repeat the other lacks)

Global alignment on pitch classes: a pair of equal notes scores 2, two different notes -1, a gap -1.
With lengths, an equal pair scores up to 1 more the closer its two lengths are (after scaling): where a
pitch repeats ("5. 6.- 5/ 6/" against a swaralipi's 5 and long 6), the long 6 goes with the long 6
instead of whichever comes first.
"""
import math
from collections import Counter


def shifts(a, b):
    ha, hb = Counter(p % 12 for p in a), Counter(p % 12 for p in b)
    sc = sorted(((sum(ha[c] * hb[(c - s) % 12] for c in range(12)), s) for s in range(12)), reverse=True)
    return [s for _, s in sc[:2]]


def _nw(a, b, la=None, lb=None, scale=1.0):
    n, m = len(a), len(b)
    G = -1
    prev = [j * G for j in range(m + 1)]
    back = []
    for i in range(1, n + 1):
        cur = [i * G] + [0] * m
        bk = [2] + [0] * m
        ai = a[i - 1]
        for j in range(1, m + 1):
            if ai == b[j - 1]:
                sc = 2
                if la is not None:
                    r = abs(math.log2(max(la[i - 1], 1e-3) / max(lb[j - 1] * scale, 1e-3)))
                    sc += 1 - min(1, r)
            else:
                sc = -1
            d = prev[j - 1] + sc
            u = prev[j] + G
            l = cur[j - 1] + G
            if d >= u and d >= l:
                cur[j], bk[j] = d, 0
            elif u >= l:
                cur[j], bk[j] = u, 1
            else:
                cur[j], bk[j] = l, 2
        back.append(bk)
        prev = cur
    pair = [None] * n
    i, j = n, m
    while i > 0 and j > 0:
        k = back[i - 1][j]
        if k == 0:
            pair[i - 1] = j - 1; i -= 1; j -= 1
        elif k == 1:
            i -= 1
        else:
            j -= 1
    return pair, prev[m]


def align(a, b, a_len=None, b_len=None):
    best = None
    for sh in shifts(a, b):
        pair, score = _nw([p % 12 for p in a], [(p + sh) % 12 for p in b])
        if best is None or score > best[1]:
            best = (pair, score, sh)
    pair, _, sh = best
    if a_len is not None and b_len is not None:
        rat = sorted(a_len[i] / b_len[j] for i, j in enumerate(pair)
                     if j is not None and b_len[j] and a[i] % 12 == (b[j] + sh) % 12)
        if rat:
            pair, _ = _nw([p % 12 for p in a], [(p + sh) % 12 for p in b], a_len, b_len, rat[len(rat) // 2])
    return pair, sh
