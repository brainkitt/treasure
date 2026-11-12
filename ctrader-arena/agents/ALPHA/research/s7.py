from lib import *; from core import *
B = {}
for sid in (1, 2, 4, 5, 6, 8, 7, 3):
    b = resample(load(1), 15).drop(columns="m1_idx") if sid == 1 else load(sid, "M_15")
    B[sid] = b[b.time >= "2026-09-21"].reset_index(drop=True)
split = pd.Timestamp("2026-10-27")
def pooled(sids, **kw):
    trs = []
    for sid in sids:
        pip = PIP[sid]; cap = 1.45 / (UPQ[sid] * 1000 * pip)
        p = dict(tf=15, basemin=15, slcap=cap, slmin=min(5, cap), **kw)
        tr = run(sid, B[sid], orb(B[sid], p, pip)); tr["sid"] = sid; trs.append(tr)
    return pd.concat(trs).sort_values("exit_time")
def show(lbl, tr):
    a = tr[tr.entry_time < split]; o = tr[tr.entry_time >= split]
    per = " ".join(f"{sid}:{pf(g.pnl):.2f}" for sid, g in a.groupby("sid"))
    print(f"{lbl:46s} IS n={len(a):3d} PF={pf(a.pnl):.2f} net={a.pnl.sum():6.2f} [{per}] || OOS n={len(o):3d} PF={pf(o.pnl):.2f} net={o.pnl.sum():6.2f}")
M3 = (1, 2, 4)
for r1, e1 in ((7, 10), (8, 11), (7, 9), (7, 12), (8, 10)):
    for slm, tpm in ((0.5, 2.0), (0.75, 2.0), (1.0, 1.5), (1.0, 1.0), (0.5, 3.0), (1.0, 2.5)):
        for xh in (14, 16, 20):
            if xh != 16 and (slm, tpm) not in ((0.75, 2.0), (1.0, 1.5)): continue
            show(f"M3 r0-{r1} e<{e1} x{xh} slm{slm} tpm{tpm}", pooled(M3, r0=0, r1=r1, e1=e1, xh=xh, slm=slm, tpm=tpm))
print("-- all 8 symbols")
for slm, tpm in ((0.75, 2.0), (1.0, 1.5)):
    show(f"ALL8 r0-7 slm{slm} tpm{tpm}", pooled(tuple(B), r0=0, r1=7, e1=10, xh=16, slm=slm, tpm=tpm))
    show(f"ALL8 r0-8 slm{slm} tpm{tpm}", pooled(tuple(B), r0=0, r1=8, e1=11, xh=16, slm=slm, tpm=tpm))
