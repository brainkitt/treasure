from strat import *
sid = int(sys.argv[1]); tf = 5
b = prep(load(sid, "M_5"), tf); pip = PIP[sid]; split = split_time(b)
print("== ORB Asian->London")
for (r0, r1, e1, xh) in ((0, 7, 10, 16), (0, 7, 12, 20), (0, 6, 9, 13), (3, 7, 10, 16), (7, 12, 16, 20), (8, 12.5, 16, 20), (0, 12, 16, 20)):
    for slm, tpm in ((0.5, 2.0), (1.0, 1.5), (0.5, 4.0), (1.0, 3.0)):
        od = orb(b, tf, pip, r0, r1, e1, xh, slm=slm, tpm=tpm)
        rep(run(sid, b, od), split, f"orb {r0}-{r1} e<{e1} x{xh} slm{slm} tpm{tpm}")
print("== MeanRev")
for (h0, h1) in ((22, 6), (0, 6), (23, 5), (10, 12), (17, 21), (7, 17)):
    for n, k in ((24, 2.0), (24, 2.5), (48, 2.5), (12, 2.0)):
        od = meanrev(b, tf, pip, h0, h1, n=n, k=k, sl=10, mb=24)
        rep(run(sid, b, od), split, f"mr {h0}-{h1} n{n} k{k}")
