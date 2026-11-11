"""Round 2: frozen rule on M5 history (pre-sample = before 2026-09-21). Entry at next M5 open, SL/TP/time exit in the engine."""
from lib import *
P0 = dict(r0=0.0, r1=8.0, e1=11.0, xh=16.0, slm=0.75, tpm=2.0, slmin=5.0, slcap_usd=1.40)
PRE_END = pd.Timestamp("2026-09-21")
def sig_m5(b, p, pip, pipval):
    lt = b.time.dt.tz_localize("UTC").dt.tz_convert("Europe/London")
    h = (lt.dt.hour + lt.dt.minute / 60.0).to_numpy(); day = lt.dt.strftime("%Y-%m-%d").to_numpy()
    hi_, lo_, c = b.high.to_numpy(), b.low.to_numpy(), b.close.to_numpy()
    need = (p["r1"] - p["r0"]) * 12 * 0.7; cap = p["slcap_usd"] / pipval; rows = []
    for _, ix in pd.Series(np.arange(len(b))).groupby(day, sort=True).indices.items():
        hh = h[ix]; rm = (hh >= p["r0"]) & (hh < p["r1"])
        if rm.sum() < need: continue
        hi, lo = hi_[ix][rm].max(), lo_[ix][rm].min()
        sl = float(np.clip(p["slm"] * (hi - lo) / pip, min(p["slmin"], cap), cap))
        for j in np.where((hh >= p["r1"]) & (hh < p["e1"]))[0]:
            k = ix[j]; side = 1 if c[k] > hi else (-1 if c[k] < lo else 0)
            if side == 0: continue
            mb = int(round((p["xh"] - hh[j]) * 12)) - 2
            if mb >= 1: rows.append((k, side, 0, sl * pip, p["tpm"] * sl * pip, mb))
            break
    return pd.DataFrame(rows, columns=["idx", "side", "kind", "sl", "tp", "max_bars"])
def run_m5(sid, p=P0, lo=None, hi=PRE_END, mult=1.0):
    b = load(sid, "M_5")
    if lo is not None: b = b[b.time >= lo]
    if hi is not None: b = b[b.time < hi]
    b = b.reset_index(drop=True)
    pip = PIP[sid]; pipval = pip * 1000 * UPQ[sid]
    tr = run(sid, b, sig_m5(b, p, pip, pipval), mult=mult); tr["sid"] = sid
    return tr
def line(lbl, tr):
    if len(tr) == 0: return f"{lbl:26s} n=0"
    eq = tr.sort_values("exit_time").pnl.cumsum(); dd = (eq.cummax().clip(lower=0) - eq).max()
    return f"{lbl:26s} n={len(tr):4d} PF={pf(tr.pnl):5.2f} net={tr.pnl.sum():7.2f} win={100*(tr.pnl>0).mean():3.0f}% maxDD={dd:5.2f} worst={tr.pnl.min():5.2f}"
if __name__ == "__main__":
    sids = [int(x) for x in sys.argv[1:]] or [1]
    allt = []
    for sid in sids:
        b = load(sid, "M_5"); print(sid, "M5 bars", len(b), b.time.iloc[0], "->", b.time.iloc[-1])
        tr = run_m5(sid); allt.append(tr); print(line(f"PRE {sid}", tr)); print(line("  long", tr[tr.side > 0])); print(line("  short", tr[tr.side < 0]))
        fw = run_m5(sid, lo=PRE_END, hi=None); print(line(f"FWD(M5 engine) {sid}", fw))
    t = pd.concat(allt).sort_values("exit_time"); print(line("PRE portfolio", t))
    for m, g in t.groupby(pd.to_datetime(t.entry_time).dt.to_period("M")): print(line(f"  {m}", g))
