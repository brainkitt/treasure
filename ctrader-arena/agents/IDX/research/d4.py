from lib import *
import itertools
SW={2517:1.54,2521:0.57,2522:0.76}
def daily15(b, last_h=14):
    ny=b.time.dt.tz_localize('UTC').dt.tz_convert('America/New_York').dt.tz_localize(None)
    sd=(ny+pd.Timedelta(hours=24-(last_h+1))).dt.floor('D')
    g=b.groupby(sd.values)
    D=pd.DataFrame({'high':g.high.max(),'low':g.low.min(),'close':g.close.last(),
                    'last_idx':g.apply(lambda x:x.index[-1]),'last_h':g.nyh.last(),'n':g.size()})
    return D[(D.n>=10)&(D.last_h==last_h)]
def dip_orders(b,D,N,tpm,slm,hold,vol=1.0,atr_n=14):
    c=D.close; pc=c.shift(1)
    tr=np.maximum(D.high-D.low,np.maximum((D.high-pc).abs(),(D.low-pc).abs())); a=tr.rolling(atr_n).mean()
    sig=(c<=c.rolling(N).min())&a.notna()
    return pd.DataFrame({'idx':D.last_idx[sig].to_numpy(),'side':1,'kind':0,'sl':(slm*a[sig]).to_numpy(),
                         'tp':(tpm*a[sig]).to_numpy(),'max_bars':hold*23-1,'volume':vol})
if __name__=='__main__':
    pre={s:(bars(s),daily15(bars(s))) for s in (2517,2521,2522)}
    cut={s:pre[s][0].time.iloc[int(len(pre[s][0])*0.7)] for s in pre}
    rows=[]
    for N,tpm,slm,hold in itertools.product((5,6,7,8,10),(0,0.75,1.5),(2.0,3.0,4.0),(1,2,3,4)):
        r={'N':N,'tp':tpm,'sl':slm,'hold':hold}; P_is=[];P_oos=[]
        for s in pre:
            b,D=pre[s]; tr=run(b,dip_orders(b,D,N,tpm,slm,hold),s,swap_long=SW[s])
            p=(tr.pnl/tr.entry_px*100).to_numpy(); i=(pd.to_datetime(tr.entry_time)<cut[s]).to_numpy()
            P_is.append(p[i]); P_oos.append(p[~i]); r[NAME[s]+'_is']=round(pf(p[i]),2); r[NAME[s]+'_oos']=round(pf(p[~i]),2)
        pi=np.concatenate(P_is); po=np.concatenate(P_oos)
        r.update(n=len(pi)+len(po),pf_is=round(pf(pi),3),pf_oos=round(pf(po),3)); rows.append(r)
    X=pd.DataFrame(rows); X.to_csv('d4.csv'); print(len(X))
    for c in ['N','tp','sl','hold']:
        print(X.groupby(c)[['pf_is','pf_oos']].median().round(3).T)
    print(X.sort_values('pf_is',ascending=False).head(15).to_string())
