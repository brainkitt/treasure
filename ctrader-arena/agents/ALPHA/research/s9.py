from s8 import *
import importlib.util, json
base = dict(tf=5, r0=0, r1=8, e1=11, xh=16, slm=0.75, tpm=2.0)
def pooled2(**kw):
    trs = []
    for sid in (1, 2):
        p = dict(slcap=14, slmin=5, **{**base, **kw}); tr = run(sid, M[sid], orb(M[sid], p, PIP[sid])); tr["sid"] = sid; trs.append(tr)
    return pd.concat(trs).sort_values("exit_time")
print("== neighbour table (one parameter changed at a time), M1 engine, EURUSD+GBPUSD")
show("BASE", pooled2())
for k, vals in (("r1", ((7, 10), (7.5, 10.5), (8.5, 11.5), (9, 12))), ("r0", (1, 2, 3)), ("e1", (10, 12, 13)), ("xh", (14, 15, 17, 18, 20)), ("slm", (0.5, 0.6, 0.9, 1.0, 1.25)),
                ("tpm", (1.0, 1.5, 2.5, 3.0, 4.0)), ("tf", (1, 3, 10, 15)), ("buf", (0.5, 1, 2))):
    for v in vals:
        kw = dict(r1=v[0], e1=v[1]) if k == "r1" else {k: v}
        show(f"{k}={v}", pooled2(**kw))
tr = pooled2()
print("== splits of BASE (full sample)")
for nm, g in (("long", tr[tr.side > 0]), ("short", tr[tr.side < 0]), ("EURUSD", tr[tr.sid == 1]), ("GBPUSD", tr[tr.sid == 2])):
    print(f"{nm:7s} n={len(g):3d} PF={pf(g.pnl):.2f} net={g.pnl.sum():6.2f} win={100*(g.pnl>0).mean():.0f}%")
print("exit reasons:", tr.groupby("reason").pnl.agg(["size", "sum"]).round(2).to_dict("index"))
wk = tr.groupby(pd.to_datetime(tr.exit_time).dt.to_period("W")).pnl.agg(["size", "sum"]).round(2); print(wk.T.to_string())
p = tr.pnl.to_numpy(); print(f"mean trade ${p.mean():.3f}  t-stat={p.mean()/p.std(ddof=1)*np.sqrt(len(p)):.2f}  n={len(p)}")
rng = np.random.default_rng(7); bs = np.array([pf(rng.choice(p, len(p))) for _ in range(5000)])
print("bootstrap PF 5%/50%/95%:", np.round(np.percentile(bs, [5, 50, 95]), 2), " P(PF<1.0)=%.3f P(PF<1.7)=%.3f" % ((bs < 1).mean(), (bs < 1.7).mean()))
# daily pnl dependence between the two legs
d = tr.assign(day=pd.to_datetime(tr.entry_time).dt.floor("D")).pivot_table(index="day", columns="sid", values="pnl", aggfunc="sum")
print("days both traded:", d.dropna().shape[0], "corr of leg pnl:", round(d.dropna().corr().iloc[0, 1], 2), "same direction share:", round((np.sign(d.dropna()[1]) == np.sign(d.dropna()[2])).mean(), 2))
dd = tr.assign(day=pd.to_datetime(tr.entry_time).dt.floor("D")).groupby("day").pnl.sum(); print(f"day-level: n={len(dd)} mean={dd.mean():.3f} t={dd.mean()/dd.std(ddof=1)*np.sqrt(len(dd)):.2f} worst day={dd.min():.2f}")
print("== placebo: same entry times/stops, direction REVERSED (fade the break) and RANDOM")
def placebo(mode, seed=0):
    trs = []; rng = np.random.default_rng(seed)
    for sid in (1, 2):
        od = orb(M[sid], dict(slcap=14, slmin=5, **base), PIP[sid])
        od["side"] = -od.side if mode == "rev" else rng.choice([-1, 1], len(od))
        trs.append(run(sid, M[sid], od))
    return pd.concat(trs)
print("reversed PF=%.2f" % pf(placebo("rev").pnl), " random-direction PF (20 seeds) median=%.2f max=%.2f" % tuple(np.percentile([pf(placebo("rnd", s).pnl) for s in range(20)], [50, 100])))
