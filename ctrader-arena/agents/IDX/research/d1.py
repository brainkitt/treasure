from lib import *
import itertools
SW={2517:(1.54,1.0),2521:(0.57,0.4),2522:(0.76,0.5)}
def daily(b):
    # session day ends at close of 16:00 NY bar (17:00); label by ny date of that bar
    d=b.copy(); d['sd']=(d.time.dt.tz_localize('UTC').dt.tz_convert('America/New_York')+pd.Timedelta(hours=7)).dt.tz_localize(None).dt.floor('D')
    g=d.groupby('sd'); D=pd.DataFrame({'open':g.open.first(),'high':g.high.max(),'low':g.low.min(),'close':g.close.last(),'last_idx':g.apply(lambda x:x.index[-1]),'n':g.size()})
    return D[D.n>=10]
def d1_orders(b,D,rsin,lo,trendn,tpm,slm,hold,entry='close15'):
    c=D.close; dlt=c.diff(); up=dlt.clip(lower=0).rolling(rsin).mean(); dn=(-dlt.clip(upper=0)).rolling(rsin).mean()
    rsi=100-100/(1+up/dn)
    pc=c.shift(1); tr=np.maximum(D.high-D.low,np.maximum((D.high-pc).abs(),(D.low-pc).abs())); a=tr.rolling(14).mean()
    cond=(rsi<lo)&a.notna()
    if trendn: cond&=c>c.rolling(trendn).mean()
    sel=D[cond]
    idx=sel.last_idx.to_numpy()  # decide at close of the day's last H1 bar
    return pd.DataFrame({'idx':idx,'side':1,'kind':0,'sl':(slm*a[cond]).to_numpy(),'tp':(tpm*a[cond]).to_numpy(),'max_bars':hold*23,'volume':1.0})
if __name__=='__main__':
    rows=[]
    for s in (2517,2521,2522):
        b=bars(s); D=daily(b)
        for rsin,lo,trendn,tpm,slm,hold in itertools.product((2,3),(10,20,30),(0,100),(0.5,1.0),(2.0,3.0),(3,5)):
            od=d1_orders(b,D,rsin,lo,trendn,tpm,slm,hold); tr=run(b,od,s,swap_long=SW[s][0],swap_short=SW[s][1])
            r=summ(tr,b); r.update(s=NAME[s],rsin=rsin,lo=lo,tn=trendn,tp=tpm,sl=slm,hold=hold); rows.append(r)
    X=pd.DataFrame(rows); X.to_csv('d1.csv'); print(len(X))
    for c in ['rsin','lo','tn','tp','sl','hold']:
        print(X.groupby(['s',c])[['pf_is','pf_oos']].median().unstack(0).round(2))
    print(X.sort_values('pf_is',ascending=False).head(15).to_string())
