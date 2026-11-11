from lib import *
exec(open("s5.py").read().split('print("--- D: intraday')[0])
def mom(a0, a1, b0, b1, lo=0.0, hi=9e9, rev=False, sids=SIDS, lbl=None, norm=True):
    rows = []
    for sid in sids:
        b = D[sid]
        A = window_ret(b, a0, a1); B = window_ret(b, b0, b1); j = A.join(B, lsuffix="a", rsuffix="b", how="inner")
        j = j[(j.na >= (a1 - a0) * 4 * 0.7) & (j.nb >= (b1 - b0) * 4 * 0.7)]
        dr = ((j.hia - j.loa)).rolling(10, min_periods=3).median().shift(1)   # typical window-A range (past days only)
        z = (j.ca - j.oa).abs() / dr
        j = j[(z >= lo) & (z < hi)]
        s = np.sign(j.ca - j.oa) * (-1 if rev else 1)
        for is_, g in zip(j.ISa, s * (j.cb - j.ob) / PIP[sid]): rows.append((is_, g, SPREAD[sid] / PIP[sid], sid))
    summarize(lbl or f"mom {a0}-{a1}->{b0}-{b1} z[{lo},{hi}]", rows)
print("--- noon momentum neighbours")
for a0 in (7, 8):
    for a1 in (11, 12, 13):
        for b1 in (15, 16, 17, 18):
            mom(a0, a1, a1, b1)
print("--- by strength of morning move (z = |move| / typical morning range)")
for lo, hi in ((0, 0.25), (0.25, 0.5), (0.5, 0.75), (0.75, 9)):
    mom(7, 12, 12, 16, lo, hi)
print("--- per symbol 7-12 -> 12-16")
for sid in SIDS: mom(7, 12, 12, 16, sids=(sid,), lbl=f"sym {sid}")
print("--- from midnight / prev close reference")
mom(0, 12, 12, 16); mom(0, 12, 12, 17); mom(0, 13, 13, 17); mom(3, 12, 12, 16)
print("--- late reversal")
for a0, a1, b1 in ((12, 15, 18), (12, 16, 20), (13, 16, 18), (13, 17, 20), (7, 16, 20), (12, 16, 18)):
    mom(a0, a1, a1, b1, rev=True, lbl=f"REV {a0}-{a1}->{a1}-{b1}")
