"""Scout on M5: event studies EURUSD"""
from lib import *
sid = int(sys.argv[1]) if len(sys.argv) > 1 else 1
b = load(sid, "M_5"); pip = PIP[sid]; sp = SPREAD[sid]
split = split_time(b); IS = b.time < split
b["h"] = b.time.dt.hour; b["d"] = b.time.dt.floor("D")
c = b.close.to_numpy(); n = len(b)
def fwd(k):
    f = np.full(n, np.nan); f[:-k-1] = c[k+1:] - b.open.to_numpy()[1:-k]  # enter next open, exit close k bars later
    return f
print("split", split, "bars", n)
# H4/H5: impulsive bar continuation/fade
atr = (b.high - b.low).rolling(48).mean().shift(1)
body = (b.close - b.open)
for thr in (2.0, 3.0, 4.0):
    sig = np.sign(body) * (body.abs() > thr * atr)
    for k in (3, 12, 36):
        f = fwd(k)
        for nm, m in (("IS", IS), ("OOS", ~IS)):
            mm = m & (sig != 0) & ~np.isnan(f)
            r = (f[mm] * sig[mm]) / pip
            print(f"impulse thr={thr} k={k:2d} {nm:3s} n={mm.sum():4d} mean_cont={r.mean():6.2f}p  t={r.mean()/r.std()*np.sqrt(len(r)):5.2f}  (cost {sp/pip:.1f}p)")
# hour-of-day drift IS vs OOS
hr = b.assign(ret=(b.close - b.open) / pip, IS=IS).groupby(["h", "IS"]).ret.sum().unstack()
nd = b.groupby(IS).d.nunique()
print((hr / [nd[False], nd[True]]).round(1).T.to_string())
