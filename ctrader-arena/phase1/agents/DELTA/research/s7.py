import sys; sys.path.insert(0,"agents/DELTA")
from lib import *; import fam
m1=load(2517,"M_1"); SPR=0.36; V=0.1; CAP=14; SPLIT="2026-10-23"
def run(b,od,label,spr=SPR,show=True):
    tr=engine.simulate(m1,od,spread=spr)
    if show: summ(tr,m1,label)
    return tr
B={tf: ny(engine.resample(m1,tf)) for tf in (5,10,15,30)}
print("--- n / tf grid (asia 18-03, sl1.5 tp0 mb120)")
for tf in (5,10,15,30):
    b=B[tf]; hm=fam.hours_mask(b,18,3)
    for nn in (4,8,12,16,24,36):
        run(b,fam.donchian(b,nn,1.5,0,120,V,hm=hm,cap=CAP),f"tf{tf} n={nn}")
b=B[15]
print("--- session window (tf15 n12)")
for ss in ((18,3),(18,0),(20,3),(19,2),(18,22),(22,3),(0,3),(18,5),(16,3),(3,9.5),(9.5,16)):
    run(b,fam.donchian(b,12,1.5,0,120,V,hm=fam.hours_mask(b,*ss),cap=CAP),f"sess {ss}")
print("--- sl / mb / tp (tf15 n12 asia)")
hm=fam.hours_mask(b,18,3)
for slk in (1,1.5,2,3):
    for mb in (30,60,120,240,480):
        run(b,fam.donchian(b,12,slk,0,mb,V,hm=hm,cap=CAP),f"sl={slk} mb={mb}")
for tpk in (1,2,3,5): run(b,fam.donchian(b,12,1.5,tpk,120,V,hm=hm,cap=CAP),f"tp={tpk}")
tr=run(b,fam.donchian(b,12,1.5,0,120,V,hm=hm,cap=CAP),"base")
t=ny(tr.rename(columns={"entry_time":"time"}))
print(t.groupby(t.nyh.astype(int)).pnl.agg(["size","sum","mean"]).round(2).T.to_string())
print(t.groupby("dow").pnl.agg(["size","sum"]).round(2).T.to_string())
print("by side", t.groupby("side").pnl.agg(["size","sum"]).round(2).to_dict())
print("reasons", tr.groupby("reason").pnl.agg(["size","sum"]).round(2).to_dict())
print("top5 wins", np.sort(tr.pnl)[-5:].round(2), "sum", tr.pnl.sum().round(2))
print("weekly", tr.groupby(tr.exit_time.dt.to_period("W")).pnl.sum().round(2).to_dict())
for mult in (1.5,2,3): run(b,fam.donchian(b,12,1.5,0,120,V,hm=hm,cap=CAP),f"spread x{mult}",spr=SPR*mult)
