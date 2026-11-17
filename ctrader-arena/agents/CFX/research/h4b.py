"""H4 refinement: burst with optional filters. IS-only grid on BTC+ETH."""
from lib import *
import itertools
VOL = {101: 0.01, 102: 0.1, 2408: 10.0, 2387: 0.1}
BLOCK = {20, 21, 22}   # never hold through 20:00-22:59 UTC (rollover / swap risk, thin liquidity)

def burst2(sid, k=2.5, n=48, H=2, slm=2.0, wick=0.0, trendL=0, volm=0.0, tpm=0.0):
    b = bars(sid)
    rng = (b.high - b.low).to_numpy()
    rngm = pd.Series(rng).rolling(n).mean().to_numpy()
    o, c, h, l = b.open.to_numpy(), b.close.to_numpy(), b.high.to_numpy(), b.low.to_numpy()
    v = b.volume.to_numpy().astype(float); vm = pd.Series(v).rolling(n).mean().to_numpy()
    body = c - o; hr = b.time.dt.hour.to_numpy()
    rows = []
    for i in np.where(np.abs(body) > k * np.nan_to_num(rngm, nan=1e18))[0]:
        side = 1 if body[i] > 0 else -1
        if wick > 0:
            pos = (c[i] - l[i]) / max(h[i] - l[i], 1e-12)
            if (side > 0 and pos < 1 - wick) or (side < 0 and pos > wick): continue
        if trendL > 0:
            if i < trendL or np.sign(c[i] - c[i - trendL]) != side: continue
        if volm > 0 and not (v[i] > volm * vm[i]): continue
        if any(((hr[i] + 1 + j) % 24) in BLOCK for j in range(H)): continue
        rows.append((i, side, 0, slm * rngm[i], tpm * rngm[i], H))
    return pd.DataFrame(rows, columns=["idx", "side", "kind", "sl", "tp", "max_bars"]).assign(volume=VOL[sid])

def pooled(sids, **kw):
    ps, po = [], []
    for sid in sids:
        tr = sim(sid, burst2(sid, **kw)); sp = split_time(sid)
        i = (pd.to_datetime(tr.entry_time) < sp).to_numpy()
        ps.append(tr.pnl.to_numpy()[i]); po.append(tr.pnl.to_numpy()[~i])
    return np.concatenate(ps), np.concatenate(po)

if __name__ == "__main__":
    res = []
    grid = list(itertools.product([2.0, 2.5, 3.0], [24, 48, 96], [1, 2, 3], [1.0, 2.0], [0.0, 0.3], [0, 24], [0.0, 1.5]))
    for k, n, H, slm, wick, trendL, volm in grid:
        p, _ = pooled([101, 102], k=k, n=n, H=H, slm=slm, wick=wick, trendL=trendL, volm=volm)
        res.append((k, n, H, slm, wick, trendL, volm, len(p), pf(p), p.mean() / p.std() * np.sqrt(len(p)) if len(p) > 2 else 0))
    df = pd.DataFrame(res, columns=["k", "n", "H", "slm", "wick", "trendL", "volm", "n_is", "isPF", "t"])
    df.to_csv("h4b_grid.csv", index=False)
    print(len(df), "sets; IS PF quantiles", df.isPF.quantile([0, .25, .5, .75, 1]).round(2).tolist())
    for col in ["k", "n", "H", "slm", "wick", "trendL", "volm"]:
        print(col, df.groupby(col).isPF.median().round(3).to_dict(), "| t", df.groupby(col).t.median().round(2).to_dict())
    print(df[df.n_is >= 120].sort_values("t").tail(12).to_string())
