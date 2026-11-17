import sys, numpy as np, pandas as pd
from arena.ingest import load
sid=int(sys.argv[1]); per=sys.argv[2]
b=load(sid,per); c=b.close.to_numpy(); n=len(c)
gapok = (b.time.diff().dt.total_seconds().fillna(60).to_numpy() <= {'M_1':60,'M_5':300}[per]*1.5)
days=(b.time.iloc[-1]-b.time.iloc[0]).days
for N in [3,6,10,15,20]:
    d=np.abs(np.diff(c,prepend=c[0])); path=pd.Series(d).rolling(N).sum().to_numpy()
    net=c-np.roll(c,N); er=net/np.maximum(path,1e-9)
    for thr in [0.3,0.5,0.7]:
        row=[]
        for H in [3,6,12,24]:
            i=np.where((np.abs(er)>thr))[0]; i=i[(i>N)&(i<n-H)]
            # non-overlap
            keep=[]; last=-10**9
            for k in i:
                if k>=last+H: keep.append(k); last=k
            i=np.array(keep); g=np.sign(er[i])*(c[i+H]-c[i])
            row.append('%5.2f(t%4.1f,n/d%4.0f)'%(g.mean(),g.mean()/g.std()*np.sqrt(len(g)),len(g)/days))
        print('N%2d thr%.1f'%(N,thr),' '.join(row))
