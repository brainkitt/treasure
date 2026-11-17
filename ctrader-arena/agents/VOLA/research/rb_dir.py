"""Range Break: are consecutive break directions autocorrelated? (H: Deriv RNG -> independent, P(same)=0.5)"""
import sys, numpy as np; sys.path.insert(0, '.')
from scipy import stats as st
from arena.ingest import load
for sid, per in [(2450, 'M_5'), (2449, 'M_5'), (2450, 'H_1'), (2449, 'H_1')]:
    b = load(sid, per); r = b.close.diff().fillna(0).to_numpy()
    med = np.median(r); mad = np.median(np.abs(r - med)) * 1.4826
    J = np.abs(r - med) > 6 * mad
    s = np.sign(r[J]); same = (s[1:] == s[:-1])
    k, n = same.sum(), len(same)
    p = st.binomtest(k, n, 0.5).pvalue if n else np.nan
    # follow-through: next 12 bars return in break direction (net), in units of break size
    ji = np.where(J)[0]; ji = ji[ji < len(r) - 13]
    fwd = np.array([r[i+1:i+13].sum() * np.sign(r[i]) for i in ji])
    print(f'{sid} {per}: bars={len(b)} breaks={J.sum()} up={int((s>0).sum())} P(same dir)={k/n:.3f} (n={n}) p={p:.3f}  fwd12 mean={fwd.mean():+.2f} t={fwd.mean()/fwd.std()*np.sqrt(len(fwd)):+.2f}  mean|break|={np.abs(r[J]).mean():.1f}')
