import json, numpy as np, pandas as pd
R = 'agents/VOLA/research/'
cost = pd.read_csv(R + 'screen_cost.csv')
st = {k: pd.read_csv(R + f'stats_{k}.csv').set_index('id') for k in ('disc', 'h1', 'deep')}
tests = pd.concat([pd.read_csv(R + f'stats_{k}_tests.csv').assign(sample=k) for k in ('disc', 'h1', 'deep')])
screen = []
for _, r in cost.iterrows():
    s = int(r.id); ks = r.key_stats
    if pd.isna(r.m5_range):
        verdict = 'untestable: no pre-holdout history (launched after 2026-09-15 or only post-holdout bars)'
    else:
        parts = []
        for k, d in st.items():
            if s in d.index:
                x = d.loc[s]; parts.append(f"{k}: drift_t {x.drift_t:+.2f} AC1 {x.ac1:+.3f} VR6 {x.vr6:.2f}")
        ks = ks + ' | ' + ' ; '.join(parts)
        bh = tests[(tests.id == s) & (tests.bh < 0.10)]
        verdict = 'fair game: no BH-significant structure' if bh.empty else 'BH-significant: ' + ', '.join(f"{t}({sm})" for t, sm in zip(bh.test, bh['sample'])) + ' (vol-clustering only; no directional edge)'
        if r.cost_ratio >= 0.25: verdict += '; cost/M5-range >= 0.25 -> too expensive at M5'
    screen.append(dict(symbol=r.symbol, id=s, spread=r.spread, m5_range=None if pd.isna(r.m5_range) else r.m5_range,
                       cost_ratio=None if pd.isna(r.cost_ratio) else r.cost_ratio, key_stats=ks, verdict=verdict))
tr = pd.read_csv('submissions/VOLA/trades.csv')
w = tr.sort_values('pnl', ascending=False).head(3); l = tr.sort_values('pnl').head(2)
ex = []
for _, t in pd.concat([w, l]).iterrows():
    ex.append(dict(time=str(t.entry_time), side='BUY' if t.side > 0 else 'SELL', entry=round(t.entry_px, 2), sl='2 x ATR24 (trailing)', tp='none',
                   exit=round(t.exit_px, 2), pnl=round(t.pnl, 2), why=f"Donchian-24 close breakout, exit {t.reason}" +
                   (' - range-break jump against the position filled at bar extreme' if t.pnl < -2 else '')))
