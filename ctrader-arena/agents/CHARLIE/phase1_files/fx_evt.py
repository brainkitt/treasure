"""Pre-sample event study: Donchian-N cross on M15 -> forward return in break direction, by local-session bucket."""
import sys; sys.path.insert(0,'.'); sys.path.insert(0,'agents/CHARLIE')
import numpy as np, pandas as pd
from fx_tod import pre
BUCK=[('Tokyo 00-03',0,3),('Tokyo 03-06',3,6),('Lon 06-08',6,8),('Lon 08-11',8,11),('mid 11-12.5',11,12.5),('NY 12.5-15',12.5,15),('NY 15-18',15,18),('late 18-20.5',18,20.5)]
def study(sid,pip,N,ks=(4,8,16)):
    m=pre(sid); c=m.close.to_numpy(); h=m.high.to_numpy(); l=m.low.to_numpy(); n=len(m)
    hh=pd.Series(h).rolling(N).max().shift(1).to_numpy(); ll=pd.Series(l).rolling(N).min().shift(1).to_numpy()
    up=(c>hh)&(np.r_[False,c[:-1]<=hh[:-1]]); dn=(c<ll)&(np.r_[False,c[:-1]>=ll[:-1]])
    sg=np.where(up,1,np.where(dn,-1,0))
    ts=m.ts.to_numpy(); hr=(m.time.dt.hour+m.time.dt.minute/60).to_numpy()   # UTC (pre-sample is all summer time)
    out=[]
    for name,a,b in BUCK:
        idx=np.where((sg!=0)&(hr>=a)&(hr<b))[0]; s=f"{name:13s} n={len(idx):4d}"
        for k in ks:
            ok=[i for i in idx if i+k<n and ts[i+k]-ts[i]==k*900000]
            f=np.array([(c[i+k]-c[i])*sg[i]/pip for i in ok]); hf=len(f)//2
            if len(f)>20: s+=f" | f{k}: {f.mean():+.2f}±{f.std()/np.sqrt(len(f)):.2f} (h1 {f[:hf].mean():+.1f} h2 {f[hf:].mean():+.1f})"
        out.append(s)
    return out
if __name__=='__main__':
    sid,pip=sys.argv[1].split(':'); 
    for N in map(int,sys.argv[2:]):
        print(f"-- {sid} Donchian N={N} (M15), forward pips in break direction"); print('\n'.join(study(sid,float(pip),N)))
