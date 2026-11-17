from lib import *
# H-A overnight drift: long at close of bar with nyh==entry_h (decision at close), exit after k bars (time exit)
rows=[]
for s in (2517,2521,2522):
    b=bars(s)
    for eh in (17,18,19,20):   # bar starting at eh NY; decision at its close
        for xh in (4,8,9):
            sel=b.index[b.nyh==eh]
            # bars to hold until bar starting xh closes
            hold = ((xh - eh - 1) % 24) + 1
            od=pd.DataFrame({'idx':sel,'side':1,'kind':0,'sl':b.close[sel]*0.03,'tp':0.0,'max_bars':hold,'volume':1.0})
            tr=run(b,od,s); r=summ(tr,b); r.update(s=NAME[s],eh=eh,xh=xh,f=folds(tr,b)); rows.append(r)
print(pd.DataFrame(rows).to_string())
# H-D intraday momentum: sign of return prev 16:00 close -> close of 10:00 bar ; trade 15:00 bar (enter at close of 14 bar, hold 1-2)
rows=[]
for s in (2517,2521,2522):
    b=bars(s)
    c16=b.close.where(b.nyh==15).ffill()   # close of 15:00-16:00 bar = cash close
    for sig_h in (9,10,11,12,13):
        ret=(b.close - c16.shift(1))
        for eh in (13,14):
            if eh<=sig_h: continue
            sel=b.index[b.nyh==eh]
            # signal = return from prev cash close to close of bar sig_h same day
            sig = (b.close.where(b.nyh==sig_h).ffill() - c16.shift(1).where(b.nyh==sig_h).ffill())
            sd=np.sign(sig[sel]); keep=sd!=0
            od=pd.DataFrame({'idx':sel[keep],'side':sd[keep].astype(int),'kind':0,'sl':b.close[sel[keep]]*0.03,'tp':0.0,'max_bars':15-eh,'volume':1.0})
            tr=run(b,od,s); r=summ(tr,b); r.update(s=NAME[s],sig=sig_h,eh=eh,f=folds(tr,b)); rows.append(r)
print(pd.DataFrame(rows).to_string())
