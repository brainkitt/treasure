# M1 microstructure: AC lags 1-5, VR, step quantisation (fraction of zero-change closes, close parity), bar-range dist
import sys, numpy as np
sys.path.insert(0,'/home/user/treasure/ctrader-arena')
from arena.ingest import load
from universe import U
for sid in (2448,2564,2565,2617,2654,2429):
    b=load(sid,'M_1'); c=b.close.to_numpy(); r=np.diff(c); n=len(r)
    ac=[np.corrcoef(r[:-k],r[k:])[0,1] for k in (1,2,3,5)]
    vr=lambda q:((c[q:]-c[:-q]).var()/(q*r.var()))
    # open vs prev close gap
    gap=(b.open.to_numpy()[1:]-c[:-1]); 
    print(f"{U[sid][0]:10s} n={n} ac1-5={np.round(ac,3)} se={1/np.sqrt(n):.3f} VR5={vr(5):.2f} VR30={vr(30):.2f} zero_ret={np.mean(r==0):.3f} gap!=0 {np.mean(np.abs(gap)>1e-9):.2f}")
