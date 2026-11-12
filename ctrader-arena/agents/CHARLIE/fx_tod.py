"""Pre-sample time-of-day study on M15 (only bars before PRE_END are used)."""
import sys; sys.path.insert(0,'.')
from arena.ingest import load
import numpy as np, pandas as pd
PRE_END=pd.Timestamp('2026-09-16')
def pre(sid):
    m=load(sid,'M_15'); m=m[m.time<PRE_END].reset_index(drop=True); return m
if __name__=='__main__':
    for a in sys.argv[1:]:
        sid,pip=a.split(':'); pip=float(pip)
        m=pre(sid); r=(m.close-m.open)/pip
        print(f"== {sid} n={len(m)} {str(m.time.iloc[0])[:10]}..{str(m.time.iloc[-1])[:10]} days={m.time.dt.floor('D').nunique()} M15 |r| mean={r.abs().mean():.2f} pips sd={r.std():.2f}")
        for tz in ('UTC','Asia/Tokyo','Europe/London','America/New_York'):
            lt=m.time.dt.tz_localize('UTC').dt.tz_convert(tz); slot=lt.dt.hour*4+lt.dt.minute//15
            g=r.groupby(slot.values).agg(['mean','std','count']); g['t']=g['mean']/g['std']*np.sqrt(g['count'])
            top=g.reindex(g.t.abs().sort_values(ascending=False).index).head(5)
            print(' ',tz,'top slots:',' | '.join(f"{int(s)//4:02d}:{int(s)%4*15:02d} {x['mean']:+.2f}p t={x.t:+.1f}" for s,x in top.iterrows()))
        # hourly-block drift (UTC), half-sample stability
        lt=m.time.dt.hour; half=np.arange(len(m))<len(m)//2
        g1=r[half].groupby(lt[half].values).sum()/m.time[half].dt.floor('D').nunique(); g2=r[~half].groupby(lt[~half].values).sum()/m.time[~half].dt.floor('D').nunique()
        print('  hourly drift pips/day (UTC) h1:',' '.join(f"{x:+.1f}" for x in g1)); print('                              h2:',' '.join(f"{x:+.1f}" for x in g2), ' corr=%.2f'%np.corrcoef(g1,g2)[0,1])
