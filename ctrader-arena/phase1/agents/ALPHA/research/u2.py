from lib import *; from core import *
sid = 2517; m1 = load(sid); pip = 1.0; split = split_time(m1)
NY = dict(tz="America/New_York", slcap=14, slmin=4)
def t(lbl, **kw):
    p = {**NY, **kw}; tr = run(sid, m1, orb(m1, p, pip)); rep(tr, split, lbl); return tr
print("== NY cash-open ORB (range from 9:30)")
for rmin in (5, 15, 30, 60):
    for slm, tpm in ((1.0, 2.0), (1.0, 4.0), (0.5, 3.0), (1.0, 1.0)):
        for sides in ("first", "both"):
            t(f"NY ORB {rmin}m slm{slm} tpm{tpm} {sides}", tf=5 if rmin >= 15 else 1 if rmin < 5 else 5, r0=9.5, r1=9.5 + rmin / 60, e1=12, xh=15.9, slm=slm, tpm=tpm, sides=sides)
print("== premarket range (4:00-9:30) break after open")
for slm, tpm in ((0.5, 2.0), (0.25, 3.0), (1.0, 1.5)):
    t(f"NY premkt slm{slm} tpm{tpm}", tf=5, r0=4, r1=9.5, e1=12, xh=15.9, slm=slm, tpm=tpm)
print("== Asian range (18:00-3:00 NY is cross-midnight; use London tz 0-7) -> London open")
for slm, tpm in ((0.5, 2.0), (1.0, 1.5), (0.5, 4.0)):
    t(f"LDN 0-8 slm{slm} tpm{tpm}", tz="Europe/London", tf=5, r0=0, r1=8, e1=11, xh=14, slm=slm, tpm=tpm)
    t(f"LDN 0-7 slm{slm} tpm{tpm}", tz="Europe/London", tf=5, r0=0, r1=7, e1=10, xh=14, slm=slm, tpm=tpm)
