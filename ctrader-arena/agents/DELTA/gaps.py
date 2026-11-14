import sys, pandas as pd
sys.path.insert(0, '.')
from arena.ingest import load
sid, per = sys.argv[1], sys.argv[2]
d = load(sid, per); print(len(d), d.time.iloc[0], d.time.iloc[-1])
g = d.time.diff(); big = d[g > pd.Timedelta(days=4.2)]
for i in big.index: print("GAP", d.time[i-1], "->", d.time[i])
