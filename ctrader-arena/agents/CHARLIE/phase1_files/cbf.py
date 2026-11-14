import sys; sys.path.insert(0,'.')
from arena.ingest import load
import numpy as np, pandas as pd
sid=int(sys.argv[1]); 
m=load(sid,'M_1'); o,h,l,c=[m[x].to_numpy() for x in ('open','high','low','close')]
d=c-o; n=len(m)
drift=np.median(np.abs(d)); print('n',n,'median |d|',round(drift,3), 'mean d',round(d.mean(),4),'t',round(d.mean()/d.std()*np.sqrt(n),2))
tol=0.35*drift
cd=(np.abs(d+drift)<tol)&(h-o<tol)      # clean down-drift bar
cu=(np.abs(d-drift)<tol)&(o-l<tol)
st=np.where(cd,-1,np.where(cu,1,0))
print('clean dn %.2f clean up %.2f other %.2f'%(cd.mean(),cu.mean(),(st==0).mean()))
nxt=np.r_[d[1:],np.nan]
def rep(mask,name,sign):
    x=nxt[mask]*sign; x=x[~np.isnan(x)]
    if len(x)<5: return
    print(f"{name:28s} n={len(x):5d} next-bar mean in drift dir={x.mean():+.3f}±{x.std()/np.sqrt(len(x)):.3f}  P(cont clean)={np.mean(np.abs(x-drift)<tol):.2f} P(adverse<-1)={np.mean(x<-1):.3f} P(fav>1)={np.mean(x>1):.3f}")
rep(cd,'after clean down',-1); rep(cu,'after clean up',1)
for k in (2,3,5,8):
    run_d=pd.Series(cd).rolling(k).sum().to_numpy()==k; run_u=pd.Series(cu).rolling(k).sum().to_numpy()==k
    rep(run_d,f'after {k} clean down',-1); rep(run_u,f'after {k} clean up',1)
# after a spike bar (|d|>3*drift): next bars in spike direction
sp=np.abs(d)>3*drift
for k in (1,2,3,5,10):
    f=np.array([ (c[i+k]-c[i])*np.sign(d[i]) for i in np.where(sp)[0] if i+k<n])
    print(f"after spike(n={len(f)}) fwd{k} in spike dir: {f.mean():+.3f}±{f.std()/np.sqrt(len(f)):.3f}")
# transition matrix of st
print(pd.crosstab(st[:-1],st[1:],normalize='index').round(2).to_string())
