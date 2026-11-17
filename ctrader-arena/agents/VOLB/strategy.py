"""VOLB - Drift Switch 30 long-only regime follower with a live entry-spread cap (Deriv DSI30, M5).

Why this is the VOLB finalist (see NOTES.md): the round-3 screen of 47 continuous synthetics (Volatility 5..250
incl. (1s) and HF versions, Step 100..10000, Multi Step 2/3/4, VolSwitch L/M/H, DSI 10/20/30) found NO
statistical structure except the documented Drift Switch regimes. Volatility / Step / Multi Step / VolSwitch
behave as fair random walks (BH-corrected screens, null-simulation controls, out-of-time checks), so no
strategy on them can beat the spread. DSI30 has the largest gross edge per trade (~5 pts long-only).

Mechanism tried here that VOL (rounds 1-2) did not use: COST-SIDE selection.
  * long-only -> the spread is paid exactly once, at entry (exits/stops execute on the BID);
  * the cBot refuses entries when the live spread exceeds `max_spread` (spread cap), so the cost actually paid
    can never exceed the cap.
The backtest cannot know which signals the cap would block (no spread history exists), so the official run
uses the WIDEST DSI30 spread ever observed (10.16) - i.e. it assumes the cap never helps. Live samples show
DSI30's spread is 6.5-10 exactly when it drifts, so the cap would block most real signals: NOT an edge.

Signal (decided on the close of a completed M5 bar, filled at next open):
  er = (close - close[N]) / sum |dclose| over N bars;  long if er > thr
  SL = sl_atr * ATR(atr_n), trailing stop = trail_atr * ATR, time exit after max_bars bars.
  No entries on bars stamped 18:50-21:05 UTC (no trade can cross the 21:00 rollover -> no swap).
"""
import numpy as np
import pandas as pd

START_BALANCE = 60.0

PARAMS = {"N": 6, "thr": 0.8, "atr_n": 20, "sl_atr": 2.5, "trail_atr": 1.5, "max_bars": 24,
          "units": 0.10, "no_entry_from": 18 * 60 + 50, "no_entry_to": 21 * 60 + 5}

LEGS = [{"symbol_id": 2470, "period": "M_5", "params": dict(PARAMS), "max_open": 1}]


def signals(bars, params, spec):
    p = {**PARAMS, **params}
    N = int(p["N"])
    c = bars.close.to_numpy(float)
    d = np.abs(np.diff(c, prepend=c[0]))
    path = pd.Series(d).rolling(N).sum().to_numpy()
    prev = np.concatenate([np.full(N, np.nan), c[:-N]])
    er = (c - prev) / np.maximum(path, 1e-12)
    atr = pd.Series((bars.high - bars.low).to_numpy(float)).rolling(int(p["atr_n"])).mean().to_numpy()
    gap = bars.time.diff().dt.total_seconds().fillna(300).to_numpy() > 450
    clean = pd.Series(gap.astype(float)).rolling(max(N, int(p["atr_n"])) + 1).sum().to_numpy() == 0
    mins = (bars.time.dt.hour * 60 + bars.time.dt.minute).to_numpy()
    window_ok = ~((mins >= p["no_entry_from"]) & (mins < p["no_entry_to"]))
    sig = (er > p["thr"]) & clean & np.isfinite(atr) & (atr > 0) & window_ok
    i = np.where(sig)[0]
    i = i[i < len(c) - 1]
    vol = max(float(p["units"]), float(spec.get("min_units") or p["units"]))
    return pd.DataFrame({"idx": i, "side": 1.0, "kind": 0, "price": 0.0,
                         "sl": p["sl_atr"] * atr[i], "tp": 0.0, "max_bars": int(p["max_bars"]),
                         "trail": p["trail_atr"] * atr[i], "valid": 1, "volume": vol})
