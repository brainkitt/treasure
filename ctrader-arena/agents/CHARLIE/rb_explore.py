import sys; sys.path.insert(0,'.')
from arena.ingest import load
import numpy as np, pandas as pd
pd.set_option('display.width',250)
def feats(m, thr):
    o,h,l,c=[m[x].to_numpy() for x in ('open','high','low','close')]
    n=len(m); U=np.full(n,np.nan); L=np.full(n,np.nan); age=np.zeros(n,int); bdir=np.zeros(n)
    u=h[0]; lo=l[0]; a=0; d=0
    for i in range(n):
        if h[i]-l[i]>thr or (i>0 and m.ts.iloc[i]-m.ts.iloc[i-1]>60000):
            d=np.sign(c[i]-o[i]); a=0
            # new range anchored: after up-break, the high is the upper bound
            u=h[i] if d>0 else c[i]; lo=l[i] if d<0 else c[i]
        else:
            a+=1; u=max(u,h[i]); lo=min(lo,l[i])
        U[i]=u; L[i]=lo; age[i]=a; bdir[i]=d
    return U,L,age,bdir
for sid,thr in ((2449,35),(2450,35)):
    m=load(sid,'M_1'); U,L,age,bdir=feats(m,thr)
    c=m.close.to_numpy(); w=U-L
    df=pd.DataFrame(dict(c=c,U=U,L=L,w=w,age=age,bdir=bdir))
    df['pos']=(c-L)/np.where(w>0,w,np.nan)
    for k in (1,5,15,30,60):
        df[f'f{k}']=pd.Series(c).shift(-k)-c
    print(sid,'width by age:',df.groupby(pd.cut(df.age,[0,2,5,10,20,40,80,1000])).w.median().round(1).to_dict())
    d=df[(df.age>=10)]
    print(d.groupby(pd.cut(d.pos,[-.01,.1,.25,.75,.9,1.01]))[['f1','f5','f15','f30','f60']].agg(['mean','count']).round(2).to_string())
    # right after break: by break dir
    d=df[(df.age==0)&(df.bdir!=0)]
    print('after break, signed fwd (in break dir):', {k:round((d[f'f{k}']*d.bdir).mean(),2) for k in (1,5,15,30,60)}, len(d))
