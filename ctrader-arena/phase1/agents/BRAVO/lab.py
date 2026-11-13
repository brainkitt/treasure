import numpy as np, pandas as pd, hmm
from arena.ingest import load
from arena import engine

def pstats(tr):
    p=tr.pnl.to_numpy()
    if len(p)==0: return "no trades"
    gp=p[p>0].sum(); gl=-p[p<0].sum(); eq=np.cumsum(p); dd=(np.maximum.accumulate(np.r_[0,eq])[1:]-eq).max()
    return f"n={len(p):4d} PF={gp/max(gl,1e-9):5.2f} net={p.sum():7.2f} win={100*(p>0).mean():3.0f}% dd={dd:5.2f} worst={p.min():5.2f} avg={p.mean():.3f}"

def filt2(m1, par):
    """causal 2-state filter on M1 log returns (bp). returns P(calm/bull) per bar (aligned to bar close)."""
    c=m1.close.to_numpy(); r=np.zeros(len(c)); r[1:]=np.diff(np.log(c))*1e4
    mu=np.array([par['mu_b'],par['mu_s']]); sd=np.array([par['sd_b'],par['sd_s']])
    A=np.array([[1-1/par['dur_b'],1/par['dur_b']],[1/par['dur_s'],1-1/par['dur_s']]])
    return hmm.filt(r,mu,sd,A)[:,0]

def orders_from_state(pb, par, vol):
    """enter long at close of bar i if pb>=hi and flat-ish; engine drops overlapping signals, so emit signal on every bar where pb>=hi"""
    idx=np.where(pb>=par['hi'])[0]
    return pd.DataFrame({"idx":idx,"side":1,"kind":0,"sl":par['sl'],"tp":par.get('tp',0.0),"max_bars":par.get('mb',0),"trail":par.get('trail',0.0),"volume":vol})

PAR30=dict(mu_b=0.56,mu_s=-0.42,sd_b=1.39,sd_s=3.42,dur_b=25.0,dur_s=33.5)
def split_is(sid):
    m=load(sid); days=sorted(m.time.dt.floor('D').unique()); split=days[int(len(days)*0.7)]
    n=int((m.time<split).sum())
    return m, m.iloc[:n].reset_index(drop=True), m.iloc[n:].reset_index(drop=True)
