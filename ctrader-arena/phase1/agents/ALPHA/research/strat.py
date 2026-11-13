from lib import *

def prep(b, tfmin):
    b = b.copy(); b["h"] = b.time.dt.hour + b.time.dt.minute / 60; b["d"] = b.time.dt.floor("D"); b["dow"] = b.time.dt.dayofweek
    return b

def orb(b, tfmin, pip, r0, r1, e1, xh, slm=1.0, slcap=15, slmin=5, tpm=2.0, minr=0, maxr=1e9, buf=0.0, both=False):
    """Range [r0,r1) hours; first M-bar close beyond range within [r1,e1) -> market entry; SL=clip(slm*range) pips, TP=tpm*SL; exit at xh."""
    rows = []
    for d, g in b.groupby("d", sort=True):
        rg = g[(g.h >= r0) & (g.h < r1)]
        if len(rg) < (r1 - r0) * 60 / tfmin * 0.7: continue
        hi, lo = rg.high.max(), rg.low.min(); R = (hi - lo) / pip
        if R < minr or R > maxr: continue
        eg = g[(g.h >= r1) & (g.h < e1)]
        done = set()
        for i, row in eg.iterrows():
            s = 1 if row.close > hi + buf * pip else (-1 if row.close < lo - buf * pip else 0)
            if s == 0 or s in done: continue
            done.add(s)
            sl = float(np.clip(slm * R, slmin, slcap))
            mb = int(round((xh - row.h) * 60 / tfmin)) - 1
            if mb < 1: continue
            rows.append((i, s, sl * pip, tpm * sl * pip, mb))
            if not both: break
    return pd.DataFrame(rows, columns=["idx", "side", "sl", "tp", "max_bars"]).assign(kind=0)

def meanrev(b, tfmin, pip, h0, h1, n=24, k=2.0, sl=10, tp=0, tpfrac=1.0, mb=24, minsd=0):
    """Fade: close beyond mean +- k*sd (rolling n) during [h0,h1) (wraps midnight). TP = tpfrac*distance to mean (or fixed tp pips)."""
    ma = b.close.rolling(n).mean(); sd = b.close.rolling(n).std()
    z = (b.close - ma) / sd
    inh = ((b.h >= h0) & (b.h < h1)) if h0 < h1 else ((b.h >= h0) | (b.h < h1))
    sig = inh & (z.abs() > k) & (sd / pip > minsd)
    r = b[sig]
    side = -np.sign(z[sig]).to_numpy()
    dist = (b.close - ma).abs()[sig].to_numpy()
    tpv = np.full(len(r), tp * pip) if tp > 0 else np.maximum(tpfrac * dist, 2 * pip)
    return pd.DataFrame({"idx": r.index.to_numpy(), "side": side, "kind": 0, "sl": sl * pip, "tp": tpv, "max_bars": mb})
