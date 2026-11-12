import sys; sys.path.insert(0,"agents/DELTA")
from lib import *; import fam, importlib.util, json
SPR=0.36; V=0.1; CAP=14
m1=load(2517,"M_1"); b=ny(engine.resample(m1,15)); hm=fam.hours_mask(b,3,9.5)
p=ny(load(2517,"M_15")); p=p[p.time<"2026-09-10"].reset_index(drop=True); hp=fam.hours_mask(p,3,9.5)
print("NEIGHBOUR TABLE  (pre-sample PF/n | official-window PF/n, IS, OOS)")
def w(nn,slk,tpk,mb):
    t=engine.simulate(m1,fam.donchian(b,nn,slk,tpk,mb,V,hm=hm,cap=CAP,fade=True),spread=SPR)
    i=t[t.entry_time<"2026-10-23"]; o=t[t.entry_time>="2026-10-23"]
    q=engine.simulate(p,fam.donchian(p,nn,slk,tpk,mb//15,V,hm=hp,cap=CAP,fade=True),spread=SPR)
    print(f"n={nn:2d} sl={slk} tp={tpk} hold={mb:3d} | pre {pf(q.pnl):.2f}/{len(q)} | win {pf(t.pnl):.2f}/{len(t)} IS {pf(i.pnl):.2f} OOS {pf(o.pnl):.2f} net {t.pnl.sum():5.1f}")
for nn in (20,24,28,32,36,40,48): w(nn,2,1,240)
for slk in (1.5,2.5,3): w(32,slk,1,240)
for tpk in (0.75,1.25,1.5): w(32,2,tpk,240)
for mb in (120,360): w(32,2,1,mb)
# combined 7.5 months
t=engine.simulate(m1,fam.donchian(b,32,2,1,240,V,hm=hm,cap=CAP,fade=True),spread=SPR)
q=engine.simulate(p,fam.donchian(p,32,2,1,16,V,hm=hp,cap=CAP,fade=True),spread=SPR)
allp=pd.concat([q,t]); print("combined 2026-03-26..11-11: n=%d PF=%.2f net=%.1f win=%.2f"%(len(allp),pf(allp.pnl),allp.pnl.sum(),(allp.pnl>0).mean()))
print(allp.groupby(allp.exit_time.dt.to_period("M")).pnl.agg(["size","sum",pf]).round(2).to_string())
# bootstrap CI of PF on combined
rng=np.random.default_rng(1); x=allp.pnl.to_numpy(); bs=[pf(rng.choice(x,len(x))) for _ in range(4000)]
print("bootstrap PF 5/50/95%:", np.percentile(bs,[5,50,95]).round(2), " P(PF>=1.7)=",np.mean(np.array(bs)>=1.7).round(3), "P(PF<=1)=",np.mean(np.array(bs)<=1).round(3))
# daily loss / streak in official window
d=t.groupby(t.exit_time.dt.floor("D")).pnl.sum(); print("worst day %.2f best day %.2f, max trades/day %d"%(d.min(),d.max(),t.groupby(t.entry_time.dt.floor("D")).size().max()))
print("reasons", t.groupby("reason").pnl.agg(["size","sum"]).round(2).to_dict())
print("sides", t.groupby("side").pnl.agg(["size","sum"]).round(2).to_dict(), "avg hold min", ((t.exit_time-t.entry_time).dt.total_seconds()/60).mean().round(1))
for mult in (2,3):
    tt=engine.simulate(m1,fam.donchian(b,32,2,1,240,V,hm=hm,cap=CAP,fade=True),spread=SPR*mult); print("official window spread x",mult,"PF",round(pf(tt.pnl),2))
# NAS cross-check on M5 (no cap; units 0.1)
nb=ny(load(2518,"M_5")); nb15=nb.groupby(nb.ts//900000).agg(ts=("ts","first"),time=("time","first"),open=("open","first"),high=("high","max"),low=("low","min"),close=("close","last"),m1_idx=("ts",lambda s:s.index[-1])).reset_index(drop=True); nb15=ny(nb15)
for nn in (24,32,48):
    tt=engine.simulate(nb,fam.donchian(nb15,nn,2,1,48,0.1,hm=fam.hours_mask(nb15,3,9.5),fade=True),spread=0.9); print(f"NAS100 pre-open fade n={nn} (Sep29-Nov11, M5 sim, uncapped): n={len(tt)} PF={pf(tt.pnl):.2f} win={(tt.pnl>0).mean():.2f}")
