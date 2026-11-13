import sys; sys.path.insert(0,"agents/DELTA")
from lib import *; import fam
p=ny(load(2517,"M_15")); p=p[p.time<"2026-09-10"].reset_index(drop=True)
p["r"]=np.log(p.close/p.open)*1e4; p["h"]=p.nyh.astype(int)
p["half"]=np.where(p.time<"2026-06-18","h1","h2")
g=p.groupby("h").r.agg(n="size",mean="mean",t=lambda x: x.mean()/x.std()*np.sqrt(len(x)))
g["h1"]=p[p.half=="h1"].groupby("h").r.mean(); g["h2"]=p[p.half=="h2"].groupby("h").r.mean()
print(g.round(2).T.to_string())
# by quarter-hour slot: top |t|
p["slot"]=p.nymin
s=p.groupby("slot").r.agg(n="size",mean="mean",t=lambda x: x.mean()/x.std()*np.sqrt(len(x)))
s["h1"]=p[p.half=="h1"].groupby("slot").r.mean(); s["h2"]=p[p.half=="h2"].groupby("slot").r.mean()
print(s[s.t.abs()>2.2].round(2).to_string())
# daily structure
rows=[]
for d,gg in p.groupby("nyd"):
    x=gg.set_index("nymin")
    try:
        rows.append(dict(d=d, on=np.log(x.open[570]/x.open.iloc[0]), eur=np.log(x.open[570]/x.open[180]) if 180 in x.index else np.nan,
            f30=np.log(x.close[585]/x.open[570]), f60=np.log(x.close[615]/x.open[570]), mid=np.log(x.open[930]/x.close[585]), l30=np.log(x.close[945]/x.open[930]), l60=np.log(x.close[945]/x.open[900]),
            am=np.log(x.open[720]/x.close[585]), pm=np.log(x.close[945]/x.open[720]), day=np.log(x.close[945]/x.open[570])))
    except KeyError: pass
D=pd.DataFrame(rows).dropna(); print(len(D),"days")
print(D.drop(columns="d").corr().round(2).to_string())
print("mean bp:", (D.drop(columns="d").mean()*1e4).round(1).to_dict())
print("t:", (D.drop(columns="d").mean()/D.drop(columns="d").std()*np.sqrt(len(D))).round(2).to_dict())
