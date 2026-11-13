"""Pre-sample Bollinger-fade sims on M15 (engine), by session. usage: fx_mr.py sid:pip:spread ..."""
import sys, itertools; sys.path.insert(0,'.'); sys.path.insert(0,'agents/CHARLIE')
import numpy as np, pandas as pd
from arena import engine
from fx_tod import pre
SES={'asia 23-06':(23,6),'lon 07-12':(7,12),'ny 12-19':(12,19)}
def orders(m,p,a,b):
    c=m.close; ma=c.rolling(p['n']).mean(); sd=c.rolling(p['n']).std()
    tr=np.maximum(m.high-m.low,np.maximum((m.high-c.shift()).abs(),(m.low-c.shift()).abs())); atr=tr.rolling(14).mean()
    z=(c-ma)/sd; hr=m.time.dt.hour+m.time.dt.minute/60
    ins=((hr>=a)|(hr<b)) if a>b else ((hr>=a)&(hr<b))
    sig=ins&(z.abs()>p['k'])&atr.notna()&(m.time.dt.dayofweek<5)
    i=np.where(sig)[0]
    tp=(c-ma).abs().to_numpy()[i] if p['tp']==0 else p['tp']*atr.to_numpy()[i]
    return pd.DataFrame(dict(idx=i,side=-np.sign(z.to_numpy()[i]),kind=0,sl=p['sl']*atr.to_numpy()[i],tp=tp,max_bars=p['mb'],volume=1000.0))
def pf(tr,q=1.0):
    p=tr.pnl.to_numpy()*q
    return (len(p), p[p>0].sum()/max(1e-9,-p[p<0].sum()), p.sum()) if len(p) else (0,0,0)
if __name__=='__main__':
    grid=[dict(n=20,k=k,sl=sl,tp=tp,mb=mb) for k,sl,tp,mb in itertools.product((2.0,2.5),(1.5,3.0),(0,1.0),(6,16))]
    for a in sys.argv[1:]:
        sid,pip,spr=a.split(':'); pip=float(pip); spr=float(spr); m=pre(sid); q=(0.006257 if pip==0.01 else 1.0)
        for nm,(x,y) in SES.items():
            r=[pf(engine.simulate(m,orders(m,p,x,y),spread=spr*pip),q) for p in grid]
            pfs=np.array([v[1] for v in r]); b=int(pfs.argmax())
            g0=[pf(engine.simulate(m,orders(m,grid[b],x,y),spread=0.0),q)[1]]
            print(f"{sid} {nm:10s} sets={len(grid)} PF min/med/max={pfs.min():.2f}/{np.median(pfs):.2f}/{pfs.max():.2f} best={grid[b]} n={r[b][0]} net=${r[b][2]:.1f} (PF at zero spread {g0[0]:.2f})")
