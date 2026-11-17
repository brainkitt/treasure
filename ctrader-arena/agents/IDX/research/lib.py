import numpy as np, pandas as pd, sys, os
sys.path.insert(0, '/home/user/treasure/ctrader-arena')
from arena.ingest import load
from arena import engine
SPREAD = {2517: 0.36, 2521: 0.30, 2522: 1.22, 2518: 0.90, 2509: 1.8}
NAME = {2517: 'SP', 2521: 'RUT', 2522: 'MID', 2518: 'NAS', 2509: 'DJ'}
_cache = {}
def bars(s, period='H_1'):
    if (s, period) not in _cache:
        b = load(s, period)
        ny = b.time.dt.tz_localize('UTC').dt.tz_convert('America/New_York')
        b['nyh'] = ny.dt.hour; b['nym'] = ny.dt.minute; b['dow'] = ny.dt.dayofweek
        b['nyd'] = ny.dt.tz_localize(None).dt.floor('D')
        _cache[(s, period)] = b
    return _cache[(s, period)]

def atr(b, n=14):
    pc = b.close.shift(1)
    tr = np.maximum(b.high - b.low, np.maximum((b.high - pc).abs(), (b.low - pc).abs()))
    return tr.rolling(n).mean()

def run(b, od, s, spread_mult=1.0, swap_long=0.0, swap_short=0.0, slip=0.0):
    if len(od) == 0:
        return pd.DataFrame(columns=['pnl', 'entry_time'])
    od = od.sort_values('idx', kind='stable').reset_index(drop=True)
    tr = engine.simulate(b, od, spread=SPREAD[s] * spread_mult, slip=slip, max_open=1)
    vol = od.volume.to_numpy(float)[tr.order_row.astype(int)] if 'volume' in od else np.ones(len(tr))
    tr['vol'] = vol
    # nights crossing 21 UTC
    et = pd.to_datetime(tr.entry_time); xt = pd.to_datetime(tr.exit_time)
    first = (et - pd.Timedelta(hours=21)).dt.floor('D') + pd.Timedelta(days=1, hours=21)
    nights = np.where(first <= xt, ((xt - first).dt.total_seconds() // 86400 + 1), 0)
    tr['nights'] = nights
    rate = np.where(tr.side > 0, swap_long, swap_short)
    tr['pnl'] = tr.pnl - nights * rate * vol
    return tr

def pf(p):
    p = np.asarray(p); gl = -p[p < 0].sum()
    return p[p > 0].sum() / gl if gl > 0 else 99.0

def summ(tr, b, frac=0.7):
    if len(tr) == 0:
        return dict(n=0, pf=0, pf_is=0, pf_oos=0, net=0, t=0, n_oos=0)
    cut = b.time.iloc[int(len(b) * frac)]
    p = tr.pnl.to_numpy(); isel = (pd.to_datetime(tr.entry_time) < cut).to_numpy()
    t = p.mean() / (p.std(ddof=1) / np.sqrt(len(p))) if len(p) > 2 else 0
    return dict(n=len(p), pf=round(pf(p), 3), pf_is=round(pf(p[isel]), 3), pf_oos=round(pf(p[~isel]), 3),
                net=round(p.sum(), 2), t=round(t, 2), n_oos=int((~isel).sum()))

def folds(tr, b, k=5):
    edges = np.linspace(0, len(b) - 1, k + 1).astype(int)
    T = b.time.to_numpy(); et = pd.to_datetime(tr.entry_time).to_numpy(); out = []
    for a, c in zip(edges[:-1], edges[1:]):
        sel = (et >= T[a]) & (et < T[c]) if c != edges[-1] else (et >= T[a])
        out.append(round(pf(tr.pnl.to_numpy()[sel]), 2))
    return out
