"""Arena v2 official scoring (safety-first, any timeframe, any start balance).

    python -m arena.evaluate2 agents/<NAME>/strategy.py [--out submissions/<NAME>] [--fast]

Strategy module contract
------------------------
    START_BALANCE = 30.0          # USD the system is evaluated with (optional, default 30)
    LEGS = [ {"symbol_id": 2517, "period": "M_15", "params": {...}, "max_open": 1}, ... ]
    def signals(bars, params, spec) -> DataFrame of orders (arena/engine.py documents the columns)

`bars` = arena.ingest.load(symbol_id, period) - BID OHLC of the leg's own period (M_1 .. D_1).
Order `idx` = bar at whose CLOSE the decision is made; fills happen from bar idx+1 on.
`spec` = arena/specs.json entry merged with agents/<NAME>/specs.json.

Costs modelled
--------------
* spread (constant, widest sampled; longs pay on entry, shorts on exit) + optional `slip` per stop fill
* commission: spec["commission_per_unit_side"] USD per unit per side (Deriv cTrader history shows 0)
* swap: spec["swap_long"] / spec["swap_short"] = USD COST per unit per night held (negative = credit).
  A "night" = each crossing of spec["rollover_hour_utc"] (default 21 UTC). spec["triple_weekday"]
  (0=Mon .. 6=Sun, default None) charges x3 on that weekday's rollover. If a leg holds overnight and
  spec["swap_known"] is not true, the swap gate FAILS.
* stress run: spread x1.5 AND extra slippage of 0.25 x spread on every stop/market fill.

Robustness extras
-----------------
* walk-forward consistency: the sample is split in 5 equal time folds; each fold's PF is reported.
* Monte-Carlo: 5000 bootstrap resamples of the trade sequence -> 95th / 99th percentile drawdown.
* t-stat of mean trade (expectancy / standard error).
* minimum-balance model: recommended minimum = max(MC95 DD / 0.25, |worst trade| / 0.03, 2 x margin);
  technical minimum = MC99 DD + margin of the maximum simultaneous exposure.
"""
import argparse, importlib.util, json, os, sys
import numpy as np, pandas as pd
from . import engine, ingest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OOS_FRACTION = 0.30
PERIOD_MIN = {"M_1": 1, "M_5": 5, "M_15": 15, "M_30": 30, "H_1": 60, "H_4": 240, "D_1": 1440}


def gates(m):
    B = m["start_balance"]
    return {
        "PF full >= 1.30": m["full"]["pf"] >= 1.30,
        "PF in-sample >= 1.20": m["is"]["pf"] >= 1.20,
        "PF out-of-sample >= 1.20": m["oos"]["pf"] >= 1.20,
        "PF under cost stress (1.5x spread + slippage) >= 1.10": m["stress"]["pf"] >= 1.10,
        "trades >= 100": m["full"]["trades"] >= 100,
        "OOS trades >= 30": m["oos"]["trades"] >= 30,
        ">= 4 of 5 walk-forward folds profitable": sum(f["net"] > 0 for f in m["folds"]) >= 4,
        "expectancy t-stat >= 2.0": m["full"]["t_stat"] >= 2.0,
        "max drawdown <= 25% of start balance": m["full"]["max_dd_usd"] <= 0.25 * B,
        "Monte-Carlo 95% drawdown <= 35% of start balance": m["mc"]["dd95"] <= 0.35 * B,
        "worst trade <= 5% of start balance": m["full"]["worst_trade"] >= -0.05 * B,
        "no look-ahead": m["lookahead_ok"],
        "min lot known and respected": m["min_lot_ok"],
        "swap known for overnight holds": m["swap_ok"],
        "margin <= 50% of start balance": m["margin_usd"] is None or m["margin_usd"] <= 0.5 * B,
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
    spec = importlib.util.spec_from_file_location("strat_" + str(abs(hash(path))), path)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, os.path.dirname(os.path.abspath(path)))
    spec.loader.exec_module(mod)
    return mod


