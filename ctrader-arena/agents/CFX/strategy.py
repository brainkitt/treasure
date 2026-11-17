"""CFX - Crypto Momentum Burst (ETHUSD, H1, intraday).

Hypothesis (written before fitting, see NOTES.md): in 24/7 crypto markets an unusually large hourly candle is the
footprint of forced flow (leveraged-perp liquidations, stop cascades, momentum chasing). That flow is autocorrelated
for a few hours, so price tends to keep moving in the direction of the shock. FX majors do not show this (tested).

Rules (identical for both legs, all times UTC, decisions on CLOSED H1 bars only):
  1. ATR = mean(high-low) of the last n=24 completed H1 bars (including the signal bar).
  2. Signal bar i: |close-open| > k * ATR (k = 2.5). Direction = sign(close-open).
  3. Market order in that direction at the open of bar i+1.  Hard stop = slm * ATR (2.0 x ATR). No take-profit.
  4. Time exit: the position is held for hold=3 H1 bars (fill bar + 2) and closed at the close of the third bar,
     i.e. 3 hours after entry (engine max_bars = hold - 1).
  5. Rollover guard: no trade whose holding window touches 20:00-22:59 UTC -> never held through the daily
     rollover (no swap is ever charged; swap bound in specs.json is a safety net only).
  6. One position, minimum broker volume (0.1 ETH).

BTCUSD with the identical rule is also positive (PF 1.40, t 1.66 over 3.5y) but its 0.01-BTC minimum makes single
losses up to $26, which would push the required balance to ~$900; it is documented in NOTES.md as an optional
second instance, not part of the submitted portfolio.
"""
import numpy as np, pandas as pd

START_BALANCE = 300.0
P = {"k": 2.5, "n": 24, "hold": 3, "slm": 2.0, "block": [20, 21, 22]}
LEGS = [
    {"symbol_id": 102, "period": "H_1", "params": dict(P), "max_open": 1},   # ETHUSD, 0.1 ETH
]


def signals(bars, p, spec):
    k, n, hold, slm = float(p["k"]), int(p["n"]), int(p["hold"]), float(p["slm"])
    block = set(p.get("block", [20, 21, 22]))
    o, h, l, c = (bars[x].to_numpy(float) for x in ("open", "high", "low", "close"))
    atr = pd.Series(h - l).rolling(n).mean().to_numpy()          # uses bars <= i only (causal)
    body = c - o
    hr = bars.time.dt.hour.to_numpy()
    sig = np.abs(body) > k * np.nan_to_num(atr, nan=np.inf)
    rows = []
    for i in np.where(sig)[0]:
        if any(((hr[i] + 1 + j) % 24) in block for j in range(hold)):   # every hour the trade is held
            continue
        rows.append((i, 1 if body[i] > 0 else -1, 0, slm * atr[i], 0.0, hold - 1))
    od = pd.DataFrame(rows, columns=["idx", "side", "kind", "sl", "tp", "max_bars"])
    od["volume"] = float(spec["min_units"])
    return od
