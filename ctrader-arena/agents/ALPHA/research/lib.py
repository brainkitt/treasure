import numpy as np, pandas as pd, sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
from arena.ingest import load
from arena import engine
PIP = {2517: 1.0, 1: 1e-4, 2: 1e-4, 4: 1e-2, 5: 1e-4, 7: 1e-2, 3: 1e-2, 41: 1.0, 6: 1e-4, 8: 1e-4, 9: 1e-4}
SPREAD = {2517: 0.36, 1: 0.00013, 2: 0.00013, 4: 0.014, 5: 0.00011, 7: 0.025, 3: 0.036, 41: 0.29, 6: 0.00015, 8: 0.00015, 9: 0.00012}
UPQ = {2517: 1.0, 1: 1.0, 2: 1.0, 4: 0.006257, 5: 1.0, 7: 0.006257, 3: 0.006257, 41: 1.0, 6: 1.25, 8: 0.71, 9: 1.327}
UNITS = {2517: 0.1, 1: 1000, 2: 1000, 4: 1000, 5: 1000, 7: 1000, 3: 1000, 41: 1, 6: 1000, 8: 1000, 9: 1000}

def pf(p):
    p = np.asarray(p); g = p[p > 0].sum(); l = -p[p < 0].sum()
    return g / l if l > 0 else np.inf

def split_time(bars, frac=0.7):
    days = np.sort(bars.time.dt.floor("D").unique())
    return pd.Timestamp(days[int(len(days) * frac)])

def run(sid, bars, od, mult=1.0, max_open=1):
    od = od.copy(); od["volume"] = UNITS[sid]
    tr = engine.simulate(bars, od, spread=SPREAD[sid] * mult, max_open=max_open, usd_per_quote=UPQ[sid])
    return tr

def rep(tr, split, label=""):
    a = tr[tr.entry_time < split]; b = tr[tr.entry_time >= split]
    def s(x):
        if len(x) == 0: return "n=0"
        eq = x.pnl.cumsum(); dd = (eq.cummax().clip(lower=0) - eq).max()
        return f"n={len(x):4d} PF={pf(x.pnl):5.2f} net={x.pnl.sum():7.2f} win={100*(x.pnl>0).mean():3.0f}% dd={dd:5.2f} worst={x.pnl.min():5.2f}"
    print(f"{label:38s} IS[{s(a)}]  OOS[{s(b)}]")
    return pf(a.pnl) if len(a) else 0, pf(b.pnl) if len(b) else 0