def _nights(entry, exit_, hour, triple):
    """number of rollover crossings (with weekday multiplier) between entry and exit timestamps."""
    out = np.zeros(len(entry))
    for i, (a, b) in enumerate(zip(entry, exit_)):
        if b <= a:
            continue
        first = (a - pd.Timedelta(hours=hour)).floor("D") + pd.Timedelta(days=1, hours=hour)
        if first > b:
            continue
        roll = pd.date_range(first, b, freq="D")
        w = np.ones(len(roll))
        if triple is not None:
            w[roll.weekday == triple] = 3
        out[i] = w.sum()
    return out


def apply_costs(tr, orders, spec):
    if len(tr) == 0:
        tr["nights"] = []; tr["swap"] = []; tr["commission"] = []
        return tr
    vol = orders.volume.to_numpy(float)[tr.order_row.astype(int)] if "volume" in orders else np.ones(len(tr))
    usd = spec.get("usd_per_quote", 1.0)
    tr["volume"] = vol
    tr["gross"] = tr.pnl
    nights = _nights(pd.to_datetime(tr.entry_time), pd.to_datetime(tr.exit_time),
                     spec.get("rollover_hour_utc", 21), spec.get("triple_weekday"))
    rate = np.where(tr.side > 0, spec.get("swap_long", 0.0), spec.get("swap_short", 0.0))
    tr["nights"] = nights
    tr["swap"] = -nights * rate * vol
    tr["commission"] = -2 * spec.get("commission_per_unit_side", 0.0) * vol
    tr["pnl"] = tr.gross + tr.swap + tr.commission
    return tr


def market_days(bars, period):
    cnt = bars.time.dt.floor("D").value_counts() * PERIOD_MIN[period]
    if PERIOD_MIN[period] >= 1440:
        return set(cnt.index)
    return set(cnt[cnt >= 360].index)


