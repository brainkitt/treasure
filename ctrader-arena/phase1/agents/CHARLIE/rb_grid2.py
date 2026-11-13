import sys, itertools; sys.path.insert(0,'.'); sys.path.insert(0,'agents/CHARLIE')
from arena.ingest import load
from arena import engine
import numpy as np, pandas as pd, rbcore
sid=int(sys.argv[1]); spread=float(sys.argv[2]); vol=0.01
m=load(sid,'M_1'); days=sorted(m.time.dt.floor('D').unique()); split=days[int(len(days)*0.7)]
def st(tr):
    p=tr.pnl.to_numpy()
    if len(p)<5: return (0,0,0,0,0)
    gp=p[p>0].sum(); gl=-p[p<0].sum(); eq=np.cumsum(p); dd=(np.maximum.accumulate(np.r_[0,eq])[1:]-eq).max()
    return (len(p), gp/max(gl,1e-9), p.sum(), dd, p.min())
rows=[]
grid=list(itertools.product((1,2,4,8),(6,10,15,25),(3,5,10,20,60),(0,1),(1,-1)))
for near,sl,mb,tr_on,d in grid:
    p=dict(thr=30,near=near,sl=sl,mb=mb,trail=sl if tr_on else 0,dir=d)
    od=rbcore.orders(m,p,vol); tr=engine.simulate(m,od,spread=spread,gap_sl=True)
    a=st(tr[tr.entry_time<split]); b=st(tr[tr.entry_time>=split])
    rows.append(dict(dir=d,near=near,sl=sl,mb=mb,trail=tr_on,n_is=a[0],pf_is=round(a[1],2),net_is=round(a[2],1),dd_is=round(a[3],1),worst=round(min(a[4],b[4]),2),n_oos=b[0],pf_oos=round(b[1],2),net_oos=round(b[2],1)))
df=pd.DataFrame(rows); df.to_csv(f'agents/CHARLIE/grid_{sid}.csv',index=False)
pd.set_option('display.width',250)
print('combos',len(df)); 
for d in (1,-1):
    x=df[df.dir==d]; print('dir',d,'pf_is quantiles',x.pf_is.quantile([0,.25,.5,.75,1]).round(2).tolist(),'pf_oos',x.pf_oos.quantile([0,.25,.5,.75,1]).round(2).tolist(),'corr(is,oos)=%.2f'%np.corrcoef(x.pf_is,x.pf_oos)[0,1])
print(df.sort_values('pf_is',ascending=False).head(12).to_string(index=False))
