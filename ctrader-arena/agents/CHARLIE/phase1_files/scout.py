"""Scout: per-symbol M1 structure. usage: python agents/CHARLIE/scout.py id [id...]"""
import sys, json, numpy as np, pandas as pd
sys.path.insert(0, ".")
from arena.ingest import load
specs = json.load(open("arena/specs.json"))
try: specs.update(json.load(open("agents/CHARLIE/specs.json")))
except Exception: pass
for sid in sys.argv[1:]:
    try: m = load(sid, "M_1")
    except Exception as e: print(sid, "no data"); continue
    r = np.log(m.close / m.close.shift(1)).dropna().to_numpy()
    rng = ((m.high - m.low) / m.close).to_numpy()
    med = np.median(np.abs(r)); 
    up = (m.high - m.open) / m.close; dn = (m.open - m.low) / m.close
    sp = specs.get(str(sid), {}).get("spread", np.nan)
    px = m.close.iloc[-1]
    ac1 = np.corrcoef(r[1:], r[:-1])[0, 1]
    print(f"{sid} {specs.get(str(sid),{}).get('name','?'):28s} n={len(m)} px={px:.2f} spread={sp} ({sp/px*1e4:.2f}bp) "
          f"medabs={med*1e4:.2f}bp std={r.std()*1e4:.2f}bp mean={r.mean()*1e4:.3f}bp skew={pd.Series(r).skew():.2f} kurt={pd.Series(r).kurt():.1f} "
          f"ac1={ac1:.3f} frac_up={(r>0).mean():.2f} maxup={up.max()*1e4:.1f}bp maxdn={dn.max()*1e4:.1f}bp medrng={np.median(rng)*1e4:.2f}bp")
