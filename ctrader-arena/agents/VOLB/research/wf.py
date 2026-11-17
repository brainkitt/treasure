"""Anchored walk-forward for the finalist (DSI30 long-only), re-fit per fold on all data before the fold.
Grid 4x4x3x2 = 96 sets. Reported at the official spread 10.16 and, for information only, at 4.0."""
import sys, itertools, json, numpy as np, pandas as pd
sys.path.insert(0,'/home/user/treasure/ctrader-arena'); sys.path.insert(0,'..')
import strategy as S
from arena.ingest import load
from arena import engine
def pf(x): return x[x>0].sum()/-x[x<0].sum() if (x<0).any() else 99.
b=load(2470,'M_5'); spec={"min_units":0.1}
grid=dict(N=[4,6,8,12],thr=[0.6,0.7,0.8,0.9],sl_atr=[2.0,2.5,3.0],trail_atr=[1.5,2.5])
sets=[dict(zip(grid,v)) for v in itertools.product(*grid.values())]
res={}
for sp in (10.16,4.0):
    trs=[]
    for p in sets:
        tr=engine.simulate(b,S.signals(b,p,spec),spread=sp,slip=0.1); trs.append(tr)
    edges=b.time.iloc[np.linspace(0,len(b)-1,6).astype(int)].to_numpy()
    rows=[]
    for k in range(1,5):   # folds 2..5 are OOS; fold 1 is the first training block
        a,e=edges[k],edges[k+1]
        isp=[pf(t[t.entry_time<a].pnl.to_numpy()) for t in trs]
        best=int(np.argmax(isp)); t=trs[best]
        o=t[(t.entry_time>=a)&(t.entry_time<e)].pnl.to_numpy()
        rows.append(dict(fold=k+1,start=str(pd.Timestamp(a).date()),end=str(pd.Timestamp(e).date()),best=sets[best],is_pf=round(isp[best],2),
                         oos_pf=round(pf(o),2),oos_trades=len(o),oos_net=round(float(o.sum()),2)))
    allpf=[pf(t.pnl.to_numpy()) for t in trs]
    res[sp]=dict(folds=rows,share_sets_pf_gt1=float(np.mean(np.array(allpf)>1)),median_pf=float(np.median(allpf)))
    print(f"spread {sp}: sets PF>1 {res[sp]['share_sets_pf_gt1']:.0%} median PF {res[sp]['median_pf']:.2f}")
    for r in rows: print('  ',r)
# neighbour table at official spread around default
d=[]
for p in sets:
    if p['sl_atr']==2.5 and p['trail_atr']==1.5:
        x=engine.simulate(b,S.signals(b,p,spec),spread=10.16,slip=0.1).pnl.to_numpy()
        y=engine.simulate(b,S.signals(b,p,spec),spread=4.0,slip=0.1).pnl.to_numpy()
        d.append(dict(N=p['N'],thr=p['thr'],trades=len(x),pf_at_10_16=round(pf(x),2),pf_at_4_0=round(pf(y),2)))
json.dump(dict(wf=res,neighbours=d),open('wf.json','w'),indent=1,default=str)
print(pd.DataFrame(d).to_string(index=False))
