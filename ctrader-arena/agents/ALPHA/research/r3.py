from r2 import *
T = {s: run_m5(s) for s in (1, 2)}
for s in (1, 2):
    t = T[s]; print(line(f"PRE {s}", t)); print(line("  long", t[t.side > 0])); print(line("  short", t[t.side < 0])); print(line(f"FWD(M5) {s}", run_m5(s, lo=PRE_END, hi=None)))
t = pd.concat(T.values()).sort_values("exit_time"); print(line("PRE portfolio", t)); print(line("  @2.0pip spread", pd.concat([run_m5(s, mult=2.0 / (SPREAD[s] / PIP[s])) for s in (1, 2)])))
mon = t.groupby(pd.to_datetime(t.entry_time).dt.to_period("M")).pnl.agg(n="size", net="sum", pf=pf).round(2); print(mon.T.to_string())
p = t.pnl.to_numpy(); d = t.groupby(pd.to_datetime(t.entry_time).dt.floor("D")).pnl.sum()
print(f"trade t={p.mean()/p.std(ddof=1)*np.sqrt(len(p)):.2f} day t={d.mean()/d.std(ddof=1)*np.sqrt(len(d)):.2f} days={len(d)}")
print("== sensitivity surface PRE portfolio PF (rows range end r1, cols entry-window length h); n in ()")
for r1 in (6, 6.5, 7, 7.5, 8, 8.5, 9, 10):
    row = []
    for w in (1, 2, 3, 5):
        x = pd.concat([run_m5(s, {**P0, "r1": r1, "e1": r1 + w}) for s in (1, 2)]); row.append(f"{pf(x.pnl):.2f}({len(x)})")
    print(f"r1={r1:4}: " + "  ".join(row))
print("== other knobs PRE portfolio")
for k, vs in (("slm", (0.5, 1.0)), ("tpm", (1.0, 1.5, 3.0)), ("xh", (13, 20)), ("r0", (2, 4))):
    print(k, "  ".join(f"{v}:{pf(pd.concat([run_m5(s, {**P0, k: v}) for s in (1, 2)]).pnl):.2f}" for v in vs))
print("== reversed direction (fade) PRE:", end=" ")
def fade(s):
    b = load(s, "M_5"); b = b[b.time < PRE_END].reset_index(drop=True); od = sig_m5(b, P0, PIP[s], PIP[s] * 1000); od["side"] = -od.side; return run(s, b, od)
print(f"{pf(pd.concat([fade(1), fade(2)]).pnl):.2f}")
