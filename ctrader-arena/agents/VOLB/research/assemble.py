import json, numpy as np, pandas as pd
wf = json.load(open('wf.json')); screen = json.load(open('screen_rows.json'))
m = json.load(open('/home/user/treasure/ctrader-arena/submissions/VOLB/metrics.json'))
d = pd.read_csv('dsi_spreads.csv'); d['sp'] = (d.ask - d.bid) / 1e5; d['bid'] /= 1e5
dsi = []
for sid, g in d.groupby('sid'):
    g = g.sort_values('ts_ms').reset_index(drop=True); mv = g.bid.diff(2).abs()
    dsi.append(dict(symbol_id=int(sid), samples=len(g), spread_min=round(g.sp.min(), 2), spread_max=round(g.sp.max(), 2),
                    corr_spread_vs_abs_move_prev_2_samples=round(float(np.corrcoef(g.sp.iloc[2:], mv.iloc[2:])[0, 1]), 2) if len(g) > 3 else None, series=[f'{(a-g.ts_ms[0])/1000:.0f}s bid {b:.2f} spread {c:.2f}' for a,b,c in zip(g.ts_ms,g.bid,g.sp)]))
t = pd.read_csv('/home/user/treasure/ctrader-arena/submissions/VOLB/trades.csv')
ex = []
for _, r in pd.concat([t.sort_values('pnl').tail(3), t.sort_values('pnl').head(2)]).iterrows():
    sl = None
    ex.append(dict(time=r.entry_time, side='BUY', entry=round(r.entry_px, 2), sl='2.5 x ATR20 below entry', tp=None,
                   exit=round(r.exit_px, 2), pnl=round(r.pnl, 2),
                   why=('ER(6) > 0.8 on the closed M5 bar; drift regime persisted, ' + ('time exit after 24 bars' if r.reason == 'TIME' else 'stopped')
                        if r.pnl > 0 else 'ER(6) > 0.8 but the regime flipped / spread 10.16 paid at entry -> ' + r.reason)))
rep = {
 "strategy_name": "VOLB DSI30 long-only regime follower with entry-spread cap (NOT QUALIFIED)",
 "one_line": "Screen of 49 continuous Deriv synthetics found only Drift Switch regime momentum; its DSI30 long-only edge (+4.9 pts/trade gross) is consumed by a drift-linked dynamic spread (PF 0.41 at the widest observed 10.16).",
 "instrument(s)": ["Drift Switch Index 30 (2470)"], "timeframe": "M5",
 "logic": {"entry": "long when efficiency ratio of last 6 closed M5 bars > 0.8 and live spread <= cap (cBot); no entries on bars stamped 18:50-21:05 UTC",
           "exit": "trailing stop 1.5 x ATR20 (ratchets on bar closes) or time exit after 24 bars (2 h)",
           "stop": "hard SL 2.5 x ATR20 attached to every order", "take_profit": "none",
           "sizing": "broker minimum 0.10 units (optional risk-% capped in the cBot)",
           "risk": "one position, daily loss limit, equity kill-switch 25 %, pause after 8 consecutive losses, spread cap 4.0"},
 "parameters": [
  {"name": "N", "default": 6, "range": "4-12", "meaning": "ER lookback (bars)"},
  {"name": "thr", "default": 0.8, "range": "0.6-0.9", "meaning": "ER entry threshold"},
  {"name": "atr_n", "default": 20, "range": "fixed", "meaning": "ATR window (mean bar range)"},
  {"name": "sl_atr", "default": 2.5, "range": "2-3", "meaning": "hard stop in ATR"},
  {"name": "trail_atr", "default": 1.5, "range": "1.5-2.5", "meaning": "trailing stop in ATR"},
  {"name": "max_bars", "default": 24, "range": "fixed", "meaning": "time exit (bars)"},
  {"name": "max_spread (cBot)", "default": 4.0, "range": "-", "meaning": "entry spread cap, not modelled in backtest"}],
 "rejected_alternatives": [
  {"name": "F1 quantised mean reversion (Step100, VolSwMed, HFV10, V75(1s))", "result": "288 sets, max IS t 1.69, IS-top5 OOS PF 0.72-1.31", "why_rejected": "fair random walks; no edge net of spread"},
  {"name": "F2 Donchian breakout + trail", "result": "Step100 last-24-day PF 1.15-1.27; prior 6 weeks median PF 1.04, max t 0.95; null RW sim PF 0.99", "why_rejected": "one trending month; out-of-time failure"},
  {"name": "F3 vol-regime breakout (VolSwitch focus)", "result": "VolSwMed 21% sets PF>1, none >1.2; Step/V75(1s) hits on 35-68 trades within null p90", "why_rejected": "noise"},
  {"name": "F4 time-series momentum", "result": "max IS t 2.41 over 40 sets/symbol, corr(IS,OOS)~0", "why_rejected": "consistent with null max"},
  {"name": "F5 time-of-day / spread schedule", "result": "304 ANOVA tests, 1 BH hit (artefact)", "why_rejected": "no schedule"},
  {"name": "F6 DSI low-vol regime filter", "result": "gross capture/trade not improved (DSI30 4.9 -> 4.3-4.8)", "why_rejected": "no added information"},
  {"name": "DSI10 / DSI20 long-only", "result": "break-even spread ~1.6 / ~2.8 vs observed 2.4-3.8 / up to 4.05", "why_rejected": "spread"}],
 "walk_forward": wf["wf"]["10.16"]["folds"], "walk_forward_info_at_spread_4": wf["wf"]["4.0"]["folds"],
 "neighbour_table": wf["neighbours"],
 "trade_examples": ex,
 "failure_conditions": ["entry spread > ~5 (DSI30 drift regimes show 4.6-10.16)", "regime flips shortly after entry (memoryless durations)",
                        "data gaps (signals suppressed)"],
 "timeframe_comparison": [{"timeframe": "M5", "pf": 0.41, "trades": 2479, "note": "official, spread 10.16"},
                          {"timeframe": "M15 / H1 (VOL round 2)", "pf": "<1 at 10.16 (0/648 H1 sets PF>1)", "trades": None, "note": "regimes are minutes long; longer bars average them out"}],
 "params_tried": 964,
 "tests_count": {"statistical_tests": 674, "symbols_screened": 49, "symbols_with_preholdout_data": 39, "multiple_testing": "Benjamini-Hochberg 5% over each block"},
 "dsi_live_spread_samples": dsi,
 "official": {"pf": m["full"]["pf"], "is_pf": m["is"]["pf"], "oos_pf": m["oos"]["pf"], "trades": m["full"]["trades"], "qualified": m["qualified"], "score": m["score"]},
 "screen": screen}
json.dump(rep, open('../report_data.json', 'w'), indent=1, default=str)
print('ok', dsi)
