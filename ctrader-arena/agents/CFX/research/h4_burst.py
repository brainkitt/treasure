"""H4: crypto momentum burst. After an impulsive H1 bar, ride continuation for a few hours.
Why: liquidation cascades / stop runs and momentum-chasing retail flow in 24/7 crypto with leveraged perps;
order flow is autocorrelated over 1-3 hours after a shock."""
from lib import *
import itertools
VOL = {101: 0.01, 102: 0.1, 2408: 10.0, 2387: 0.1}

def burst(sid, k=2.0, H=3, slm=1.5, tpm=0.0, n=48, roll=21, wick=0.0, both=True):
    b = bars(sid)
    rngm = (b.high - b.low).rolling(n).mean().to_numpy()
    o, c, h, l = b.open.to_numpy(), b.close.to_numpy(), b.high.to_numpy(), b.low.to_numpy()
    body = c - o
    hr = b.time.dt.hour.to_numpy()
    rows = []
    for i in np.where(np.abs(body) > k * rngm)[0]:
        if i < n: continue
        side = 1 if body[i] > 0 else -1
        if not both and side < 0: continue
        # close location filter: close in the outer part of the bar
        if wick > 0:
            pos = (c[i] - l[i]) / max(h[i] - l[i], 1e-12)
            if (side > 0 and pos < 1 - wick) or (side < 0 and pos > wick): continue
        # rollover guard: entry at bar i+1 opens at hour hr[i]+1; exit at close of bar i+H -> must end before roll
        start = (hr[i] + 1) % 24
        hours = [(start + j) % 24 for j in range(H)]
        if roll in hours: continue
        a = rngm[i]
        rows.append((i, side, 0, slm * a, tpm * a, H))
    return pd.DataFrame(rows, columns=["idx", "side", "kind", "sl", "tp", "max_bars"]).assign(volume=VOL[sid])

if __name__ == "__main__":
    res = []
    for k, H, slm, tpm in itertools.product([1.5, 2.0, 2.5, 3.0], [1, 2, 3, 4, 6], [1.0, 1.5, 2.0], [0.0, 2.0]):
        ps, po = [], []
        for sid in [101, 102]:
            tr = sim(sid, burst(sid, k, H, slm, tpm)); sp = split_time(sid)
            i = (pd.to_datetime(tr.entry_time) < sp).to_numpy()
            ps.append(tr.pnl.to_numpy()[i]); po.append(tr.pnl.to_numpy()[~i])
        p = np.concatenate(ps)
        res.append((k, H, slm, tpm, len(p), pf(p), p.mean() / p.std() * np.sqrt(len(p))))
    df = pd.DataFrame(res, columns=["k", "H", "slm", "tpm", "n", "isPF", "t"])
    df.to_csv("h4_grid.csv", index=False)
    print(len(df), "sets; IS PF quantiles", df.isPF.quantile([0, .25, .5, .75, 1]).round(2).tolist())
    print(df.pivot_table(index="k", columns="H", values="isPF", aggfunc="median").round(2))
    print(df.sort_values("isPF").tail(10).to_string())
