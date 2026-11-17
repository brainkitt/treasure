from lib import *
SW={2517:(1.54,1.0),2521:(0.57,0.4),2522:(0.76,0.5)}
rows=[]; cnt=0
for s in (2517,2521,2522):
    b=bars(s); a=atr(b,14)
    for n in (10,20,40):
        ma=b.close.rolling(n).mean()
        z=(b.close-ma)/a
        for L in (0,200):
            trend = (b.close>b.close.rolling(L).mean()) if L else pd.Series(True,index=b.index)
            for k in (1.5,2.0,2.5):
                for side in (1,-1):
                    cond = (z< -k)&trend if side==1 else (z>k)&(~trend if L else trend)
                    cond = cond & ~cond.shift(1,fill_value=False)
                    idx=b.index[cond & a.notna()]
                    for slm in (2.0,):
                        for mb in (6,24):
                            od=pd.DataFrame({'idx':idx,'side':side,'kind':0,'sl':(slm*a[idx]).to_numpy(),
                               'tp':(np.abs(b.close-ma)[idx]).to_numpy(),'max_bars':mb,'volume':1.0})
                            tr=run(b,od,s,swap_long=SW[s][0],swap_short=SW[s][1]); cnt+=1
                            r=summ(tr,b); r.update(s=NAME[s],n_=n,L=L,k=k,side=side,mb=mb,f=folds(tr,b)); rows.append(r)
d=pd.DataFrame(rows); print(cnt); print(d.sort_values('pf_is',ascending=False).head(40).to_string())
d.to_csv('h_b.csv')
