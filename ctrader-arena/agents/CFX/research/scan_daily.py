"""Gross daily-signal scan, IS only (first 70% of days). Returns in units of daily vol."""
from lib import *
rows = []
for sid in [1,2,3,4,5,6,8,9,101,102]:
    b = bars(sid)
    d = b.set_index("time").close.resample("D").last().dropna()
    if sid < 100: d = d[d.index.dayofweek < 5]
    r = np.log(d).diff()
    sp = split_time(sid)
    vol = r.rolling(20).std().shift(1)
    nxt = r.shift(-1) / vol
    for L in [1, 2, 3, 5, 10, 20, 40, 60]:
        s = np.sign(np.log(d).diff(L))
        x = (s * nxt)[(d.index < sp)].dropna()
        xo = (s * nxt)[(d.index >= sp)].dropna()
        rows.append((NAMES[sid], L, x.mean()/x.std()*np.sqrt(len(x)), xo.mean()/xo.std()*np.sqrt(len(xo))))
df = pd.DataFrame(rows, columns=["sym", "L", "t_IS", "t_OOS"])
print(df.pivot(index="sym", columns="L", values="t_IS").round(1))
print("pooled IS t by L (mean over syms):"); print(df.groupby("L").t_IS.mean().round(2).to_dict())
