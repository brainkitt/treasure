import sys, itertools, numpy as np, pandas as pd
sys.path.insert(0,'agents/VOL'); import strategy as S
from arena.ingest import load
from arena import engine
from arena.engine import resample
sid=int(sys.argv[1]); sp=float(sys.argv[2]); tf=int(sys.argv[3]) if len(sys.argv)>3 else 1
b=load(sid,'M_5')
if tf>1:  # derive higher TF bars from M5 (causal)
    b['ts']=b.ts; b=resample(b,tf).drop(columns='m1_idx'); b['time']=pd.to_datetime(b.time)
n=int(len(b)*float(__import__("os").environ.get("ISF","0.7"))); bi=b.iloc[:n].reset_index(drop=True)
rows=[]; grid=list(itertools.product([3,6,12],[0.5,0.7,0.85],[3.0,5.0],[2.5,4.0,6.0],[24,96,288],[False,True]))
for N,thr,sl,trl,H,sh in grid:
    p=dict(bar_sec=300*max(1,tf//5) if tf>5 else 300,N=N,thr=thr,sl_atr=sl,trail_atr=trl,max_bars=H,shorts=sh)
    od=S.signals(b,p,{'min_units':0.1}); tra=engine.simulate(b,od,spread=sp); tr=tra[tra.entry_bar<n]; xo=tra.pnl[tra.entry_bar>=n].to_numpy(); x=tr.pnl.to_numpy()
    if len(x)<20: continue
    gl=-x[x<0].sum(); rows.append(dict(N=N,thr=thr,sl=sl,trail=trl,H=H,shorts=sh,n=len(x),pf=x[x>0].sum()/gl,gross_pts=(x.mean()/0.1)+ (sp if True else 0),t=x.mean()/x.std()*np.sqrt(len(x)),n_oos=len(xo),pf_oos=(xo[xo>0].sum()/-xo[xo<0].sum()) if (xo<0).any() else 99))
df=pd.DataFrame(rows); print(sid,'tf',tf,'sp',sp,len(grid),'sets; PF>1 share %.2f PF>1.2 %.2f'%((df.pf>1).mean(),(df.pf>1.2).mean()))
print(df.sort_values('t',ascending=False).head(6).round(2).to_string()); print('OOS share PF>1 %.2f, median OOS PF of IS top10 %.2f, corr(pf_is,pf_oos) %.2f'%((df.pf_oos>1).mean(), df.sort_values('t',ascending=False).head(10).pf_oos.median(), df[['pf','pf_oos']].corr().iloc[0,1])); df.to_csv('agents/VOL/research/grid2_%d_tf%d.csv'%(sid,tf),index=False)
