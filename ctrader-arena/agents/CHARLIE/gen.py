import sys; sys.path.insert(0,'.')
from arena.ingest import load
import numpy as np, pandas as pd
names={2641:'CBFlip150',2643:'CBFlip500',2569:'Skew5Up',2576:'Skew4Dn',2666:'Snap50',2568:'VolBoom550',2606:'TrekUp',2453:'Jump50',2451:'Jump10',2455:'Jump100',2620:'Boom150',2645:'Boom50',2449:'RB100',2450:'RB200'}
sp={2641:0.1722,2643:1.02,2569:0.8,2576:0.6,2666:8.71,2568:1.09,2606:1.05,2453:9.5,2451:3.02,2449:2.6,2450:2.0}
for sid in map(int,sys.argv[1:]):
    m=load(sid,'M_1'); c=m.close.to_numpy(); r=np.diff(np.log(c))*1e4; n=len(r)
    se=1/np.sqrt(n)
    ac=[np.corrcoef(r[k:],r[:-k])[0,1] for k in (1,2,3,5,10)]
    a=np.abs(r); med=np.median(a); big=a>5*med
    # after a big move: signed forward returns (sum next k), excluding
    out=[]
    for k in (1,5,15,30):
        f=np.array([r[i+1:i+1+k].sum()*np.sign(r[i]) for i in np.where(big)[0] if i+1+k<=n])
        out.append(f"{k}:{f.mean():+.2f}±{f.std()/np.sqrt(len(f)):.2f}")
    # sign alternation of big moves
    sg=np.sign(r[big]); alt=(sg[1:]!=sg[:-1]).mean() if len(sg)>2 else np.nan
    print(f"{sid} {names.get(sid,''):10s} n={n} px={c[-1]:.1f} spr={sp.get(sid,np.nan)/c[-1]*1e4:.2f}bp std={r.std():.2f}bp med|r|={med:.2f} mean_t={r.mean()/r.std()*np.sqrt(n):+.2f} ac(1,2,3,5,10)={' '.join(f'{x:+.3f}' for x in ac)} (se {se:.3f}) big={big.sum()} (up {int((r[big]>0).sum())}) alt={alt:.2f} postbig_signed[{' '.join(out)}]")
