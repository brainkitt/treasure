"""BRAVO — Drift Switch 30 regime follower (long only).

Hypothesis: the DS30 BID series has a calm-rising state and a volatile-falling state (2-state HMM, parameters
fitted on in-sample only, see NOTES.md). Buy when the causal filter probability of the calm state is high,
exit by trailing stop / hard stop.

WARNING (see NOTES.md): the live spread on Drift Switch indices widens to 6-9 px exactly in the calm-rising
state, so specs.json carries the widest observed spread and this system is NOT expected to be profitable.
"""
import numpy as np, pandas as pd
from numba import njit

LEGS = [{"symbol_id": 2470,
         "params": {"mu_b": 0.56, "sd_b": 1.39, "dur_b": 25.0,     # calm-up state: bp/min, bp, minutes
                    "mu_s": -0.42, "sd_s": 3.42, "dur_s": 33.5,    # volatile-down state
                    "hi": 0.97, "sl": 14.0, "trail": 6.0},
         "max_open": 1}]


@njit(cache=True)
def _filter(r, mu_b, sd_b, mu_s, sd_s, stay_b, stay_s):
    """Causal forward filter: P(calm state at bar t | returns up to t)."""
    n = len(r); out = np.empty(n); pb = 0.5
    for t in range(n):
        prior = pb * stay_b + (1.0 - pb) * (1.0 - stay_s)
        lb = np.exp(-0.5 * ((r[t] - mu_b) / sd_b) ** 2) / sd_b
        ls = np.exp(-0.5 * ((r[t] - mu_s) / sd_s) ** 2) / sd_s
        a = prior * lb; b = (1.0 - prior) * ls
        pb = a / (a + b + 1e-300)
        out[t] = pb
    return out


def calm_prob(m1, p):
    c = m1.close.to_numpy(np.float64)
    r = np.zeros(len(c)); r[1:] = np.diff(np.log(c)) * 1e4
    return _filter(r, p["mu_b"], p["sd_b"], p["mu_s"], p["sd_s"], 1 - 1 / p["dur_b"], 1 - 1 / p["dur_s"])


def signals(m1, p, spec):
    pb = calm_prob(m1, p)
    idx = np.where(pb >= p["hi"])[0]          # engine drops signals while a position is open
    return pd.DataFrame({"idx": idx, "side": 1, "kind": 0, "sl": p["sl"], "tp": 0.0, "max_bars": 0,
                         "trail": p["trail"], "volume": spec["min_units"]})
