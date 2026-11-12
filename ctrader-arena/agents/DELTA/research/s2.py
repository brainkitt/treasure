import sys; sys.path.insert(0,"agents/DELTA")
from lib import *
SP={2517:(0.36,0.1),2518:(0.9,0.1)}
def orb(b, nbar, slcap, tpR, fade=False, endmin=955, buf=0.0, minR=0, maxR=1e9):
    rows=[]
    for d,g in b.groupby("nyd"):
        o = g[(g.nymin>=570)&(g.nymin<570+nbar*5)]
        if len(o)<nbar: continue
        hi,lo=o.high.max(),o.low.min(); R=hi-lo
        if R<minR or R>maxR: continue
        rest = g[(g.nymin>=570+nbar*5)&(g.nymin<endmin-10)]
        for i,r in rest.iterrows():
            left = int((endmin - r.nymin)/5)-1
            if r.close>hi+buf:
                s=1; break
            if r.close<lo-buf:
                s=-1; break
        else: continue
        if fade: s=-s
        sl=min(R if not fade else R, slcap)
        rows.append(dict(idx=i, side=s, kind=0, sl=sl, tp=tpR*sl, max_bars=left, volume=0.1))
    return pd.DataFrame(rows)
for sid in (2517,2518):
    b=ny(load(sid,"M_5")); sp,mu=SP[sid]
    cap = 14 if sid==2517 else 14
    for nbar in (1,3,6):
        for tpR in (0,2,4):
            for fade in (False,True):
                od=orb(b,nbar,cap,tpR,fade)
                tr=engine.simulate(b,od,spread=sp)
                summ(tr,b,f"{sid} orb n={nbar} tpR={tpR} fade={fade}")
