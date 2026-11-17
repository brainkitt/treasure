"""CFX research helpers: load bars from a common start, simulate with official engine, IS/OOS stats."""
import sys, os, json
sys.path.insert(0, "/home/user/treasure/ctrader-arena")
import numpy as np, pandas as pd
from arena import engine, ingest
from arena.evaluate2 import apply_costs, load_specs

START = pd.Timestamp("2024-10-28")
SPECS = load_specs("/home/user/treasure/ctrader-arena/agents/CFX/strategy.py")
NAMES = {1: "EURUSD", 2: "GBPUSD", 3: "EURJPY", 4: "USDJPY", 5: "AUDUSD", 6: "USDCHF", 8: "USDCAD", 9: "EURGBP",
         101: "BTCUSD", 102: "ETHUSD", 2408: "XRPUSD", 2387: "BNBUSD"}
PIP = {1: 1e-4, 2: 1e-4, 3: 1e-2, 4: 1e-2, 5: 1e-4, 6: 1e-4, 8: 1e-4, 9: 1e-4, 101: 1.0, 102: 1.0, 2408: 1.0, 2387: 1.0}
# research spreads (widest seen so far, price units) and usd/quote approximations
SPREAD = {1: 0.00014, 2: 0.00014, 3: 0.016, 4: 0.014, 5: 0.00011, 6: 0.00011, 8: 0.00014, 9: 0.0001,
          101: 25.0, 102: 2.0, 2408: 0.0011, 2387: 0.9}
USDQ = {1: 1.0, 2: 1.0, 3: 1 / 150.0, 4: 1 / 150.0, 5: 1.0, 6: 1 / 0.80, 8: 1 / 1.40, 9: 1.33, 101: 1.0, 102: 1.0, 2408: 1.0, 2387: 1.0}

_cache = {}
def bars(sid, period="H_1"):
    k = (sid, period)
    if k not in _cache:
        b = ingest.load(sid, period)
        b = b[b.time >= START].reset_index(drop=True)
        _cache[k] = b
    return _cache[k]

def split_time(sid, frac=0.7):
    b = bars(sid)
    days = sorted(b.time.dt.floor("D").unique())
    return pd.Timestamp(days[int(len(days) * frac)])

def sim(sid, od, spread_mult=1.0, slip_frac=0.0, swap=(0.0, 0.0), period="H_1"):
    b = bars(sid, period)
    sp = SPREAD[sid] * spread_mult
    if len(od) == 0:
        return pd.DataFrame(columns=["pnl", "entry_time", "exit_time", "side"])
    tr = engine.simulate(b, od, spread=sp, slip=slip_frac * SPREAD[sid], max_open=1, usd_per_quote=USDQ[sid])
    if "volume" not in od:
        od = od.assign(volume=1.0)
    tr = apply_costs(tr, od.sort_values("idx", kind="stable").reset_index(drop=True),
                     {"usd_per_quote": USDQ[sid], "swap_long": swap[0], "swap_short": swap[1], "triple_weekday": 2})
    return tr

def pf(p):
    p = np.asarray(p); gl = -p[p < 0].sum()
    return p[p > 0].sum() / gl if gl > 0 else 99.0

def summ(tr, split, label=""):
    if len(tr) == 0:
        return f"{label:30s} n=0"
    p = tr.pnl.to_numpy(); t = pd.to_datetime(tr.entry_time)
    i = (t < split).to_numpy()
    ts = p.mean() / (p.std(ddof=1) / np.sqrt(len(p))) if len(p) > 2 else 0
    return (f"{label:30s} n={len(p):4d} PF={pf(p):.2f} IS n={i.sum():4d} PF={pf(p[i]):.2f} "
            f"OOS n={(~i).sum():4d} PF={pf(p[~i]):.2f} t={ts:.2f} net={p.sum():.2f}")

def is_only(tr, split):
    p = tr.pnl.to_numpy(); i = (pd.to_datetime(tr.entry_time) < split).to_numpy()
    return p[i]
