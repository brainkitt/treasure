from lib import *
import itertools
def orders(b, d, L, X, k, slm, a14=None):
    a = atr(b,14) if a14 is None else a14
    lp=np.log(b.close)
    mv=(b.close-b.close.shift(L))/a     # move in ATR units over last L bars
    m=(b.nyh==d)&(b.dow<5)&a.notna()&mv.notna()
    # ensure lookback bars are contiguous (no weekend gap): time diff == L hours
    contig=(b.time-b.time.shift(L))==pd.Timedelta(hours=L)
    m&=contig&(mv.abs()>k)
    idx=b.index[m]
    side=-np.sign(mv[idx]).astype(int).to_numpy()
    return pd.DataFrame({'idx':idx,'side':side,'kind':0,'sl':(slm*a[idx]).to_numpy(),'tp':0.0,'max_bars':X-d-1,'volume':1.0})
if __name__=='__main__':
    rows=[]
    for s in (2517,2521,2522):
        b=bars(s); a=atr(b,14)
        for d,L,X,k,slm in itertools.product((4,5,6),(4,6,8),(8,9),(0,0.5,1.0,1.5),(1.5,3.0)):
            od=orders(b,d,L,X,k,slm,a); tr=run(b,od,s)
            r=summ(tr,b); r.update(s=NAME[s],d=d,L=L,X=X,k=k,sl=slm,f=folds(tr,b)); rows.append(r)
    D=pd.DataFrame(rows); D.to_csv('h_e.csv'); print(len(D))
    pd.set_option('display.width',250)
    print(D.groupby(['s','d','X']).pf_is.median().unstack())
    print(D.groupby(['s','d','X']).pf_oos.median().unstack())
    print(D.groupby(['s','k']).pf_is.median().unstack(), D.groupby(['s','L']).pf_is.median().unstack(),D.groupby(['s','sl']).pf_is.median().unstack())
    print(D[D.s=='SP'].sort_values('pf_is',ascending=False).head(25).to_string())
