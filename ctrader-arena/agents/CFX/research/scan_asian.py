"""H3 scan: Asian-session mean reversion. Signal: price deviation from rolling mean during 23-06 UTC,
fade it, measure forward move (gross pips) vs spread."""
from lib import *
for sid in [1,2,4,5,6,8,9,3]:
    b = bars(sid); sp = split_time(sid); hr = b.time.dt.hour
    c = b.close; pip = PIP[sid]
    for L in [6, 12]:
        ma = c.rolling(L).mean(); sd = (c.diff()).rolling(48).std()*np.sqrt(L)
        z = (c - ma) / sd
        for zt in [1.0, 1.5]:
            asian = hr.isin([23,0,1,2,3,4])
            ev = asian & (z.abs() > zt)
            for Hf in [3]:
                f = -(c.shift(-Hf) - c) * np.sign(z) / pip
                a = f[ev & (b.time < sp)].dropna(); o = f[ev & (b.time >= sp)].dropna()
                print(f"{NAMES[sid]} L{L} z>{zt} H{Hf}: IS n={len(a)} {a.mean():+.2f}pip t={a.mean()/a.std()*np.sqrt(len(a)):+.1f} | OOS {o.mean():+.2f} | spread {SPREAD[sid]/pip:.1f}")
