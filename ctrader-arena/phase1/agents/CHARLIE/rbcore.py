"""Range Break core: causal boundary tracking + order generation (shared by research and strategy)."""
import numpy as np, pandas as pd
from numba import njit

@njit(cache=True)
def track(ts, o, h, l, c, thr):
    """Causal state per bar (uses bars <= i only).
    side: +1 = last event was an UP break (upper boundary known exactly = level), -1 = DOWN break, 0 = unknown (start/gap)
    level: the known boundary price; age: bars since the break bar (0 = break bar itself)."""
    n = len(o)
    side = np.zeros(n); level = np.zeros(n); age = np.zeros(n, np.int64)
    s = 0.0; lev = 0.0; a = 0
    for i in range(n):
        if i > 0 and ts[i] - ts[i-1] > 60000:      # data gap -> state unknown
            s = 0.0; a = 0
        if h[i] - l[i] > thr:
            if c[i] > o[i]: s = 1.0; lev = h[i]
            else: s = -1.0; lev = l[i]
            a = 0
        else:
            a += 1
            if s > 0 and h[i] > lev: lev = h[i]     # boundary can only be re-learned outward
            if s < 0 and l[i] < lev: lev = l[i]
        side[i] = s; level[i] = lev; age[i] = a
    return side, level, age

def orders(m1, p, vol):
    ts = m1.ts.to_numpy(np.int64); o, h, l, c = [m1[x].to_numpy(np.float64) for x in ("open", "high", "low", "close")]
    side, level, age = track(ts, o, h, l, c, float(p["thr"]))
    dist = np.where(side > 0, level - c, c - level)
    ok = (side != 0) & (dist <= p["near"]) & (age <= p.get("max_age", 10**9)) & (age >= p.get("min_age", 0))
    idx = np.where(ok)[0]
    return pd.DataFrame({"idx": idx, "side": side[idx] * p.get("dir", 1), "kind": 0, "sl": float(p["sl"]), "tp": float(p.get("tp", 0.0)),
                         "max_bars": int(p["mb"]), "trail": float(p.get("trail", 0.0)), "volume": vol})
