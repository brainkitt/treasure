import sys, numpy as np
from arena.ingest import load
def vr(r,k):
    rk=np.convolve(r,np.ones(k),'valid')
    return rk.var()/(k*r.var())
for sid in sys.argv[1:]:
    m=load(int(sid)); c=np.log(m.close.to_numpy()); r=np.diff(c)
    print(f"== {sid} n={len(m)} px={m.close.iloc[-1]:.2f} sd1m={r.std():.2e} ({r.std()*m.close.iloc[-1]:.3f} px) mean/sd={r.mean()/r.std()*np.sqrt(len(r)):.2f}t  kurt={((r-r.mean())**4).mean()/r.var()**2:.1f}")
    print(" acf", " ".join(f"{k}:{np.corrcoef(r[:-k],r[k:])[0,1]:+.3f}" for k in (1,2,3,4,5,10,15,20,30,60)), " (se %.3f)"%(1/np.sqrt(len(r))))
    print(" VR ", " ".join(f"{k}:{vr(r,k):.3f}" for k in (2,3,5,10,15,20,30,60,120)))
    a=np.abs(r); print(" |r| acf", " ".join(f"{k}:{np.corrcoef(a[:-k],a[k:])[0,1]:+.3f}" for k in (1,2,5,10,30,60,120)))
    # bar-construction: open vs prev close
    g=(m.open.to_numpy()[1:]-m.close.to_numpy()[:-1]); print(" gap open-prevclose mean %.4f sd %.4f; range mean %.3f"%(g.mean(),g.std(),(m.high-m.low).mean()))
