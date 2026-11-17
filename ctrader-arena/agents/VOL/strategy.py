"""VOL - Drift Switch regime-trend follower (Deriv Drift Switch Index, M5).

Structural premise (documented by Deriv): Drift Switch Indices (DSI10/20/30) switch between three
regimes - positive drift, negative drift, driftless - every 10/20/30 minutes ON AVERAGE. While a drift
regime lasts, price has a persistent mean; regime durations are memoryless, so a regime that is already
detected is expected to last another ~mean-duration. A trend detector (efficiency ratio over N closed M5
bars) therefore has positive expected forward return in the detected direction.

Signal (decided on the CLOSE of a completed M5 bar, filled at the next bar's open):
  er   = (close - close[N]) / sum(|close_i - close_{i-1}|, last N bars)      (efficiency ratio)
  long  if er >  thr      (shorts only if params["shorts"])
  stop  = sl_atr  * ATR(atr_n)  (hard SL on every order)
  trail = trail_atr * ATR(atr_n) (ratchets on bar closes)
  time exit after max_bars bars.
No signal on a bar whose N-bar window contains a data gap (> 1.5 bar periods).
Volume = broker minimum (0.10 units, probed).
"""
import numpy as np
import pandas as pd

START_BALANCE = 30.0

PARAMS = {"N": 6, "thr": 0.8, "atr_n": 20, "sl_atr": 3.0, "trail_atr": 1.5, "max_bars": 24,
          "shorts": False, "units": 0.10}

LEGS = [{"symbol_id": 2469, "period": "M_5", "params": dict(PARAMS), "max_open": 1}]

BAR_SEC = {"M_1": 60, "M_5": 300, "M_15": 900}


def features(bars, N, atr_n, bar_sec=300):
    c = bars.close.to_numpy(float)
    d = np.abs(np.diff(c, prepend=c[0]))
    path = pd.Series(d).rolling(N).sum().to_numpy()
    prev = np.concatenate([np.full(N, np.nan), c[:-N]])
    net = c - prev
    er = net / np.maximum(path, 1e-12)
    tr = (bars.high - bars.low).to_numpy(float)
    atr = pd.Series(tr).rolling(atr_n).mean().to_numpy()
    gap = bars.time.diff().dt.total_seconds().fillna(bar_sec).to_numpy() > 1.5 * bar_sec
    # window clean if no gap among the last max(N, atr_n) bars
    w = max(N, atr_n)
    clean = pd.Series(gap.astype(float)).rolling(w + 1).sum().to_numpy() == 0
    return c, er, atr, clean


def signals(bars, params, spec):
    p = {**PARAMS, **params}
    c, er, atr, clean = features(bars, p["N"], p["atr_n"])
    sig = np.zeros(len(c))
    sig[er > p["thr"]] = 1
    if p["shorts"]:
        sig[er < -p["thr"]] = -1
    ok = clean & np.isfinite(atr) & np.isfinite(er) & (atr > 0)
    sig[~ok] = 0
    i = np.where(sig != 0)[0]
    i = i[i < len(c) - 1]
    vol = max(float(p["units"]), float(spec.get("min_units") or p["units"]))
    return pd.DataFrame({"idx": i, "side": sig[i], "kind": 0, "price": 0.0,
                         "sl": p["sl_atr"] * atr[i], "tp": 0.0, "max_bars": int(p["max_bars"]),
                         "trail": p["trail_atr"] * atr[i], "valid": 1, "volume": vol})
