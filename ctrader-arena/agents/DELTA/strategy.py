"""DELTA - "PreOpenFade": fade failed range breakouts of the US SP 500 CFD in the European morning.

Hypothesis (stated before fitting): between 03:00 and 09:30 New York time the S&P 500 CFD trades on thin,
Europe-driven flow with no US cash market and (mostly) no US news. Breakouts of the prior multi-hour range in
that window are liquidity events rather than information and tend to revert (variance ratio < 1 in that window).

Rules (signals on completed M15 bars, built from M1):
  * Window: M15 bar opens 03:00 <= t < 09:30 America/New_York (DST-aware).
  * Short when the M15 close crosses ABOVE the highest high of the previous N=32 completed M15 bars (8 h);
    long when it crosses BELOW the lowest low of the previous 32 bars.
  * Market entry on the next M1 open. SL = min(2 x ATR14(M15), 14 pts) -> max ~$1.40 at 0.1 units.
    TP = 1 x ATR14(M15). Time exit after 240 minutes. One position at a time.
All parameters were chosen on a PRE-SAMPLE (M15 history 2026-03-26 .. 2026-09-09) that lies entirely before
the official M1 window, see NOTES.md.
"""
import numpy as np, pandas as pd
from arena.engine import resample

LEGS = [{"symbol_id": 2517,
         "params": {"tf": 15, "n": 32, "atr_n": 14, "sl_atr": 2.0, "tp_atr": 1.0, "sl_cap": 14.0,
                    "hold_min": 240, "start_h": 3.0, "end_h": 9.5},
         "max_open": 1}]

_COLS = ["idx", "side", "kind", "price", "sl", "tp", "max_bars", "trail", "valid", "volume"]


def signals(m1, p, spec):
    b = resample(m1, p["tf"])
    if len(b) < p["n"] + p["atr_n"] + 2:
        return pd.DataFrame({c: [] for c in _COLS})
    ny = b.time.dt.tz_localize("UTC").dt.tz_convert("America/New_York")
    nyh = (ny.dt.hour + ny.dt.minute / 60.0).to_numpy()
    in_win = (nyh >= p["start_h"]) & (nyh < p["end_h"])

    pc = b.close.shift(1)
    tr = np.maximum(b.high - b.low, np.maximum((b.high - pc).abs(), (b.low - pc).abs()))
    atr = tr.rolling(p["atr_n"]).mean().to_numpy()

    hi = b.high.rolling(p["n"]).max().shift(1)          # prior N completed bars only
    lo = b.low.rolling(p["n"]).min().shift(1)
    up = ((b.close > hi) & (b.close.shift(1) <= hi.shift(1))).to_numpy()   # fresh upside breakout -> SHORT
    dn = ((b.close < lo) & (b.close.shift(1) >= lo.shift(1))).to_numpy()   # fresh downside breakout -> LONG

    m = (up | dn) & in_win & np.isfinite(atr) & (atr > 0)
    a = atr[m]
    return pd.DataFrame({
        "idx": b.m1_idx.to_numpy()[m].astype(np.int64),
        "side": np.where(up[m], -1, 1),
        "kind": 0, "price": 0.0,
        "sl": np.minimum(p["sl_atr"] * a, p["sl_cap"]),
        "tp": p["tp_atr"] * a,
        "max_bars": int(p["hold_min"]), "trail": 0.0, "valid": 1,
        "volume": float(spec["min_units"]),
    })[_COLS]
