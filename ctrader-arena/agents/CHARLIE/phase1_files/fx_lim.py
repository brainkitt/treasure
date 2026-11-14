"""Pre-sample passive LIMIT fade on M15: both halves must hold. usage: fx_lim.py sid:pip:spreadpips:usdq ..."""
import sys, itertools; sys.path.insert(0,'.'); sys.path.insert(0,'agents/CHARLIE')
import numpy as np, pandas as pd
from arena import engine
from fx_tod import pre
SES={'lon':(7,12),'ny':(12,16)}
def orders(m,p,a,b,spr,vol=1000.0):
    c=m.close; ma=c.rolling(p['n']).mean(); sd=c.rolling(p['n']).std()
    tr=np.maximum(m.high-m.low,np.maximum((m.high-c.shift()).abs(),(m.low-c.shift()).abs())); atr=tr.rolling(14).mean()
    z=((c-ma)/sd).to_numpy(); hr=(m.time.dt.hour+m.time.dt.minute/60).to_numpy(); A=atr.to_numpy(); C=c.to_numpy()
    i=np.where((hr>=a)&(hr<b)&(np.abs(z)>p['k'])&~np.isnan(A))[0]; side=-np.sign(z[i])
    price=np.where(side>0, C[i]-p['off']*A[i], C[i]+spr+p['off']*A[i])       # long: ASK must fall to price; short: BID must rise
    tp=np.maximum(np.abs(C[i]-ma.to_numpy()[i]),0.3*A[i])
    return pd.DataFrame(dict(idx=i,side=side,kind=1,price=price,sl=p['sl']*A[i],tp=tp,max_bars=p['mb'],valid=p['v'],volume=vol))
def st(tr,q):
    p=tr.pnl.to_numpy()*q
    return (len(p), p[p>0].sum()/max(1e-9,-p[p<0].sum()) if len(p) else 0, p.sum() if len(p) else 0, p.min() if len(p) else 0)
GRID=[dict(n=20,k=k,off=off,sl=sl,mb=mb,v=2) for k,off,sl,mb in itertools.product((2.0,2.5),(0.0,0.25,0.5),(1.5,3.0),(6,16))]
if __name__=='__main__':
    for a in sys.argv[1:]:
        sid,pip,spr,q=a.split(':'); pip=float(pip); spr=float(spr)*pip; q=float(q); m=pre(sid); half=m.time.iloc[len(m)//2]
        for nm,(x,y) in SES.items():
            rows=[]
            for p in GRID:
                tr=engine.simulate(m,orders(m,p,x,y,spr),spread=spr); h1=st(tr[tr.entry_time<half],q); h2=st(tr[tr.entry_time>=half],q); al=st(tr,q)
                rows.append((p['k'],p['off'],p['sl'],p['mb'],al[0],round(al[1],2),round(h1[1],2),round(h2[1],2),round(al[2],1),round(al[3],2)))
            df=pd.DataFrame(rows,columns='k off sl mb n pf pf_h1 pf_h2 net worst'.split()); df['mn']=df[['pf_h1','pf_h2']].min(axis=1)
            print(f"{sid} {nm}: sets={len(df)} PF med={df.pf.median():.2f} max={df.pf.max():.2f}; both halves>1.2: {(df.mn>1.2).sum()}; top by min-half:")
            print(df.sort_values('mn',ascending=False).head(3).drop(columns='mn').to_string(index=False))
