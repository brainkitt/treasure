from lib import *
import itertools
SW={2517:(1.54,1.0),2521:(0.57,0.4),2522:(0.76,0.5)}
def s2_orders(b,a,vr,h0,h1,L,k,H,vmin,slm,trail,flat16):
    mv=(b.close-b.close.shift(L))/a
    contig=(b.time-b.time.shift(L))<=pd.Timedelta(hours=L+2)
    m=(b.nyh>=h0)&(b.nyh<=h1)&(b.dow<5)&contig&(mv.abs()>k)&(vr>vmin)&a.notna()
    idx=b.index[m]
    hb=np.full(len(idx),H)
    if flat16: hb=np.minimum(H,(15-b.nyh[idx]).to_numpy()); 
    od=pd.DataFrame({'idx':idx,'side':np.sign(mv[idx]).astype(int).to_numpy(),'kind':0,
        'sl':(slm*a[idx]).to_numpy(),'tp':0.0,'max_bars':hb,'trail':(trail*a[idx]).to_numpy(),'volume':1.0})
    return od[od.max_bars>0]
if __name__=='__main__':
    rows=[]
    for s in (2517,2521):
        b=bars(s); a=atr(b,14); vr=a/a.rolling(500,min_periods=100).median()
        for (h0,h1),L,k,H,vmin,slm,trail,f16 in itertools.product(((10,13),(11,14),(12,14)),(6,12),(1.5,2.5,3.5),(3,6),(0,1.1,1.3),(1.5,2.5),(0,2.0),(True,False)):
            od=s2_orders(b,a,vr,h0,h1,L,k,H,vmin,slm,trail,f16); tr=run(b,od,s,swap_long=SW[s][0],swap_short=SW[s][1])
            r=summ(tr,b); r.update(s=NAME[s],h0=h0,L=L,k=k,H=H,vmin=vmin,sl=slm,trail=trail,f16=f16); rows.append(r)
    D=pd.DataFrame(rows); D.to_csv('s2.csv'); print(len(D))
    for c in ['h0','L','k','H','vmin','sl','trail','f16']:
        print(D.groupby(['s',c])[['pf_is','pf_oos']].median().unstack(0).round(3))
