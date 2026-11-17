"""Label each live spread sample with the regime state visible in M1 bars just before it."""
import numpy as np, pandas as pd
from arena.ingest import load
s=pd.read_csv('agents/VOL/research/spreads.csv')
s['spread']=(s.ask-s.bid)/1e5; s['t']=pd.to_datetime(s.ts_ms,unit='ms')
rows=[]
for sid,g in s.groupby('sid'):
    b=load(sid,'M_1'); c=b.close.to_numpy(); t=b.time.to_numpy()
    rng=(b.high-b.low).to_numpy()
    for _,r in g.iterrows():
        k=np.searchsorted(t, np.datetime64(r.t.floor('min')))-1  # last fully closed M1 bar
        if k<20: continue
        net10=c[k]-c[k-10]; path=np.abs(np.diff(c[k-10:k+1])).sum(); er=net10/path
        rows.append(dict(sid=sid,t=r.t,spread=r.spread,net10=net10,er10=er,rng10=rng[k-9:k+1].mean(),net20=c[k]-c[k-20]))
d=pd.DataFrame(rows); pd.set_option('display.width',200)
print(d.round(2).to_string())
