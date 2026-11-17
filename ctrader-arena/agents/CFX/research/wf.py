"""Anchored walk-forward with re-fit per fold (final system = ETH leg; BTC+ETH shown for reference).
Grid of 54 sets: k{2,2.5,3} x n{24,48} x H{1,2,3} x slm{1.5,2,3}. Selection = highest train t-stat with >=60 train trades."""
import sys, itertools
import lib
lib.START = lib.pd.Timestamp("2023-05-01"); lib._cache.clear()
lib.SPREAD[101] = 25.0; lib.SPREAD[102] = 2.0
from h4b import *
grid = list(itertools.product([2.0, 2.5, 3.0], [24, 48], [1, 2, 3], [1.5, 2.0, 3.0]))
edges = [pd.Timestamp(x) for x in ["2024-06-01", "2024-12-01", "2025-06-01", "2025-12-01", "2026-06-01", "2026-11-18"]]
def trades(sids, k, n, H, slm):
    out = []
    for sid in sids:
        tr = sim(sid, burst2(sid, k=k, n=n, H=H, slm=slm), slip_frac=0.2)
        out.append(tr[["entry_time", "pnl"]])
    t = pd.concat(out); t["entry_time"] = pd.to_datetime(t.entry_time); return t
for sids in ([102], [101, 102]):
    cache = {g: trades(sids, *g) for g in grid}
    print("universe", [NAMES[s] for s in sids])
    allp = []
    for a, b in zip(edges[:-1], edges[1:]):
        best, bt = None, -9
        for g, t in cache.items():
            p = t[t.entry_time < a].pnl.to_numpy()
            if len(p) < 60: continue
            ts = p.mean() / p.std() * np.sqrt(len(p))
            if ts > bt: best, bt = g, ts
        t = cache[best]; p = t[(t.entry_time >= a) & (t.entry_time < b)].pnl.to_numpy(); allp.append(p)
        tb = cache[(2.5, 24, 2, 2.0)]; pb = tb[(tb.entry_time >= a) & (tb.entry_time < b)].pnl.to_numpy()
        print(f"  train->{a.date()} pick k={best[0]} n={best[1]} H={best[2]} slm={best[3]} (train t={bt:.2f}) | test {a.date()}..{b.date()} n={len(p)} PF={pf(p):.2f} net={p.sum():.1f} | fixed BASE PF={pf(pb):.2f} net={pb.sum():.1f}")
    ap = np.concatenate(allp); print(f"  WF stitched OOS: n={len(ap)} PF={pf(ap):.2f} net={ap.sum():.1f} t={ap.mean()/ap.std()*np.sqrt(len(ap)):.2f}")
