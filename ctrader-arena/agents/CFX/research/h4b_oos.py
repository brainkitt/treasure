from h4b import *
base = dict(k=2.5, n=24, H=2, slm=2.0)
rows = []
def row(lbl, **kw):
    p, q = pooled([101, 102], **{**base, **kw})
    a = np.concatenate([p, q])
    rows.append((lbl, len(p), round(pf(p), 2), len(q), round(pf(q), 2), round(pf(a), 2), round(a.mean()/a.std()*np.sqrt(len(a)), 2)))
row("BASE")
for k in [2.0, 2.25, 2.75, 3.0]: row(f"k={k}", k=k)
for n in [12, 36, 48, 96]: row(f"n={n}", n=n)
for H in [1, 3, 4]: row(f"H={H}", H=H)
for s in [1.0, 1.5, 2.5, 3.0]: row(f"slm={s}", slm=s)
row("tp=2", tpm=2.0); row("wick0.3", wick=0.3); row("trend24", trendL=24); row("vol1.5", volm=1.5)
print(pd.DataFrame(rows, columns=["set", "IS_n", "IS_PF", "OOS_n", "OOS_PF", "ALL_PF", "t"]).to_string(index=False))
