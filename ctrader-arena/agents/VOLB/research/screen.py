"""Statistics screen for VOLB universe. Usage: python screen.py PERIOD [min_bars]"""
import sys, numpy as np, pandas as pd, os
sys.path.insert(0, '/home/user/treasure/ctrader-arena')
from arena.ingest import load
from universe import U
from scipy import stats as ss
per = sys.argv[1] if len(sys.argv) > 1 else 'M_5'
sp = pd.read_csv(os.path.join(os.path.dirname(__file__), 'spreads.csv'))
sp['s'] = (sp.ask - sp.bid) / 1e5
spmax = sp.groupby('sid').s.max()
rows = []
for sid, (name, fam, par) in U.items():
    f = f'/home/user/treasure/ctrader-arena/data/{sid}_{per}.csv.gz'
    if not os.path.exists(f): continue
    b = load(sid, per)
    if len(b) < 300: continue
    c = b.close.to_numpy(); r = np.diff(c)            # arithmetic returns (price units)
    lr = np.diff(np.log(c))
    n = len(r); rng = np.median(b.high - b.low)
    s = spmax.get(sid, np.nan)
    t_drift = r.mean() / (r.std() / np.sqrt(n))
    ac = [np.corrcoef(r[:-k], r[k:])[0, 1] for k in (1, 2, 3)]
    def vr(q):
        rq = c[q:] - c[:-q]; return rq.var() / (q * r.var())
    vrs = {q: vr(q) for q in (3, 12, 48)}
    # vol clustering: AC of |r|
    a = np.abs(r - r.mean()); acabs = np.corrcoef(a[:-1], a[1:])[0, 1]
    kurt = ss.kurtosis(r)
    # p-values (two sided) for AC1 and VR12 (Lo-MacKinlay homoskedastic approx)
    p_ac1 = 2 * ss.norm.sf(abs(ac[0]) * np.sqrt(n))
    q = 12; z = (vrs[q] - 1) / np.sqrt(2 * (2 * q - 1) * (q - 1) / (3 * q * n)); p_vr = 2 * ss.norm.sf(abs(z))
    p_dr = 2 * ss.t.sf(abs(t_drift), n - 1)
    p_cl = 2 * ss.norm.sf(abs(acabs) * np.sqrt(n))
    rows.append(dict(sym=name, sid=sid, n=n, spread=s, rng=rng, cost=s / rng, t_dr=t_drift, ac1=ac[0], ac2=ac[1],
                     vr3=vrs[3], vr12=vrs[12], vr48=vrs[48], acabs=acabs, kurt=kurt,
                     p_dr=p_dr, p_ac1=p_ac1, p_vr12=p_vr, p_clu=p_cl))
d = pd.DataFrame(rows)
# BH over all p-values
P = d[['p_dr', 'p_ac1', 'p_vr12', 'p_clu']].to_numpy().ravel()
def bh(p):
    p=np.asarray(p); m=len(p); o=np.argsort(p); q=p[o]*m/np.arange(1,m+1)
    q=np.minimum.accumulate(q[::-1])[::-1]; out=np.empty(m); out[o]=np.minimum(q,1); return out<0.05,out
rej, padj = bh(P)
d[['q_dr', 'q_ac1', 'q_vr12', 'q_clu']] = padj.reshape(-1, 4)
d.to_csv(f'screen_{per}.csv', index=False)
pd.set_option('display.width', 250)
print(d[['sym', 'n', 'spread', 'rng', 'cost', 't_dr', 'ac1', 'vr12', 'vr48', 'acabs', 'kurt', 'q_dr', 'q_ac1', 'q_vr12', 'q_clu']].round(3).to_string(index=False))
print('tests', len(P), 'BH-significant', rej.sum())
