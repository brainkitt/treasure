"""Time-of-day / day-of-week screen: one-way ANOVA of returns (drift) and |returns| (vol) on UTC hour and weekday."""
import sys, os, numpy as np, pandas as pd
from scipy import stats as ss
sys.path.insert(0,'/home/user/treasure/ctrader-arena')
from arena.ingest import load
from universe import U
rows=[]
for sid,(nm,fam,_) in U.items():
    for per in ('M_5','H_1'):
        f=f'/home/user/treasure/ctrader-arena/data/{sid}_{per}.csv.gz'
        if not os.path.exists(f): continue
        b=load(sid,per)
        if len(b)<700: continue
        r=np.diff(np.log(b.close.to_numpy())); h=b.time.dt.hour.to_numpy()[1:]; w=b.time.dt.weekday.to_numpy()[1:]
        z=r/r.std()
        def anova(x,g): return ss.f_oneway(*[x[g==k] for k in np.unique(g) if (g==k).sum()>5]).pvalue
        rows.append(dict(sym=nm,per=per,n=len(r),p_hour_drift=anova(z,h),p_hour_vol=anova(np.abs(z),h),p_wd_drift=anova(z,w),p_wd_vol=anova(np.abs(z),w)))
d=pd.DataFrame(rows); P=d[['p_hour_drift','p_hour_vol','p_wd_drift','p_wd_vol']].to_numpy().ravel()
m=len(P); o=np.argsort(P); q=P[o]*m/np.arange(1,m+1); q=np.minimum.accumulate(q[::-1])[::-1]; Q=np.empty(m); Q[o]=np.minimum(q,1)
d[['q_hd','q_hv','q_wd','q_wv']]=Q.reshape(-1,4)
d.to_csv('tod.csv',index=False)
print('tests',m,'min raw p %.4f'%P.min(),'BH-significant:',(Q<0.05).sum())
print(d[(d[['q_hd','q_hv','q_wd','q_wv']]<0.05).any(axis=1)].round(4).to_string(index=False))
