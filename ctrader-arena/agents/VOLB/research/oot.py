"""Out-of-time check: families/grids selected on the last 24 days, evaluated on EARLIER bars only."""
import sys, itertools, numpy as np, pandas as pd
sys.path.insert(0,'.'); sys.path.insert(0,'/home/user/treasure/ctrader-arena')
import lab
from arena.ingest import load
from arena import engine
sid, spread, cutoff = int(sys.argv[1]), float(sys.argv[2]), pd.Timestamp(sys.argv[3])
b = load(sid,'M_5'); early = b[b.time < cutoff].reset_index(drop=True); late = b[b.time >= cutoff].reset_index(drop=True)
print(f"early {len(early)} bars {early.time.iloc[0]}..{early.time.iloc[-1]}; late {len(late)}")
for fam in sys.argv[4].split(','):
    f, grid = lab.FAM[fam]; rows=[]
    for vals in itertools.product(*grid.values()):
        p = dict(zip(grid.keys(), vals))
        r = {}
        for nm, bb in (('late', late), ('early', early)):
            tr = engine.simulate(bb, f(bb, **p), spread=spread); x = tr.pnl.to_numpy()
            r[nm+'_pf'] = lab.pf(x); r[nm+'_n'] = len(x); r[nm+'_t'] = x.mean()/(x.std()/np.sqrt(len(x))+1e-12) if len(x)>2 else 0
        rows.append({**p, **r})
    d = pd.DataFrame(rows)
    top = d.sort_values('late_pf', ascending=False).head(5)
    print(f"{fam:6s} sets={len(d)} late: PF>1 {np.mean(d.late_pf>1):.0%} | early: PF>1 {np.mean(d.early_pf>1):.0%}, median PF {d.early_pf.median():.2f}, max t {d.early_t.max():.2f} | top5-late -> early PF {np.round(top.early_pf.values,2)} n {top.early_n.values}")
