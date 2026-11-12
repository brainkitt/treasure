"""Candidate signal generators in final (engine) form. All session hours are Europe/London local time."""
import numpy as np, pandas as pd
from arena.engine import resample

def bars_local(m1, tf, tz="Europe/London"):
    b = resample(m1, tf) if tf > 1 else m1.assign(m1_idx=np.arange(len(m1)))
    lt = b.time.dt.tz_localize("UTC").dt.tz_convert(tz)
    b = b.assign(h=(lt.dt.hour + lt.dt.minute / 60).to_numpy(), d=lt.dt.strftime("%Y-%m-%d").to_numpy(), dow=lt.dt.dayofweek.to_numpy())
    return b

def orb(m1, p, pip):
    """Opening-range breakout. Range [r0,r1) local hours; entries in [r1,e1) on first tf-bar CLOSE beyond range (+buf);
    SL = clip(slm*range, slmin, slcap) pips; TP = tpm*SL; time exit at xh. sides: 'first' (only first break) or 'both'."""
    tf = p.get("tf", 5); b = bars_local(m1, tf, p.get("tz", "Europe/London"))
    r0, r1, e1, xh = p["r0"], p["r1"], p["e1"], p["xh"]
    rows = []
    h = b.h.to_numpy(); hi_ = b.high.to_numpy(); lo_ = b.low.to_numpy(); c = b.close.to_numpy(); mi = b.m1_idx.to_numpy()
    for d, ix in b.groupby("d", sort=True).indices.items():
        hh = h[ix]
        rm = (hh >= r0) & (hh < r1)
        if rm.sum() < (r1 - r0) * 60 / tf * 0.7: continue
        hi = hi_[ix][rm].max(); lo = lo_[ix][rm].min(); R = (hi - lo) / pip
        if R < p.get("minr", 0) or R > p.get("maxr", 1e9): continue
        sl = float(np.clip(p.get("slm", 1.0) * R, p.get("slmin", 5), p.get("slcap", 15)))
        done = set()
        for j in np.where((hh >= r1) & (hh < e1))[0]:
            k = ix[j]
            s = 1 if c[k] > hi + p.get("buf", 0) * pip else (-1 if c[k] < lo - p.get("buf", 0) * pip else 0)
            if s == 0 or s in done: continue
            if p.get("maxext", 0) and abs(c[k] - (hi if s > 0 else lo)) / pip > p["maxext"]: continue
            done.add(s)
            mb = (int(round((xh - hh[j]) * 60)) - tf) // p.get("basemin", 1)
            if mb < 1: continue
            rows.append((mi[k], s, 0, sl * pip, p.get("tpm", 2.0) * sl * pip, mb))
            if p.get("sides", "first") == "first": break
    return pd.DataFrame(rows, columns=["idx", "side", "kind", "sl", "tp", "max_bars"])
