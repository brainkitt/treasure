import sys, numpy as np
from arena.ingest import load
sid=int(sys.argv[1]); per=sys.argv[2] if len(sys.argv)>2 else 'M_5'
b=load(sid,per); c=b.close.to_numpy(); d=np.diff(c)
print(sid, per, len(b), b.time.iloc[0], b.time.iloc[-1], 'sd/bar %.3f'%d.std(), 'px %.1f'%c[-1])
for half in (0,1):
  cc = c[:len(c)//2] if half==0 else c[len(c)//2:]
  print(' half',half)
  for L in [1,2,3,6,12]:
    row=[]
    for H in [1,2,3,6,12]:
        i=np.arange(L,len(cc)-H,H); g=np.sign(cc[i]-cc[i-L])*(cc[i+H]-cc[i])
        row.append('%6.2f(t%4.1f)'%(g.mean(),g.mean()/g.std()*np.sqrt(len(g))))
    print(' L',L,' '.join(row))
