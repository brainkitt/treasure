"""Official scoring.  python -m arena.evaluate agents/<name>/strategy.py [--out DIR] [--spread-mult X] [--quiet]

A strategy module must define:
    LEGS = [ {"symbol_id": 41, "params": {...}, "max_open": 1}, ... ]     # one leg per symbol
    def signals(m1, params, spec) -> pandas.DataFrame of orders (see arena/engine.py)
`m1` is the M1 BID bar frame from arena.ingest.load (use arena.engine.resample for M2..M15 logic).
`spec` is the symbol's entry from arena/specs.json (merged with agents/<name>/specs.json if present).
"""
import argparse, importlib.util, json, os, sys
import numpy as np, pandas as pd
from . import engine, ingest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
START_BALANCE = 30.0
OOS_FRACTION = 0.30

GATES = {
    "pf_full >= 1.7": lambda m: m["full"]["pf"] >= 1.7,
    "pf_oos >= 1.5 (last 30% of time)": lambda m: m["oos"]["pf"] >= 1.5,
    "pf_is >= 1.5": lambda m: m["is"]["pf"] >= 1.5,
    "pf under 1.5x spread >= 1.4": lambda m: m["stress"]["pf"] >= 1.4,
    "trades >= 150": lambda m: m["full"]["trades"] >= 150,
    "oos trades >= 40": lambda m: m["oos"]["trades"] >= 40,
    "active days >= 85%": lambda m: m["full"]["active_day_pct"] >= 85,
    "max drawdown <= 30% of $30 start ($9)": lambda m: m["full"]["max_dd_usd"] <= 9.0,
    "worst single trade <= $1.50 (5% of $30)": lambda m: m["full"]["worst_trade"] >= -1.5,
    "no look-ahead": lambda m: m["lookahead_ok"],
    "min lot respected": lambda m: m["min_lot_ok"],
    "weekly PF >= 1.0 in >= 70% of weeks": lambda m: m["full"]["weeks_profitable_pct"] >= 70,
}


def load_specs(strategy_path):
    specs = json.load(open(os.path.join(ROOT, "arena", "specs.json")))
    extra = os.path.join(os.path.dirname(os.path.abspath(strategy_path)), "specs.json")
    if os.path.exists(extra):
        for k, v in json.load(open(extra)).items():
            if isinstance(v, dict):
                specs[k] = {**specs.get(k, {}), **v}
    return specs


