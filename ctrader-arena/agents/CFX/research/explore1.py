from lib import *
for sid in [1,2,3,4,5,6,8,9,101,102]:
    b = bars(sid)
    d = b.set_index("time").resample("D").agg({"open":"first","high":"max","low":"min","close":"last"}).dropna()
    rng = (d.high-d.low).median()
    r = np.log(d.close).diff().dropna()
    h = np.log(b.close).diff().dropna()
    ac1d = r.autocorr(1); ac1h = h.autocorr(1)
    # variance ratio daily 5
    vr5 = (np.log(d.close).diff(5).var()/5)/r.var()
    print(f"{NAMES[sid]:7s} days={len(d)} medDayRange={rng/PIP[sid]:.0f}pip spread/range={SPREAD[sid]/rng*100:.2f}% acD={ac1d:+.3f} acH={ac1h:+.3f} VR5d={vr5:.2f} totret={(d.close.iloc[-1]/d.close.iloc[0]-1)*100:+.1f}%")
