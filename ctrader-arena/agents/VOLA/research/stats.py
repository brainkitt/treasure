"""Statistical screen of every spike/jump synthetic with pre-holdout M5 history.
Tests per symbol (pre-registered):
 T1 drift: mean M5 price change (t-test, HAC-free since AC~0)
 T2 AC1 of M5 returns (z = r*sqrt(n))
 T3 variance ratio VR(6) (30 min) Lo-MacKinlay homoskedastic z
 T4 hour-of-day mean return (F-test over 24 bins)
 T5 hour-of-day abs-return (Kruskal-ish F on |r|)  -> volatility schedule
 T6 post-jump drift: mean signed (in jump direction) return over next 3 bars after a jump bar (t-test)
 T7 jump hazard vs bars since last jump (chi2 over 5 buckets) [only if >=40 jumps]
 T8 volatility clustering: AC1 of |r| (excluding jump bars)
Usage: python stats.py [start] [end]  (dates; default whole pre-holdout file)
Output: research/stats_<tag>.csv and BH-adjusted summary."""
import sys, json, os, numpy as np, pandas as pd
from scipy import stats as st
sys.path.insert(0, '.')
from arena.ingest import load
R = 'agents/VOLA/research/'
start = sys.argv[1] if len(sys.argv) > 1 else None
end = sys.argv[2] if len(sys.argv) > 2 else None
tag = sys.argv[3] if len(sys.argv) > 3 else 'disc'
syms = [int(x) for x in sys.argv[4].split(',')] if len(sys.argv) > 4 else None
cost = pd.read_csv(R + 'screen_cost.csv')
cost = cost[cost.m5_range.notna()]
ids = syms or cost.id.tolist()
name = dict(zip(cost.id, cost.symbol))
rows = []
STEP = {'M_5': 300000, 'M_15': 900000, 'H_1': 3600000}[os.environ.get('PER', 'M_5')]
for s in ids:
    b = load(s, os.environ.get('PER', 'M_5'))
    if start: b = b[b.time >= start]
    if end: b = b[b.time < end]
    b = b.reset_index(drop=True)
    # use contiguous diffs only
    dt = b.ts.diff().fillna(STEP)
    r = b.close.diff()
    r[dt != STEP] = np.nan
    r = r.dropna()
    n = len(r)
    if n < 300: continue
    rr = r.to_numpy()
    med = np.median(rr); mad = np.median(np.abs(rr - med)) * 1.4826
    jump = np.abs(rr - med) > 6 * mad
    res = {}
    # T1
    res['T1_drift'] = st.ttest_1samp(rr, 0).pvalue
    t1 = rr.mean() / (rr.std(ddof=1) / np.sqrt(n))
    # T2
    ac1 = np.corrcoef(rr[:-1], rr[1:])[0, 1]
    res['T2_ac1'] = 2 * st.norm.sf(abs(ac1) * np.sqrt(n))
    # T3 VR(6)
    q = 6
    rq = pd.Series(rr).rolling(q).sum().dropna().to_numpy()
    vr = rq.var() / (q * rr.var())
    se = np.sqrt(2 * (2 * q - 1) * (q - 1) / (3 * q * n))
    res['T3_vr6'] = 2 * st.norm.sf(abs(vr - 1) / se)
    # T4 / T5 hour of day
    hrs = b.time.dt.hour.to_numpy()[1:][dt.to_numpy()[1:] == STEP][:n]
    groups = [rr[hrs == h] for h in range(24) if (hrs == h).sum() > 5]
    res['T4_hour_mean'] = st.f_oneway(*groups).pvalue
    res['T5_hour_vol'] = st.kruskal(*[np.abs(g) for g in groups]).pvalue
    # T6 post-jump drift (next 3 bars, signed by jump direction)
    ji = np.where(jump[:-3])[0]
    if len(ji) >= 10:
        fwd = np.array([rr[i + 1:i + 4].sum() * np.sign(rr[i] - med) for i in ji])
        res['T6_postjump'] = st.ttest_1samp(fwd, 0).pvalue; pj = fwd.mean()
    else:
        res['T6_postjump'] = np.nan; pj = np.nan
    # T7 hazard
    if jump.sum() >= 40:
        since = np.zeros(n, int); c = 99
        for i in range(n):
            since[i] = c; c = 0 if jump[i] else c + 1
        qs = np.unique(np.quantile(since[since < 99], [0.2, 0.4, 0.6, 0.8]))
        bk = np.digitize(since, qs)
        obs = np.array([[jump[bk == k].sum(), (~jump[bk == k]).sum()] for k in np.unique(bk)])
        obs = obs[(obs.sum(1) > 0)]
        res['T7_hazard'] = st.chi2_contingency(obs)[1] if len(obs) > 1 and (obs.sum(0) > 0).all() else np.nan
    else:
        res['T7_hazard'] = np.nan
    # T8 vol clustering on non-jump bars
    a = np.abs(rr); a[jump] = np.nan
    s_ = pd.Series(a)
    acv = s_.autocorr(1)
    res['T8_volclust'] = 2 * st.norm.sf(abs(acv) * np.sqrt(n)) if np.isfinite(acv) else np.nan
    rows.append(dict(id=s, symbol=name.get(s, s), n=n, drift_t=round(t1, 2), ac1=round(ac1, 3), vr6=round(vr, 3), postjump=pj,
                     jumps=int(jump.sum()), acabs=round(acv, 3), **res))
df = pd.DataFrame(rows)
pcols = [c for c in df if c.startswith('T')]
long = df.melt(id_vars=['id', 'symbol'], value_vars=pcols, var_name='test', value_name='p').dropna()
m = len(long)
long = long.sort_values('p').reset_index(drop=True)
long['bonf'] = np.minimum(1, long.p * m)
long['bh'] = np.minimum.accumulate((long.p * m / (np.arange(m) + 1))[::-1])[::-1].clip(upper=1)
df.to_csv(R + f'stats_{tag}.csv', index=False); long.to_csv(R + f'stats_{tag}_tests.csv', index=False)
print(f'{tag}: symbols={len(df)} tests={m}  raw p<0.05: {(long.p<0.05).sum()} (expected {0.05*m:.0f})  BH q<0.10: {(long.bh<0.10).sum()}')
print(long.head(15).to_string(index=False))
