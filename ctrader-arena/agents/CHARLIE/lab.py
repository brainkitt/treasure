"""Phase-2 research harness (H_1 base). One rule, identical params across symbols."""
import sys, numpy as np, pandas as pd
sys.path.insert(0, '.')
from arena.ingest import load
from arena import engine

# id: (name, min_units, spread as fraction of price, swap/night)
SYM = {2403: ('SOL', 0.5, 0.0018, 0.0005), 102: ('ETH', 0.1, 0.00085, 0.0005), 2408: ('XRP', 100, 0.0011, 0.0005),
       2398: ('LTC', 1, 0.0038, 0.0005), 2387: ('BNB', 0.1, 0.0012, 0.0005), 2397: ('LNK', 6, 0.0017, 0.0005),
       2528: ('OIL', 1, 0.0018, 0.00025)}
RISK = 1.5          # max $ loss per trade at the stop (gate is 1.80; leaves room for spread+slip)

def atr(b, n):
    pc = b.close.shift(1)
    tr = np.maximum(b.high - b.low, np.maximum((b.high - pc).abs(), (b.low - pc).abs()))
    return tr.rolling(n).mean()

def donch(b, p, units):
    """Close breaks the prior N-bar high/low -> market in that direction. SL = k*ATR (skip if > $RISK), trail same."""
    N, k, A = p['N'], p['k'], p.get('A', 48)
    a = atr(b, A)
    hh = b.high.rolling(N).max().shift(1); ll = b.low.rolling(N).min().shift(1)
    up = (b.close > hh) & (b.close.shift(1) <= hh.shift(1)); dn = (b.close < ll) & (b.close.shift(1) >= ll.shift(1))
    side = np.where(up, 1, np.where(dn, -1, 0))
    if p.get('long_only'): side = np.where(side > 0, 1, 0)
    if p.get('F'):   # trend filter: slow MA slope
        ma = b.close.rolling(p['F']).mean()
        side = np.where((side > 0) & (b.close > ma), 1, np.where((side < 0) & (b.close < ma), -1, 0))
    sl = k * a
    cap = p.get('risk', RISK) / units
    if p.get('capmode', 'skip') == 'skip':
        ok = (side != 0) & (sl <= cap) & a.notna()
    else:
        sl = np.minimum(sl, cap); ok = (side != 0) & a.notna()
    i = np.flatnonzero(ok.to_numpy() if hasattr(ok, 'to_numpy') else ok)
    slv = np.asarray(sl)[i]
    od = pd.DataFrame({'idx': i, 'side': side[i], 'kind': 0, 'price': 0.0, 'sl': slv,
                       'tp': slv * p.get('tp', 0.0), 'max_bars': p.get('mb', 0),
                       'trail': slv * p.get('tr', 1.0), 'valid': 1, 'volume': units, 'prove': p.get('pv', 0)})
    return od

def run(sid, p, fn=donch, smult=1.0, frac=None, swap=None):
    name, units, sp, sw = SYM[sid]
    b = load(sid, 'H_1')
    if frac: b = b.iloc[int(len(b) * frac[0]):int(len(b) * frac[1])].reset_index(drop=True)
    od = fn(b, p, units)
    spread = sp * b.close.quantile(0.75) * smult      # constant, sized on a HIGH price of the sample
    tr = engine.simulate(b, od, spread=spread, swap_per_night=sw if swap is None else swap)
    tr['sym'] = name
    return tr

def pf(x):
    g, l = x[x > 0].sum(), -x[x < 0].sum()
    return g / l if l > 0 else np.inf

def summ(tr, tag=''):
    if not len(tr): return f'{tag} n=0'
    p = tr.pnl.to_numpy(); eq = np.cumsum(p); dd = (np.maximum.accumulate(np.maximum(eq, 0)) - eq).max()
    return (f'{tag} n={len(p):4d} PF={pf(p):.2f} net={p.sum():7.2f} win={100*(p>0).mean():3.0f}% dd={dd:5.2f} '
            f'worst={p.min():5.2f} swap={tr.swap.sum():6.2f}')

def port(ids, p, fn=donch, **kw):
    t = pd.concat([run(s, p, fn, **kw) for s in ids]).sort_values('exit_time').reset_index(drop=True)
    return t
