import json, numpy as np, pandas as pd
from universe import U
m5 = pd.read_csv('screen_M_5.csv').set_index('sid'); h1 = pd.read_csv('screen_H_1.csv').set_index('sid')
sp = pd.concat([pd.read_csv('spreads.csv'), pd.read_csv('dsi_spreads.csv'), pd.read_csv('../../VOL/research/spreads.csv')[['ts_ms','sid','bid','ask']]]); sp['s'] = (sp.ask - sp.bid) / 1e5; spm = sp.groupby('sid').s.max()
new = {2668, 2669, 2670, 2671, 2672, 2673, 2674, 2675, 2676, 2677}
extra = {2448: 'M1 3000 bars: zero-change share 0.107 = theory for 60 fair +/-0.1 ticks; out-of-time (Jul-Aug) breakout/MR/tsmom: max t 1.19 over 180 sets; min lot probed 1.00 unit',
         2617: 'VolSwitch H1 Apr-Sep (3598 bars): no drift by vol regime, no leverage effect, mom12 t 1.48',
         2616: 'VolSwitch H1 Apr-Sep: vol clustering only (by design), no directional structure',
         2618: 'VolSwitch H1 Apr-Sep: acabs 0.24 (vol regimes by design), AC1|regime |r|<0.03',
         2470: 'DSI30 M5 73.5k bars: AC1 0.05, VR12 1.42; long-only ER follower gross +4.9 pts/trade, break-even spread ~5; spread 6.5-10.2 when drifting',
         2469: 'DSI20: AC1 0.10, VR12 1.54; break-even spread ~2.8 (L-only); spread 2.1-4.05 when drifting',
         2464: 'DSI10: AC1 0.15, VR12 1.52; break-even spread ~1.6 (L-only); spread 2.4-3.8 observed'}
rows = []
for sid, (nm, fam, par) in U.items():
    s = spm.get(sid, np.nan)
    if sid in m5.index:
        r = m5.loc[sid]; h = h1.loc[sid] if sid in h1.index else None
        ks = f"M5 n={int(r.n)} t_drift={r.t_dr:.2f} AC1={r.ac1:.3f} VR12={r.vr12:.2f} VR48={r.vr48:.2f} AC|r|={r.acabs:.3f}"
        if h is not None: ks += f"; H1 n={int(h.n)} t_drift={h.t_dr:.2f} VR12={h.vr12:.2f} VR48={h.vr48:.2f}"
        if sid in extra: ks += '; ' + extra[sid]
        if fam == 'dsi':
            v = 'real regime momentum (BH q<0.001) but killed by regime-dependent spread'
        elif min(r.q_dr, r.q_ac1, r.q_vr12) < 0.05:
            v = 'flagged'
        else:
            v = 'fair random walk (no BH-significant drift/AC/VR); no edge possible net of spread'
            if fam == 'vsw': v = 'vol clustering by design only; directionally fair; no edge'
        rows.append(dict(symbol=nm, symbol_id=sid, spread=round(float(s), 5), m5_range=round(float(r.rng), 5),
                         cost_ratio=round(float(s / r.rng), 3), key_stats=ks, verdict=v))
    else:
        rows.append(dict(symbol=nm, symbol_id=sid, spread=None if np.isnan(s) else round(float(s), 5), m5_range=None, cost_ratio=None,
                         key_stats='no bars before 2026-09-15 (listed after the holdout cut)', verdict='untestable pre-holdout'))
json.dump(rows, open('screen_rows.json', 'w'), indent=1)
print(len(rows), 'rows;', sum(r['m5_range'] is not None for r in rows), 'with data')
