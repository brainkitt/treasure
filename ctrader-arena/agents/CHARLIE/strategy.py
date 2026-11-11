"""CHARLIE - Range Break 100 "break-continuation" (bounded-risk lottery ticket).

HONEST STATUS: this is NOT an edge. Range Break is a fair game (see NOTES.md); the system is the
least-bad risk-compliant construction found on the jump/spike family and is submitted with its true numbers.

Logic (M1, symbol 2449):
  * A "break" bar is an M1 bar with high-low > thr (normal bars <= 26 points, breaks >= 31: clean separation).
  * After an UP break the bar high is exactly the new upper range boundary (verified 142/150), mirror for DOWN.
  * If the break bar closes within `near` points of that boundary, enter WITH the break at the next bar open.
    The position sits on the boundary; every further "attempt" has ~1% chance of another ~100-point break in
    our favour, otherwise price reflects and we lose a few points.
  * SL `sl` points (inside the range, so normally not gapped), trailing stop `sl` points ratcheted on bar closes
    (locks in a favourable break), time exit after `mb` bars. TP is only a far 'disaster' bracket (600 points, beyond the largest break seen, 432)
    so that every order carries a hard SL and TP; it never triggers in the sample.
Parameters were chosen on the in-sample 70% only, subject to in-sample worst trade >= -$1.50.
"""
import numpy as np, pandas as pd

LEGS = [{"symbol_id": 2449, "params": {"thr": 30.0, "near": 2.0, "sl": 25.0, "mb": 30, "tp": 600.0}, "max_open": 1}]


def signals(m1, p, spec):
    o, h, l, c = [m1[x].to_numpy(np.float64) for x in ("open", "high", "low", "close")]
    brk = (h - l) > p["thr"]                       # uses the completed bar only -> causal
    up = brk & (c > o) & (h - c <= p["near"])
    dn = brk & (c < o) & (c - l <= p["near"])
    idx = np.where(up | dn)[0]
    side = np.where(up[idx], 1.0, -1.0)
    return pd.DataFrame({"idx": idx, "side": side, "kind": 0, "sl": float(p["sl"]), "tp": float(p["tp"]),
                         "max_bars": int(p["mb"]), "trail": float(p["sl"]), "volume": float(spec["min_units"])})
