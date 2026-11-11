import sys; sys.path.insert(0,"agents/DELTA")
from lib import *; import fam
m1=load(2517,"M_1"); SPR=0.36; V=0.1; CAP=14
b=ny(engine.resample(m1,15)); 
print("=== forward test on M1 window (Sep10-Nov11), params from pre-sample cluster")
for ss,sn in (((3,9.5),"eur"),((4,9.5),"pre"),((2,8),"eurL")):
    hm=fam.hours_mask(b,*ss)
    for nn in (24,48):
        for slk in (2,3):
            for mb in (120,240):
                od=fam.donchian(b,nn,slk,1,mb,V,hm=hm,cap=CAP,fade=True)
                summ(engine.simulate(m1,od,spread=SPR),m1,f"{sn} donfade n={nn} sl={slk} tp=1 mb={mb}")
p=ny(load(2517,"M_15")); p=p[p.time<"2026-09-10"].reset_index(drop=True)
print("=== pre-sample detail eur donfade n=24: tp x sl (mb=16)")
hm=fam.hours_mask(p,3,9.5)
for tpk in (0.5,0.75,1,1.5,2,0):
    for slk in (1,1.5,2,3,4):
        tr=engine.simulate(p,fam.donchian(p,24,slk,tpk,16,V,hm=hm,cap=CAP,fade=True),spread=SPR)
        print(f"tp={tpk} sl={slk} n={len(tr)} PF={pf(tr.pnl):.2f} win={(tr.pnl>0).mean():.2f} net={tr.pnl.sum():.1f} worst={tr.pnl.min():.2f}")
tr=engine.simulate(p,fam.donchian(p,24,2,1,16,V,hm=hm,cap=CAP,fade=True),spread=SPR)
print(tr.groupby(tr.exit_time.dt.to_period("M")).pnl.agg(["size","sum",lambda x: pf(x)]).round(2).to_string())
print(tr.groupby("reason").pnl.agg(["size","sum","mean"]).round(2))
t=ny(tr.rename(columns={"entry_time":"time"})); print(t.groupby(t.nyh.astype(int)).pnl.agg(["size","sum"]).round(1).T.to_string())
print("side", t.groupby("side").pnl.agg(["size","sum"]).round(1).to_dict())
