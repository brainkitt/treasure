import sys, itertools, numpy as np, pandas as pd
sys.path.insert(0, 'agents/VOLA/research'); sys.path.insert(0, '.')
from lab import *
SYMS = {2619: ('Crash 150', +1), 2620: ('Boom 150', -1), 2567: ('VolCrash 550', +1), 2468: ('DEX600UP', -1),
        2606: ('Trek Up', -1), 2450: ('RB200', 0), 2454: ('Jump 75', 0)}
fam = sys.argv[1]
for sid, (nm, dside) in SYMS.items():
    b = bars(sid); n = len(b); A = atr(b); ok = np.isfinite(A)
    rows = []
    if fam == 'F1' and dside != 0:
        r, med, mad, J = mad_jumps(b, 6)
        since = np.full(n, 999); c = 999
        for i in range(n):
            c = 0 if J[i] else c + 1; since[i] = c
        for s, H, k in itertools.product([0, 1, 3, -1], [1, 3, 6, 12, 24], [2, 4, 8]):
            m = ok & ((since == s) if s >= 0 else np.ones(n, bool))
            idx = np.where(m)[0]; idx = idx[idx < n - 2]
            od = orders(idx, dside, k * A[idx], 0, H)
            rows.append(run(b, od, sid, 'F1_drift_harvest', dict(s=s, H=H, k=k))[0])
    if fam == 'F2':
        for kj, d, H, k in itertools.product([4, 6, 8], [1, -1], [1, 3, 6, 12], [2, 4]):
            r, med, mad, J = mad_jumps(b, kj)
            idx = np.where(J & ok)[0]; idx = idx[idx < n - 2]
            od = orders(idx, d * np.sign(r[idx] - med), k * A[idx], 0, H)
            rows.append(run(b, od, sid, 'F2_postjump', dict(kj=kj, d=d, H=H, k=k))[0])
    if fam == 'F3' and sid in (2454, 2606, 2450, 2619):
        for N, d, tk, H in itertools.product([6, 12, 24, 48], [1, -1], [1, 2, 3], [12, 48]):
            hh = b.high.rolling(N).max().shift(1).to_numpy(); ll = b.low.rolling(N).min().shift(1).to_numpy()
            c = b.close.to_numpy()
            up = (c > hh) & ok; dn = (c < ll) & ok
            idx = np.where(up | dn)[0]; idx = idx[idx < n - 2]
            side = np.where(up[idx], 1, -1) * d
            od = orders(idx, side, tk * A[idx], 0, H, trail=tk * A[idx] if d == 1 else 0.0)
            if d == -1: od['tp'] = tk * A[idx]
            rows.append(run(b, od, sid, 'F3_breakout', dict(N=N, d=d, tk=tk, H=H))[0])
    if fam == 'F6':
        c = b.close.to_numpy()
        for N, H, d in itertools.product([3, 12, 48], [3, 12, 48], [1, -1]):
            mom = np.sign(c - np.roll(c, N)); mom[:N] = 0
            idx = np.arange(N, n - 2, H)  # non-overlapping decision points
            idx = idx[ok[idx] & (mom[idx] != 0)]
            od = orders(idx, d * mom[idx], 4 * A[idx], 0, H)
            rows.append(run(b, od, sid, 'F6_tsmom', dict(N=N, H=H, d=d))[0])
    if fam == 'F4' and sid == 2450:
        c = b.close.to_numpy()
        for N, near, slf, H in itertools.product([12, 24, 48], [0.1, 0.2], [0.25, 0.5], [6, 24]):
            hh = b.high.rolling(N).max().to_numpy(); ll = b.low.rolling(N).min().to_numpy(); w = hh - ll
            top = (hh - c) < near * w; bot = (c - ll) < near * w
            m = (top ^ bot) & (w > 0)
            idx = np.where(m)[0]; idx = idx[(idx < n - 2) & (idx > N)]
            side = np.where(top[idx], -1, 1)
            od = orders(idx, side, slf * w[idx] + 2.0, 0.4 * w[idx], H)
            rows.append(run(b, od, sid, 'F4_rb_fade', dict(N=N, near=near, slf=slf, H=H))[0])
            od = orders(idx, -side, slf * w[idx] + 2.0, 0, H)
            rows.append(run(b, od, sid, 'F4_rb_follow', dict(N=N, near=near, slf=slf, H=H))[0])
    if rows:
        summarize(rows, f'{fam} {nm}')
