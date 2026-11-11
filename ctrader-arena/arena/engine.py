"""Official arena backtest engine (bar based, deliberately pessimistic).

Bars are BID prices. ask = bid + spread. Longs buy at ask / sell at bid, shorts sell at bid / buy at ask.

Orders (one row each, numpy arrays of equal length, sorted by `idx`):
  idx        bar index at whose CLOSE the decision is made. The order becomes live at bar idx+1.
  side       +1 long, -1 short
  kind       0 = market (fills at open of idx+1), 1 = limit, 2 = stop (pending, live for `valid` bars)
  price      limit/stop trigger price in BID terms for shorts and ASK terms for longs (ignored for market)
  sl, tp     stop-loss / take-profit DISTANCE from fill price, in price units (>0). tp=0 -> no TP
  max_bars   time exit: close at the close of the max_bars-th bar after the fill bar (0 -> none)
  trail      trailing stop distance (0 = off); stop ratchets on bar closes, effective next bar
  valid      bars a pending order stays live (kind 1/2)
  volume     position size in UNITS of the base asset (cTrader volume / 100)

Pessimism rules
  * SL and TP inside the same bar -> SL.
  * On the fill bar of a pending order only the SL is checked (TP cannot be assumed to come after the fill).
  * Stops slip by `slip`; if a bar OPENS beyond the stop, fill at the open.
  * gap_sl=True (spike instruments: Boom/Crash/Jump...): a stopped trade fills at the bar EXTREME, not at the stop,
    and a stop ENTRY order also fills at the bar extreme (it cannot fill in the middle of a one-tick jump).
  * max_open concurrent positions (default 1); signals arriving while full are dropped.
"""
import numpy as np
from numba import njit


@njit(cache=True)
def _run(o, h, l, c, idx, side, kind, price, sl, tp, max_bars, trail, valid, volume,
         spread, slip, gap_sl, max_open):
    n = len(o)
    m = len(idx)
    out = np.zeros((m, 8))  # entry_bar, exit_bar, side, entry_px, exit_px, pnl(price*units), reason, order_row
    k = 0
    # open position slots
    p_side = np.zeros(max_open); p_entry = np.zeros(max_open); p_sl = np.zeros(max_open)
    p_tp = np.zeros(max_open); p_end = np.zeros(max_open, np.int64); p_tr = np.zeros(max_open)
    p_vol = np.zeros(max_open); p_bar = np.zeros(max_open, np.int64); p_row = np.zeros(max_open, np.int64)
    p_on = np.zeros(max_open, np.bool_)
    # pending slots (bounded by max_open too)
    q_on = np.zeros(max_open, np.bool_); q_row = np.zeros(max_open, np.int64); q_exp = np.zeros(max_open, np.int64)
    j = 0
    for i in range(1, n):
        # 1) new orders decided at close of bar i-1
        while j < m and idx[j] < i - 1:
            j += 1
        while j < m and idx[j] == i - 1:
            busy = 0
            for s in range(max_open):
                if p_on[s]: busy += 1
                if q_on[s]: busy += 1
            if busy < max_open:
                for s in range(max_open):
                    if not q_on[s]:
                        q_on[s] = True; q_row[s] = j
                        q_exp[s] = i if kind[j] == 0 else i + max(1, valid[j]) - 1
                        break
            j += 1
        ob = o[i]; hb = h[i]; lb = l[i]; cb = c[i]
        # 2) manage open positions on this bar
        for s in range(max_open):
            if not p_on[s]:
                continue
            done = False; px = 0.0; reason = 0.0
            if p_side[s] > 0:  # long exits on bid
                if lb <= p_sl[s]:
                    px = lb if gap_sl else (min(ob, p_sl[s]) - slip); reason = 1; done = True
                elif p_tp[s] > 0 and hb >= p_tp[s]:
                    px = p_tp[s]; reason = 2; done = True
            else:  # short exits on ask
                if hb + spread >= p_sl[s]:
                    px = (hb + spread) if gap_sl else (max(ob + spread, p_sl[s]) + slip); reason = 1; done = True
                elif p_tp[s] > 0 and lb + spread <= p_tp[s]:
                    px = p_tp[s]; reason = 2; done = True
            if not done and p_end[s] > 0 and i >= p_end[s]:
                px = cb if p_side[s] > 0 else cb + spread; reason = 3; done = True
            if done:
                out[k, 0] = p_bar[s]; out[k, 1] = i; out[k, 2] = p_side[s]; out[k, 3] = p_entry[s]
                out[k, 4] = px; out[k, 5] = (px - p_entry[s]) * p_side[s] * p_vol[s]; out[k, 6] = reason
                out[k, 7] = p_row[s]; k += 1; p_on[s] = False
            elif p_tr[s] > 0:
                if p_side[s] > 0:
                    p_sl[s] = max(p_sl[s], cb - p_tr[s])
                else:
                    p_sl[s] = min(p_sl[s], cb + spread + p_tr[s])
        # 3) pending / market fills on this bar
        for s in range(max_open):
            if not q_on[s]:
                continue
            r = q_row[s]; filled = False; fpx = 0.0; pend = kind[r] != 0
            if kind[r] == 0:
                fpx = ob + spread + slip if side[r] > 0 else ob - slip; filled = True
            elif kind[r] == 1:  # limit
                if side[r] > 0 and lb + spread <= price[r]:
                    fpx = min(price[r], ob + spread); filled = True
                elif side[r] < 0 and hb >= price[r]:
                    fpx = max(price[r], ob); filled = True
            else:  # stop
                # on gap_sl (single-tick jump) instruments a stop entry fills AFTER the jump: bar extreme
                if side[r] > 0 and hb + spread >= price[r]:
                    fpx = (hb + spread) if gap_sl else max(price[r], ob + spread) + slip; filled = True
                elif side[r] < 0 and lb <= price[r]:
                    fpx = lb if gap_sl else min(price[r], ob) - slip; filled = True
            if filled:
                q_on[s] = False
                slot = -1
                for t in range(max_open):
                    if not p_on[t]:
                        slot = t; break
                if slot < 0:
                    continue
                p_on[slot] = True; p_side[slot] = side[r]; p_entry[slot] = fpx; p_vol[slot] = volume[r]
                p_sl[slot] = fpx - side[r] * sl[r]
                p_tp[slot] = fpx + side[r] * tp[r] if tp[r] > 0 else 0.0
                p_end[slot] = i + max_bars[r] if max_bars[r] > 0 else 0
                p_tr[slot] = trail[r]; p_bar[slot] = i; p_row[slot] = r
                # same-bar adverse check (pessimistic): SL only for pending, SL then TP for market
                hit = False; px = 0.0; reason = 0.0
                if side[r] > 0:
                    if lb <= p_sl[slot]:
                        px = lb if gap_sl else p_sl[slot] - slip; reason = 1; hit = True
                    elif (not pend) and tp[r] > 0 and hb >= p_tp[slot]:
                        px = p_tp[slot]; reason = 2; hit = True
                else:
                    if hb + spread >= p_sl[slot]:
                        px = (hb + spread) if gap_sl else p_sl[slot] + slip; reason = 1; hit = True
                    elif (not pend) and tp[r] > 0 and lb + spread <= p_tp[slot]:
                        px = p_tp[slot]; reason = 2; hit = True
                if hit:
                    out[k, 0] = i; out[k, 1] = i; out[k, 2] = side[r]; out[k, 3] = fpx; out[k, 4] = px
                    out[k, 5] = (px - fpx) * side[r] * volume[r]; out[k, 6] = reason; out[k, 7] = r
                    k += 1; p_on[slot] = False
            elif i >= q_exp[s]:
                q_on[s] = False
    # force-close leftovers at last close
    for s in range(max_open):
        if p_on[s]:
            px = c[n - 1] if p_side[s] > 0 else c[n - 1] + spread
            out[k, 0] = p_bar[s]; out[k, 1] = n - 1; out[k, 2] = p_side[s]; out[k, 3] = p_entry[s]
            out[k, 4] = px; out[k, 5] = (px - p_entry[s]) * p_side[s] * p_vol[s]; out[k, 6] = 4
            out[k, 7] = p_row[s]; k += 1
    return out[:k]


