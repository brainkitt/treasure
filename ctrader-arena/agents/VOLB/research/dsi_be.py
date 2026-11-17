import sys, numpy as np, pandas as pd
sys.path.insert(0,'/home/user/treasure/ctrader-arena'); sys.path.insert(0,'/home/user/treasure/ctrader-arena/agents/VOL')
import strategy as S
from arena.ingest import load
from arena import engine
def pf(x): return x[x>0].sum()/-x[x<0].sum()
for sid in (2464,2469,2470):
    b=load(sid,'M_5')
    for shorts in (False,True):
        o=S.signals(b,{"shorts":shorts},{"min_units":1.0}); o['volume']=1.0
        row=[]
        for sp in (0.0,0.5,1.0,1.5,2.0,3.0,4.0):
            tr=engine.simulate(b,o,spread=sp,slip=0.1); x=tr.pnl.to_numpy()
            row.append(f"{sp}:{pf(x):.2f}")
        tr=engine.simulate(b,o,spread=0,slip=0.1)
        print(sid,'L+S' if shorts else 'L  ',len(tr),'gross/trade %.2f'%tr.pnl.mean(),' '.join(row))
