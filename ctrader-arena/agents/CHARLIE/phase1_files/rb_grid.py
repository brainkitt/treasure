import sys; sys.path.insert(0,'.')
from arena.ingest import load
from arena import engine
import numpy as np, pandas as pd
sid=int(sys.argv[1]); spread=float(sys.argv[2]); vol=0.01
m=load(sid,'M_1'); o,h,l,c=[m[x].to_numpy() for x in ('open','high','low','close')]
rng=h-l; n=len(m); cut=int(n*0.7)
brk=np.where(rng>30)[0]; d=np.sign(c[brk]-o[brk])
def run(side_mult, sl, tp, mb, lo=0, hi=n):
    sel=(brk>=lo)&(brk<hi)
    od=pd.DataFrame(dict(idx=brk[sel], side=d[sel]*side_mult, kind=0, sl=sl, tp=tp, max_bars=mb, volume=vol))
    od=od[od.side!=0]
    tr=engine.simulate(m, od, spread=spread, gap_sl=True)
    p=tr.pnl.to_numpy(); 
    if len(p)==0: return None
    gp=p[p>0].sum(); gl=-p[p<0].sum()
    return dict(n=len(p), pf=round(gp/max(gl,1e-9),2), net=round(p.sum(),2), avg_pts=round(p.mean()/vol,2), se=round(p.std()/vol/np.sqrt(len(p)),2), win=round((p>0).mean()*100), worst=round(p.min(),2))
print('n bars',n,'breaks',len(brk))
for sm,name in ((1,'MOMENTUM'),(-1,'FADE')):
    for sl in (8,15,25,500):
        for tp in (0,10,20,60):
            for mb in (5,20,60):
                a=run(sm,sl,tp,mb,0,cut); b=run(sm,sl,tp,mb,cut,n)
                print(name,f"sl={sl} tp={tp} mb={mb}  IS {a}  | OOS pf={b['pf']} avg={b['avg_pts']}±{b['se']} n={b['n']}")
