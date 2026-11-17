import sys, numpy as np
sys.path.insert(0,'/home/user/treasure/ctrader-arena'); sys.path.insert(0,'.')
from arena.ingest import load
import hmm
for sid in (2464,2469,2470):
    b=load(sid,'M_5'); x=np.diff(b.close.to_numpy())
    x=x[:20000]
    s=x.std()
    mu,sd,A,ll=hmm.fit(x,np.array([-s/2,0,s/2]),np.array([s,s,s]),np.full((3,3),0.02)+np.eye(3)*0.94,iters=150,tie_sd=False)
    dur=1/(1-np.diag(A))*5
    print(sid,'mu',np.round(mu,3),'sd',np.round(sd,3),'dur_min',np.round(dur,1),'occupancy?')
    print('   A',np.round(A,3).tolist())
