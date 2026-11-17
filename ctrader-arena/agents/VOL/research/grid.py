import sys, itertools, numpy as np, pandas as pd
sys.path.insert(0,'agents/VOL'); import strategy as S
from arena.ingest import load
from arena import engine
sid=int(sys.argv[1]); sp=float(sys.argv[2])
b=load(sid,'M_5'); n=int(len(b)*0.7); bi=b.iloc[:n].reset_index(drop=True)
spec={'min_units':0.1}
rows=[]
grid=list(itertools.product([4,6,9],[0.5,0.65,0.8],[2.0,3.0],[1.0,1.5,2.5],[12,24,48],[False,True]))
for N,thr,sl,trl,H,sh in grid:
    p=dict(N=N,thr=thr,sl_atr=sl,trail_atr=trl,max_bars=H,shorts=sh)
    od=S.signals(bi,p,spec); tr=engine.simulate(bi,od,spread=sp)
    x=tr.pnl.to_numpy(); gl=-x[x<0].sum()
    rows.append(dict(N=N,thr=thr,sl=sl,trail=trl,H=H,shorts=sh,n=len(x),pf=x[x>0].sum()/gl,exp=x.mean(),t=x.mean()/x.std()*np.sqrt(len(x))))
df=pd.DataFrame(rows); df.to_csv(f'agents/VOL/research/grid_{sid}_{sp}.csv',index=False)
print(len(grid),'param sets; IS bars',n, bi.time.iloc[0], bi.time.iloc[-1])
for sh in (False,True):
    print(df[df.shorts==sh].sort_values('t',ascending=False).head(10).round(3).to_string())
print('share of sets with PF>1:', (df.pf>1).mean().round(2), ' PF>1.2:',(df.pf>1.2).mean().round(2))
