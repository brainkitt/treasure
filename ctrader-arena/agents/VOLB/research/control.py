"""Null control: simulate exact Step-100 random walk (±0.1 per 1s tick) as M5 bars, run lab families on it."""
import sys, numpy as np, pandas as pd
sys.path.insert(0, '.'); sys.path.insert(0, '/home/user/treasure/ctrader-arena')
import lab
from arena import engine
from numba import njit
@njit(cache=True)
def walk(nb, tpb, step, p0, seed):
    np.random.seed(seed)
    o = np.empty(nb); h = np.empty(nb); l = np.empty(nb); c = np.empty(nb); x = p0
    for i in range(nb):
        x += step if np.random.random() < .5 else -step
        o[i] = x; hi = x; lo = x
        for k in range(tpb - 1):
            x += step if np.random.random() < .5 else -step
            if x > hi: hi = x
            if x < lo: lo = x
        h[i] = hi; l[i] = lo; c[i] = x
    return o, h, l, c
def bars(nb, seed):
    o, h, l, c = walk(nb, 300, 0.1, 7000.0, seed)
    t = pd.date_range('2026-01-01', periods=nb, freq='5min')
    return pd.DataFrame(dict(ts=t.astype('int64') // 10**6, time=t, open=o, high=h, low=l, close=c, volume=300))
fam = sys.argv[1]; params = eval(sys.argv[2]); spread = float(sys.argv[3]); reps = int(sys.argv[4])
pfs = []; nt = []
for s in range(reps):
    b = bars(7000, s)
    tr = engine.simulate(b, lab.FAM[fam][0](b, **params), spread=spread)
    pfs.append(lab.pf(tr.pnl.to_numpy())); nt.append(len(tr))
pfs = np.array(pfs)
print(f"{fam} {params} sp={spread}: null PF median {np.median(pfs):.2f}  p90 {np.percentile(pfs,90):.2f}  share>1.2 {np.mean(pfs>1.2):.0%}  trades~{np.mean(nt):.0f}")
