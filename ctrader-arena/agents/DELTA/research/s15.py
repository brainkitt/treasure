import sys; sys.path.insert(0,"agents/DELTA")
from lib import *; import fam
p=ny(load(2517,"M_15")); p=p[p.time<"2026-09-10"].reset_index(drop=True); hp=fam.hours_mask(p,3,9.5)
SPR=0.36; V=0.1; CAP=14; n=0
def rep(tr,label):
    global n; n+=1
    a=tr[tr.entry_time<"2026-06-18"]; c=tr[tr.entry_time>="2026-06-18"]
    eq=np.cumsum(tr.pnl.to_numpy()); dd=(np.maximum.accumulate(np.r_[0,eq])[1:]-eq).max()
    wk=tr.groupby(tr.exit_time.dt.to_period("W")).pnl.sum()
    print(f"{label:40s} n={len(tr):3d} PF={pf(tr.pnl):.2f} h1={pf(a.pnl):.2f} h2={pf(c.pnl):.2f} net={tr.pnl.sum():6.1f} dd={dd:.1f} win={(tr.pnl>0).mean():.2f} wk+={(wk>0).mean():.2f}")
base=fam.donchian(p,32,2,1,16,V,hm=hp,cap=CAP,fade=True)
tr=engine.simulate(p,base,spread=SPR); rep(tr,"base n32 sl2 tp1 mb16")
a=fam.atr(p,14); ar=(a/a.rolling(96*5).median()).to_numpy()
# vol filter
for lo,hi in ((0,0.8),(0.8,1.2),(1.2,9),(0,1.2),(0,1.5),(0.6,1.5)):
    od=base[(ar[base.idx]>=lo)&(ar[base.idx]<hi)]; rep(engine.simulate(p,od,spread=SPR),f"ATR ratio in [{lo},{hi})")
# breakout magnitude: how far close beyond level (in ATR)
hi_=p.high.rolling(32).max().shift(1).to_numpy(); lo_=p.low.rolling(32).min().shift(1).to_numpy(); c=p.close.to_numpy()
ex=np.where(base.side.to_numpy()<0,(c[base.idx]-hi_[base.idx]),(lo_[base.idx]-c[base.idx]))/a.to_numpy()[base.idx]
for lo,hi in ((0,0.15),(0.15,0.4),(0.4,9),(0,0.4)):
    od=base[(ex>=lo)&(ex<hi)]; rep(engine.simulate(p,od,spread=SPR),f"excess in [{lo},{hi}) ATR")
# trend context: position of level vs 96*2-bar (2 day) mean
ma=p.close.rolling(192).mean().to_numpy(); up=c[base.idx]>ma[base.idx]
rep(engine.simulate(p,base[(base.side.to_numpy()<0)==up],spread=SPR),"fade only WITH 2d-mean reversion (short above ma)")
rep(engine.simulate(p,base[(base.side.to_numpy()<0)!=up],spread=SPR),"fade only against (short below ma)")
t=ny(tr.rename(columns={"entry_time":"time"})); print(t.groupby("dow").pnl.agg(["size","sum",pf]).round(2).T.to_string())
# trailing / breakeven-free alternatives: time exit shorter/longer already; tp mult by sl
for slk,tpk,mb in ((2,1,24),(2,1,32),(2.5,1.25,16),(1.5,0.75,16),(2,1.25,16)):
    rep(engine.simulate(p,fam.donchian(p,32,slk,tpk,mb,V,hm=hp,cap=CAP,fade=True),spread=SPR),f"sl={slk} tp={tpk} mb={mb}")
print("sets",n)
