"""Family B: passive limit fade of the rolling N-bar range extreme (M15), bigger targets. TRAIN only."""
from r4 import *
import itertools
def orders_b(b, tf, N, off, tpf, sl_pips, hold, hours, pip, sp):
    hi = b.high.rolling(N).max(); lo = b.low.rolling(N).min(); R = hi - lo
    mins = b.time.dt.hour * 60 + b.time.dt.minute + tf; end = mins + (hold + 1) * tf
    ok = ((end <= 20 * 60 + 45) | (mins >= 22 * 60 + 30)) & (mins >= hours[0] * 60) & (mins < hours[1] * 60) & R.notna() & (b.time.dt.dayofweek < 5)
    tp = np.maximum(tpf * R, 3 * pip); out = {}
    for side in (1, -1):
        px = (lo - off * pip + sp) if side > 0 else (hi + off * pip)
        m = ok & ((px < b.close + sp) if side > 0 else (px > b.close))
        out[side] = pd.DataFrame({"idx": b.index[m], "side": side, "kind": 1, "price": px[m].to_numpy(), "sl": sl_pips * pip, "tp": tp[m].to_numpy(), "max_bars": hold, "valid": 1})
    return out
def simb(cfg, lo, hi, mult=1.0):
    trs = []
    for s in (1, 2):
        b = frame(s, 15); b = b[(b.time >= lo) & (b.time < hi)].reset_index(drop=True)
        od = orders_b(b, 15, cfg["N"], cfg["off"], cfg["tpf"], cfg["sl"], cfg["hold"], cfg["hours"], PIP[s], SP[s] * mult)
        for side in (1, -1):
            o = od[side].copy(); o["volume"] = 1000.0; trs.append(engine.simulate(b, o, spread=SP[s] * mult, max_open=1))
    return pd.concat(trs).sort_values("exit_time")
res = []
for N, off, tpf, sl, hours in itertools.product((16, 48, 96), (0, 3), (0.25, 0.5), (8, 14), ((0, 24), (0, 7), (7, 20))):
    cfg = dict(N=N, off=off, tpf=tpf, sl=sl, hold=16, hours=hours); t = simb(cfg, TR0, TR1); res.append((pf(t.pnl) if len(t) else 0, len(t), t.pnl.sum(), cfg))
res.sort(key=lambda r: -r[0])
print("TRAIN grid B: %d configs; PF>1.0: %d; PF>1.2: %d; median %.2f; best %.2f worst %.2f" % (len(res), sum(r[0] > 1 for r in res), sum(r[0] > 1.2 for r in res), np.median([r[0] for r in res]), res[0][0], res[-1][0]))
for r in res[:6]: print(f"PF={r[0]:.2f} n={r[1]:4d} net={r[2]:7.2f}", {k: v for k, v in r[3].items() if k != "hold"})
top = res[0][3]; print("top config zero-spread TRAIN:", st(simb(top, TR0, TR1, mult=1e-9)))
