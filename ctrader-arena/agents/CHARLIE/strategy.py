"""CHARLIE phase 2 - overnight-gap fade on US Small Cap 2000 (H_1 bars, one leg, minimum size 0.1 unit).

Hypothesis (fixed before fitting): the pre-market price of a small-cap index CFD overshoots; whoever has to trade the
overnight move before the New York cash open pays a liquidity premium that is given back during the cash session.
The effect grows with the size of the overnight move (IS: PF 1.2 -> 1.4 -> 1.5 -> 1.65 for thr 0 / .25 / .5 / .75).

Rule (all times New York, DST handled by the tz database):
  09:00  on = ln(price / yesterday's 16:00 price);  z = on / std(last 20 daily 16:00->16:00 returns)
         if |z| > 0.5 and today is a normal NYSE session: market order AGAINST the overnight move, 0.1 unit
  stop   hard SL $1.50 (15 index points at 0.1 unit), no profit target
  16:00  close (6 H1 bars after the entry bar).  Never held overnight or over a weekend -> no financing.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gapfade import signals_gapfade

PARAMS = {"thr": 0.5, "W": 20, "hour": 8, "hold": 6, "risk": 1.5, "m": 99.0}
LEGS = [{"symbol_id": 2521, "period": "H_1", "params": PARAMS, "max_open": 1}]


def signals(bars, params, spec):
    return signals_gapfade(bars, params, spec["min_units"])