def stats(tr, day_index, B):
    keys = dict(trades=0, pf=0.0, net=0.0, return_pct=0.0, win_rate=0.0, avg_win=0.0, avg_loss=0.0, expectancy=0.0,
                t_stat=0.0, max_dd_usd=0.0, max_dd_pct=0.0, worst_trade=0.0, best_trade=0.0, max_consec_losses=0,
                sharpe_daily=0.0, trades_per_week=0.0, weeks_profitable_pct=0.0, months_profitable_pct=0.0,
                avg_hold_hours=0.0, overnight_trades=0, exposure_pct=0.0, swap_total=0.0, commission_total=0.0,
                spread_cost_est=0.0, recovery_factor=0.0, longest_dd_days=0.0, days=len(day_index))
    if len(tr) == 0:
        return keys
    p = tr.pnl.to_numpy()
    gp, gl = p[p > 0].sum(), -p[p < 0].sum()
    eq = B + np.cumsum(p)
    peak = np.maximum.accumulate(np.concatenate([[B], eq]))[1:]
    dd = peak - eq
    # longest time under water
    t_exit = pd.to_datetime(tr.exit_time).to_numpy()
    uw, start, longest = False, None, pd.Timedelta(0)
    for i in range(len(dd)):
        if dd[i] > 1e-12 and not uw:
            uw, start = True, t_exit[i]
        elif dd[i] <= 1e-12 and uw:
            uw = False; longest = max(longest, pd.Timedelta(t_exit[i] - start))
    if uw:
        longest = max(longest, pd.Timedelta(t_exit[-1] - start))
    days = pd.DatetimeIndex(day_index)
    daily = tr.groupby(pd.to_datetime(tr.exit_time).dt.floor("D")).pnl.sum().reindex(days, fill_value=0.0)
    wk = tr.groupby(pd.to_datetime(tr.exit_time).dt.to_period("W")).pnl.sum()
    mo = tr.groupby(pd.to_datetime(tr.exit_time).dt.to_period("M")).pnl.sum()
    streak = best = 0
    for x in p:
        streak = streak + 1 if x < 0 else 0
        best = max(best, streak)
    hold = (pd.to_datetime(tr.exit_time) - pd.to_datetime(tr.entry_time)).dt.total_seconds() / 3600
    span_h = max(1.0, (days[-1] - days[0]).total_seconds() / 3600 + 24) if len(days) else 1.0
    nweeks = max(1.0, len(days) / 5.0)
    return dict(
        trades=int(len(p)), pf=float(gp / gl) if gl > 0 else 99.0, net=float(p.sum()),
        return_pct=float(p.sum() / B * 100), win_rate=float((p > 0).mean() * 100),
        avg_win=float(p[p > 0].mean()) if (p > 0).any() else 0.0,
        avg_loss=float(p[p < 0].mean()) if (p < 0).any() else 0.0, expectancy=float(p.mean()),
        t_stat=float(p.mean() / (p.std(ddof=1) / np.sqrt(len(p)))) if len(p) > 2 and p.std() > 0 else 0.0,
        max_dd_usd=float(dd.max()), max_dd_pct=float((dd / peak).max() * 100),
        worst_trade=float(p.min()), best_trade=float(p.max()), max_consec_losses=int(best),
        sharpe_daily=float(daily.mean() / daily.std() * np.sqrt(252)) if daily.std() > 0 else 0.0,
        trades_per_week=float(len(p) / nweeks), weeks_profitable_pct=float((wk > 0).mean() * 100),
        months_profitable_pct=float((mo > 0).mean() * 100), avg_hold_hours=float(hold.mean()),
        overnight_trades=int((tr.get("nights", pd.Series(0, index=tr.index)) > 0).sum()),
        exposure_pct=float(min(100.0, hold.sum() / span_h * 100)),
        swap_total=float(tr["swap"].sum()) if "swap" in tr else 0.0,
        commission_total=float(tr["commission"].sum()) if "commission" in tr else 0.0,
        spread_cost_est=float(tr["spread_cost"].sum()) if "spread_cost" in tr else 0.0,
        recovery_factor=float(p.sum() / dd.max()) if dd.max() > 0 else 99.0,
        longest_dd_days=float(longest.total_seconds() / 86400), days=int(len(days)),
    )


def monte_carlo(p, n=5000, seed=7):
    if len(p) < 5:
        return dict(dd95=0.0, dd99=0.0, dd50=0.0, p_loss=1.0)
    rng = np.random.default_rng(seed)
    s = rng.choice(p, size=(n, len(p)), replace=True)
    eq = np.cumsum(s, axis=1)
    peak = np.maximum.accumulate(np.concatenate([np.zeros((n, 1)), eq], axis=1), axis=1)[:, 1:]
    dd = (peak - eq).max(axis=1)
    return dict(dd50=float(np.percentile(dd, 50)), dd95=float(np.percentile(dd, 95)),
                dd99=float(np.percentile(dd, 99)), p_loss=float((eq[:, -1] <= 0).mean()))


def run_legs(mod, specs, spread_mult=1.0, extra_slip_frac=0.0, cut=None):
    all_tr, days, orders_by_leg, ok, swap_ok, margin = [], set(), [], True, True, 0.0
    margin_known = True
    for n, leg in enumerate(mod.LEGS):
        sid = str(leg["symbol_id"]); period = leg.get("period", "M_1")
        spec = specs[sid]
        bars = ingest.load(sid, period)
        if cut is not None:
            bars = bars.iloc[:int(len(bars) * cut)].reset_index(drop=True)
        od = mod.signals(bars, leg.get("params", {}), spec)
        od = od.sort_values("idx", kind="stable").reset_index(drop=True)
        orders_by_leg.append(od)
        mu = spec.get("min_units")
        if mu is None or (len(od) and od.volume.min() < mu - 1e-12):
            ok = False
        sp = spec["spread"] * spread_mult
        tr = engine.simulate(bars, od, spread=sp, slip=spec.get("slip", 0.0) + extra_slip_frac * spec["spread"],
                             gap_sl=spec.get("gap_sl", False), max_open=leg.get("max_open", 1),
                             usd_per_quote=spec.get("usd_per_quote", 1.0))
        tr = apply_costs(tr, od, spec)
        if len(tr):
            tr["spread_cost"] = -sp * tr.volume * spec.get("usd_per_quote", 1.0)
            if (tr.nights > 0).any() and not spec.get("swap_known", False):
                swap_ok = False
        tr["leg"] = n; tr["symbol"] = spec["name"]; tr["period"] = period
        all_tr.append(tr)
        days |= market_days(bars, period)
        if spec.get("margin_per_unit") is None:
            margin_known = False
        elif len(od):
            margin += spec["margin_per_unit"] * od.volume.max() * leg.get("max_open", 1)
    tr = pd.concat(all_tr).sort_values("exit_time").reset_index(drop=True) if all_tr else pd.DataFrame()
    return tr, sorted(days), orders_by_leg, ok, swap_ok, (margin if margin_known else None)


