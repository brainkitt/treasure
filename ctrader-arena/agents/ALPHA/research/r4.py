"""Final round: passive LIMIT fades of M5/M15 band extremes. TRAIN Jan-Jun 2026, VALIDATE Jul..09-20, FORWARD official window."""
from lib import *
SP = {1: 0.00013, 2: 0.00014}
TR0, TR1, VA1 = pd.Timestamp("2026-01-01"), pd.Timestamp("2026-07-01"), pd.Timestamp("2026-09-21")
RAW = {s: load(s, "M_5") for s in (1, 2)}
def frame(s, tf):
    b = RAW[s] if tf == 5 else engine.resample(RAW[s], tf).drop(columns="m1_idx")
    return b.reset_index(drop=True)
def orders(b, tf, n, k, tpf, slm, hold, hours, pip, sp, slcap=14.0):
    ma = b.close.rolling(n).mean(); tr = (b.high - b.low).rolling(n).mean()
    mins = b.time.dt.hour * 60 + b.time.dt.minute + tf            # time the order goes live (UTC minutes)
    end = mins + (hold + 1) * tf
    ok = ((end <= 20 * 60 + 45) | (mins >= 22 * 60 + 30)) & (mins >= hours[0] * 60) & (mins < hours[1] * 60) & ma.notna() & (b.time.dt.dayofweek < 5)
    d = k * tr; tp = np.maximum(tpf * d, 2 * pip); sl = np.minimum(np.maximum(slm * tr, 4 * pip), slcap * pip)
    out = {}
    for side in (1, -1):
        px = (ma - d + sp) if side > 0 else (ma + d)               # buy limit in ASK terms sits at bid level MA-d ; sell limit in BID terms
        # only orders resting away from the market: buy below current ask, sell above current bid
        m = ok & ((px < b.close + sp) if side > 0 else (px > b.close))
        out[side] = pd.DataFrame({"idx": b.index[m], "side": side, "kind": 1, "price": px[m].to_numpy(), "sl": sl[m].to_numpy(), "tp": tp[m].to_numpy(), "max_bars": hold, "valid": 1})
    return out
def sim(s, cfg, lo, hi, mult=1.0):
    tf = cfg["tf"]; b = frame(s, tf); b = b[(b.time >= lo) & (b.time < hi)].reset_index(drop=True)
    od = orders(b, tf, cfg["n"], cfg["k"], cfg["tpf"], cfg["slm"], cfg["hold"], cfg["hours"], PIP[s], SP[s] * mult)
    trs = []
    for side in (1, -1):
        o = od[side].copy(); o["volume"] = 1000.0
        trs.append(engine.simulate(b, o, spread=SP[s] * mult, max_open=1))
    t = pd.concat(trs); t["sid"] = s; return t
def both(cfg, lo, hi, mult=1.0): return pd.concat([sim(s, cfg, lo, hi, mult) for s in (1, 2)]).sort_values("exit_time")
def st(t):
    if len(t) == 0: return "n=0"
    eq = t.pnl.cumsum(); dd = (eq.cummax().clip(lower=0) - eq).max()
    return f"n={len(t):4d} PF={pf(t.pnl):4.2f} net={t.pnl.sum():7.2f} win={100*(t.pnl>0).mean():2.0f}% dd={dd:5.2f} worst={t.pnl.min():5.2f}"
if __name__ == "__main__":
    import itertools
    res = []
    for tf, k, tpf, slm, hours in itertools.product((5, 15), (1.5, 2.0, 3.0), (0.5, 1.0), (2.0, 4.0), ((0, 24), (0, 7), (7, 20))):
        cfg = dict(tf=tf, n=20, k=k, tpf=tpf, slm=slm, hold=12, hours=hours)
        t = both(cfg, TR0, TR1); res.append((pf(t.pnl) if len(t) else 0, len(t), t.pnl.sum(), cfg))
    res.sort(key=lambda r: -r[0])
    print("TRAIN grid: %d configs; PF>1.0: %d; PF>1.2: %d; median PF %.2f" % (len(res), sum(r[0] > 1 for r in res), sum(r[0] > 1.2 for r in res), np.median([r[0] for r in res])))
    for r in res[:12]: print(f"PF={r[0]:.2f} n={r[1]:4d} net={r[2]:7.2f}", {k: v for k, v in r[3].items() if k not in ("n", "hold")})
    print("worst:", [round(r[0], 2) for r in res[-5:]])
    # zero-spread diagnostic for the median config
    cfg = dict(tf=5, n=20, k=2.0, tpf=1.0, slm=4.0, hold=12, hours=(0, 24)); print("diag k2 tf5 all-hours TRAIN:", st(both(cfg, TR0, TR1)), "| zero-spread:", st(both(cfg, TR0, TR1, mult=1e-9)))
