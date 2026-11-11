import sys; sys.path.insert(0,"agents/DELTA")
from lib import *; import fam
b=ny(load(101,"M_5")); print(len(b), b.time.iloc[0], b.time.iloc[-1])
b["utch"]=b.time.dt.hour
IS=b[b.time<"2026-10-24"]
lc=np.log(IS.close); r=lc.diff()
print("M5 std bp", r.std()*1e4, "spread bp", 18.9/IS.close.mean()*1e4, "med range", (IS.high-IS.low).median())
for k in (2,3,6,12,24,48): print("VR",k, round(lc.diff(k).var()/(k*r.var()),3), "corr past/fut", round(np.corrcoef(lc.diff(k).dropna()[:-k], (lc.shift(-k)-lc).dropna()[k:])[0,1],3))
g=IS.groupby("utch").apply(lambda x: pd.Series(dict(mean_bp=np.log(x.close/x.open).mean()*1e4, t=np.log(x.close/x.open).mean()/np.log(x.close/x.open).std()*np.sqrt(len(x)), rng=(x.high-x.low).median())))
print(g.round(2).T.to_string())
SPR=18.9; n=0
def run(od,label):
    global n; n+=1
    tr=engine.simulate(b,od,spread=SPR)
    if len(tr)>=60 and pf(tr[tr.entry_time<"2026-10-24"].pnl)>=1.15: summ(tr,b,label)
V=0.01; CAP=140
for nn in (12,24,48,96,288):
    for slk in (1.5,3):
        for tpk in (0,2,4):
            for fade in (False,True):
                run(fam.donchian(b,nn,slk,tpk,48,V,cap=CAP,fade=fade), f"don n={nn} sl={slk} tp={tpk} fade={fade}")
for nn in (12,24,48,96):
    for zt in (1.5,2,2.5):
        for slk in (2,4):
            for tpk in (1,2):
                for tr_ in (False,True):
                    run(fam.zfade(b,nn,zt,slk,tpk,36,V,cap=CAP,trend=tr_), f"z n={nn} zt={zt} sl={slk} tp={tpk} trend={tr_}")
for k in (3,6,12,24,48):
    for thr in (1,2):
        for mb in (6,12,24):
            run(fam.tsmom(b,k,thr,4,mb,V,cap=CAP), f"tsmom k={k} thr={thr} mb={mb}")
            od=fam.tsmom(b,k,thr,4,mb,V,cap=CAP); od["side"]=-od.side; run(od, f"tsrev k={k} thr={thr} mb={mb}")
print("sets",n)
