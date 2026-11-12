import sys; sys.path.insert(0,"agents/DELTA")
from lib import *; import fam
m1=load(2517,"M_1"); SPR=0.36; V=0.1; CAP=14
b=ny(engine.resample(m1,15)); hm=fam.hours_mask(b,3,9.5)
b2=b.drop(columns="m1_idx")
print("M1-sim vs M15-sim on the same window")
for nn in (24,36,48):
    od=fam.donchian(b,nn,2,1,240,V,hm=hm,cap=CAP,fade=True); t1=engine.simulate(m1,od,spread=SPR)
    od2=fam.donchian(b2,nn,2,1,16,V,hm=hm,cap=CAP,fade=True); t2=engine.simulate(b2,od2,spread=SPR)
    print(nn, "M1sim n=%d PF=%.2f net=%.1f | M15sim n=%d PF=%.2f net=%.1f"%(len(t1),pf(t1.pnl),t1.pnl.sum(),len(t2),pf(t2.pnl),t2.pnl.sum()))
p=ny(load(2517,"M_15")); p=p[p.time<"2026-09-10"].reset_index(drop=True); hp=fam.hours_mask(p,3,9.5)
print("pre-sample n plateau (sl2 tp1 mb16)")
for nn in (8,12,16,20,24,28,32,36,40,48,56,64,96):
    tr=engine.simulate(p,fam.donchian(p,nn,2,1,16,V,hm=hp,cap=CAP,fade=True),spread=SPR)
    a=tr[tr.entry_time<"2026-06-18"]; c=tr[tr.entry_time>="2026-06-18"]
    eq=np.cumsum(tr.pnl.to_numpy()); dd=(np.maximum.accumulate(np.r_[0,eq])[1:]-eq).max()
    print(f"n={nn:3d} trades={len(tr):3d} PF={pf(tr.pnl):.2f} h1={pf(a.pnl):.2f} h2={pf(c.pnl):.2f} net={tr.pnl.sum():6.1f} dd={dd:.1f} win={(tr.pnl>0).mean():.2f}")
print("pre-sample ATR len / session edges (n=32)")
for an in (7,14,28,56):
    tr=engine.simulate(p,fam.donchian(p,32,2,1,16,V,hm=hp,cap=CAP,fade=True,an=an),spread=SPR); print("atr",an,len(tr),round(pf(tr.pnl),2))
for ss in ((2,9.5),(3,9.5),(4,9.5),(3,8.5),(3,9),(3,10),(3,11),(5,9.5),(3,7),(7,9.5)):
    tr=engine.simulate(p,fam.donchian(p,32,2,1,16,V,hm=fam.hours_mask(p,*ss),cap=CAP,fade=True),spread=SPR); print("sess",ss,len(tr),round(pf(tr.pnl),2),round(tr.pnl.sum(),1))
for mult in (1.5,2,3):
    tr=engine.simulate(p,fam.donchian(p,32,2,1,16,V,hm=hp,cap=CAP,fade=True),spread=SPR*mult); print("spread x",mult,len(tr),round(pf(tr.pnl),2))
