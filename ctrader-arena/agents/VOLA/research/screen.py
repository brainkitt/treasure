"""Cost screen: live spread vs median M5 range (pre-holdout data only, via arena.ingest.load)."""
import json, os, sys, numpy as np, pandas as pd
sys.path.insert(0, '.')
from arena.ingest import load
R = 'agents/VOLA/research/'
uni = {u[0]: u[1] for u in json.load(open(R+'universe.json'))}
fam = [s for s in uni if not uni[s].startswith(('Volatility 1','Volatility 2','Volatility 3','Volatility 4','Volatility 5',
       'Volatility 6','Volatility 7','Volatility 8','Volatility 9','Volatility 5','Step','Multi','Drift','VolSwitch','High Freq'))]
sp = {}
for l in open(R+'spreads_raw.txt'):
    if l.startswith('#') or not l.strip(): continue
    a = l.split(); s = int(a[0]); v = (int(a[2]) - int(a[1])) / 1e5
    sp.setdefault(s, []).append(v)
rows = []
for s in sorted(fam):
    p = f'data/{s}_M_5.csv.gz'
    spread = max(sp.get(s, [np.nan]))
    if not os.path.exists(p):
        rows.append(dict(symbol=uni[s], id=s, spread=spread, m5_range=None, cost_ratio=None, key_stats='no pre-holdout history', verdict='untestable (launched after holdout start)'))
        continue
    b = load(s, 'M_5')
    if len(b) < 100:
        rows.append(dict(symbol=uni[s], id=s, spread=spread, m5_range=None, cost_ratio=None, key_stats=f'{len(b)} bars', verdict='untestable')); continue
    rng = (b.high - b.low).median()
    r = np.log(b.close).diff().dropna()
    absr = (b.close.diff().abs()).dropna()
    # spikes: |ret| > 6 robust sd
    mad = (r - r.median()).abs().median() * 1.4826
    jumps = (np.abs(r - r.median()) > 6 * mad)
    ac1 = r.autocorr(1)
    rows.append(dict(symbol=uni[s], id=s, spread=round(spread, 4), m5_range=round(float(rng), 4), cost_ratio=round(float(spread / rng), 3),
                     key_stats=f'n={len(b)} price={b.close.iloc[-1]:.1f} AC1={ac1:+.3f} jumpbars={jumps.mean()*100:.1f}% skew={r.skew():+.1f}', verdict=''))
df = pd.DataFrame(rows)
df.to_csv(R+'screen_cost.csv', index=False)
pd.set_option('display.width', 200)
print(df[['id','symbol','spread','m5_range','cost_ratio','key_stats']].sort_values('cost_ratio').to_string(index=False))
