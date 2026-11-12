from lib import *; from core import *
M = {sid: load(sid) for sid in (1, 2)}
for sid in M: M[sid] = M[sid][M[sid].time >= "2026-09-21 04:00"].reset_index(drop=True)
split = pd.Timestamp("2026-10-27")
def pooled(sids=(1, 2), **kw):
    trs = []
    for sid in sids:
        pip = PIP[sid]; cap = 1.45 / (UPQ[sid] * 1000 * pip)
        p = dict(slcap=cap, slmin=min(5, cap), **kw)
        tr = run(sid, M[sid], orb(M[sid], p, pip)); tr["sid"] = sid; trs.append(tr)
    return pd.concat(trs).sort_values("exit_time")
def show(lbl, tr, oos=True):
    a = tr[tr.entry_time < split]; o = tr[tr.entry_time >= split]
    per = " ".join(f"{sid}:{pf(g.pnl):.2f}" for sid, g in a.groupby("sid"))
    s = f"{lbl:44s} IS n={len(a):3d} PF={pf(a.pnl):.2f} net={a.pnl.sum():6.2f} win={100*(a.pnl>0).mean():.0f}% [{per}]"
    if oos: s += f" || OOS n={len(o):3d} PF={pf(o.pnl):.2f} net={o.pnl.sum():6.2f}"
    print(s)
if __name__ == "__main__":
    print(len(M[2]), M[2].time.iloc[0], M[2].time.iloc[-1])
    for tf in (5, 15):
        for r1, e1 in ((7, 10), (8, 11), (8, 10)):
            for slm, tpm in ((0.5, 2.0), (0.75, 2.0), (1.0, 1.5), (1.0, 1.0), (1.0, 2.5)):
                show(f"tf{tf} r0-{r1} e<{e1} x16 slm{slm} tpm{tpm}", pooled(tf=tf, r0=0, r1=r1, e1=e1, xh=16, slm=slm, tpm=tpm), oos=False)
