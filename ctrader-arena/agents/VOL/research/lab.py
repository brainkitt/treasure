import numpy as np, pandas as pd
from arena.ingest import load
from arena import engine

def gapmask(b, per_s):
    return (b.time.diff().dt.total_seconds().fillna(per_s).to_numpy() <= per_s*1.5)

def feats(b, N, atrn=20):
    c=b.close.to_numpy(); d=np.abs(np.diff(c,prepend=c[0]))
    path=pd.Series(d).rolling(N).sum().to_numpy()
    net=c-np.concatenate([np.full(N,np.nan),c[:-N]])
    er=net/np.maximum(path,1e-9)
    tr=(b.high-b.low).to_numpy()
    atr=pd.Series(tr).rolling(atrn).mean().to_numpy()
    return c, er, net, atr

def orders(b, p, per_s=300, vol=0.1):
    c,er,net,atr=feats(b,p['N'])
    ok=gapmask(b,per_s); okN=pd.Series(ok).rolling(p['N']+1).min().fillna(0).to_numpy().astype(bool)
    sig=np.zeros(len(c))
    up=(er>p['thr'])&(net>p.get('k',0)*atr); dn=(er<-p['thr'])&(-net>p.get('k',0)*atr)
    sig[up]=1
    if p.get('shorts',True): sig[dn]=-1
    sig[~okN]=0; sig[np.isnan(atr)]=0
    i=np.where(sig!=0)[0]; i=i[i<len(c)-1]
    return pd.DataFrame({'idx':i,'side':sig[i],'kind':0,'sl':p['sl']*atr[i],'tp':p.get('tp',0)*atr[i],
        'max_bars':p['H'],'trail':p.get('trail',0)*atr[i],'volume':vol})

def run(b, od, spread, slip=0.0):
    return engine.simulate(b, od, spread=spread, slip=slip)

def summ(tr):
    p=tr.pnl.to_numpy()
    if len(p)<3: return dict(n=len(p))
    gl=-p[p<0].sum()
    return dict(n=len(p), pf=p[p>0].sum()/gl if gl>0 else 99, net=p.sum(), exp=p.mean(), t=p.mean()/p.std()*np.sqrt(len(p)))
