"""H1: London-open breakout of the Asian range (retest of ALPHA on 2y of H1 bars)."""
from lib import *
import itertools

def lob(sid, r0=0, r1=8, e1=11, xh=16, slm=0.75, tpm=2.0, slmin=5, slmax=14, tz="Europe/London", buf=0.0):
    b = bars(sid); pip = PIP[sid]
    lt = b.time.dt.tz_localize("UTC").dt.tz_convert(tz)
    h = lt.dt.hour.to_numpy(); day = lt.dt.date.to_numpy()
    hi_, lo_, c = b.high.to_numpy(), b.low.to_numpy(), b.close.to_numpy()
    rows = []
    for dkey, ix in pd.Series(np.arange(len(b))).groupby(day).indices.items():
        hh = h[ix]
        rm = (hh >= r0) & (hh < r1)
        if rm.sum() < (r1 - r0) * 0.7: continue
        hi, lo = hi_[ix][rm].max(), lo_[ix][rm].min()
        sl = float(np.clip(slm * (hi - lo) / pip, slmin, slmax))
        for j in np.where((hh >= r1) & (hh < e1))[0]:
            k = ix[j]
            side = 1 if c[k] > hi + buf*pip else (-1 if c[k] < lo - buf*pip else 0)
            if side == 0: continue
            mb = xh - hh[j] - 1
            if mb >= 1: rows.append((k, side, 0, sl * pip, tpm * sl * pip, mb))
            break
    return pd.DataFrame(rows, columns=["idx", "side", "kind", "sl", "tp", "max_bars"]).assign(volume=1000.0)

if __name__ == "__main__":
    for sid in [1, 2, 3, 4, 5, 6, 8, 9]:
        sp = split_time(sid)
        print(summ(sim(sid, lob(sid)), sp, f"{NAMES[sid]} ALPHA-default"))
