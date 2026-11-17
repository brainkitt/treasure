"""DSI: does a low-volatility filter (HMM: up-regimes are low-vol) raise gross capture per long trade? IS = first 70%."""
import sys, numpy as np, pandas as pd
sys.path.insert(0,'/home/user/treasure/ctrader-arena'); sys.path.insert(0,'/home/user/treasure/ctrader-arena/agents/VOL')
import strategy as S
from arena.ingest import load
from arena import engine
def pf(x): return x[x>0].sum()/-x[x<0].sum()
for sid,spw in ((2469,4.05),(2470,10.16),(2464,3.77)):
    b=load(sid,'M_5'); n=int(len(b)*.7); b=b.iloc[:n].reset_index(drop=True)
    rng=(b.high-b.low).to_numpy(); r6=pd.Series(rng).rolling(6).mean()/pd.Series(rng).rolling(288).median()
    for N,thr in ((6,0.8),(4,0.7),(12,0.6)):
        o=S.signals(b,{"N":N,"thr":thr,"sl_atr":3.0,"trail_atr":2.0,"max_bars":36},{"min_units":1.0}); o['volume']=1.0
        out=[]
        for vmax in (99,1.2,1.0,0.8,0.6):
            oo=o[r6.to_numpy()[o.idx]<vmax]
            if len(oo)<30: out.append(f"v<{vmax}: n<30"); continue
            tr=engine.simulate(b,oo,spread=0,slip=0.1); x=tr.pnl.to_numpy()
            tw=engine.simulate(b,oo,spread=spw,slip=0.1).pnl.to_numpy()
            out.append(f"v<{vmax}: n={len(x)} g/tr={x.mean():.2f} PF@{spw}={pf(tw):.2f}")
        print(sid,N,thr,' | '.join(out))
