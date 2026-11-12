import sys; sys.path.insert(0,"agents/DELTA")
from lib import *; import fam
m1=ny(load(2517,"M_1")); SPR=0.36; V=0.1; CAP=14; SPLIT="2026-10-23"
IS=m1[m1.time<SPLIT]
# overnight drift per NY session-day (18:00 -> 03:00 -> 09:30 -> 16:00)
m1["sd"]=(m1.time.dt.tz_localize("UTC").dt.tz_convert("America/New_York")+pd.Timedelta(hours=6)).dt.strftime("%Y-%m-%d")
rows=[]
for d,g in m1.groupby("sd"):
    a=g[(g.nyh>=18)|(g.nyh<3)]; e=g[(g.nyh>=3)&(g.nyh<9.5)]; r=g[(g.nyh>=9.5)&(g.nyh<16)]
    if len(a)>300 and len(r)>300:
        rows.append(dict(sd=d, asia=np.log(a.close.iloc[-1]/a.open.iloc[0])*1e4, eur=np.log(e.close.iloc[-1]/e.open.iloc[0])*1e4, rth=np.log(r.close.iloc[-1]/r.open.iloc[0])*1e4))
D=pd.DataFrame(rows); D["is"]=D.sd<SPLIT
for nm,g in D.groupby("is"):
    print("IS" if nm else "OOS", len(g), {c:(round(g[c].mean(),1), round(g[c].mean()/g[c].std()*np.sqrt(len(g)),2)) for c in ("asia","eur","rth")})
b=ny(engine.resample(m1,15)); hm=fam.hours_mask(b,18,3)
od=fam.donchian(b,12,1.5,0,120,V,hm=hm,cap=CAP)
for s,nm in ((1,"long only"),(-1,"short only")):
    tr=engine.simulate(m1,od[od.side==s],spread=SPR); summ(tr,m1,"breakout "+nm)
# naive: random-direction-free baselines: always long at each M15 close in asia w/ same exits (max_open=1)
a=fam.atr(b,14).to_numpy()
for side,nm in ((1,"always long"),(-1,"always short")):
    m=hm.to_numpy()&np.isfinite(a)
    o=pd.DataFrame({"idx":b.m1_idx[m],"side":side,"kind":0,"sl":np.minimum(1.5*a[m],CAP),"tp":0,"max_bars":120,"volume":V})
    summ(engine.simulate(m1,o,spread=SPR),m1,"baseline "+nm)
# pure momentum sign of last 3h in asia, entering whenever flat
r=np.sign(b.close-b.close.shift(12)).to_numpy(); m=hm.to_numpy()&np.isfinite(a)&(r!=0)
o=pd.DataFrame({"idx":b.m1_idx[m],"side":r[m],"kind":0,"sl":np.minimum(1.5*a[m],CAP),"tp":0,"max_bars":120,"volume":V})
summ(engine.simulate(m1,o,spread=SPR),m1,"sign(3h mom) always-in")
# NAS M5 cross-check (bars sim on M5)
nb=ny(load(2518,"M_5")); nb15=nb.groupby(nb.ts//900000).agg(ts=("ts","first"),time=("time","first"),open=("open","first"),high=("high","max"),low=("low","min"),close=("close","last"),m1_idx=("ts",lambda s:s.index[-1])).reset_index(drop=True); nb15=ny(nb15)
od=fam.donchian(nb15,12,1.5,0,24,0.1,hm=fam.hours_mask(nb15,18,3))
summ(engine.simulate(nb,od,spread=0.9),nb,"NAS asia breakout (M5 sim, uncapped)")
od=fam.donchian(nb15,12,1.5,0,24,0.1,hm=fam.hours_mask(nb15,9.5,16))
summ(engine.simulate(nb,od,spread=0.9),nb,"NAS RTH breakout (M5 sim, uncapped)")
