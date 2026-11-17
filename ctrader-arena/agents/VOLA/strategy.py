"""VOLA (AGENT_03, spike/jump families) - round-3 submission. NOT an edge: see NOTES.md.

C1 "Range Break 200 breakout-follow" (M5): the strongest in-sample plateau found in the 7-symbol family lab
(Donchian close-breakout FOLLOW on Range Break 200). Pre-declared confirmation on an unseen earlier sample
(2026-07-21..08-18) FAILED (PF 0.66, t -2.0), consistent with a fair (martingale) game. Submitted for completeness
so the supervisor can see the official numbers; do not trade it.

Logic (decided on the CLOSE of bar i, filled at the next open):
  long  if close[i] > highest high of the previous N bars; short if close[i] < lowest low of the previous N bars
  initial stop = trailing stop = K * ATR(24) (trail ratchets on bar closes), time exit after H bars
  entries only 00:00-16:59 UTC so every trade is flat before the 21:00 UTC rollover (no swap exposure)
  one position at a time, broker-minimum volume 0.01 units.
"""
import numpy as np, pandas as pd

START_BALANCE = 30.0
PARAMS = {"N": 24, "K": 2.0, "H": 48, "atr_n": 24, "last_entry_hour": 16, "volume": 0.01}
LEGS = [{"symbol_id": 2450, "period": "M_5", "params": PARAMS, "max_open": 1}]


def _atr(b, n):
    pc = b.close.shift()
    tr = np.maximum(b.high - b.low, np.maximum((b.high - pc).abs(), (b.low - pc).abs()))
    return tr.rolling(n, min_periods=n).mean().to_numpy()


def signals(bars, params, spec):
    p = {**PARAMS, **(params or {})}
    n = len(bars)
    A = _atr(bars, p["atr_n"])
    hh = bars.high.rolling(p["N"]).max().shift(1).to_numpy()
    ll = bars.low.rolling(p["N"]).min().shift(1).to_numpy()
    c = bars.close.to_numpy()
    # decision at bar close: bar open time + 5 min; entry fills at next bar open
    hour = (bars.time + pd.Timedelta(minutes=5)).dt.hour.to_numpy()
    ok = np.isfinite(A) & np.isfinite(hh) & (hour <= p["last_entry_hour"])
    up = ok & (c > hh); dn = ok & (c < ll)
    idx = np.where(up | dn)[0]
    idx = idx[idx < n - 1]
    side = np.where(up[idx], 1.0, -1.0)
    d = p["K"] * A[idx]
    return pd.DataFrame(dict(idx=idx, side=side, kind=0, price=0.0, sl=d, tp=0.0, max_bars=int(p["H"]),
                             trail=d, valid=1, volume=float(p["volume"])))
