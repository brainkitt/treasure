import sys; sys.path.insert(0,"agents/DELTA")
from lib import *; import fam
p=ny(load(2517,"M_15")); p=p[p.time<"2026-09-10"].reset_index(drop=True)
SPR=0.36; V=0.1; CAP=14; MID="2026-06-18"; n=0; rows=[]
def run(od,label,mx=1):
    global n; n+=1
    tr=engine.simulate(p,od,spread=SPR,max_open=mx)
    if len(tr)<60: return
    a=tr[tr.entry_time<MID]; c=tr[tr.entry_time>=MID]
    eq=np.cumsum(tr.pnl.to_numpy()); dd=(np.maximum.accumulate(np.r_[0,eq])[1:]-eq).max()
    rows.append(dict(label=label,n=len(tr),pf=pf(tr.pnl),h1=pf(a.pnl),h2=pf(c.pnl),net=tr.pnl.sum(),dd=dd,win=(tr.pnl>0).mean(),worst=tr.pnl.min()))
# 1) trend families all sessions
SESS={"all":None,"rth":(9.5,16),"eur":(3,9.5),"asia":(18,3),"am":(9.5,12),"pm":(12,16)}
for sn,ss in SESS.items():
    hm=None if ss is None else fam.hours_mask(p,*ss)
    for nn in (4,12,24,48,96):
        for slk in (1.5,3):
            for tpk in (0,3):
                for mb in (8,16,32):
                    run(fam.donchian(p,nn,slk,tpk,mb,V,hm=hm,cap=CAP), f"T {sn} don n={nn} sl={slk} tp={tpk} mb={mb}")
T=pd.DataFrame(rows); print("trend sets",n); print(T.groupby(T.label.str.split().str[1]).pf.agg(["median","max"]).round(2).T.to_string())
print(T.sort_values("pf",ascending=False).head(6).round(2).to_string(index=False))
# 2) limit-entry fade in EUR session: sell limit at N-high + k*ATR, buy limit at N-low - k*ATR, valid 1 bar
rows=[]
a=fam.atr(p,14).to_numpy()
def limfade(nn,k,slk,tpk,mb,ss=(3,9.5)):
    hm=fam.hours_mask(p,*ss).to_numpy()
    hi=p.high.rolling(nn).max().to_numpy(); lo=p.low.rolling(nn).min().to_numpy()
    m=hm&np.isfinite(a)&np.isfinite(hi)
    idx=np.flatnonzero(m)
    s=pd.DataFrame({"idx":idx,"side":-1,"kind":1,"price":hi[m]+k*a[m],"sl":np.minimum(slk*a[m],CAP),"tp":tpk*a[m],"max_bars":mb,"valid":1,"volume":V})
    l=pd.DataFrame({"idx":idx,"side":1,"kind":1,"price":lo[m]-k*a[m]+SPR,"sl":np.minimum(slk*a[m],CAP),"tp":tpk*a[m],"max_bars":mb,"valid":1,"volume":V})
    return pd.concat([s,l])
for nn in (12,24,48):
    for k in (0,0.25,0.5,1):
        for slk in (2,3):
            for tpk in (1,1.5):
                run(limfade(nn,k,slk,tpk,16), f"L eur lim n={nn} k={k} sl={slk} tp={tpk}", mx=2)
L=pd.DataFrame(rows); print(L.sort_values("pf",ascending=False).round(2).to_string(index=False)); print("total sets",n)
