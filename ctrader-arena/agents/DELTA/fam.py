"""Research signal families. Each returns an orders DataFrame indexed on bars `b` (idx = b.m1_idx if present else row)."""
import numpy as np, pandas as pd

def atr(b, n):
    tr = np.maximum(b.high - b.low, np.maximum((b.high - b.close.shift()).abs(), (b.low - b.close.shift()).abs()))
    return tr.rolling(n).mean()

def _out(b, mask, side, sl, tp, max_bars, vol, trail=0.0, cap=None):
    m = mask.to_numpy() & np.isfinite(sl) & (sl > 0)
    idx = b.m1_idx.to_numpy()[m] if "m1_idx" in b else np.flatnonzero(m)
    s = sl[m]
    if cap is not None:
        s = np.minimum(s, cap)
    tpv = (tp[m] if hasattr(tp, "__len__") else np.full(m.sum(), tp))
    trv = (trail[m] if hasattr(trail, "__len__") else np.full(m.sum(), trail))
    return pd.DataFrame({"idx": idx, "side": side[m] if hasattr(side, "__len__") else side, "kind": 0, "sl": s, "tp": tpv,
                         "max_bars": max_bars, "trail": trv, "volume": vol})

def hours_mask(b, h0, h1, col="nyh"):
    h = b[col]
    return (h >= h0) & (h < h1) if h0 <= h1 else (h >= h0) | (h < h1)

def donchian(b, n, slk, tpk, mb, vol, hm=None, cap=None, an=14, trailk=0.0, fade=False):
    a = atr(b, an).to_numpy()
    hi = b.high.rolling(n).max().shift(1); lo = b.low.rolling(n).min().shift(1)
    up = (b.close > hi) & (b.close.shift(1) <= hi.shift(1)); dn = (b.close < lo) & (b.close.shift(1) >= lo.shift(1))
    side = np.where(up, 1, -1) * (-1 if fade else 1)
    m = up | dn
    if hm is not None: m &= hm
    return _out(b, m, side, slk * a, tpk * a, mb, vol, trail=trailk * a, cap=cap)

def zfade(b, n, zt, slk, tpk, mb, vol, hm=None, cap=None, an=14, trend=False):
    a = atr(b, an).to_numpy()
    ma = b.close.rolling(n).mean(); sd = b.close.rolling(n).std()
    z = (b.close - ma) / sd
    up = (z > zt) & (z.shift(1) <= zt); dn = (z < -zt) & (z.shift(1) >= -zt)
    side = np.where(up, -1, 1) * (-1 if trend else 1)
    m = up | dn
    if hm is not None: m &= hm
    return _out(b, m, side, slk * a, tpk * a, mb, vol, cap=cap)

def tsmom(b, k, thr, slk, mb, vol, hm=None, cap=None, an=14, every=None, tpk=0.0):
    a = atr(b, an).to_numpy()
    r = (b.close - b.close.shift(k)) / (a * np.sqrt(k))
    m = (r.abs() > thr)
    if every: m &= (np.arange(len(b)) % every == 0)
    if hm is not None: m &= hm
    return _out(b, m, np.sign(r.to_numpy()), slk * a, tpk * a, mb, vol, cap=cap)
