import sys; sys.path.insert(0,"agents/DELTA")
from lib import *
m1=ny(load(2517,"M_1")); IS=m1[m1.time<"2026-10-23"].copy()
lc=np.log(IS.close); IS["r"]=lc.diff()
IS["h"]=IS.nyh.astype(int)
for k in (5,15,30,60):
    IS[f"p{k}"]=lc.diff(k); IS[f"f{k}"]=lc.shift(-k)-lc
rows=[]
for h,g in IS.groupby("h"):
    d=dict(h=h, n=len(g), sd_bp=g.r.std()*1e4, ac1=g.r.autocorr(1), zero=(g.r==0).mean(), rng=(g.high-g.low).median())
    for k in (5,15,30,60):
        x=g[[f"p{k}",f"f{k}"]].dropna(); d[f"c{k}"]=np.corrcoef(x.iloc[:,0],x.iloc[:,1])[0,1]
    rows.append(d)
print(pd.DataFrame(rows).round(3).to_string(index=False))
# per-week stability of c15,c30 in asia
A=IS[(IS.nyh>=18)|(IS.nyh<3)]
A=A.assign(wk=A.time.dt.to_period("W"))
print(A.groupby("wk").apply(lambda g: pd.Series({k: g[[f"p{k}",f"f{k}"]].dropna().corr().iloc[0,1] for k in (15,30,60)})).round(3))
