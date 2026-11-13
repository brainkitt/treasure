from lib import *; from core import *
for sid in (1, 2, 4, 7, 5, 3, 6, 8, 41):
    try: b = load(sid, "M_15")
    except Exception as e:
        b = resample(load(sid), 15).drop(columns="m1_idx")
    pip = PIP[sid]; split = split_time(b)
    day = b.groupby(b.time.dt.floor("D")).agg(hi=("high", "max"), lo=("low", "min"), n=("open", "size")); day = day[day.n > 80]
    print(f"=== {sid} bars={len(b)} {b.time.iloc[0]} split={split.date()} median daily range={((day.hi-day.lo)/pip).median():.0f}p spread={SPREAD[sid]/pip:.1f}p")
    slcap = 15 / (UPQ[sid] * 1000 * pip * 10)  # pips giving $1.5
    slcap = 1.45 / (UPQ[sid] * UNITS[sid] * pip)
    for lbl, kw in (("LDN 0-7 slm.5 tp2", dict(r0=0, r1=7, e1=10, xh=16, slm=0.5, tpm=2)), ("LDN 0-7 slm1 tp1.5", dict(r0=0, r1=7, e1=10, xh=16, slm=1, tpm=1.5)),
                    ("LDN 0-8 slm.5 tp2", dict(r0=0, r1=8, e1=11, xh=16, slm=0.5, tpm=2)), ("LDN 0-8 slm1 tp1.5", dict(r0=0, r1=8, e1=11, xh=16, slm=1, tpm=1.5)),
                    ("NY 8-13 slm.5 tp2", dict(r0=8, r1=13, e1=16, xh=20, slm=0.5, tpm=2)), ("NY 8-13 slm1 tp1.5", dict(r0=8, r1=13, e1=16, xh=20, slm=1, tpm=1.5)),
                    ("ASIA 21-24 -> 0-4", dict(r0=0, r1=1, e1=5, xh=8, slm=1, tpm=1.5))):
        p = dict(tf=15, basemin=15, slcap=slcap, slmin=min(5, slcap), **kw)
        rep(run(sid, b, orb(b, p, pip)), split, lbl)
