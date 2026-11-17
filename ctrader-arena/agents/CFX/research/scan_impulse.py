"""Conditional scan: after an impulsive H1 bar (|body| > k*ATR), forward return in bar direction (in ATR units)."""
from lib import *
def run(sids, label):
    for k in [1.5, 2.0, 3.0]:
        res = {H: [] for H in [1, 3, 6, 12, 24]}; reso = {H: [] for H in res}
        for sid in sids:
            b = bars(sid); sp = split_time(sid)
            atr = (b.high - b.low).rolling(48).mean().shift(1)
            body = (b.close - b.open)
            ev = np.where(body.abs() > k * atr)[0]
            c = b.close.to_numpy(); t = b.time.to_numpy()
            for H in res:
                for i in ev:
                    if i + H >= len(c) or np.isnan(atr[i]): continue
                    f = (c[i + H] - c[i]) * np.sign(body[i]) / atr[i]
                    (res if t[i] < sp else reso)[H].append(f)
        s = " ".join(f"H{H}:{np.mean(v):+.3f}(t{np.mean(v)/np.std(v)*np.sqrt(len(v)):+.1f},oos{np.mean(reso[H]):+.3f})" for H, v in res.items())
        print(f"{label} k={k} n={len(res[1])}: {s}")
run([1,2,3,4,5,6,8,9], "FX ")
run([101,102], "CRY")
