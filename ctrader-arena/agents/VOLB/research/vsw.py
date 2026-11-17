import sys, numpy as np, pandas as pd
sys.path.insert(0,'/home/user/treasure/ctrader-arena')
from arena.ingest import load
for sid in (2616,2617,2618):
    b=load(sid,'H_1'); c=b.close.to_numpy(); r=np.diff(c); n=len(r)
    a=np.abs(r)
    # regime: rolling 12h realized vol percentile
    rv=pd.Series(a).rolling(12).mean().to_numpy()
    hi=rv>np.nanmedian(rv)
    out=[f"{sid} n={n} {b.time.iloc[0].date()}..{b.time.iloc[-1].date()} t_drift={r.mean()/r.std()*np.sqrt(n):.2f}"]
    for k in (1,2,6,24):
        x=r[:-k]; y=c[k:][1:] - c[1:-k] if False else None
    # leverage: corr(r_t, |r_{t+1..t+6}|)
    fut=pd.Series(a[::-1]).rolling(6).mean().to_numpy()[::-1]
    lev=np.corrcoef(r[:-6],fut[1:-5])[0,1]
    # momentum by regime: corr(r_t, r_{t+1}) when hi/lo
    m_hi=np.corrcoef(r[:-1][hi[:-1]&~np.isnan(rv[:-1])], r[1:][hi[:-1]&~np.isnan(rv[:-1])])[0,1]
    lo=(~hi)&~np.isnan(rv)
    m_lo=np.corrcoef(r[:-1][lo[:-1]], r[1:][lo[:-1]])[0,1]
    # drift by regime (signed mean return / sd)
    d_hi=r[1:][hi[:-1]].mean()/r[1:][hi[:-1]].std()*np.sqrt(hi.sum())
    d_lo=r[1:][lo[:-1]].mean()/r[1:][lo[:-1]].std()*np.sqrt(lo.sum())
    # 12h sign momentum
    L=12; s=np.sign(c[L:-L]-c[:-2*L]); f=c[2*L:]-c[L:-L]; mom=(s*f)[::L]; tm=mom.mean()/mom.std()*np.sqrt(len(mom))
    acab=np.corrcoef(a[:-1],a[1:])[0,1]
    # vol regime switching visible: ratio of hi/lo rv
    out.append(f"lev corr(r,|r|fut6)={lev:+.3f} ac1|hi={m_hi:+.3f} ac1|lo={m_lo:+.3f} t_drift hi={d_hi:+.2f} lo={d_lo:+.2f} mom12 t={tm:+.2f} acabs={acab:.3f} rv p90/p10={np.nanpercentile(rv,90)/np.nanpercentile(rv,10):.1f}")
    print(' '.join(out))