wf = json.load(open(R + 'wf_c1.json'))
trials = pd.read_csv(R + 'trials.csv')
m = json.load(open('submissions/VOLA/metrics.json'))
rep = {
 "strategy_name": "VOLA C1 - Range Break 200 breakout-follow (NOT an edge)",
 "one_line": "No validated edge in the spike/jump synthetics; the best in-sample plateau (RB200 M5 breakout-follow) failed two pre-declared out-of-sample confirmations and the official evaluate2 (PF 0.92).",
 "instrument(s)": ["Range Break 200 Index (2450)"], "timeframe": "M5",
 "logic": {"entry": "close of M5 bar above the highest high (below the lowest low) of the previous 24 bars -> buy (sell) at next open; signal bar must close <= 16:59 UTC",
           "exit": "trailing stop on bar closes or time exit after 48 bars (4 h); always flat before the 21:00 UTC rollover",
           "stop": "2 x ATR(24) hard stop, trailing by the same distance (gap fills at bar extreme in the engine)",
           "take_profit": "none", "sizing": "broker minimum 0.01 units", "risk": "one position; cBot: spread gate, daily loss 10%, equity kill-switch 25%, 6-loss pause"},
 "parameters": [{"name": "N", "default": 24, "range": "6-48", "meaning": "Donchian lookback (bars)"},
                {"name": "K", "default": 2.0, "range": "1-3", "meaning": "stop & trail distance in ATR(24)"},
                {"name": "H", "default": 48, "range": "12-48", "meaning": "time exit (bars)"},
                {"name": "last_entry_hour", "default": 16, "range": "fixed", "meaning": "no entries after 16:59 UTC (no rollover crossing)"}],
 "rejected_alternatives": [
   {"name": "F1 spike-hazard drift harvest (Crash150/Boom150/VolCrash550/DEX600UP/TrekUp)", "result": "300 sets; median PF IS 0.82/0.00-1.06, no set with IS and OOS t>2", "why_rejected": "hazard memoryless (T7 p>0.1 everywhere); drift side pays spread + gap-filled spikes"},
   {"name": "F2 post-spike fade/follow (7 symbols)", "result": "336 sets; median PF IS 0.17-0.87, OOS 0.00-0.89", "why_rejected": "no post-jump drift (T6 never BH-significant)"},
   {"name": "F3 Donchian breakout/fade (Jump75, TrekUp, RB200, Crash150)", "result": "192 sets; only RB200-follow plateau PF>1 (IS 1.2-1.7)", "why_rejected": "RB200 plateau failed unseen Jul-Aug (PF 0.66, t -2.0) and Jun-Jul (C1 0.79 / WF-selected R2 0.89); break directions independent (P(same)=0.54, p=0.28)"},
   {"name": "F4 Range Break boundary fade/follow at M5", "result": "48 sets; IS PF>1 6%, OOS 0%", "why_rejected": "fair reflection at boundaries (confirms CHARLIE at M1)"},
   {"name": "F6 time-series momentum/reversal (7 symbols)", "result": "126 sets; median PF 0.86-0.99 IS, 0.83-0.95 OOS", "why_rejected": "VR(6) 0.97-1.01 on 8-16k bars; no autocorrelation"},
   {"name": "F8 Volatility Crash 550 short (drift lead t=-2.2/-2.3 in screen)", "result": "independent Feb-Aug H1: PF 1.19/1.53, t 1.3/1.7", "why_rejected": "not significant; consistent with negative median path of a multiplicative martingale (zero mean); 1 of 36 symbols"},
   {"name": "Boom 150 negative drift (t -2.15/-2.54 in screen)", "result": "10 months earlier H1: t -0.43", "why_rejected": "did not replicate"},
   {"name": "time-of-day / spread schedule", "result": "T4/T5 hour tests: 0 BH-significant of 140; spreads identical across 3 sampling times", "why_rejected": "no schedule"}],
 "walk_forward": wf["walk_forward"], "neighbour_table": wf["neighbour_table"], "trade_examples": ex,
 "failure_conditions": ["It is a fair game: expectancy is about -1 spread per trade plus gap-filled stops", "range-break jumps of 200-530 points against the position (worst trade -$5.30 at 0.01 units)", "any period: fold PFs 0.48-1.32 flip sign randomly"],
 "timeframe_comparison": [{"timeframe": "M5", "pf": m["full"]["pf"], "trades": m["full"]["trades"], "note": "official evaluate2"},
                          {"timeframe": "H1 (stats only)", "pf": None, "trades": None, "note": "H1 drift/VR/hour tests on 36 symbols x 30 days: 11 raw p<0.05 of 218 (11 expected), 0 BH"}],
 "params_tried": int(len(trials)), "distinct_param_sets_approx": 1050,
 "statistical_tests": {"count": int(len(tests)) + 4, "raw_p_lt_0.05": int((tests.p < 0.05).sum()), "BH_q_lt_0.10": int((tests.bh < 0.10).sum()),
                       "note": "BH-significant only: vol clustering (|r| AC1) on RB200 and Jump 75 - no directional content"},
 "official": {k: m[k] for k in ("full", "is", "oos", "stress", "folds", "mc", "balance", "gates", "qualified", "score")},
 "screen": screen}
json.dump(rep, open('agents/VOLA/report_data.json', 'w'), indent=1, default=str)
print('screen rows', len(screen), 'tests', len(tests), 'trials', len(trials), 'BH', int((tests.bh < 0.10).sum()))
