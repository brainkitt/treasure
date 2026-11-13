"""Pooled event studies on M15 across FX symbols. Returns in units of spread-cost-adjusted pips and in ATR units."""
from lib import *; from core import *
SIDS = (1, 2, 4, 7, 5, 3, 6, 8)
D = {}
for sid in SIDS:
    b = resample(load(1), 15).drop(columns="m1_idx") if sid == 1 else load(sid, "M_15")
    b = bars_local(b.assign(), 15) if False else b
    lt = b.time.dt.tz_localize("UTC").dt.tz_convert("Europe/London")
    b["h"] = lt.dt.hour + lt.dt.minute / 60; b["d"] = lt.dt.strftime("%Y-%m-%d"); b["dow"] = lt.dt.dayofweek
    b = b[b.time >= "2026-09-21"].reset_index(drop=True)
    b["IS"] = b.time < pd.Timestamp("2026-10-27")
    D[sid] = b
def summarize(lbl, rows):
    # rows: list of (IS, ret_in_pips_gross, cost_pips)
    r = pd.DataFrame(rows, columns=["IS", "g", "c", "sid"])
    out = []
    for nm, m in (("IS", r.IS), ("OOS", ~r.IS)):
        x = r[m]; 
        if len(x) < 5: out.append(f"{nm} n={len(x)}"); continue
        net = x.g - x.c
        out.append(f"{nm} n={len(x):4d} gross={x.g.mean():6.2f}p net={net.mean():6.2f}p t_gross={x.g.mean()/x.g.std()*np.sqrt(len(x)):5.2f} PFnet={pf(net):4.2f} sym+={(x.assign(n=net).groupby('sid').n.mean()>0).sum()}/{x.sid.nunique()}")
    print(f"{lbl:44s} " + " | ".join(out))

def window_ret(b, h0, h1):
    """per day: open at first bar >= h0, close of last bar < h1"""
    g = b[(b.h >= h0) & (b.h < h1)].groupby("d")
    return pd.DataFrame({"o": g.open.first(), "c": g.close.last(), "hi": g.high.max(), "lo": g.low.min(), "n": g.size(), "IS": g.IS.first()})

print("--- D: intraday momentum: sign(ret window A) -> ret window B")
for (a0, a1, b0, b1) in ((0, 7, 7, 10), (0, 7, 7, 16), (7, 9, 9, 16), (7, 10, 10, 16), (7, 12, 12, 16), (7, 12, 13, 20), (7, 13, 13, 17), (12, 15, 15, 20), (13, 16, 16, 20), (7, 16, 16, 21), (8, 9, 9, 12), (13, 14.5, 14.5, 17), (14.5, 15.5, 15.5, 20)):
    rows = []
    for sid, b in D.items():
        A = window_ret(b, a0, a1); B = window_ret(b, b0, b1); j = A.join(B, lsuffix="a", rsuffix="b", how="inner")
        j = j[(j.na >= (a1 - a0) * 4 * 0.7) & (j.nb >= (b1 - b0) * 4 * 0.7)]
        s = np.sign(j.ca - j.oa)
        for is_, g in zip(j.ISa, s * (j.cb - j.ob) / PIP[sid]): rows.append((is_, g, SPREAD[sid] / PIP[sid], sid))
    summarize(f"mom {a0}-{a1} -> {b0}-{b1}", rows)
print("--- D2: same but only when |ret A| > 0.5*range of A window median (strong moves)")
for (a0, a1, b0, b1) in ((0, 7, 7, 16), (7, 10, 10, 16), (7, 12, 12, 16), (7, 12, 13, 20), (7, 13, 13, 17), (13, 16, 16, 20)):
    rows = []
    for sid, b in D.items():
        A = window_ret(b, a0, a1); B = window_ret(b, b0, b1); j = A.join(B, lsuffix="a", rsuffix="b", how="inner")
        j = j[(j.na >= (a1 - a0) * 4 * 0.7) & (j.nb >= (b1 - b0) * 4 * 0.7)]
        thr = (j.ca - j.oa).abs().rolling(10, min_periods=5).median().shift(1)
        j = j[(j.ca - j.oa).abs() > 1.5 * thr]
        s = np.sign(j.ca - j.oa)
        for is_, g in zip(j.ISa, s * (j.cb - j.ob) / PIP[sid]): rows.append((is_, g, SPREAD[sid] / PIP[sid], sid))
    summarize(f"strong mom {a0}-{a1} -> {b0}-{b1}", rows)
print("--- C: hour-of-day drift (long each hour), pooled over symbols individually")
for sid, b in D.items():
    hr = b.assign(r=(b.close - b.open) / PIP[sid], hh=np.floor(b.h)).groupby(["d", "hh", "IS"]).r.sum().reset_index()
    t = hr.groupby(["hh", "IS"]).r.agg(lambda x: x.mean() / x.std() * np.sqrt(len(x))).unstack()
    both = t[(np.sign(t[True]) == np.sign(t[False])) & (t[True].abs() > 2.0)]
    print(sid, "hours with |t_IS|>2 & same sign OOS:", [(int(h), round(r[True], 1), round(r[False], 1)) for h, r in both.iterrows()], " | all IS |t|>2:", [(int(h), round(v, 1)) for h, v in t[True].items() if abs(v) > 2])
print("--- G: big M15 bar (body > k*ATR48) -> next 1/4/16 bars continuation")
for k in (2.0, 3.0):
    for hz in (1, 4, 16):
        rows = []
        for sid, b in D.items():
            atr = (b.high - b.low).rolling(48).mean().shift(1); body = b.close - b.open
            sig = np.sign(body) * (body.abs() > k * atr)
            f = (b.close.shift(-hz) - b.open.shift(-1))
            m = (sig != 0) & f.notna() & (b.h > 1) & (b.h < 20)
            for is_, g in zip(b.IS[m], (sig * f)[m] / PIP[sid]): rows.append((is_, g, SPREAD[sid] / PIP[sid], sid))
        summarize(f"bigbar k={k} hz={hz}", rows)
print("--- E: prior-day high/low break (first M15 close beyond PDH/PDL between 7-17) -> hold to 20:00")
rows = []; rows2 = []
for sid, b in D.items():
    dd = b.groupby("d").agg(hi=("high", "max"), lo=("low", "min"), n=("open", "size")); dd = dd[dd.n > 60]
    pdh = dd.hi.shift(1); pdl = dd.lo.shift(1)
    for d, g in b[(b.h >= 7) & (b.h < 20)].groupby("d"):
        if d not in pdh.index or np.isnan(pdh[d]): continue
        e = g[g.h < 17]
        up = e[e.close > pdh[d]]; dn = e[e.close < pdl[d]]
        for x, s in ((up, 1), (dn, -1)):
            if len(x):
                i = x.index[0]
                if i + 1 in g.index:
                    rows.append((g.IS.iloc[0], s * (g.close.iloc[-1] - b.open[i + 1]) / PIP[sid], SPREAD[sid] / PIP[sid], sid))
                    if i + 5 in g.index: rows2.append((g.IS.iloc[0], s * (b.close[i + 4] - b.open[i + 1]) / PIP[sid], SPREAD[sid] / PIP[sid], sid))
summarize("PDH/PDL break -> 20:00", rows); summarize("PDH/PDL break -> +1h", rows2)
