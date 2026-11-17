from lib import *
import itertools
# overnight long conditioned on the US day session move (09:00 open bar -> 16:00 close), in units of daily ATR
def daymove(b, start_h=9, ref='open'):
    o9=b.open.where(b.nyh==start_h).ffill()
    return (b.close-o9)
rows=[]
for s in (2517,2521,2522):
    b=bars(s); a=atr(b,14); ad=a*np.sqrt(7)  # rough day-session scale
    dm=daymove(b)/ad
    for xh,th,side in itertools.product((4,6,8,9),(-9,-1,-0.5,0,0.5,1),(1,-1)):
        if side==1: m=(b.nyh==16)&(dm<th) if th!=-9 else (b.nyh==16)
        else: m=(b.nyh==16)&(dm>-th) if th!=-9 else (b.nyh==16)
        m&=b.dow<4  # Mon-Thu evenings (Fri evening = weekend gap)
        m&=a.notna()
        idx=b.index[m]
        # hold until close of bar xh-1 next day; bars from 18 .. xh-1 -> count = (24-18)+xh
        hold=(24-18)+xh
        od=pd.DataFrame({'idx':idx,'side':side,'kind':0,'sl':(3*a[idx]).to_numpy(),'tp':0.0,'max_bars':hold,'volume':1.0})
        tr=run(b,od,s); r=summ(tr,b); r.update(s=NAME[s],xh=xh,th=th,side=side,f=folds(tr,b),nights=int((tr.nights>0).sum())); rows.append(r)
D=pd.DataFrame(rows); pd.set_option('display.width',250); print(D.to_string())
