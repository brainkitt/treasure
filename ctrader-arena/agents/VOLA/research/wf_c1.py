"""Anchored walk-forward (refit per fold on the 48-set F3 breakout grid, select max PF on all data before the fold)
and neighbour table around C1, RB200 M5, full pre-holdout file. Writes research/wf_c1.json."""
import sys, json, itertools; sys.path.insert(0, 'agents/VOLA/research'); sys.path.insert(0, '.')
from lab import *
from c1_confirm import c1
b = load(2450, 'M_5'); n = len(b)
grid = list(itertools.product([6, 12, 24, 48], [1, -1], [1, 2, 3], [12, 48]))
trs = {}
for g in grid:
    N, d, tk, H = g
    _, tr = run(b, c1(b, N, tk, H, d), 2450, 'WF_grid_full', dict(N=N, d=d, tk=tk, H=H), log=True)
    trs[g] = tr
edges = [b.time.iloc[int(n * f)] for f in (0.0, 0.3, 0.44, 0.58, 0.72, 0.86)] + [b.time.iloc[-1] + pd.Timedelta(minutes=5)]
wf = []
for k in range(1, 6):
    a, z = edges[k], edges[k + 1]
    best = max(grid, key=lambda g: pf(trs[g][trs[g].entry_time < a].pnl.to_numpy()))
    t = trs[best]; isp = pf(t[t.entry_time < a].pnl.to_numpy()); o = t[(t.entry_time >= a) & (t.entry_time < z)].pnl.to_numpy()
    wf.append(dict(fold=k, test_start=str(a), test_end=str(z), chosen=dict(zip('N d tk H'.split(), best)), is_pf=round(isp, 3),
                   oos_pf=round(pf(o), 3), oos_trades=int(len(o)), oos_net_price_units=round(float(o.sum()), 1)))
    print(wf[-1])
nb = []
for N, tk in itertools.product([12, 24, 48], [1, 2, 3]):
    t = trs[(N, 1, tk, 48)]; cut = b.time.iloc[int(n * 0.7)]
    nb.append(dict(N=N, K=tk, H=48, pf_full=round(pf(t.pnl.to_numpy()), 3), pf_is=round(pf(t[t.entry_time < cut].pnl.to_numpy()), 3),
                   pf_oos=round(pf(t[t.entry_time >= cut].pnl.to_numpy()), 3), trades=len(t)))
print(pd.DataFrame(nb).to_string(index=False))
json.dump(dict(walk_forward=wf, neighbour_table=nb), open(R + 'wf_c1.json', 'w'), indent=1)
