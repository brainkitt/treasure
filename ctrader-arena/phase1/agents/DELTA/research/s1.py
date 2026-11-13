import sys; sys.path.insert(0,"agents/DELTA")
from lib import *
for sid in (2517,2518):
    b = ny(load(sid,"M_5"))
    print(sid, len(b), b.time.iloc[0], b.time.iloc[-1], "days", b.nyd.nunique())
    b["r"] = np.log(b.close/b.open); b["rng"]=b.high-b.low
    print(" med M5 range", b.rng.median(), "RTH med", b[(b.nyh>=9.5)&(b.nyh<16)].rng.median())
    print(" bars per day", b.groupby("nyd").size().describe()[["min","50%","max"]].to_dict())
    g = b.groupby(b.nyh.astype(int)).agg(n=("r","size"), mean_bp=("r", lambda x: x.mean()*1e4), t=("r", lambda x: x.mean()/x.std()*np.sqrt(len(x))), rng=("rng","median"))
    print(g.round(2).T.to_string())
    r = b.r
    print(" AC1..3 M5:", [round(r.autocorr(k),3) for k in (1,2,3)])
    rth = b[(b.nyh>=9.5)&(b.nyh<16)]
    print(" AC1 RTH:", round(rth.r.autocorr(1),3))
