"""Best kalimba transposition of an ABC.

    python scripts/piano_lesson_to_ktab/best_key.py song.abc

Every transposition that fits the 17 tines (C4..E6) is scored: notes played a semitone off + 10 per
retuned tine (the user prefers few retunes), keeping the top note at or below 1'' (C6) when possible.
Prints the four best and a last line "BEST <transpose> <retune list>".
"""
import sys, itertools, collections; sys.path.insert(0,'scripts/piano_lesson_to_ktab')
import abc_to_ktab as A
from pathlib import Path
_,st=A.parse_abc(Path(sys.argv[1]).read_text())
c=collections.Counter(e['midi'] for s in st for ln in s for e in ln if e['kind']=='note')
tines=[p for p in range(60,89) if A.tine(p) and A.tine(p) in A.TINES_17]
res=[]
for t in range(-24,25):
    P={p+t:n for p,n in c.items()}
    if min(P)<60 or max(P)>88: continue
    acc=[p for p in P if p not in tines]; free=[x for x in tines if x not in P]
    best=None
    for ch in itertools.product(*[[(p,p-1),(p,p+1),(p,None)] for p in acc]):
        used=[x for _,x in ch if x]
        if any(x not in free for x in used) or len(set(used))<len(used): continue
        off=sum(P[p] for p,x in ch if x is None)
        key=(off,len(used))
        if best is None or key<best[0]: best=(key,[(A.name(x),A.name(p)) for p,x in ch if x])
    (off,r),rt=best
    res.append((max(P)>84, off + 10 * r, off, r, t, rt, A.tine(min(P)), A.tine(max(P))))
res.sort()
for x in res[:4]: print(x)
b=res[0]; print("BEST",b[4],",".join(f"{a}:{z}" for a,z in b[5]))
