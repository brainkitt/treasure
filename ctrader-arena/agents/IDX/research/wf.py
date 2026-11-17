import sys, itertools, numpy as np, pandas as pd
sys.path.insert(0,'agents/IDX'); sys.path.insert(0,'agents/IDX/research')
import strategy as S
from lib import run, pf, NAME, bars
SW={2517:1.54,2521:0.57}
SPX={2517:0.40,2521:0.33}
import lib; lib.SPREAD.update(SPX)
LEGS=(2517,2521)
cache={}
def trades(s,N,tp,sl,hold):
    k=(s,N,tp,sl,hold)
    if k not in cache:
        b=bars(s); p=dict(S.PARAMS,N=N,tp_atr=tp,sl_atr=sl,hold_sessions=hold)
        od=S.signals(b,p,{'min_units':0.1}); cache[k]=run(b,od,s,swap_long=SW[s],slip=0.25)
    return cache[k]
def port(params,t0,t1):
    P=[]
    for s in LEGS:
        tr=trades(s,*params); et=pd.to_datetime(tr.entry_time); P.append(tr.pnl[(et>=t0)&(et<t1)].to_numpy())
    return np.concatenate(P)
grid=list(itertools.product((5,6,7,8,10),(0,0.75,1.5),(2.0,3.0,4.0),(1,2,3)))
T=bars(2517).time
edges=[T.iloc[int(x)] for x in np.linspace(0,len(T)-1,6)]
rows=[]
for k in range(1,5):
    t0,t1=edges[k],edges[k+1] if k<4 else T.iloc[-1]+pd.Timedelta(days=1)
    best=None
    for g in grid:
        p=port(g,edges[0],t0)
        if len(p)<30: continue
        sc=pf(p)
        if best is None or sc>best[0]: best=(sc,g)
    # plateau-robust choice: median-neighbour score
    test=port(best[1],t0,t1); fixed=port((7,0.75,3.0,1),t0,t1)
    rows.append(dict(fold=k+1,train=f"{edges[0].date()}..{t0.date()}",test=f"{t0.date()}..{t1.date()}",chosen=best[1],train_pf=round(best[0],2),
                     test_n=len(test),test_pf=round(pf(test),2),test_net=round(test.sum(),1),final_params_test_pf=round(pf(fixed),2)))
print(pd.DataFrame(rows).to_string()); print('grid size',len(grid))
pd.DataFrame(rows).to_csv('agents/IDX/research/wf.csv')
# neighbour table around final params, IS / OOS (70/30) pooled SP+RUT
cut=T.iloc[int(len(T)*0.7)]
nb=[]
base=(7,0.75,3.0,1)
for name,g in [('final',base),('N=5',(5,.75,3,1)),('N=6',(6,.75,3,1)),('N=8',(8,.75,3,1)),('N=10',(10,.75,3,1)),('TP=0 (time exit only)',(7,0,3,1)),('TP=0.5',(7,.5,3,1)),('TP=1.0',(7,1.0,3,1)),('TP=1.5',(7,1.5,3,1)),
               ('SL=2',(7,.75,2,1)),('SL=2.5',(7,.75,2.5,1)),('SL=4',(7,.75,4,1)),('hold=2',(7,.75,3,2)),('hold=3',(7,.75,3,3))]:
    a=port(g,T.iloc[0],T.iloc[-1]+pd.Timedelta(days=1)); i=port(g,T.iloc[0],cut); o=port(g,cut,T.iloc[-1]+pd.Timedelta(days=1))
    nb.append(dict(variant=name,trades=len(a),pf=round(pf(a),2),pf_is=round(pf(i),2),pf_oos=round(pf(o),2),net=round(a.sum(),1)))
print(pd.DataFrame(nb).to_string()); pd.DataFrame(nb).to_csv('agents/IDX/research/neighbours.csv')
