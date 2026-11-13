import sys; sys.path.insert(0,"agents/DELTA")
from lib import *; import fam
b=ny(load(2517,"M_15")); print(len(b), b.time.iloc[0], b.time.iloc[-1])
d=b.ts.diff()/60000; print("big gaps (>3 days):", b.time[d>4400].tolist())
SPR=0.36; V=0.1; CAP=14
def run(od,label,lo=None,hi=None,show=True):
    tr=engine.simulate(b,od,spread=SPR)
    if lo: tr=tr[(tr.entry_time>=lo)&(tr.entry_time<hi)]
    return tr
def line(tr,label):
    if len(tr)==0: print(label,"none"); return
    eq=np.cumsum(tr.pnl.to_numpy()); dd=(np.maximum.accumulate(np.r_[0,eq])[1:]-eq).max()
    wk=tr.groupby(tr.exit_time.dt.to_period("W")).pnl.sum()
    print(f"{label:34s} n={len(tr):4d} PF={pf(tr.pnl):5.2f} net={tr.pnl.sum():7.2f} win={(tr.pnl>0).mean()*100:3.0f}% dd={dd:5.2f} wk+={(wk>0).mean()*100:3.0f}% L:{pf(tr[tr.side>0].pnl):.2f}/{(tr.side>0).sum()} S:{pf(tr[tr.side<0].pnl):.2f}/{(tr.side<0).sum()}")
hm=fam.hours_mask(b,18,3)
od=fam.donchian(b,12,1.5,0,8,V,hm=hm,cap=CAP)
tr=engine.simulate(b,od,spread=SPR)
line(tr[tr.entry_time>="2026-09-10"],"M15sim: research window (Sep10+)")
line(tr[tr.entry_time<"2026-09-10"],"M15sim: PRE-SAMPLE (<Sep10)")
pre=tr[tr.entry_time<"2026-09-10"]
print(pre.groupby(pre.exit_time.dt.to_period("M")).pnl.agg(["size","sum",lambda x: pf(x)]).round(2).to_string())
print("--- pre-sample neighbours")
for nn in (4,8,12,16,24):
    for slk in (1.5,3):
        for mb in (4,8,16):
            t=engine.simulate(b,fam.donchian(b,nn,slk,0,mb,V,hm=hm,cap=CAP),spread=SPR)
            line(t[t.entry_time<"2026-09-10"],f"pre n={nn} sl={slk} mb={mb}")
for ss in ((3,9.5),(9.5,16)):
    t=engine.simulate(b,fam.donchian(b,12,1.5,0,8,V,hm=fam.hours_mask(b,*ss),cap=CAP),spread=SPR)
    line(t[t.entry_time<"2026-09-10"],f"pre sess {ss}")