def simulate(bars, orders, spread, slip=0.0, gap_sl=False, max_open=1, usd_per_quote=1.0):
    """bars: DataFrame from ingest.load(). orders: DataFrame with the columns documented above
    (missing optional columns default: kind=0, price=0, tp=0, max_bars=0, trail=0, valid=1).
    Returns a trades DataFrame with pnl in USD."""
    import pandas as pd
    od = orders.sort_values("idx", kind="stable").reset_index(drop=True)
    g = lambda col, d, t=np.float64: (od[col].to_numpy(t) if col in od else np.full(len(od), d, t))
    res = _run(bars.open.to_numpy(np.float64), bars.high.to_numpy(np.float64), bars.low.to_numpy(np.float64),
               bars.close.to_numpy(np.float64), g("idx", 0, np.int64), g("side", 1), g("kind", 0, np.int64),
               g("price", 0.0), g("sl", 0.0), g("tp", 0.0), g("max_bars", 0, np.int64), g("trail", 0.0),
               g("valid", 1, np.int64), g("volume", 1.0), float(spread), float(slip), bool(gap_sl), int(max_open))
    tr = pd.DataFrame(res, columns=["entry_bar", "exit_bar", "side", "entry_px", "exit_px", "pnl", "reason", "order_row"])
    tr["pnl"] *= usd_per_quote
    tr["entry_time"] = bars.time.to_numpy()[tr.entry_bar.astype(int)]
    tr["exit_time"] = bars.time.to_numpy()[tr.exit_bar.astype(int)]
    tr["reason"] = tr.reason.map({1: "SL", 2: "TP", 3: "TIME", 4: "EOD"})
    return tr.sort_values("exit_time").reset_index(drop=True)


def resample(m1, minutes):
    """Aggregate M1 bars to `minutes` bars. Adds `m1_idx` = index of the LAST M1 bar inside each bar,
    i.e. the M1 bar at whose close the higher-TF bar is complete -> use it as order `idx`.
    Incomplete trailing bar is dropped."""
    import pandas as pd
    g = (m1.ts // (minutes * 60_000))
    agg = m1.groupby(g).agg(ts=("ts", "first"), time=("time", "first"), open=("open", "first"), high=("high", "max"),
                            low=("low", "min"), close=("close", "last"), volume=("volume", "sum"),
                            m1_idx=("ts", lambda s: s.index[-1]))
    return agg.iloc[:-1].reset_index(drop=True)
