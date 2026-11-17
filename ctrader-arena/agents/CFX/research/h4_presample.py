"""Pre-sample holdout: 2023-05-07 -> 2024-10-27 was never used in research. Test BASE + neighbours there."""
import lib
lib.START = lib.pd.Timestamp("2023-05-01"); lib._cache.clear()
from h4b import *
END = pd.Timestamp("2024-10-28")
base = dict(k=2.5, n=24, H=2, slm=2.0)
rows = []
for lbl, kw in [("BASE", {}), ("k=2.0", dict(k=2.0)), ("k=3.0", dict(k=3.0)), ("n=48", dict(n=48)), ("H=1", dict(H=1)),
                ("H=3", dict(H=3)), ("slm=1.5", dict(slm=1.5)), ("slm=3", dict(slm=3.0))]:
    out = [lbl]
    for sid in [101, 102]:
        tr = sim(sid, burst2(sid, **{**base, **kw}))
        pre = tr[pd.to_datetime(tr.entry_time) < END].pnl.to_numpy()
        out += [len(pre), round(pf(pre), 2)]
    rows.append(out)
print(pd.DataFrame(rows, columns=["set", "BTC_n", "BTC_PF", "ETH_n", "ETH_PF"]).to_string(index=False))
