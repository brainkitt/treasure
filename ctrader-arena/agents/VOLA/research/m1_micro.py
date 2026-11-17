"""Round 4 item 2: M1 microstructure (pre-holdout 2026-09-09..09-14) on DEX600UP, VolBoom400, RB200.
Tests: AC lag1..5 (all bars), VR(2..5), post-spike signed drift over next 1..5 min (t-test),
hazard by minutes-since-spike (chi2 over 7 buckets) + logistic-free trend (corr of hazard with bucket). BH over all."""
import sys, numpy as np, pandas as pd; sys.path.insert(0, '.')
from scipy import stats as st
from arena.ingest import load
SP = {2468: 0.43, 2571: 1.24, 2450: 2.0}
rows = []
for sid in SP:
    b = load(sid, 'M_1'); dt = b.ts.diff(); r = b.close.diff(); r[dt != 60000] = np.nan
    rr = r.fillna(0).to_numpy(); valid = r.notna().to_numpy(); n = valid.sum()
    med = np.median(rr[valid]); mad = np.median(np.abs(rr[valid] - med)) * 1.4826
    J = (np.abs(rr - med) > 6 * mad) & valid
    x = rr[valid]
    for L in range(1, 6):
        a = np.corrcoef(x[:-L], x[L:])[0, 1]; rows.append((sid, f'AC{L}', a, 2 * st.norm.sf(abs(a) * np.sqrt(len(x)))))
    for q in range(2, 6):
        rq = pd.Series(x).rolling(q).sum().dropna().to_numpy(); vr = rq.var() / (q * x.var())
        se = np.sqrt(2 * (2 * q - 1) * (q - 1) / (3 * q * len(x))); rows.append((sid, f'VR{q}', vr, 2 * st.norm.sf(abs(vr - 1) / se)))
    ji = np.where(J)[0]; ji = ji[ji < len(rr) - 6]
    for k in range(1, 6):
        f = np.array([rr[i + 1:i + 1 + k].sum() * np.sign(rr[i] - med) for i in ji])
        rows.append((sid, f'post{k}m_spr', f.mean() / SP[sid], st.ttest_1samp(f, 0).pvalue))
    since = np.zeros(len(rr), int); c = 999
    for i in range(len(rr)):
        since[i] = c; c = 0 if J[i] else c + 1
    edges = [1, 2, 3, 4, 6, 11, 21, 999]
    bk = np.digitize(since, edges[1:-1]); m = valid & (since >= 1) & (since < 999)
    obs = np.array([[J[m & (bk == k)].sum(), (~J[m & (bk == k)]).sum()] for k in range(len(edges) - 1)])
    obs = obs[obs.sum(1) > 0]
    haz = obs[:, 0] / obs.sum(1)
    rows.append((sid, 'hazard_chi2', float(np.corrcoef(np.arange(len(haz)), haz)[0, 1]), st.chi2_contingency(obs)[1]))
    print(sid, 'bars', n, 'spikes', J.sum(), 'hazard by min-since-spike [1,2,3,4-5,6-10,11-20,21+]:', np.round(haz * 100, 1))
d = pd.DataFrame(rows, columns=['sid', 'test', 'stat', 'p']).sort_values('p').reset_index(drop=True)
m = len(d); d['bh'] = np.minimum.accumulate((d.p * m / (np.arange(m) + 1))[::-1])[::-1].clip(upper=1)
d.to_csv('agents/VOLA/research/m1_micro.csv', index=False)
print(f'tests={m} raw p<0.05={(d.p<0.05).sum()} (exp {0.05*m:.1f}) BH<0.10={(d.bh<0.10).sum()}')
print(d.head(10).round(4).to_string(index=False))
