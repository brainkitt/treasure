import sys,glob,os
sys.path.insert(0,'.')
from arena.ingest import load
for f in sorted(glob.glob('data/*_H_1.csv.gz')):
    s=os.path.basename(f).split('_')[0]
    if int(s)>100: continue
    d=load(s,"H_1"); g=d.time.diff().dt.total_seconds()/3600
    print(s,len(d),str(d.time.iloc[0])[:10],str(d.time.iloc[-1])[:10],"gaps>100h:",[(str(d.time[i-1])[:16],str(d.time[i])[:16]) for i in g[g>100].index])
