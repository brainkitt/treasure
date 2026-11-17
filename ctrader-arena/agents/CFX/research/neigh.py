"""Neighbour robustness for the final ETH leg on the full 3.5y sample, evaluator split (OOS from 2025-10-26)."""
import lib
lib.START = lib.pd.Timestamp("2023-05-01"); lib._cache.clear(); lib.SPREAD[102] = 2.0
from h4b import *
import json
SPL = pd.Timestamp("2025-10-26")
base = dict(k=2.5, n=24, H=2, slm=2.0)
rows = []
def row(lbl, sid=102, spread_mult=1.0, **kw):
    tr = sim(sid, burst2(sid, **{**base, **kw}), slip_frac=0.2, spread_mult=spread_mult)
    p = tr.pnl.to_numpy(); i = (pd.to_datetime(tr.entry_time) < SPL).to_numpy()
    rows.append(dict(set=lbl, n=len(p), PF=round(pf(p), 2), IS_PF=round(pf(p[i]), 2), OOS_n=int((~i).sum()), OOS_PF=round(pf(p[~i]), 2),
                     t=round(p.mean() / p.std() * np.sqrt(len(p)), 2), net=round(p.sum(), 1)))
row("BASE k2.5 n24 H2 sl2.0")
for k in [2.0, 2.25, 2.75, 3.0]: row(f"k={k}", k=k)
for n in [12, 18, 36, 48]: row(f"n={n}", n=n)
for H in [1, 3, 4]: row(f"H={H}", H=H)
for s in [1.0, 1.5, 2.5, 3.0]: row(f"slm={s}", slm=s)
row("spread x2", spread_mult=2.0)
df = pd.DataFrame(rows); print(df.to_string(index=False)); df.to_json("neigh.json", orient="records")
