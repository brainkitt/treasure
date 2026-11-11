"""Hazard / memorylessness tests on M1 bars for spike indices.
usage: python agents/CHARLIE/hazard.py sid:dir[:k] ...   dir=+1 spikes up (Boom), -1 down (Crash)"""
import sys; sys.path.insert(0,'.')
from arena.ingest import load
import numpy as np, pandas as pd
for a in sys.argv[1:]:
    p=a.split(':'); sid=p[0]; d=int(p[1]); K=float(p[2]) if len(p)>2 else 4.0
    m=load(sid,'M_1'); c=m.close.to_numpy(); o=m.open.to_numpy()
    r=np.log(c[1:]/c[:-1])*1e4*d      # spike direction positive
    gapok=(np.diff(m.ts.to_numpy())==60000)
    med=np.median(np.abs(r)); thr=K*med
    sp=r>thr
    n=len(r); rate=sp.mean()
    # bars since last spike
    since=np.zeros(n,int); s=10**6
    for i in range(n):
        since[i]=s; s=0 if sp[i] else s+1
    ok=since<10**5
    df=pd.DataFrame(dict(r=r,sp=sp,since=since))[ok]
    b=pd.cut(df.since,[-1,0,1,2,4,8,16,32,64,10**5])
    g=df.groupby(b,observed=True).agg(n=('sp','size'),haz=('sp','mean'),ret=('r','mean'),drift=('r',lambda x: x[x<=thr].mean()))
    ct=pd.crosstab(b[ok[ok]].values if False else b, df.sp)
    ct=ct.loc[ct.sum(1)>0]; ex=np.outer(ct.sum(1),ct.sum(0))/ct.values.sum(); x2=((ct.values-ex)**2/ex).sum(); dof=len(ct)-1
    chi=(x2,(x2-dof)/np.sqrt(2*dof))
    # serial dependence of non-spike drift
    ns=r[~sp]
    print(f"\n{sid} dir={d} n={n} thr={thr:.2f}bp spike_rate={rate:.3f}/bar mean_spike={r[sp].mean():.1f}bp mean_drift={ns.mean():.3f}bp  total_mean={r.mean():.3f}±{r.std()/np.sqrt(n):.3f}  chi2={chi[0]:.1f} z={chi[1]:.2f}")
    print(g.round(3).T.to_string())
    # spike size vs since
    if sp.sum()>20:
        x=df[df.sp]; print('corr(spike size, bars since)=%.3f (n=%d)  lag1 corr of spike indicator=%.3f'%(np.corrcoef(x.r,np.minimum(x.since,100))[0,1],len(x),np.corrcoef(sp[1:],sp[:-1])[0,1]))
