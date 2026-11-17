"""Strategy-family lab for VOLB. Each family -> orders DataFrame for arena.engine.simulate.
Fit = first 70% of bars (IS), report OOS last 30% untouched. Spread = widest live sample."""
import sys, itertools, numpy as np, pandas as pd
sys.path.insert(0, '/home/user/treasure/ctrader-arena')
from arena.ingest import load
from arena import engine

def atr(b, n=14):
    h, l, c = b.high.to_numpy(), b.low.to_numpy(), b.close.to_numpy()
    pc = np.r_[c[0], c[:-1]]
    tr = np.maximum(h - l, np.maximum(abs(h - pc), abs(l - pc)))
    return pd.Series(tr).rolling(n).mean().to_numpy()

def od(idx, side, sl, tp=0, mb=0, trail=0):
    n = len(idx)
    f = lambda v: np.broadcast_to(np.asarray(v, float), (n,)).copy() if np.ndim(v) == 0 else np.asarray(v, float)
    return pd.DataFrame(dict(idx=np.asarray(idx, int), side=f(side), kind=0, price=0.0, sl=f(sl), tp=f(tp),
                             max_bars=f(mb).astype(int), trail=f(trail), valid=1, volume=1.0))

def fam_mr(b, N=24, k=2.0, slm=2.0, H=12):          # F1 fade deviation from SMA, TP at SMA
    c = b.close.to_numpy(); a = atr(b); m = pd.Series(c).rolling(N).mean().to_numpy()
    z = (c - m) / a
    i = np.where((np.abs(z) > k) & (np.abs(np.r_[0, z[:-1]]) <= k))[0]
    i = i[~np.isnan(a[i])]
    return od(i, -np.sign(z[i]), slm * a[i], np.abs(c[i] - m[i]), H)

def fam_bo(b, N=24, slm=2.0, trm=2.0, H=48, volf=0.0):   # F2/F3 Donchian breakout (+ vol-regime filter)
    c = b.close.to_numpy(); a = atr(b)
    hh = pd.Series(b.high).rolling(N).max().shift(1).to_numpy(); ll = pd.Series(b.low).rolling(N).min().shift(1).to_numpy()
    up = c > hh; dn = c < ll
    sig = np.where(up, 1, np.where(dn, -1, 0))
    if volf > 0:
        ratio = atr(b, 6) / atr(b, 72)
        sig = np.where(ratio > volf, sig, 0)
    i = np.where((sig != 0) & (np.r_[0, sig[:-1]] != sig))[0]
    i = i[~np.isnan(a[i])]
    return od(i, sig[i], slm * a[i], 0, H, trm * a[i])

def fam_tsmom(b, L=12, H=12, slm=3.0):   # F2b time-series momentum: sign of L-bar return, hold H
    c = b.close.to_numpy(); a = atr(b)
    i = np.arange(max(L, 15), len(c) - 1, H)
    s = np.sign(c[i] - c[i - L]); keep = (s != 0) & ~np.isnan(a[i])
    return od(i[keep], s[keep], slm * a[i[keep]], 0, H)

FAM = {'mr': (fam_mr, dict(N=[12, 24, 48], k=[1.5, 2.0, 2.5, 3.0], slm=[1.5, 2.5, 4.0], H=[6, 24])),
       'bo': (fam_bo, dict(N=[12, 24, 48, 96], slm=[1.5, 3.0], trm=[1.5, 3.0], H=[24, 96])),
       'bovol': (fam_bo, dict(N=[12, 24, 48], slm=[1.5, 3.0], trm=[2.0], H=[24, 96], volf=[1.2, 1.5, 2.0])),
       'tsmom': (fam_tsmom, dict(L=[3, 6, 12, 24, 48], H=[3, 6, 12, 24], slm=[2.0, 4.0]))}

def pf(p):
    g, l = p[p > 0].sum(), -p[p < 0].sum(); return g / l if l > 0 else 99.0

def run(sid, per, spread, fam, slip=0.0):
    b = load(sid, per); cut = int(len(b) * 0.7); tcut = b.time.iloc[cut]
    f, grid = FAM[fam]; rows = []
    for vals in itertools.product(*grid.values()):
        p = dict(zip(grid.keys(), vals))
        o = f(b, **p)
        tr = engine.simulate(b, o, spread=spread, slip=slip)
        if len(tr) < 20: continue
        isx = tr[tr.entry_time < tcut].pnl.to_numpy(); oos = tr[tr.entry_time >= tcut].pnl.to_numpy()
        g = tr.pnl.to_numpy() + 0  # gross approx: add back spread
        rows.append(dict(**p, n=len(tr), pf_is=pf(isx), pf_oos=pf(oos), t_is=isx.mean() / (isx.std() / np.sqrt(len(isx)) + 1e-12),
                         n_oos=len(oos), gross_pf=pf(tr.pnl.to_numpy() + spread * (1))))
    return pd.DataFrame(rows)

if __name__ == '__main__':
    sid, per, spread = int(sys.argv[1]), sys.argv[2], float(sys.argv[3])
    fams = sys.argv[4].split(',') if len(sys.argv) > 4 else list(FAM)
    for fam in fams:
        d = run(sid, per, spread, fam)
        d.to_csv(f'lab_{sid}_{per}_{fam}.csv', index=False)
        top = d.sort_values('pf_is', ascending=False).head(5)
        print(f"{sid} {per} sp={spread} {fam:6s} sets={len(d)} IS PF>1: {np.mean(d.pf_is > 1):.0%} >1.2: {np.mean(d.pf_is > 1.2):.0%} "
              f"maxIS t={d.t_is.max():.2f} | top5-IS -> OOS PF median {top.pf_oos.median():.2f} | grossPF median {d.gross_pf.median():.2f} "
              f"| corr(IS,OOS)={np.corrcoef(d.pf_is, d.pf_oos)[0, 1]:.2f}")
