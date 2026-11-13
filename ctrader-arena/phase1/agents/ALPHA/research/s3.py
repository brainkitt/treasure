from lib import *; from core import *
sid = int(sys.argv[1]); m1 = load(sid); pip = PIP[sid]; split = split_time(m1)
print(sid, len(m1), m1.time.iloc[0], "split", split)
base = dict(tf=5, r0=0, r1=7, e1=10, xh=16, slm=0.5, tpm=2.0)
def t(lbl, **kw):
    p = {**base, **kw}; tr = run(sid, m1, orb(m1, p, pip)); rep(tr, split, lbl); return tr
t("base")
for kw in (dict(slm=1.0, tpm=1.5), dict(slm=1.0, tpm=1.0), dict(slm=0.75, tpm=2), dict(slm=0.5, tpm=3), dict(slm=0.5, tpm=1.5),
           dict(e1=12), dict(e1=9), dict(xh=12), dict(xh=20), dict(r0=3), dict(r1=8, e1=11), dict(r1=6, e1=9), dict(sides="both"), dict(sides="both", e1=12, xh=20),
           dict(tf=15), dict(tf=1), dict(buf=1), dict(buf=2), dict(maxr=40), dict(minr=20), dict(maxext=5),
           dict(r0=7, r1=12, e1=16, xh=20), dict(r0=8, r1=13, e1=17, xh=21), dict(r0=12, r1=14.5, e1=17, xh=21), dict(r0=7, r1=8, e1=11, xh=16), dict(r0=13.5, r1=14.5, e1=17, xh=21)):
    t(str(kw), **kw)
