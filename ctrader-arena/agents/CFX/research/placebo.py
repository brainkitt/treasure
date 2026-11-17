"""Try to disprove: reversed direction, random direction (same entries/stops), random entry times."""
import lib
lib.START = lib.pd.Timestamp("2023-05-01"); lib._cache.clear(); lib.SPREAD[102] = 2.0
from h4b import *
od = burst2(102, k=2.5, n=24, H=2, slm=2.0)
p0 = sim(102, od, slip_frac=0.2).pnl; print("real PF %.2f n %d" % (pf(p0), len(p0)))
print("reversed PF %.2f" % pf(sim(102, od.assign(side=-od.side), slip_frac=0.2).pnl))
rng = np.random.default_rng(1)
r = [pf(sim(102, od.assign(side=rng.choice([-1, 1], len(od))), slip_frac=0.2).pnl) for _ in range(200)]
print("random-direction PF median %.2f 95%% %.2f max %.2f; P(>=real)=%.3f" % (np.median(r), np.percentile(r, 95), max(r), np.mean(np.array(r) >= pf(p0))))
b = bars(102); atr = (b.high - b.low).rolling(24).mean().to_numpy(); body = (b.close - b.open).to_numpy()
hr = b.time.dt.hour.to_numpy(); ok = np.array([not any(((h + 1 + j) % 24) in BLOCK for j in range(3)) for h in hr]) & ~np.isnan(atr)
cand = np.where(ok)[0]; rr = []
for _ in range(200):
    idx = np.sort(rng.choice(cand, len(od), replace=False))
    o2 = pd.DataFrame({"idx": idx, "side": np.sign(body[idx]), "kind": 0, "sl": 2 * atr[idx], "tp": 0.0, "max_bars": 2, "volume": 0.1})
    rr.append(pf(sim(102, o2, slip_frac=0.2).pnl))
print("random-time (bar-direction) PF median %.2f 95%% %.2f; P(>=real)=%.3f" % (np.median(rr), np.percentile(rr, 95), np.mean(np.array(rr) >= pf(p0))))
