from h1_lob import *
res = []
for r1, e1, xh, tpm, slmax in itertools.product([7, 8, 9], [10, 12], [14, 17, 20], [1.0, 2.0, 3.0], [14, 30]):
    ps = []
    for sid in [1, 2]:
        tr = sim(sid, lob(sid, r1=r1, e1=e1, xh=xh, tpm=tpm, slmax=slmax))
        ps.append(is_only(tr, split_time(sid)))
    p = np.concatenate(ps)
    res.append((r1, e1, xh, tpm, slmax, len(p), pf(p)))
df = pd.DataFrame(res, columns=["r1", "e1", "xh", "tpm", "slmax", "n", "isPF"])
print(len(df), "sets; IS PF quantiles", df.isPF.quantile([0, .25, .5, .75, 1]).round(2).tolist())
print(df.sort_values("isPF").tail(8).to_string())
