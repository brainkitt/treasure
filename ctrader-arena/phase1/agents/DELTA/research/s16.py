import sys; sys.path.insert(0,"agents/DELTA")
from lib import *; import fam
SPR=0.36; V=0.1; CAP=14
def rep(tr,label,mid):
    a=tr[tr.entry_time<mid]; c=tr[tr.entry_time>=mid]
    eq=np.cumsum(tr.pnl.to_numpy()); dd=(np.maximum.accumulate(np.r_[0,eq])[1:]-eq).max() if len(tr) else 0
    wk=tr.groupby(tr.exit_time.dt.to_period("W")).pnl.sum()
    print(f"{label:34s} n={len(tr):3d} PF={pf(tr.pnl):.2f} A={pf(a.pnl):.2f}({len(a)}) B={pf(c.pnl):.2f}({len(c)}) net={tr.pnl.sum():6.1f} dd={dd:.1f} win={(tr.pnl>0).mean():.2f} wk+={(wk>0).mean():.2f}")
def sig(b,nn,thr,medn=480,slk=2,tpk=1,mb=16):
    hm=fam.hours_mask(b,3,9.5); od=fam.donchian(b,nn,slk,tpk,mb,V,hm=hm,cap=CAP,fade=True)
    a=fam.atr(b,14); ar=(a/a.rolling(medn).median()).to_numpy()
    pos=np.searchsorted(b.m1_idx.to_numpy(),od.idx.to_numpy()) if "m1_idx" in b else od.idx.to_numpy()
    return od[ar[pos]<thr]
p=ny(load(2517,"M_15")); p=p[p.time<"2026-09-10"].reset_index(drop=True)
print("PRE-SAMPLE: threshold x n  (A/B = halves)")
for nn in (24,32,48):
    for thr in (0.9,1.0,1.1,1.2,1.3,1.5,99):
        rep(engine.simulate(p,sig(p,nn,thr),spread=SPR),f"n={nn} thr={thr}","2026-06-18")
for medn in (192,480,960):
    rep(engine.simulate(p,sig(p,32,1.2,medn),spread=SPR),f"n=32 thr=1.2 medn={medn}","2026-06-18")
print("FORWARD (M1 window Sep10-Nov11), A/B = official IS/OOS split 2026-10-23")
m1=load(2517,"M_1"); b=ny(engine.resample(m1,15))
for nn in (24,32,48):
    for thr in (1.1,1.2,99):
        rep(engine.simulate(m1,sig(b,nn,thr,mb=240),spread=SPR),f"FWD n={nn} thr={thr}","2026-10-23")