def lookahead_check(mod, specs, full_orders):
    cols = ["idx", "side", "kind", "price", "sl", "tp", "max_bars", "trail", "valid", "volume"]
    for cut in (0.55, 0.8):
        part = run_legs(mod, specs, cut=cut)[2]
        for full, p, leg in zip(full_orders, part, mod.LEGS):
            n = int(len(ingest.load(str(leg["symbol_id"]), leg.get("period", "M_1"))) * cut)
            a = full[full.idx < n - 1].reset_index(drop=True)
            b = p[p.idx < n - 1].reset_index(drop=True)
            if len(a) != len(b):
                return False
            for c in cols:
                if c in a and c in b and not np.allclose(a[c].to_numpy(float), b[c].to_numpy(float), rtol=1e-9, atol=1e-9):
                    return False
    return True


def score(m):
    """User-weighted 0-100 score (weights from the mission brief)."""
    f, o, s, B = m["full"], m["oos"], m["stress"], m["start_balance"]
    c = lambda x: float(min(1.0, max(0.0, x)))
    folds_ok = sum(x["net"] > 0 for x in m["folds"]) / max(1, len(m["folds"]))
    years = max(0.25, f["days"] / 252)
    cagr_on_min = (f["net"] / years) / max(1e-9, m["balance"]["recommended_min"])
    parts = {
        "risk_adjusted_return (25)": 25 * c(f["sharpe_daily"] / 3.0),
        "profit_factor (15)": 15 * c((f["pf"] - 1.0) / 1.0),
        "drawdown_control (15)": 15 * c(1 - m["mc"]["dd95"] / (0.35 * B)),
        "out_of_sample (15)": 15 * c((o["pf"] - 1.0) / 1.0) * c(o["trades"] / 50),
        "robustness (10)": 10 * folds_ok * c((s["pf"] - 1.0) / 0.5),
        "statistical_edge (10)": 10 * c(f["t_stat"] / 4.0),
        "execution_realism (5)": 5 * c((s["pf"] - 1.0) / 0.5),
        "capital_efficiency (5)": 5 * c(cagr_on_min / 0.5),
    }
    return round(sum(parts.values()), 1), {k: round(v, 2) for k, v in parts.items()}