def load_strategy(path):
    spec = importlib.util.spec_from_file_location("strat_" + "".join(ch if ch.isalnum() else "_" for ch in os.path.abspath(path)), path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    sys.path.insert(0, os.path.dirname(os.path.abspath(path)))
    spec.loader.exec_module(mod)
    return mod


def stats(tr, day_index):
    """tr: trades with pnl, entry_time, exit_time. day_index: all calendar days the market had bars."""
    if len(tr) == 0:
        return dict(trades=0, pf=0.0, net=0.0, win_rate=0.0, avg_win=0.0, avg_loss=0.0, expectancy=0.0, max_dd_usd=0.0,
                    max_dd_pct=0.0, min_equity=START_BALANCE, worst_trade=0.0, best_trade=0.0, trades_per_day=0.0,
                    active_day_pct=0.0, max_consec_losses=0, weeks_profitable_pct=0.0, sharpe_daily=0.0,
                    return_pct=0.0, days=len(day_index), avg_hold_min=0.0, overnight_trades=0)
    p = tr.pnl.to_numpy()
    gp, gl = p[p > 0].sum(), -p[p < 0].sum()
    eq = START_BALANCE + np.cumsum(p)
    peak = np.maximum.accumulate(np.concatenate([[START_BALANCE], eq]))[1:]
    dd = peak - eq
    days = pd.Index(day_index)
    tdays = pd.to_datetime(tr.entry_time).dt.floor("D")
    daily = tr.groupby(pd.to_datetime(tr.exit_time).dt.floor("D")).pnl.sum().reindex(days, fill_value=0.0)
    wk = tr.groupby(pd.to_datetime(tr.exit_time).dt.to_period("W")).pnl.sum()
    streak = best = 0
    for x in p:
        streak = streak + 1 if x < 0 else 0
        best = max(best, streak)
    hold = (pd.to_datetime(tr.exit_time) - pd.to_datetime(tr.entry_time)).dt.total_seconds() / 60
    return dict(
        trades=int(len(p)), pf=float(gp / gl) if gl > 0 else float("inf"), net=float(p.sum()),
        win_rate=float((p > 0).mean() * 100), avg_win=float(p[p > 0].mean()) if (p > 0).any() else 0.0,
        avg_loss=float(p[p < 0].mean()) if (p < 0).any() else 0.0, expectancy=float(p.mean()),
        max_dd_usd=float(dd.max()), max_dd_pct=float((dd / peak).max() * 100), min_equity=float(eq.min()),
        worst_trade=float(p.min()), best_trade=float(p.max()), trades_per_day=float(len(p) / max(1, len(days))),
        active_day_pct=float(tdays.nunique() / max(1, len(days)) * 100), max_consec_losses=int(best),
        weeks_profitable_pct=float((wk > 0).mean() * 100), sharpe_daily=float(daily.mean() / daily.std() * np.sqrt(252)) if daily.std() > 0 else 0.0,
        return_pct=float(p.sum() / START_BALANCE * 100), days=int(len(days)), avg_hold_min=float(hold.mean()),
        overnight_trades=int((pd.to_datetime(tr.exit_time).dt.floor("D") != tdays).sum()),
    )


def run_legs(mod, specs, spread_mult=1.0, cut=None):
    """Returns (trades, day_index, orders_by_leg, min_lot_ok)."""
    all_tr, days, orders_by_leg, ok = [], set(), [], True
    for n, leg in enumerate(mod.LEGS):
        sid = str(leg["symbol_id"])
        spec = specs[sid]
        m1 = ingest.load(sid, "M_1")
        if cut is not None:
            m1 = m1.iloc[:int(len(m1) * cut)].reset_index(drop=True)
        od = mod.signals(m1, leg.get("params", {}), spec)
        od = od.sort_values("idx", kind="stable").reset_index(drop=True)
        orders_by_leg.append(od)
        if len(od) and spec.get("min_units") is not None and od.volume.min() < spec["min_units"] - 1e-12:
            ok = False
        if spec.get("min_units") is None:
            ok = False
        tr = engine.simulate(m1, od, spread=spec["spread"] * spread_mult, slip=spec.get("slip", 0.0),
                             gap_sl=spec.get("gap_sl", False), max_open=leg.get("max_open", 1),
                             usd_per_quote=spec.get("usd_per_quote", 1.0))
        tr["leg"] = n; tr["symbol"] = spec["name"]
        all_tr.append(tr)
        # a market day = a calendar day with at least 6 hours of M1 bars (skips Sunday-evening stubs)
        cnt = m1.time.dt.floor("D").value_counts()
        days |= set(cnt[cnt >= 360].index)
    tr = pd.concat(all_tr).sort_values("exit_time").reset_index(drop=True) if all_tr else pd.DataFrame()
    return tr, sorted(days), orders_by_leg, ok


def lookahead_check(mod, specs, full_orders):
    """Signals computed on truncated history must equal the full-history signals over the shared prefix."""
    cols = ["idx", "side", "kind", "price", "sl", "tp", "max_bars", "trail", "valid", "volume"]
    for cut in (0.55, 0.8):
        _, _, part, _ = run_legs(mod, specs, cut=cut)
        for full, p, leg in zip(full_orders, part, mod.LEGS):
            n = int(len(ingest.load(str(leg["symbol_id"]), "M_1")) * cut)
            a = full[full.idx < n - 1].reset_index(drop=True)
            b = p[p.idx < n - 1].reset_index(drop=True)
            if len(a) != len(b):
                return False
            for c in cols:
                if c in a and c in b and not np.allclose(a[c].to_numpy(float), b[c].to_numpy(float), rtol=1e-9, atol=1e-9):
                    return False
    return True


def evaluate(path, spread_mult=1.0, check=True):
    mod = load_strategy(path)
    specs = load_specs(path)
    tr, days, orders, ok = run_legs(mod, specs, spread_mult)
    days = pd.DatetimeIndex(days)
    split = days[int(len(days) * (1 - OOS_FRACTION))]
    m = {"strategy": path, "legs": [{"symbol": specs[str(l["symbol_id"])]["name"], **l} for l in mod.LEGS],
         "period": [str(days[0].date()), str(days[-1].date())], "oos_start": str(split.date()),
         "full": stats(tr, days),
         "is": stats(tr[tr.entry_time < split], days[days < split]),
         "oos": stats(tr[tr.entry_time >= split], days[days >= split]),
         "min_lot_ok": bool(ok)}
    if check:
        st, _, _, _ = run_legs(mod, specs, spread_mult * 1.5)
        m["stress"] = stats(st, days)
        m["lookahead_ok"] = bool(lookahead_check(mod, specs, orders))
        m["gates"] = {k: bool(f(m)) for k, f in GATES.items()}
        m["qualified"] = all(m["gates"].values())
    return m, tr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("strategy"); ap.add_argument("--out"); ap.add_argument("--spread-mult", type=float, default=1.0)
    ap.add_argument("--fast", action="store_true", help="skip stress + look-ahead checks")
    a = ap.parse_args()
    m, tr = evaluate(a.strategy, a.spread_mult, check=not a.fast)
    f = lambda s: (f"trades={s['trades']:4d} PF={s['pf']:.2f} net=${s['net']:.2f} win={s['win_rate']:.0f}% "
                   f"DD=${s['max_dd_usd']:.2f} worst=${s['worst_trade']:.2f} tr/day={s['trades_per_day']:.1f} "
                   f"active={s['active_day_pct']:.0f}% wk+={s['weeks_profitable_pct']:.0f}%")
    print(f"period {m['period'][0]} -> {m['period'][1]}  (OOS from {m['oos_start']})")
    for k in ("full", "is", "oos", "stress"):
        if k in m:
            print(f"{k:6s} {f(m[k])}")
    if "gates" in m:
        for k, v in m["gates"].items():
            print(f"  [{'PASS' if v else 'FAIL'}] {k}")
        print("QUALIFIED" if m["qualified"] else "NOT QUALIFIED")
    if a.out:
        os.makedirs(a.out, exist_ok=True)
        json.dump(m, open(os.path.join(a.out, "metrics.json"), "w"), indent=1, default=str)
        tr.to_csv(os.path.join(a.out, "trades.csv"), index=False)


if __name__ == "__main__":
    main()
