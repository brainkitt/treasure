import sys, numpy as np, pandas as pd
from arena.ingest import load
def vr(r,q):
    r=r-r.mean(); s=pd.Series(r).rolling(q).sum().dropna().to_numpy()
    return s.var()/(q*r.var())
for sid in sys.argv[2:]:
    b=load(sid,sys.argv[1]); c=b.close.to_numpy(); d=np.diff(c)
    ac=[np.corrcoef(d[:-k],d[k:])[0,1] for k in (1,2,3,5,10)]
    print(sid,len(b),'px %.1f'%c[-1],'sd/bar %.3f'%d.std(),'mean %.4f t=%.2f'%(d.mean(),d.mean()/d.std()*np.sqrt(len(d))),
      'AC',' '.join('%.3f'%a for a in ac),'VR',' '.join('%.2f'%vr(d,q) for q in (2,5,10,20,30,60)), 'N^-.5=%.3f'%(1/np.sqrt(len(d))))
