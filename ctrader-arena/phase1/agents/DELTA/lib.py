import numpy as np, pandas as pd, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from arena.ingest import load
from arena import engine

def ny(df):
    t = df.time.dt.tz_localize("UTC").dt.tz_convert("America/New_York")
    df = df.copy()
    df["nyh"] = t.dt.hour + t.dt.minute / 60.0
    df["nymin"] = t.dt.hour * 60 + t.dt.minute
    df["nyd"] = t.dt.strftime("%Y-%m-%d")
    df["dow"] = t.dt.dayofweek
    return df

def pf(p):
    p = np.asarray(p); g = p[p > 0].sum(); l = -p[p < 0].sum()
    return g / l if l > 0 else np.inf

def summ(tr, bars, label="", split=0.7):
    if len(tr) == 0:
        print(label, "no trades"); return
    days = np.sort(bars.time.dt.floor("D").unique())
    sp = days[int(len(days) * split)]
    i = tr[tr.entry_time < sp]; o = tr[tr.entry_time >= sp]
    act = tr.entry_time.dt.floor("D").nunique() / len(days) * 100
    eq = np.cumsum(tr.pnl.to_numpy()); dd = (np.maximum.accumulate(np.r_[0, eq])[1:] - eq).max()
    print(f"{label:38s} n={len(tr):4d} PF={pf(tr.pnl):5.2f} IS={pf(i.pnl):5.2f}({len(i)}) OOS={pf(o.pnl):5.2f}({len(o)}) net={tr.pnl.sum():7.2f} win={(tr.pnl>0).mean()*100:3.0f}% worst={tr.pnl.min():6.2f} dd={dd:5.2f} act={act:3.0f}%")
