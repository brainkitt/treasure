"""List missing 30-day H_1 windows (k index on the paging grid) per symbol."""
import sys, pandas as pd
sys.path.insert(0, '.')
from arena.ingest import load
T0 = pd.Timestamp('2026-11-13T22:00:00')
def gaps(sid, kmax=33, minbars=300):
    try: d = load(sid, 'H_1')
    except Exception: return list(range(kmax + 1)), 0
    out = []
    for k in range(kmax + 1):
        hi = T0 - pd.Timedelta(days=30 * k); lo = hi - pd.Timedelta(days=30)
        n = ((d.time >= lo) & (d.time < hi)).sum()
        if n < minbars: out.append(k)
    return out, len(d)
if __name__ == '__main__':
    for s in sys.argv[1:]:
        g, n = gaps(int(s)); print(s, n, 'missing k:', g, [ (T0 - pd.Timedelta(days=30*k)).strftime('%Y-%m-%dT%H:%M:%SZ') for k in g][:40])
