"""F8: the only drift lead (Vol Crash 550 negative drift in screen samples, t=-2.2/-2.3).
Confirmation on the EARLIER independent H1 sample 2026-02-13..2026-08-12 (not used in discovery):
short at each bar close, hold H bars, wide disaster SL (gap fills at bar extreme). Pre-registered: H in {6,24}."""
import sys; sys.path.insert(0, 'agents/VOLA/research'); sys.path.insert(0, '.')
from lab import *
b = load(2567, 'H_1'); b = b[b.time < '2026-08-12 12:00'].reset_index(drop=True)
A = atr(b, 24); n = len(b)
for H in (6, 24):
    idx = np.arange(30, n - 2, H)
    od = orders(idx, -1, 6 * A[idx], 0, H)
    res, tr = run(b, od, 2567, 'F8_vc550_short_H1_confirm', dict(H=H))
    p = tr.pnl.to_numpy()
    print(H, 'trades', len(p), 'PF', round(pf(p), 3), 'mean', round(p.mean(), 2), 't', round(p.mean() / p.std() * np.sqrt(len(p)), 2), 'IS/OOS PF', res['pf_is'], res['pf_oos'])
