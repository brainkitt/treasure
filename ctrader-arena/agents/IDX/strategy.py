"""IDX - "IndexDipBuy": buy US SP 500 / US Small Cap 2000 CFDs after a short-term washout, exit next session.

Hypothesis (written before fitting, see NOTES.md): US equity indices show short-horizon (1-5 day) return
reversal - liquidity providers are paid to absorb forced/impatient selling - on top of a positive drift.
A close that is the lowest close of the last N sessions marks such selling pressure; the next ~1 session
earns a premium relative to an unconditional long (tested: random-day longs PF ~0.75-1.1 vs dip longs PF 1.3-2).

Rules (H1 bars, decisions on CLOSED bars only, same parameters for every index):
  * "Session close" = close of the H1 bar that opens 14:00 New York (i.e. price at 15:00 NY, one hour before the
    cash close, when spreads are normal). Sessions/days are built from the leg's own H1 bars (no other data).
  * Signal: that close <= the lowest of the last N=7 session closes (incl. today).  LONG only.
  * Entry: market at the open of the next H1 bar (15:00 NY).
  * SL = 3.0 x ATR14(session bars), TP = 0.75 x ATR14, time exit at the close of the 22nd H1 bar after the fill
    bar (= next session's 15:00 NY close). One position per index (max_open 1). Volume = broker minimum 0.1.
  * Holds one rollover (Friday entries hold over the weekend: 3x swap) -> swap modelled with a conservative bound.
"""
import numpy as np, pandas as pd

PARAMS = {"N": 7, "tp_atr": 0.75, "sl_atr": 3.0, "hold_sessions": 1, "atr_n": 14, "signal_hour_ny": 14}
# $700 = smallest balance that passes every gate at the 0.1-unit broker minimum (binding gate: worst trade
# -$33.8 on SP 500, 2025-04-03 tariff crash, must be <= 5% of balance). See NOTES.md "Balance".
START_BALANCE = 700.0
# US Mid Cap 400 was part of the design but dropped on IN-SAMPLE evidence only (IS PF 1.15 < 1.2; spread 1.22 pts
# = 3.4 bp, 4x the SP/RUT cost). US Tech 100 / Wall Street 30 replicate the effect (NAS PF 1.64 with frozen
# parameters) but 0.1 unit = $35-60 per daily ATR: untradable at this balance.
LEGS = [{"symbol_id": 2517, "period": "H_1", "params": dict(PARAMS), "max_open": 1},
        {"symbol_id": 2521, "period": "H_1", "params": dict(PARAMS), "max_open": 1}]
_COLS = ["idx", "side", "kind", "price", "sl", "tp", "max_bars", "trail", "valid", "volume"]


def _ny(t):
    """UTC -> New York local time (US DST rule since 2007), vectorised, no tz database needed."""
    t = pd.DatetimeIndex(t)
    y = t.year
    mar1 = pd.to_datetime(pd.DataFrame({"year": y, "month": 3, "day": 1}))
    nov1 = pd.to_datetime(pd.DataFrame({"year": y, "month": 11, "day": 1}))
    start = mar1 + pd.to_timedelta((6 - mar1.dt.weekday) % 7 + 7, unit="D") + pd.Timedelta(hours=7)   # 2nd Sun Mar 02:00 EST = 07:00 UTC
    end = nov1 + pd.to_timedelta((6 - nov1.dt.weekday) % 7, unit="D") + pd.Timedelta(hours=6)          # 1st Sun Nov 02:00 EDT = 06:00 UTC
    dst = (t >= start.values) & (t < end.values)
    return t - pd.to_timedelta(np.where(dst, 4, 5), unit="h")


def sessions(bars, signal_hour_ny=14):
    """One row per trading session, ending with the H1 bar that opens at `signal_hour_ny` NY."""
    ny = _ny(bars.time)
    h = ny.hour.to_numpy()
    sd = (ny + pd.Timedelta(hours=24 - (signal_hour_ny + 1))).floor("D")
    df = pd.DataFrame({"sd": sd, "high": bars.high.to_numpy(), "low": bars.low.to_numpy(),
                       "close": bars.close.to_numpy(), "h": h, "i": np.arange(len(bars))})
    g = df.groupby("sd", sort=True)
    D = pd.DataFrame({"high": g.high.max(), "low": g.low.min(), "close": g.close.last(),
                      "last_idx": g.i.last(), "last_h": g.h.last(), "n": g.size()})
    return D[(D.n >= 10) & (D.last_h == signal_hour_ny)]


def signals(bars, p, spec):
    D = sessions(bars, p["signal_hour_ny"])
    if len(D) < p["N"] + p["atr_n"] + 2:
        return pd.DataFrame({c: [] for c in _COLS})
    c = D.close
    pc = c.shift(1)
    tr = np.maximum(D.high - D.low, np.maximum((D.high - pc).abs(), (D.low - pc).abs()))
    a = tr.rolling(p["atr_n"]).mean()
    sig = (c <= c.rolling(p["N"]).min()) & a.notna()
    n = int(sig.sum())
    return pd.DataFrame({
        "idx": D.last_idx[sig].to_numpy().astype(np.int64), "side": np.ones(n, int), "kind": 0, "price": 0.0,
        "sl": (p["sl_atr"] * a[sig]).to_numpy(), "tp": (p["tp_atr"] * a[sig]).to_numpy(),
        "max_bars": int(23 * p["hold_sessions"] - 1), "trail": 0.0, "valid": 1,
        "volume": float(spec["min_units"]),
    })[_COLS]
