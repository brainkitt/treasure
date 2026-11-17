from lib import *
def pof_orders(b, n=32, sl_atr=2.0, tp_atr=1.0, sl_cap=14.0, hold=16, h0=3.0, h1=9.5, vol=1.0, atr_n=14):
    nyh=(b.nyh+b.nym/60.0).to_numpy()
    a=atr(b,atr_n).to_numpy()
    hi=b.high.rolling(n).max().shift(1); lo=b.low.rolling(n).min().shift(1)
    up=((b.close>hi)&(b.close.shift(1)<=hi.shift(1))).to_numpy()
    dn=((b.close<lo)&(b.close.shift(1)>=lo.shift(1))).to_numpy()
    m=(up|dn)&(nyh>=h0)&(nyh<h1)&np.isfinite(a)&(a>0)
    return pd.DataFrame({'idx':np.where(m)[0],'side':np.where(up[m],-1,1),'kind':0,
        'sl':np.minimum(sl_atr*a[m],sl_cap),'tp':tp_atr*a[m],'max_bars':hold,'volume':vol})
def by_period(tr, edges):
    et=pd.to_datetime(tr.entry_time); out=[]
    for a,c in zip(edges[:-1],edges[1:]):
        p=tr.pnl[(et>=a)&(et<c)].to_numpy(); out.append((str(a.date()),len(p),round(pf(p),2),round(p.sum(),1)))
    return out
