"""CHARLIE round 2 - USDJPY New-York-morning passive band fade (LIMIT entries).

HONEST STATUS: NOT an edge. Chosen on the M15 pre-sample (2026-03-31..2026-09-15) where it scored PF 1.00
(halves 1.08 / 0.96); no rule in 352 pre-sample parameter sets held PF > 1.2 in both halves. Submitted as the best
honest FX candidate with its true forward numbers. See NOTES.md.

Hypothesis (stated first): short-horizon FX moves beyond a volatility band partly revert (true in mid prices: PF 1.2-2.1
at zero spread); entering with a resting limit order half an ATR beyond the extreme should recover the spread.
Rules (signals on completed M15 bars built from M1; times are America/New_York, DST-aware):
  * Bollinger(20) z-score of the M15 close; ATR(14) simple mean of true range.
  * M15 bar starting 08:00 <= t < 12:00 NY with |z| > 2.0  ->  fade with a LIMIT order `off`=0.5 ATR beyond the close
    (buy limit below the bid-close in ASK terms / sell limit above the ask in BID terms), valid 30 minutes.
  * SL = min(1.5 ATR, 22 pips) (max loss $1.38 at 1000 units), TP = max(|close - mean|, 0.3 ATR), time exit 90 min.
  * One position at a time; everything is flat by 14:15 NY, hours before the 17:00 NY rollover.
"""
import numpy as np, pandas as pd
from arena.engine import resample

LEGS = [{"symbol_id": 4, "params": {"tf": 15, "n": 20, "atr_n": 14, "k": 2.0, "off": 0.5, "sl_atr": 1.5, "sl_cap": 0.22,
                                    "tp_min_atr": 0.3, "valid_bars": 2, "hold_bars": 6, "h0": 8.0, "h1": 12.0,
                                    "tz": "America/New_York"}, "max_open": 1}]
_COLS = ["idx", "side", "kind", "price", "sl", "tp", "max_bars", "valid", "volume"]


def signals(m1, p, spec):
    b = resample(m1, p["tf"])
    if len(b) < p["n"] + p["atr_n"] + 2:
        return pd.DataFrame({c: [] for c in _COLS})
    c = b.close
    ma = c.rolling(p["n"]).mean(); sd = c.rolling(p["n"]).std()
    pc = c.shift()
    tr = np.maximum(b.high - b.low, np.maximum((b.high - pc).abs(), (b.low - pc).abs()))
    atr = tr.rolling(p["atr_n"]).mean().to_numpy()
    z = ((c - ma) / sd).to_numpy()
    lt = b.time.dt.tz_localize("UTC").dt.tz_convert(p["tz"])
    hr = (lt.dt.hour + lt.dt.minute / 60.0).to_numpy()
    ok = (hr >= p["h0"]) & (hr < p["h1"]) & (np.abs(np.nan_to_num(z)) > p["k"]) & ~np.isnan(atr) & (lt.dt.dayofweek.to_numpy() < 5)
    i = np.where(ok)[0]
    C = c.to_numpy()[i]; A = atr[i]; side = -np.sign(z[i]); spr = spec["spread"]
    price = np.where(side > 0, C - p["off"] * A, C + spr + p["off"] * A)
    return pd.DataFrame({"idx": b.m1_idx.to_numpy()[i], "side": side, "kind": 1, "price": price,
                         "sl": np.minimum(p["sl_atr"] * A, p["sl_cap"]),
                         "tp": np.maximum(np.abs(C - ma.to_numpy()[i]), p["tp_min_atr"] * A),
                         "max_bars": int(p["hold_bars"] * p["tf"]), "valid": int(p["valid_bars"] * p["tf"]),
                         "volume": float(spec["min_units"])})
