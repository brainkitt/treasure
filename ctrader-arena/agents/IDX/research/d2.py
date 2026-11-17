from lib import *
import itertools
SW={2517:1.54,2521:0.57,2522:0.76}
def daily_cash(b):
    # cash-close day: bars from 16:00 NY (prev) to 15:00 NY bar inclusive; close = close of 15:00 bar
    ny=b.time.dt.tz_localize('UTC').dt.tz_convert('America/New_York').dt.tz_localize(None)
    sd=(ny+pd.Timedelta(hours=8)).dt.floor('D')   # 16:00 -> next day
    g=b.groupby(sd.values)
    D=pd.DataFrame({'open':g.open.first(),'high':g.high.max(),'low':g.low.min(),'close':g.close.last(),
                    'last_idx':g.apply(lambda x:x.index[-1]),'last_h':g.nyh.last(),'n':g.size()})
    return D[(D.n>=10)&(D.last_h==15)]
def feats(D):
    c=D.close; dlt=c.diff()
    pc=c.shift(1); tr=np.maximum(D.high-D.low,np.maximum((D.high-pc).abs(),(D.low-pc).abs())); a=tr.rolling(14).mean()
    return c,dlt,a
def rsi(c,n):
    d=c.diff(); up=d.clip(lower=0).ewm(alpha=1/n,adjust=False).mean(); dn=(-d.clip(upper=0)).ewm(alpha=1/n,adjust=False).mean()
    return 100-100/(1+up/dn)
def orders(b,D,sig,a,tpm,slm,hold,vol=1.0):
    sel=sig&a.notna()
    return pd.DataFrame({'idx':D.last_idx[sel].to_numpy(),'side':1,'kind':0,'sl':(slm*a[sel]).to_numpy(),'tp':(tpm*a[sel]).to_numpy(),'max_bars':hold*23,'volume':vol})
def signal(D,kind,p):
    c,dlt,a=feats(D)
    if kind=='rsi': s=rsi(c,p[0])<p[1]
    elif kind=='zlow': s=(c-c.rolling(p[0]).mean())/a < -p[1]          # close below N-day mean by k ATR
    elif kind=='ndown': s=(c<c.shift(1))&(c.shift(1)<c.shift(2))&(c.shift(2)<c.shift(3)) if p[0]==3 else (c<c.shift(1))&(c.shift(1)<c.shift(2))
    elif kind=='lowclose': s=c<=c.rolling(p[0]).min()                  # lowest close of N days
    return s, a
if __name__=='__main__':
    rows=[]
    specs=[('rsi',(2,10)),('rsi',(2,20)),('rsi',(3,15)),('rsi',(3,25)),('zlow',(5,1.0)),('zlow',(5,1.5)),('zlow',(10,1.5)),('zlow',(10,2.0)),
           ('ndown',(2,)),('ndown',(3,)),('lowclose',(5,)),('lowclose',(10,))]
    for s in (2517,2521,2522):
        b=bars(s); D=daily_cash(b)
        for (kind,p),tpm,slm,hold in itertools.product(specs,(0.5,1.0,0),(2.0,3.0),(2,4)):
            sig,a=signal(D,kind,p); od=orders(b,D,sig,a,tpm,slm,hold)
            tr=run(b,od,s,swap_long=SW[s]); r=summ(tr,b); r.update(s=NAME[s],kind=kind,p=str(p),tp=tpm,sl=slm,hold=hold); rows.append(r)
    X=pd.DataFrame(rows); X.to_csv('d2.csv'); print(len(X))
    print(X.groupby(['kind','p','s'])[['n','pf_is','pf_oos']].median().unstack(2).round(2).to_string())
    for c in ['tp','sl','hold']:
        print(X.groupby(['s',c])[['pf_is','pf_oos']].median().unstack(0).round(2))