def evaluate(path, spread_mult=1.0, check=True):
    mod = load_strategy(path)
    B = float(getattr(mod, "START_BALANCE", 30.0))
    specs = load_specs(path)
    tr, days, orders, ok, swap_ok, margin = run_legs(mod, specs, spread_mult)
    days = pd.DatetimeIndex(days)
    split = days[int(len(days) * (1 - OOS_FRACTION))]
    m = {"strategy": path, "start_balance": B,
         "legs": [{"symbol": specs[str(l["symbol_id"])]["name"], **l} for l in mod.LEGS],
         "period": [str(days[0].date()), str(days[-1].date())], "oos_start": str(split.date()),
         "full": stats(tr, days, B), "is": stats(tr[tr.entry_time < split], days[days < split], B),
         "oos": stats(tr[tr.entry_time >= split], days[days >= split], B),
         "min_lot_ok": bool(ok), "swap_ok": bool(swap_ok), "margin_usd": margin}
    edges = days[np.linspace(0, len(days) - 1, 6).astype(int)]
    m["folds"] = []
    for a, b in zip(edges[:-1], edges[1:]):
        sel = tr[(tr.entry_time >= a) & ((tr.entry_time < b) if b != edges[-1] else True)]
        p = sel.pnl.to_numpy()
        m["folds"].append(dict(start=str(a.date()), end=str(b.date()), trades=int(len(p)), net=float(p.sum()),
                               pf=float(p[p > 0].sum() / -p[p < 0].sum()) if (p < 0).any() else 99.0))
    m["mc"] = monte_carlo(tr.pnl.to_numpy()) if len(tr) else monte_carlo(np.array([]))
    worst = abs(m["full"]["worst_trade"])
    rec = max(m["mc"]["dd95"] / 0.25, worst / 0.03, 2 * (margin or 0.0))
    m["balance"] = dict(technical_min=round(m["mc"]["dd99"] + (margin or 0.0), 2), recommended_min=round(rec, 2),
                        recommended_operating=round(1.5 * rec, 2), margin_at_max_exposure=margin)
    if check:
        st = run_legs(mod, specs, spread_mult * 1.5, extra_slip_frac=0.25)[0]
        m["stress"] = stats(st, days, B)
        m["lookahead_ok"] = bool(lookahead_check(mod, specs, orders))
        m["gates"] = {k: bool(v) for k, v in gates(m).items()}
        m["qualified"] = all(m["gates"].values())
        m["score"], m["score_parts"] = score(m)
    return m, tr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("strategy"); ap.add_argument("--out"); ap.add_argument("--spread-mult", type=float, default=1.0)
    ap.add_argument("--fast", action="store_true", help="skip stress + look-ahead checks")
    a = ap.parse_args()
    m, tr = evaluate(a.strategy, a.spread_mult, check=not a.fast)
    f = lambda s: (f"trades={s['trades']:5d} PF={s['pf']:.2f} net=${s['net']:.2f} ({s['return_pct']:.0f}%) "
                   f"win={s['win_rate']:.0f}% exp=${s['expectancy']:.3f} t={s['t_stat']:.2f} DD=${s['max_dd_usd']:.2f} "
                   f"worst=${s['worst_trade']:.2f} sharpe={s['sharpe_daily']:.2f} tr/wk={s['trades_per_week']:.1f} "
                   f"swap=${s['swap_total']:.2f}")
    print(f"start balance ${m['start_balance']:.2f}  period {m['period'][0]} -> {m['period'][1]}  (OOS from {m['oos_start']})")
    for k in ("full", "is", "oos", "stress"):
        if k in m:
            print(f"{k:6s} {f(m[k])}")
    print("folds  " + "  ".join(f"{x['start']}:{x['trades']}tr PF{x['pf']:.2f} ${x['net']:.2f}" for x in m["folds"]))
    print(f"MC DD  p50=${m['mc']['dd50']:.2f} p95=${m['mc']['dd95']:.2f} p99=${m['mc']['dd99']:.2f}")
    print(f"balance technical_min=${m['balance']['technical_min']} recommended_min=${m['balance']['recommended_min']} "
          f"operating=${m['balance']['recommended_operating']} margin={m['margin_usd']}")
    if "gates" in m:
        for k, v in m["gates"].items():
            print(f"  [{'PASS' if v else 'FAIL'}] {k}")
        print(("QUALIFIED" if m["qualified"] else "NOT QUALIFIED") + f"   score={m['score']}/100")
    if a.out:
        os.makedirs(a.out, exist_ok=True)
        json.dump(m, open(os.path.join(a.out, "metrics.json"), "w"), indent=1, default=str)
        tr.to_csv(os.path.join(a.out, "trades.csv"), index=False)


if __name__ == "__main__":
    main()
