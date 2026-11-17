"""Supervisor only: run a strategy on the full (unsealed) data and score the sealed holdout window.
    ARENA_HOLDOUT_UNLOCK=1 python -m arena.holdout_check agents/X/strategy.py 2026-09-15 [--out DIR]"""
import os, sys, json
os.environ["ARENA_HOLDOUT_UNLOCK"] = "1"
import pandas as pd
from . import evaluate2 as ev

path, start = sys.argv[1], pd.Timestamp(sys.argv[2])
mod = ev.load_strategy(path); B = float(getattr(mod, "START_BALANCE", 30.0)); specs = ev.load_specs(path)
res = {}
if len(sys.argv) > 4:
    os.makedirs(sys.argv[4], exist_ok=True)
for lab, mult, slip in (("holdout", 1.0, 0.0), ("holdout_stress", 1.5, 0.25)):
    tr, days, *_ = ev.run_legs(mod, specs, mult, extra_slip_frac=slip)
    days = pd.DatetimeIndex(days); h = tr[tr.entry_time >= start]
    s = ev.stats(h, days[days >= start], B); s["mc"] = ev.monte_carlo(h.pnl.to_numpy()); res[lab] = s
    print(f"{lab:15s} trades={s['trades']} PF={s['pf']:.2f} net=${s['net']:.2f} win={s['win_rate']:.0f}% t={s['t_stat']:.2f} "
          f"DD=${s['max_dd_usd']:.2f} worst=${s['worst_trade']:.2f} wk+={s['weeks_profitable_pct']:.0f}%")
    if lab == "holdout":
        h.to_csv(os.path.join(sys.argv[4], "holdout_trades.csv") if len(sys.argv) > 4 else os.devnull, index=False)
s = res["holdout"]
ok = s["pf"] >= 1.2 and s["net"] > 0 and s["trades"] >= 30 and s["worst_trade"] >= -0.05 * B and s["max_dd_usd"] <= 0.25 * B
print("HOLDOUT", "PASS" if ok else "FAIL", f"(start balance ${B:.0f})")
if len(sys.argv) > 4:
    os.makedirs(sys.argv[4], exist_ok=True)
    json.dump({"start": str(start.date()), "pass": ok, **res}, open(os.path.join(sys.argv[4], "holdout.json"), "w"), indent=1, default=str)
