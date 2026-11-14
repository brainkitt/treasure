"""Phase-2 research core: PreOpenFade on M15 bars directly."""
import sys, os, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
from arena.ingest import load
from arena import engine

BASE = dict(n=32, atr_n=14, sl_atr=2.0, tp_atr=1.0, sl_cap=14.0, hold=16, start_h=3.0, end_h=9.5, prove=0, vol=0.1)

def sig(b, p):
    ny = b.time.dt.tz_localize("UTC").dt.tz_convert("America/New_York")
    nyh = (ny.dt.hour + ny.dt.minute / 60.0).to_numpy()
    in_win = (nyh >= p["start_h"]) & (nyh < p["end_h"])
    pc = b.close.shift(1)
    tr = np.maximum(b.high - b.low, np.maximum((b.high - pc).abs(), (b.low - pc).abs()))
    atr = tr.rolling(p["atr_n"]).mean().to_numpy()
    hi = b.high.rolling(p["n"]).max().shift(1); lo = b.low.rolling(p["n"]).min().shift(1)
    up = ((b.close > hi) & (b.close.shift(1) <= hi.shift(1))).to_numpy()
    dn = ((b.close < lo) & (b.close.shift(1) >= lo.shift(1))).to_numpy()
    m = (up | dn) & in_win & np.isfinite(atr) & (atr > 0)
    a = atr[m]
    return pd.DataFrame({"idx": np.flatnonzero(m).astype(np.int64), "side": np.where(up[m], -1, 1), "kind": 0, "price": 0.0,
        "sl": np.minimum(p["sl_atr"] * a, p["sl_cap"]), "tp": p["tp_atr"] * a, "max_bars": int(p["hold"]),
        "trail": 0.0, "valid": 1, "volume": p["vol"], "prove": int(p["prove"])})

def run(b, p=None, spread=0.36, **kw):
    q = dict(BASE); q.update(p or {}); q.update(kw)
    return engine.simulate(b, sig(b, q), spread=spread)

def pf(x):
    x = np.asarray(x); g = x[x > 0].sum(); l = -x[x < 0].sum()
    return g / l if l > 0 else np.inf

def half(tr):
    t = pd.to_datetime(tr.entry_time)
    k = t.dt.year.astype(str) + "H" + ((t.dt.month > 6) + 1).astype(str)
    return tr.groupby(k).pnl.agg(n="size", pf=pf, net="sum", win=lambda s: (s > 0).mean() * 100, worst="min").round(2)

def line(tr, label=""):
    if len(tr) == 0: return f"{label:30s} none"
    eq = np.cumsum(tr.pnl.to_numpy()); dd = (np.maximum.accumulate(np.r_[0, eq])[1:] - eq).max()
    mo = tr.groupby(pd.to_datetime(tr.exit_time).dt.to_period("M")).pnl.sum()
    return f"{label:30s} n={len(tr):4d} PF={pf(tr.pnl):5.2f} net={tr.pnl.sum():7.2f} win={(tr.pnl>0).mean()*100:3.0f}% worst={tr.pnl.min():6.2f} dd={dd:5.2f} mo+={(mo>0).mean()*100:3.0f}%"
