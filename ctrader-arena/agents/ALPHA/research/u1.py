from lib import *
m1 = load(2517); print(len(m1), m1.time.iloc[0], m1.time.iloc[-1])
split = split_time(m1); print("split", split)
g = m1.time.diff().dt.total_seconds() / 60
print("gaps>5min:", (g > 5).sum(), g[g > 5].round().value_counts().head(8).to_dict())
days = m1.groupby(m1.time.dt.floor("D")).size(); print("days", len(days), "weekday-ish(>1000 bars)", (days > 1000).sum(), "short", (days <= 1000).sum())
m1["IS"] = m1.time < split
for tf in (1, 5, 15, 30, 60):
    b = engine.resample(m1, tf); b["IS"] = b.time < split
    r = np.log(b.close).diff()
    cont = r.shift(1).where(b.time.diff().dt.total_seconds() <= tf * 60 * 1.5)  # no gap
    for nm, m in (("IS", b.IS), ("OOS", ~b.IS)):
        x = pd.DataFrame({"a": r[m], "b": cont[m]}).dropna()
        ac = x.a.corr(x.b)
        print(f"tf={tf:2d} {nm:3s} n={len(x):6d} sd={x.a.std()*1e4:5.2f}bp  AC1={ac:+.4f} t={ac*np.sqrt(len(x)):+.2f}  spread={0.36/b.close.mean()*1e4:.2f}bp")
# AC by hour (UTC) on M5
b = engine.resample(m1, 5); r = np.log(b.close).diff(); p = r.shift(1); h = b.time.dt.hour
x = pd.DataFrame({"r": r, "p": p, "h": h, "IS": b.time < split}).dropna()
t = x.groupby(["h", "IS"]).apply(lambda d: d.r.corr(d.p) * np.sqrt(len(d))).unstack().round(1)
print("M5 AC1 t-stat by UTC hour (cols OOS/IS):"); print(t.T.to_string())
# conditional: big moves
for tf in (1, 5, 15):
    b = engine.resample(m1, tf); r = b.close.diff(); sd = r.rolling(240).std().shift(1); z = r / sd; f = b.close.shift(-1) - b.close; f3 = b.close.shift(-3) - b.close
    for k in (2, 3, 4):
        for nm, m in (("IS", b.time < split), ("OOS", b.time >= split)):
            mm = m & (z.abs() > k) & f3.notna()
            print(f"tf={tf} |z|>{k} {nm} n={mm.sum():5d} next1 cont={np.mean(np.sign(z[mm])*f[mm]):+.3f}pt  next3 cont={np.mean(np.sign(z[mm])*f3[mm]):+.3f}pt t3={np.mean(np.sign(z[mm])*f3[mm])/np.std(np.sign(z[mm])*f3[mm])*np.sqrt(mm.sum()):+.2f}")
