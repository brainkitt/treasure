"""Example only (not an edge): M5 Donchian breakout on XAUUSD with stop entries."""
import numpy as np, pandas as pd
from arena.engine import resample

LEGS = [{"symbol_id": 41, "params": {"tf": 5, "n": 20, "sl": 3.0, "tp": 4.5}, "max_open": 1}]


def signals(m1, p, spec):
    b = resample(m1, p["tf"])
    hi = b.high.rolling(p["n"]).max().shift(1)  # prior n completed bars only -> no look-ahead
    up = (b.close > hi) & (b.close.shift(1) <= hi.shift(1))
    rows = b[up]
    return pd.DataFrame({"idx": rows.m1_idx.to_numpy(), "side": 1, "kind": 0, "sl": p["sl"], "tp": p["tp"],
                         "max_bars": 120, "volume": spec["min_units"]})
