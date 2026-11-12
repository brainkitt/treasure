import sys, numpy as np, hmm
from arena.ingest import load
sid=int(sys.argv[1])
m=load(sid); c=m.close.to_numpy(); r=np.diff(np.log(c))*1e4  # bp
n=int(len(r)*0.7); x=r[:n]
s=x.std()
for K,mu0,sd0 in ((2,[-.5,.5],[1,1]),(3,[-.5,0,.5],[1,1,1]),(3,[-.5,0,.5],[1,.6,1]),(3,[0,0,0.01],[.5,1,1.5]),(4,[-.5,.5,-.5,.5],[.7,.7,1.4,1.4])):
    mu0=np.array(mu0)*s; sd0=np.array(sd0)*s
    A=np.full((K,K),0.03/(K-1)); np.fill_diagonal(A,0.97)
    mu,sd,A,ll=hmm.fit(x,mu0,sd0,A,iters=500)
    print(K,'ll',round(ll,1),'mu',mu.round(3),'sd',sd.round(3), 'dur',(1/(1-np.diag(A))).round(1))
    llo=np.log(hmm._fb(hmm.emis(r[n:],mu,sd),A,np.full(K,1/K))[2]).sum()
    print(' oos ll',round(llo,1),' vs iid gauss', round((-0.5*((r[n:]-x.mean())/s)**2-np.log(s)).sum(),1))
