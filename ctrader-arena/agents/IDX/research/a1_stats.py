import numpy as np, pandas as pd
from arena.ingest import load
for s in (2517,2521,2522):
    b=load(s,'H_1')
    b['ny']=b.time.dt.tz_localize('UTC').dt.tz_convert('America/New_York')
    b['h']=b.ny.dt.hour
    b['r']=np.log(b.close/b.open)*1e4   # bp, intrabar
    n=len(b); cut=int(n*0.7)
    is_,oo=b.iloc[:cut],b.iloc[cut:]
    g1=is_.groupby('h').r.agg(['mean','std','count']); g2=oo.groupby('h').r.mean()
    g1['t']=g1['mean']/(g1['std']/np.sqrt(g1['count'])); g1['oos']=g2
    print(s, 'IS', is_.time.iloc[0].date(), is_.time.iloc[-1].date()); print(g1.round(2).to_string())
    # atr in points
    tr=(b.high-b.low); print('median H1 range pts', tr.median(), 'price', b.close.iloc[-1])
