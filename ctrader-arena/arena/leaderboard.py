"""Supervisor re-score of every agent.  python -m arena.leaderboard  -> submissions/<NAME>/{metrics.json,trades.csv} + leaderboard.json"""
import glob, json, os
from .evaluate import evaluate, ROOT


def main():
    rows = []
    for path in sorted(glob.glob(os.path.join(ROOT, "agents", "*", "strategy.py"))):
        name = os.path.basename(os.path.dirname(path))
        if name.startswith("_"):
            continue
        try:
            m, tr = evaluate(path)
        except Exception as e:
            print(name, "ERROR", repr(e)); continue
        out = os.path.join(ROOT, "submissions", name); os.makedirs(out, exist_ok=True)
        json.dump(m, open(os.path.join(out, "metrics.json"), "w"), indent=1, default=str)
        tr.to_csv(os.path.join(out, "trades.csv"), index=False)
        f, o, s = m["full"], m["oos"], m["stress"]
        rows.append(dict(agent=name, qualified=m["qualified"], gates_passed=sum(m["gates"].values()), gates=len(m["gates"]),
                         pf=f["pf"], pf_is=m["is"]["pf"], pf_oos=o["pf"], pf_stress=s["pf"], trades=f["trades"], net=f["net"],
                         max_dd=f["max_dd_usd"], worst=f["worst_trade"], active=f["active_day_pct"],
                         symbols=", ".join(l["symbol"] for l in m["legs"])))
    rows.sort(key=lambda r: (-r["gates_passed"], -min(r["pf_oos"], r["pf"])))
    for r in rows:
        print(f"{r['agent']:8s} {'QUALIFIED' if r['qualified'] else 'no':9s} gates {r['gates_passed']}/{r['gates']}  PF {r['pf']:.2f} "
              f"(IS {r['pf_is']:.2f} / OOS {r['pf_oos']:.2f} / stress {r['pf_stress']:.2f})  trades {r['trades']}  net ${r['net']:.2f}  "
              f"DD ${r['max_dd']:.2f}  worst ${r['worst']:.2f}  active {r['active']:.0f}%  [{r['symbols']}]")
    json.dump(rows, open(os.path.join(ROOT, "submissions", "leaderboard.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
