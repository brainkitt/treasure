"""Pre-declared confirmation of candidate C1 (RB200 M5 Donchian-24 close breakout FOLLOW, SL=trail=2*ATR24, exit 48 bars)
on the NEW, previously unseen sample before 2026-08-18 05:20 (all fitting used 08-18..09-14). Plus the 48-set family on it."""
import sys, itertools; sys.path.insert(0, 'agents/VOLA/research'); sys.path.insert(0, '.')
from lab import *
full = load(2450, 'M_5')
new = full[full.time < '2026-08-18 05:20'].reset_index(drop=True)
print('new sample', len(new), new.time.iloc[0], new.time.iloc[-1])
def c1(b, N, tk, H, d=1):
    n = len(b); A = atr(b); ok = np.isfinite(A)
    hh = b.high.rolling(N).max().shift(1).to_numpy(); ll = b.low.rolling(N).min().shift(1).to_numpy(); c = b.close.to_numpy()
    up = (c > hh) & ok; dn = (c < ll) & ok
    idx = np.where(up | dn)[0]; idx = idx[idx < n - 2]
    side = np.where(up[idx], 1, -1) * d
    od = orders(idx, side, tk * A[idx], 0, H, trail=tk * A[idx] if d == 1 else 0.0)
    if d == -1: od['tp'] = tk * A[idx]
    return od
res, tr = run(new, c1(new, 24, 2, 48), 2450, 'C1_confirm_newsample', dict(N=24, tk=2, H=48))
p = tr.pnl.to_numpy(); print('C1 on new sample: trades', len(p), 'PF', round(pf(p), 3), 't', round(p.mean() / p.std() * np.sqrt(len(p)), 2))
rows = []
for N, d, tk, H in itertools.product([6, 12, 24, 48], [1, -1], [1, 2, 3], [12, 48]):
    r, tr = run(new, c1(new, N, tk, H, d), 2450, 'F3_breakout_newsample', dict(N=N, d=d, tk=tk, H=H))
    q = tr.pnl.to_numpy(); rows.append(dict(N=N, d=d, tk=tk, H=H, pf=pf(q), n=len(q)))
d = pd.DataFrame(rows)
print('follow sets PF>1:', (d[d.d == 1].pf > 1).mean(), 'median', d[d.d == 1].pf.median().round(3), '| fade sets PF>1:', (d[d.d == -1].pf > 1).mean(), 'median', d[d.d == -1].pf.median().round(3))
