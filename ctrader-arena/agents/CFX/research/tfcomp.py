"""Timeframe comparison: same rule on H1, H2, H4, D1 bars resampled from H1 (ETH; BTC for reference)."""
import lib
lib.START = lib.pd.Timestamp("2023-05-01"); lib._cache.clear()
from lib import *
from arena import engine
def rs(b, hours):
    g = b.ts // (hours * 3600_000)
    a = b.groupby(g).agg(ts=("ts", "first"), time=("time", "first"), open=("open", "first"), high=("high", "max"),
                         low=("low", "min"), close=("close", "last"), volume=("volume", "sum"))
    return a.iloc[:-1].reset_index(drop=True)
for sid, vol, sp in [(102, 0.1, 2.0), (101, 0.01, 25.0)]:
    for hours, Hb in [(1, 2), (2, 1), (4, 1), (24, 1)]:
        b = rs(bars(sid), hours) if hours > 1 else bars(sid)
        o, h, l, c = b.open.to_numpy(), b.high.to_numpy(), b.low.to_numpy(), b.close.to_numpy()
        atr = pd.Series(h - l).rolling(24).mean().to_numpy(); body = c - o
        idx = np.where(np.abs(body) > 2.5 * np.nan_to_num(atr, nan=np.inf))[0]
        od = pd.DataFrame({"idx": idx, "side": np.sign(body[idx]), "kind": 0, "sl": 2.0 * atr[idx], "tp": 0.0, "max_bars": Hb, "volume": vol})
        tr = engine.simulate(b, od, spread=sp, slip=0.2 * sp)
        p = tr.pnl.to_numpy()
        print(f"{NAMES[sid]} TF={hours}h hold={Hb} bar(s): n={len(p)} PF={pf(p):.2f} t={p.mean()/p.std()*np.sqrt(len(p)):.2f} net={p.sum():.1f}  (no rollover guard)")
