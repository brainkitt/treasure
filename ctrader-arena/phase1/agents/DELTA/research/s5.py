import sys; sys.path.insert(0,"agents/DELTA")
from lib import *; import fam
m1=load(2517,"M_1"); SPR=0.36; V=0.1; CAP=14; n=0; SPLIT="2026-10-23"
res=[]
def run(b,od,label,minn=60,thr=1.2):
    global n; n+=1
    tr=engine.simulate(m1,od,spread=SPR)
    i=tr[tr.entry_time<SPLIT]; o=tr[tr.entry_time>=SPLIT]
    res.append((label,len(tr),pf(i.pnl),pf(o.pnl) if len(o) else 0, tr.pnl.sum()))
    if len(tr)>=minn and pf(i.pnl)>=thr: summ(tr,m1,label)
SESS={"all":None,"rth":(9.5,16),"eur":(3,9.5),"asia":(18,3),"rth_am":(9.5,12),"rth_pm":(12,16)}
for tf in (5,15):
    b=ny(engine.resample(m1,tf))
    for sn,ss in SESS.items():
        hm=None if ss is None else fam.hours_mask(b,*ss)
        for nn in (12,36,96):
            for slk in (1.5,3):
                for tpk in (0,3):
                    for fade in (False,True):
                        run(b,fam.donchian(b,nn,slk,tpk,24*5//tf*tf if False else 120,V,hm=hm,cap=CAP,fade=fade), f"tf{tf} {sn} don n={nn} sl={slk} tp={tpk} fade={fade}")
        for nn in (20,60):
            for zt in (2,2.5):
                for slk,tpk in ((2,1),(3,2),(1.5,3)):
                    for tr_ in (False,True):
                        run(b,fam.zfade(b,nn,zt,slk,tpk,120,V,hm=hm,cap=CAP,trend=tr_), f"tf{tf} {sn} z n={nn} zt={zt} sl={slk} tp={tpk} trend={tr_}")
print("sets",n)
R=pd.DataFrame(res,columns=["label","n","is","oos","net"])
R=R[R.n>=60]
print("IS PF distribution:", R["is"].describe().round(2).to_dict())
print("corr IS/OOS PF:", np.corrcoef(R["is"],R["oos"])[0,1])
