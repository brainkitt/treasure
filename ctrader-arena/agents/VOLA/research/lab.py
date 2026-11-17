"""Strategy-family lab: vectorised signal generators + official engine, IS (first 70% of bars) / OOS split.
Every evaluated parameter set is appended to research/trials.csv (data-mining count)."""
import sys, os, itertools, numpy as np, pandas as pd
sys.path.insert(0, '.')
from arena.ingest import load
from arena import engine
R = 'agents/VOLA/research/'
SPREAD = {}
for l in open(R + 'spreads_raw.txt'):
    if l.strip() and not l.startswith('#'):
        a = l.split(); SPREAD[int(a[0])] = max(SPREAD.get(int(a[0]), 0), (int(a[2]) - int(a[1])) / 1e5)

def bars(sid, per='M_5'):
    b = load(sid, per)
    return b

def orders(idx, side, sl, tp=0.0, mb=0, trail=0.0):
    n = len(idx)
    f = lambda x: np.broadcast_to(np.asarray(x, float), (n,)).copy()
    return pd.DataFrame(dict(idx=np.asarray(idx, int), side=f(side), kind=0, price=0.0, sl=f(sl), tp=f(tp),
                             max_bars=np.broadcast_to(np.asarray(mb, int), (n,)).copy(), trail=f(trail), valid=1, volume=1.0))

def pf(p):
    gl = -p[p < 0].sum()
    return p[p > 0].sum() / gl if gl > 0 else (99.0 if len(p) else 0.0)

def run(b, od, sid, family, params, spread_mult=1.0, log=True):
    sp = SPREAD[sid] * spread_mult
    tr = engine.simulate(b, od, spread=sp, slip=0.0, gap_sl=True, max_open=1)
    cut = b.time.iloc[int(len(b) * 0.7)]
    p = tr.pnl.to_numpy(); isel = (tr.entry_time < cut).to_numpy()
    res = dict(sid=sid, family=family, params=str(params), n=len(p), n_is=int(isel.sum()), n_oos=int((~isel).sum()),
               pf_is=round(pf(p[isel]), 3), pf_oos=round(pf(p[~isel]), 3),
               exp_is_spr=round(p[isel].mean() / sp, 3) if isel.any() else 0, exp_oos_spr=round(p[~isel].mean() / sp, 3) if (~isel).any() else 0,
               t_is=round(p[isel].mean() / p[isel].std() * np.sqrt(isel.sum()), 2) if isel.sum() > 2 else 0,
               t_oos=round(p[~isel].mean() / p[~isel].std() * np.sqrt((~isel).sum()), 2) if (~isel).sum() > 2 else 0)
    if log:
        pd.DataFrame([res]).to_csv(R + 'trials.csv', mode='a', header=not os.path.exists(R + 'trials.csv'), index=False)
    return res, tr

def mad_jumps(b, k):
    r = b.close.diff().fillna(0).to_numpy()
    med = np.median(r); mad = np.median(np.abs(r - med)) * 1.4826
    return r, med, mad, np.abs(r - med) > k * mad

def atr(b, n=24):
    tr = np.maximum(b.high - b.low, np.maximum((b.high - b.close.shift()).abs(), (b.low - b.close.shift()).abs()))
    return tr.rolling(n, min_periods=n).mean().to_numpy()

def summarize(rows, label):
    d = pd.DataFrame(rows)
    if d.empty: return d
    best = d.sort_values('pf_is', ascending=False).iloc[0]
    print(f"{label:38s} sets={len(d):3d} IS PF>1: {(d.pf_is>1).mean()*100:3.0f}%  OOS PF>1: {(d.pf_oos>1).mean()*100:3.0f}%  "
          f"medPF is/oos {d.pf_is.median():.2f}/{d.pf_oos.median():.2f}  best-IS {best.pf_is:.2f}(t{best.t_is}) -> OOS {best.pf_oos:.2f}(n{best.n_oos})  corr {d.pf_is.corr(d.pf_oos):+.2f}")
    return d
