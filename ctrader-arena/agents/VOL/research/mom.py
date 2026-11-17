import sys, numpy as np, pandas as pd
from arena.ingest import load
sid, per = sys.argv[1], sys.argv[2]
b=load(sid,per); c=b.close.to_numpy()
print(sid, per, len(b), b.time.iloc[0], b.time.iloc[-1])
for L in [5,10,15,20,30,45,60,90,120]:
    row=[]
    for H in [5,10,20,30,60]:
        i=np.arange(L, len(c)-H, H)  # non-overlapping entries
        s=np.sign(c[i]-c[i-L]); f=c[i+H]-c[i]
        g=s*f
        row.append('%6.2f(t%4.1f)'%(g.mean(), g.mean()/g.std()*np.sqrt(len(g))))
    print('L=%3d'%L, ' '.join(row))
