"""Anchored walk-forward: for each of 5 test folds (last 5/7 of data split equally after an initial 2/7 train block),
re-select the parameter set with the best in-sample t-stat (min 100 trades) on ALL data before the fold, then test."""
import sys, itertools, numpy as np, pandas as pd
sys.path.insert(0,'agents/VOL'); import strategy as S
from arena.ingest import load
from arena import engine
sid=int(sys.argv[1]); sp=float(sys.argv[2]); shorts_opts=[s=='1' for s in sys.argv[3].split(',')] if len(sys.argv)>3 else [False]
b=load(sid,'M_5'); spec={'min_units':0.1}
grid=list(itertools.product([4,6,9],[0.5,0.65,0.8],[2.0,3.0],[1.0,1.5,2.5],[12,24,48],shorts_opts))
def run(p, lo, hi):
    od=S.signals(b,p,spec); tr=engine.simulate(b,od,spread=sp)
    tr=tr[(tr.entry_bar>=lo)&(tr.entry_bar<hi)]; return tr.pnl.to_numpy()
# precompute full-sample trades per param set once (signals are causal, so slicing by entry bar is valid)
cache={}
for g in grid:
    p=dict(N=g[0],thr=g[1],sl_atr=g[2],trail_atr=g[3],max_bars=g[4],shorts=g[5])
    od=S.signals(b,p,spec); tr=engine.simulate(b,od,spread=sp); cache[g]=(p,tr.entry_bar.to_numpy(),tr.pnl.to_numpy())
n=len(b); edges=np.linspace(int(n*2/7), n, 6).astype(int)
rows=[]
for k in range(5):
    lo,hi=edges[k],edges[k+1]; best=None
    for g,(p,eb,x) in cache.items():
        xi=x[eb<lo]
        if len(xi)<100: continue
        t=xi.mean()/xi.std()*np.sqrt(len(xi))
        if best is None or t>best[0]: best=(t,g)
    p,eb,x=cache[best[1]]; xo=x[(eb>=lo)&(eb<hi)]
    gl=-xo[xo<0].sum()
    rows.append(dict(fold=k+1,test_from=str(b.time.iloc[lo].date()),test_to=str(b.time.iloc[hi-1].date()),chosen=str(best[1]),is_t=round(best[0],2),
                     oos_n=len(xo),oos_pf=round(xo[xo>0].sum()/gl,3) if gl>0 else 99,oos_net=round(xo.sum(),2),oos_t=round(xo.mean()/xo.std()*np.sqrt(len(xo)),2)))
print(pd.DataFrame(rows).to_string()); print(len(grid),'param sets per refit')
