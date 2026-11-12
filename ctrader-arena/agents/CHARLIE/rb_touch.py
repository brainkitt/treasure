import sys; sys.path.insert(0,'.')
from arena.ingest import load
import numpy as np, pandas as pd
sid=int(sys.argv[1]); thr=30
m=load(sid,'M_1'); o,h,l,c=[m[x].to_numpy() for x in ('open','high','low','close')]
n=len(m); gap=np.r_[False,np.diff(m.ts.to_numpy())>60000]; rng=h-l
U=np.full(n,np.nan); L=np.full(n,np.nan); age=np.zeros(n,int); knownU=np.zeros(n,bool); knownL=np.zeros(n,bool)
u=lo=np.nan; a=0; ku=kl=False
for i in range(n):
    if gap[i]: u=h[i]; lo=l[i]; a=0; ku=kl=False
    elif rng[i]>thr:
        up=c[i]>o[i]; a=0
        if up: u=h[i]; lo=c[i]-1; ku=True; kl=False     # after up-break upper bound = break high (exact)
        else: lo=l[i]; u=c[i]+1; kl=True; ku=False
    else:
        a+=1
        if h[i]>u: u=h[i]
        if l[i]<lo: lo=l[i]
    U[i]=u; L[i]=lo; age[i]=a; knownU[i]=ku; knownL[i]=kl
res=[]
for name,mask,sgn in (('at known U (after up-break), dist<=2',knownU&(U-c<=2)&(age>=1),1),('at known L (after dn-break), dist<=2',knownL&(c-L<=2)&(age>=1),-1),
                      ('known U, dist 3..8',knownU&(U-c>2)&(U-c<=8)&(age>=1),1),('known L, dist 3..8',knownL&(c-L>2)&(c-L<=8)&(age>=1),-1),
                      ('known U, dist>15',knownU&(U-c>15)&(age>=1),1),('known L, dist>15',knownL&(c-L>15)&(age>=1),-1)):
    idx=np.where(mask)[0]
    s=f"{name:38s} n={len(idx):5d}"
    for k in (1,3,10,30):
        f=np.array([(c[i+k]-c[i])*sgn for i in idx if i+k<n and not gap[i+1:i+k+1].any()])
        s+=f" | f{k} toward-break {f.mean():+.2f}±{f.std()/np.sqrt(len(f)):.2f}"
    print(s)
