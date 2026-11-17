"""H1 regime-hold grid with swap. usage: grid3.py sid spread [swap_per_unit_night]"""
import sys, itertools, numpy as np, pandas as pd
sys.path.insert(0,'agents/VOL'); import strategy as S
from arena.ingest import load
from arena import engine
from arena.evaluate2 import apply_costs
sid=int(sys.argv[1]); sp=float(sys.argv[2]); sw=float(sys.argv[3]) if len(sys.argv)>3 else 1.5
b=load(sid,'H_1'); n=int(len(b)*0.7)
spec={'min_units':0.1,'swap_long':sw,'swap_short':sw,'triple_weekday':4,'rollover_hour_utc':21}
grid=list(itertools.product([2,3,6,12],[0.5,0.7,0.85],[2.0,3.0,5.0],[2.5,4.0,6.0],[12,48,96],[False,True]))
rows=[]
for N,thr,sl,trl,H,sh in grid:
    p=dict(bar_sec=3600,N=N,thr=thr,sl_atr=sl,trail_atr=trl,max_bars=H,shorts=sh,atr_n=20)
    od=S.signals(b,p,spec); tr=apply_costs(engine.simulate(b,od,spread=sp),od,spec)
    for part,sel in (('is',tr.entry_bar<n),('oos',tr.entry_bar>=n)):
        x=tr.pnl[sel].to_numpy()
        if len(x)<5: rows.append(dict(N=N,thr=thr,sl=sl,trail=trl,H=H,shorts=sh,part=part,n=len(x),pf=np.nan,t=np.nan)); continue
        gl=-x[x<0].sum(); rows.append(dict(N=N,thr=thr,sl=sl,trail=trl,H=H,shorts=sh,part=part,n=len(x),pf=x[x>0].sum()/gl if gl>0 else 99,t=x.mean()/x.std()*np.sqrt(len(x))))
df=pd.DataFrame(rows); w=df.pivot_table(index=['N','thr','sl','trail','H','shorts'],columns='part',values=['n','pf','t']).reset_index()
w.columns=['_'.join(c).strip('_') for c in w.columns]
print(sid,'H1 bars',len(b),b.time.iloc[0],'IS end',b.time.iloc[n],'spread',sp,'sets',len(grid))
print('IS share PF>1 %.2f PF>1.2 %.2f'%((w.pf_is>1).mean(),(w.pf_is>1.2).mean()))
top=w.sort_values('t_is',ascending=False).head(8); print(top.round(2).to_string())
print('OOS PF of IS-top10 median: %.2f ; corr(IS t, OOS t)=%.2f'%(w.sort_values('t_is',ascending=False).head(10).pf_oos.median(), w[['t_is','t_oos']].corr().iloc[0,1]))
w.to_csv(f'agents/VOL/research/grid3_{sid}.csv',index=False)
