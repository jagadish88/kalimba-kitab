#!/usr/bin/env python3
"""How many bars of the drafts are flagged by the checks (source_check.csv, syllable_check.csv), per kind.

    python scripts/review/bars_off.py
"""
import sys,os,csv,collections
sys.path.insert(0,'scripts/review'); sys.path.insert(0,'scripts/piano_lesson_to_ktab')
import roundtrip_check as RC, abc_offkey_score as OS, ktab
last,rbp,songs=RC.drafts()
def note_bars(abc_text):
    _,items=OS.read_abc(abc_text); bars=[]; b=0; prev_tie=False; prev_m=None
    for it in items:
        if it[0]!='line': continue
        for e in it[1]:
            if e[0]=='bar': b+=1; continue
            if e[0]=='note':
                if prev_tie and prev_m==e[1]: prev_tie=e[3]; continue
                bars.append(b); prev_tie=e[3]; prev_m=e[1]
    return bars, b
flags={k:collections.defaultdict(set) for k in ('strong','weak','syl','rhythm','octave')}
src=list(csv.DictReader(open('data/intermediate_data/comparison/source_check.csv',encoding='utf-8')))
syl=list(csv.DictReader(open('data/intermediate_data/comparison/syllable_check.csv',encoding='utf-8')))
tot_bars=0; per={}
for s in songs:
    r=last[s]; sr=RC.source_of(s,rbp,r)
    if not sr: continue
    nb,nbars=note_bars(open(sr[0],encoding='utf-8').read())
    song=ktab.parse_file(r[2]); got,_=RC.played(song)
    if len(got)!=len(nb): continue
    pos2bars=collections.defaultdict(set)
    for i,g in enumerate(got): pos2bars[f'{g[3][0]}:{g[3][1]}'].add(nb[i])
    tot_bars+=nbars; d={'bars':nbars}
    for kind,rows in (('strong',[x for x in src if x['song']==s and x['kind']=='strong']),('weak',[x for x in src if x['song']==s and x['kind'] in ('weak','octave')]),('syl',[x for x in syl if x['song']==s and x['kind'] in ('missing','extra','different')]),('rhythm',[x for x in syl if x['song']==s and x['kind']=='rhythm']),('octave',[x for x in syl if x['song']==s and x['kind'].startswith('octave')])):
        bs=set()
        for x in rows: bs|=pos2bars.get(x['tab'],set())
        d[kind]=len(bs); flags[kind][s]=bs
    d['any']=len(flags['strong'][s]|flags['weak'][s]|flags['syl'][s]|flags['rhythm'][s]|flags['octave'][s]); per[s]=d
n=len(per)
S=lambda k: sum(d[k] for d in per.values())
print(f'{n} drafts, {tot_bars} bars')
print(f"bars with a strong note flag (two sources agree on another note): {S('strong')} ({100*S('strong')/tot_bars:.1f}%) in {sum(1 for d in per.values() if d['strong'])} drafts")
print(f"bars with a weak note flag (one source, a run):                   {S('weak')} ({100*S('weak')/tot_bars:.1f}%) in {sum(1 for d in per.values() if d['weak'])} drafts")
print(f"bars with a syllable flag (not on the swaralipi's notes):          {S('syl')} ({100*S('syl')/tot_bars:.1f}%) in {sum(1 for d in per.values() if d['syl'])} drafts")
print(f"bars with a rhythm flag (a syllable much longer/shorter):         {S('rhythm')} ({100*S('rhythm')/tot_bars:.1f}%) in {sum(1 for d in per.values() if d['rhythm'])} drafts")
print(f"bars with an octave flag:                                          {S('octave')} ({100*S('octave')/tot_bars:.1f}%) in {sum(1 for d in per.values() if d['octave'])} drafts")
print(f"bars with any flag:                                                {S('any')} ({100*S('any')/tot_bars:.1f}%)")
print(f"drafts with no flagged bar: {sum(1 for d in per.values() if not d['any'])}")
print('most bars flagged:',sorted(((d['any'],s,d['bars']) for s,d in per.items()),reverse=True)[:10])

print()
for label,key in (('by flagged bars',lambda s:per[s]['any']),('by share of bars flagged',lambda s:per[s]['any']/per[s]['bars'])):
    worst=sorted(per,key=key,reverse=True)[:10]
    rest={s:d for s,d in per.items() if s not in worst}
    tb=sum(d['bars'] for d in rest.values()); fa=sum(d['any'] for d in rest.values())
    print(f"dropping the 10 worst {label} ({', '.join(worst)}):")
    print(f"  {len(rest)} drafts, {tb} bars: any flag {fa} ({100*fa/tb:.1f}%); strong {sum(d['strong'] for d in rest.values())}, "
          f"weak {sum(d['weak'] for d in rest.values())}, syllable {sum(d['syl'] for d in rest.values())}, rhythm {sum(d['rhythm'] for d in rest.values())}, octave {sum(d['octave'] for d in rest.values())}; "
          f"drafts with no flagged bar {sum(1 for d in rest.values() if not d['any'])}")
