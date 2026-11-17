from lib import *
import itertools
def s1_orders(b,a,vr,h0,h1,L,k,H,vmin,slm,tpm,nyexit=None):
    mv=(b.close-b.close.shift(L))/a
    contig=(b.time-b.time.shift(L))==pd.Timedelta(hours=L)
    m=(b.nyh>=h0)&(b.nyh<=h1)&(b.dow<5)&contig&(mv.abs()>k)&(vr>vmin)&a.notna()
    idx=b.index[m]
    return pd.DataFrame({'idx':idx,'side':-np.sign(mv[idx]).astype(int).to_numpy(),'kind':0,
        'sl':(slm*a[idx]).to_numpy(),'tp':(tpm*a[idx]).to_numpy(),'max_bars':H,'volume':1.0})
if __name__=='__main__':
    rows=[]
    for s in (2517,2521):
        b=bars(s); a=atr(b,14); vr=a/a.rolling(500,min_periods=100).median()
        for (h0,h1),L,k,H,vmin,slm,tpm in itertools.product(((3,6),(2,5),(4,7)),(2,3,4,6),(0.75,1.25,1.75),(2,3,4),(0,0.9),(1.5,2.5),(0,1.0)):
            od=s1_orders(b,a,vr,h0,h1,L,k,H,vmin,slm,tpm); tr=run(b,od,s)
            r=summ(tr,b); r.update(s=NAME[s],h0=h0,L=L,k=k,H=H,vmin=vmin,sl=slm,tp=tpm); rows.append(r)
    D=pd.DataFrame(rows); D.to_csv('s1.csv'); print(len(D))
    for c in ['h0','L','k','H','vmin','sl','tp']:
        print(D.groupby(['s',c])[['pf_is','pf_oos']].median().unstack(0).round(3))
