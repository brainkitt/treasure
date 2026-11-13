import sys; sys.path.insert(0,"agents/DELTA")
from lib import *; import fam
V=0.1
def rep(tr,label,mid="2026-06-18"):
    if len(tr)==0: print(label,"none"); return
    a=tr[tr.entry_time<mid]; c=tr[tr.entry_time>=mid]
    eq=np.cumsum(tr.pnl.to_numpy()); dd=(np.maximum.accumulate(np.r_[0,eq])[1:]-eq).max()
    print(f"{label:44s} n={len(tr):3d} PF={pf(tr.pnl):.2f} h1={pf(a.pnl):.2f}({len(a)}) h2={pf(c.pnl):.2f}({len(c)}) net={tr.pnl.sum():6.1f} dd={dd:.1f} win={(tr.pnl>0).mean():.2f} worst={tr.pnl.min():.2f}")
for sid,name,spr,upq in ((2521,"RUT",0.30,1.0),(2516,"UK100",3.36,1.31)):
    p=ny(load(sid,"M_15")); p=p[p.time<"2026-09-10"].reset_index(drop=True)
    a=fam.atr(p,14); p["h"]=p.nyh.astype(int)
    print(name, len(p), p.time.iloc[0], p.time.iloc[-1], "price", p.close.iloc[-1])
    print(" ATR14(M15) median by NY hour:", a.groupby(p.h).median().round(2).to_dict())
    cap=1.4/(V*upq)
    wins={"RUT":[(3,9.5)], "UK100":[(3,9.5),(18,3),(16,3),(12,18)]}[name]
    for ss in wins:
        hm=fam.hours_mask(p,*ss)
        for s in ([spr] if name=="RUT" else [spr,1.0]):
            tr=engine.simulate(p,fam.donchian(p,32,2,1,16,V,hm=hm,cap=cap,fade=True),spread=s,usd_per_quote=upq)
            rep(tr,f"{name} sess{ss} spread={s} cap={cap:.1f}")
    if name=="RUT":
        hm=fam.hours_mask(p,3,9.5)
        for nn in (20,24,48,64):
            rep(engine.simulate(p,fam.donchian(p,nn,2,1,16,V,hm=hm,cap=cap,fade=True),spread=spr),f"RUT n={nn}")
        for m in (0,1.5,2):
            rep(engine.simulate(p,fam.donchian(p,32,2,1,16,V,hm=hm,cap=cap,fade=True),spread=spr*m),f"RUT n=32 spread x{m}")
        tr=engine.simulate(p,fam.donchian(p,32,2,1,16,V,hm=hm,cap=cap,fade=True),spread=spr)
        print(tr.groupby(tr.exit_time.dt.to_period("M")).pnl.agg(["size","sum",pf]).round(2).T.to_string())
