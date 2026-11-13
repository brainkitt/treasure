"""STATUS: REJECTED BY PRE-SAMPLE VALIDATION (round 2). On Jan-Sep 2026 M5 history this exact rule has PF 0.95 over
285 trades (max DD $47). The official-window PF below is a lucky 7.5 weeks. Kept as the submission of record only;
do not trade it. See NOTES.md "Round 2" and "Final round".

ALPHA - London-open breakout of the overnight (Asian) range on FX majors.

Hypothesis (stated before fitting): between 00:00 and 08:00 London time EUR and GBP pairs consolidate in a
thin market; resting stops accumulate outside that range. When European liquidity arrives (08:00 London) the first
decisive break of the range tends to follow through for the rest of the European morning / NY overlap.

Rules (identical for every leg, all clock times are Europe/London local time, DST handled by tz conversion):
  1. Range = highest high / lowest low of the M5 bars that start in [r0, r1)  (00:00-08:00).
  2. From r1 to e1 (08:00-11:00): the FIRST M5 bar that CLOSES outside the range -> market order in that
     direction at the next M1 open. At most one trade per symbol per day.
  3. Stop-loss  = clip(slm * range, slmin, slcap) pips   (0.75 x range, 5..14 pips -> max loss $1.40 at 1000 units)
     Take-profit = tpm * stop-loss                         (2 x)
     Time exit at xh (16:00 London) - never held overnight.
Only completed bars are used (range bars precede the signal bar; entry is at the next bar's open) -> no look-ahead.
"""
import numpy as np, pandas as pd
from arena.engine import resample

P = {"tf": 5, "r0": 0.0, "r1": 8.0, "e1": 11.0, "xh": 16.0, "slm": 0.75, "tpm": 2.0, "slmin": 5.0, "slcap": 14.0,
     "tz": "Europe/London"}
LEGS = [
    {"symbol_id": 1, "params": {**P, "pip": 0.0001}, "max_open": 1},   # EURUSD
    {"symbol_id": 2, "params": {**P, "pip": 0.0001}, "max_open": 1},   # GBPUSD
    # USDJPY (id 4) was tested with the identical rule and REJECTED on in-sample evidence (IS PF 1.0-1.3), see NOTES.md
]


def signals(m1, p, spec):
    tf, pip = int(p["tf"]), p["pip"]
    b = resample(m1, tf)
    lt = b.time.dt.tz_localize("UTC").dt.tz_convert(p["tz"])
    h = (lt.dt.hour + lt.dt.minute / 60.0).to_numpy()            # local start time of each M5 bar (hours)
    day = lt.dt.strftime("%Y-%m-%d").to_numpy()
    hi_, lo_, c, mi = b.high.to_numpy(), b.low.to_numpy(), b.close.to_numpy(), b.m1_idx.to_numpy()
    need = (p["r1"] - p["r0"]) * 60 / tf * 0.7                    # require >=70% of the range bars (skips holidays/gaps)
    rows = []
    for _, ix in pd.Series(np.arange(len(b))).groupby(day, sort=True).indices.items():
        hh = h[ix]
        rm = (hh >= p["r0"]) & (hh < p["r1"])
        if rm.sum() < need:
            continue
        hi, lo = hi_[ix][rm].max(), lo_[ix][rm].min()
        sl = float(np.clip(p["slm"] * (hi - lo) / pip, p["slmin"], p["slcap"]))
        for j in np.where((hh >= p["r1"]) & (hh < p["e1"]))[0]:
            k = ix[j]
            side = 1 if c[k] > hi else (-1 if c[k] < lo else 0)
            if side == 0:
                continue
            mb = int(round((p["xh"] - hh[j]) * 60)) - tf - 1      # M1 bars from the fill bar to the bar closing at xh
            if mb >= 1:
                rows.append((mi[k], side, 0, sl * pip, p["tpm"] * sl * pip, mb))
            break                                                 # first break only -> one trade per day
    od = pd.DataFrame(rows, columns=["idx", "side", "kind", "sl", "tp", "max_bars"])
    od["volume"] = float(spec["min_units"])
    return od
