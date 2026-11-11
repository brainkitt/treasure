import sys; sys.path.insert(0,"agents/DELTA")
from lib import *; import fam
b=ny(load(2517,"M_15")); b=b[b.time<"2026-09-10"].reset_index(drop=True)
SPR=0.36; V=0.1; CAP=14; n=0; MID="2026-06-18"
print("pre-sample", b.time.iloc[0], b.time.iloc[-1], "days", b.nyd.nunique())
rows=[]
def run(od,label):
    global n; n+=1
    tr=engine.simulate(b,od,spread=SPR)
    if len(tr)<80: return
    a=tr[tr.entry_time<MID]; c=tr[tr.entry_time>=MID]
    eq=np.cumsum(tr.pnl.to_numpy()); dd=(np.maximum.accumulate(np.r_[0,eq])[1:]-eq).max()
    rows.append(dict(label=label,n=len(tr),pf=pf(tr.pnl),h1=pf(a.pnl),h2=pf(c.pnl),net=tr.pnl.sum(),dd=dd,win=(tr.pnl>0).mean()))
SESS={"all":None,"rth":(9.5,16),"eur":(3,9.5),"asia":(18,3),"eurL":(2,8),"pre":(4,9.5),"am":(9.5,12),"pm":(12,16)}
for sn,ss in SESS.items():
    hm=None if ss is None else fam.hours_mask(b,*ss)
    for nn in (4,8,12,24,48):
        for slk in (1,2,3):
            for tpk in (0,1,2):
                for mb in (4,8,16):
                    run(fam.donchian(b,nn,slk,tpk,mb,V,hm=hm,cap=CAP,fade=True), f"{sn} donfade n={nn} sl={slk} tp={tpk} mb={mb}")
    for nn in (8,20,40):
        for zt in (1.5,2,2.5):
            for slk,tpk in ((2,1),(3,2),(3,0),(1.5,1.5)):
                for mb in (4,8,16):
                    run(fam.zfade(b,nn,zt,slk,tpk,mb,V,hm=hm,cap=CAP), f"{sn} zfade n={nn} zt={zt} sl={slk} tp={tpk} mb={mb}")
R=pd.DataFrame(rows); print("sets",n,"kept",len(R))
R["minh"]=R[["h1","h2"]].min(axis=1)
print(R.sort_values("minh",ascending=False).head(30).round(2).to_string(index=False))
print(R.groupby(R.label.str.split().str[0])[["pf","h1","h2"]].median().round(2))
print(R.groupby([R.label.str.split().str[0],R.label.str.split().str[1]])[["pf"]].agg(["median","max","count"]).round(2))
