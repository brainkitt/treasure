"""Pre-declared test of R2 (WF-selected: RB200 M5 Donchian-48 FOLLOW, SL=trail=3*ATR24, H=12) on the unseen month
before 2026-07-21 10:40. Success criterion (declared before running): PF >= 1.2 and t >= 1. Otherwise kill."""
import sys; sys.path.insert(0, 'agents/VOLA/research'); sys.path.insert(0, '.')
import contextlib, io
with contextlib.redirect_stdout(io.StringIO()):
    from c1_confirm import c1
from lab import *
full = load(2450, 'M_5'); new = full[full.time < '2026-07-21 10:40'].reset_index(drop=True)
print('unseen sample', len(new), new.time.iloc[0], new.time.iloc[-1])
for nm, (N, tk, H) in {'R2': (48, 3, 12), 'C1': (24, 2, 48)}.items():
    res, tr = run(new, c1(new, N, tk, H, 1), 2450, f'{nm}_confirm_junjul', dict(N=N, tk=tk, H=H))
    p = tr.pnl.to_numpy(); print(nm, 'trades', len(p), 'PF', round(pf(p), 3), 't', round(p.mean() / p.std() * np.sqrt(len(p)), 2))
