"""Overnight-gap fade on an index CFD, H_1 bars. Shared by lab tests and strategy.py."""
import numpy as np, pandas as pd

# NYSE full holidays + early-close days (published calendar, known in advance): no trade on these dates.
NYSE_OFF = pd.to_datetime([
    '2024-01-01','2024-01-15','2024-02-19','2024-03-29','2024-05-27','2024-06-19','2024-07-03','2024-07-04','2024-09-02',
    '2024-11-28','2024-11-29','2024-12-24','2024-12-25',
    '2025-01-01','2025-01-09','2025-01-20','2025-02-17','2025-04-18','2025-05-26','2025-06-19','2025-07-03','2025-07-04',
    '2025-09-01','2025-11-27','2025-11-28','2025-12-24','2025-12-25',
    '2026-01-01','2026-01-19','2026-02-16','2026-04-03','2026-05-25','2026-06-19','2026-07-03','2026-09-07','2026-11-26',
    '2026-11-27','2026-12-24','2026-12-25',
    '2027-01-01','2027-01-18','2027-02-15','2027-03-26','2027-05-31','2027-06-18','2027-07-05','2027-09-06','2027-11-25',
    '2027-11-26','2027-12-24']).to_numpy()

def signals_gapfade(b, p, units):
    """At 09:00 New York (close of the 08:00 NY H1 bar): on = log(price / yesterday's 16:00 NY price);
    z = on / (20-day std of 16:00->16:00 returns, up to yesterday). If |z| > thr -> market order AGAINST the overnight
    move, filled at the open of the 09:00 bar, closed at 16:00 NY (max_bars), hard SL = min(m*vol*price, cap)."""
    ny = b.time.dt.tz_localize('UTC').dt.tz_convert('America/New_York')
    h = ny.dt.hour.to_numpy(); day = ny.dt.tz_localize(None).dt.floor('D').to_numpy()
    c = b.close.to_numpy()
    is16 = h == 15                                   # bar 15:00-16:00 NY: its close = cash close
    # last cash close strictly before each bar (as of the bar's own close for 15:00 bars -> shift)
    cc = pd.Series(np.where(is16, c, np.nan)); cday = pd.Series(np.where(is16, day, np.datetime64('NaT')))
    prev_close = cc.ffill().to_numpy(); prev_day = cday.ffill().to_numpy()
    closes = pd.Series(c[is16]); ret = np.log(closes).diff()
    vol_at = ret.rolling(p.get('W', 20)).std()       # known at that day's 16:00 close
    vol = pd.Series(np.nan, index=range(len(c))); vol[np.flatnonzero(is16)] = vol_at.to_numpy(); vol = vol.ffill().to_numpy()
    sig = (h == p.get('hour', 8)) & (prev_day < day) & ~np.isnan(vol)
    wd = pd.DatetimeIndex(day).dayofweek.to_numpy()
    sig &= wd < 5
    sig &= ~np.isin(day, NYSE_OFF)
    on = np.log(c / prev_close)
    z = on / vol
    lo, hi = p.get('thr', 0.5), p.get('zmax', 99)
    sig &= (np.abs(z) > lo) & (np.abs(z) < hi)
    # stale reference guard: previous cash close must be at most 4 calendar days old (weekend/holiday)
    age = (pd.DatetimeIndex(day) - pd.DatetimeIndex(prev_day)).days.to_numpy()
    sig &= age <= 4
    i = np.flatnonzero(sig)
    side = -np.sign(on[i])
    if p.get('dir', 0): 
        keep = side == p['dir']; i = i[keep]; side = side[keep]
    cap = p.get('risk', 1.5) / units
    sl = np.minimum(p.get('m', 1.0) * vol[i] * c[i], cap)
    tp = p.get('fill', 0.0) * np.abs(on[i]) * c[i]          # target = this fraction of the overnight move (0 = none)
    return pd.DataFrame({'idx': i, 'side': side, 'kind': 0, 'price': 0.0, 'sl': sl, 'tp': tp,
                         'max_bars': p.get('hold', 6), 'trail': 0.0, 'valid': 1, 'volume': units, 'prove': 0})
