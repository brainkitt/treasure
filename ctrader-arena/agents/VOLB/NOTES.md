# VOLB (AGENT_03, team B) - continuous Deriv synthetics, round 3 research log

**Bottom line: NOT QUALIFIED - no candidate for the sealed holdout.** I screened all 49 continuous synthetics in
scope (39 with pre-holdout history) with ~670 statistical tests and 964 strategy parameter sets over 4+1 mechanism
families. Every Volatility, HF-Volatility, Step, Multi Step and VolSwitch index behaves as a fair random walk
(nothing survives Benjamini-Hochberg; null-simulation and out-of-time controls agree), so no strategy on them can
earn more than the spread it pays. The only real structure is the documented Drift Switch regime momentum
(DSI10/20/30). Its gross edge is large (DSI30 long-only +4.9 pts/trade, t = 12 at a 0.55 spread), but the
DSI spread widens *while* the index drifts (measured live again this round), and at the widest observed DSI30
spread (10.16) every one of 96 parameter sets loses (median PF 0.38). The submitted file is that DSI30 finalist,
reported honestly at the conservative spread: **PF 0.41, score 0/100**. Do not trade it for money.

All research data is pre-2026-09-15 (loader-enforced holdout; I never touched ARENA_HOLDOUT_UNLOCK, data/.holdout
or raw files). The holdout has NOT been used.

## 1. Universe and costs (screen)
* 49 symbols: Volatility 5/10/15/25/30/50/75/90/100 (2 s) and 5/10/15/20/25/30/40/50/60/75/80/90/100/120/150/250 (1 s),
  HF Vol 10/25/50/75/100, Step 100/200/300/400/500/3000/4000/5000/6000/10000, Multi Step 2/3/4, VolSwitch L/M/H, DSI 10/20/30.
  10 symbols (V20/40/60/80/120 (1 s), Step 3000-10000) have **no bars before 2026-09-15** (listed later) -> untestable.
* Live spreads: 2 full rounds (16:22 and 16:32 UTC 2026-11-17) + 8 extra DSI10/20/30 samples over 3.5 min (~16:35-16:39 UTC) -> `research/spreads.csv`,
  `research/dsi_spreads.csv`. Volatility and Step spreads were identical in both rounds (fixed quotes; V90 49-69 and
  VolSwitch High 0.11-0.14 varied); DSI spreads are dynamic (DSI10 2.4-3.8, DSI20 0.23-1.65, DSI30 2.3-7.6 this round;
  VOL round 1 saw DSI30 up to 10.16, DSI20 4.05).
* Cost / median M5 range: Step 100-500 0.038-0.040 (spread = exactly 1 step), VolSwitch Med/High 0.026-0.029,
  HF Vol 0.049-0.059, Vol (1 s/2 s) 0.06-0.22, V250(1 s) 0.34, DSI 0.5-1.3. Deriv prices the Volatility family at a
  near-constant ~0.10-0.19 of one M5 standard deviation, i.e. the spread scales with volatility by design.
* Minimum volume probed this round: **Step Index 1.00 unit** (LIMIT BUY volume=1 at 3639 rejected: "minimum allowed
  volume = 1.00"; no order created, pending list confirmed empty). DSI 0.10 (VOL). Commission 0. Swap not exposed
  (owner history: synthetics only negative swaps, V75 -0.07/0.01 unit/night) -> no carry trade exists.

## 2. Statistics screen (counts and multiple-testing)
| test block | symbols x tests | result |
|---|---|---|
| M5 (1000-7000 bars/symbol, 2026-08..09-14; DSI 11-73k bars): drift t, AC1, VR12 (Lo-MacKinlay), AC of abs returns | 39 x 4 = 156 | BH(5%) significant: 12 = DSI10/20/30 (AC1 0.05-0.15, VR12 1.42-1.54, all q<0.001) + VolSwitch vol-clustering (3) |
| H1 (720 bars each 08-16..09-14; V75 7102, DSI30 15016, VolSwitch 3598) same 4 tests | 37 x 4 = 148 | BH significant: 5 = DSI30 (3) + V75/V250 abs-return AC (price-level artefact of arithmetic returns over a decaying/trending level) |
| Time-of-day / weekday ANOVA (drift and vol by UTC hour and weekday), M5 + H1 | 76 series x 4 = 304 | 1 BH hit (VolSwitch Low M5 hour-vol: regime clustering inside 3.5 days, not a schedule; vanishes on 3598 H1 bars) |
| M1 microstructure (AC1-5, VR5/VR30, zero-change share): Step100 3000 bars, Step500, MultiStep2, VolSwMed, HFV10, V10(1s) | 6 x 7 = 42 | all |AC| < 2.3 SE; Step100 zero-change share 0.107 vs 0.103 theoretical for 60 fair +/-0.1 ticks -> exact fair binary walk |
| VolSwitch regime tests (drift by vol regime, leverage corr, AC by regime, 12 h momentum), 3598 H1 bars each | 3 x 7 = 21 | no directional structure (max |t| 2.36 before correction) |
| DSI 3-state HMM (M5) | 3 | up-regimes low-vol / down-regimes high-vol (asymmetric), durations 5-38 min |
Total ~674 tests. Only DSI survives correction.

## 3. Hypotheses -> strategy families (written before fitting) and results
Fit = first 70 % of bars, OOS = last 30 % untouched; spread = widest live sample per symbol; `research/lab.py`.
| # | family / why it could work | symbols (M5) | sets | result | verdict |
|---|---|---|---|---|---|
| F1 | quantised mean reversion: fade z = (close-SMA_N)/ATR beyond k, TP at SMA (step quantisation vs 1-step spread) | Step100, VolSwMed, HFV10, V75(1s) | 288 | IS PF>1 in 24-69 % of sets, max IS t 1.69; IS-top5 -> OOS median PF 0.72-1.31 | fair game; reject |
| F2 | Donchian breakout + trailing stop (trend persistence) | same | 128 | Step100 looked good on the last 24 days (88 % sets PF>1, OOS 1.49) -> **out-of-time test on the prior 6 weeks: median PF 1.04, max t 0.95**; null RW simulation of the same rule: PF 0.99 | one lucky trending month; reject |
| F3 | volatility-regime breakout (ATR6/ATR72 > v), aimed at VolSwitch regime structure | same | 84 | VolSwMed 21 % sets PF>1, none >1.2; Step100/V75(1s) "100 % PF>1.2" came from 35-68 trades - null simulation p90 PF 1.43; out-of-time: 0-1 trades | noise; reject |
| F4 | time-series momentum (sign of L-bar return, hold H) | same | 160 + 40 OOT | max IS t 2.41 (expected max of ~40 null sets ~2.2), corr(IS,OOS) ~0 | reject |
| F5 | time-of-day / spread schedule | all | (304 tests) | no hour/weekday drift or vol effect; Volatility/Step spreads constant across samples | no schedule to exploit |
| F6 | DSI regime + low-vol filter (HMM asymmetry: up-regimes are calm) | DSI10/20/30 IS | 45 | the filter does not raise gross capture/trade (DSI30 4.9 -> 4.3-4.8) | reject |
| F7 | **DSI30 long-only + live entry-spread cap** (cost-side mechanism: long-only pays the spread once at entry; the cBot refuses entries above a cap) | DSI30 73.5k bars | 96 x 2 spreads (WF) | gross edge real, break-even spread ~5; at the official 10.16: 0/96 sets PF>1; live DSI30 spread rose 2.34 -> 4.63 -> 7.62 while the bid fell 9 pts in 3 min; DSI20 0.23 -> 2.14 as it started to fall; corr(spread, |2-sample move|) = 0.58 / 0.88 / 0.62 for DSI30/20/10 (dsi_spreads.csv, n=8 each) - the cap would block exactly the drift entries | finalist, NOT QUALIFIED |
| F8 | multi-symbol portfolio of independent RNGs | - | - | not run: no leg has positive expectancy; a sum of zero-edge legs minus spreads is negative | skipped |

## 4. Official evaluate2 (finalist, DSI30 M5, spread 10.16, START_BALANCE 60)
```
full   trades= 2479 PF=0.41 net=$-1374.86 t=-18.50 DD=$1376.63 worst=$-7.46      is PF 0.37   oos PF 0.51   stress PF 0.00
folds  PF 0.36 / 0.31 / 0.36 / 0.56 / 0.48 (all negative)       NOT QUALIFIED   score 0.0/100
```
(`research/evaluate2_official.txt`, `submissions/VOLB/{metrics.json,trades.csv}`.) START_BALANCE is 60 only so the
risk gates do not obscure the real failure (expectancy); at any balance the system loses.

Spread sensitivity (same code, `--fast --spread-mult`, `research/spread_sensitivity.txt`):
| spread | 0.55 (quiet DSI30) | 2.0 | 4.0 | 6.45 | 10.16 (widest) |
|---|---|---|---|---|---|
| PF full / IS / OOS | 2.16 / 2.09 / 2.31 | 1.69 / 1.62 / 1.86 | 1.21 / 1.15 / 1.36 | 0.84 / 0.79 / 0.95 | 0.41 / 0.37 / 0.51 |

## 5. Walk-forward (anchored, re-fit per fold on all earlier data, 96-set grid N x thr x SL x trail) - `research/wf.json`
| fold | OOS window | IS-best @10.16 -> OOS PF | IS-best @4.0 -> OOS PF (information only) |
|---|---|---|---|
| 2 | 02-22..04-14 | 0.49 | 1.16 |
| 3 | 04-14..06-04 | 0.56 | 1.54 |
| 4 | 06-04..07-25 | 0.68 | 1.95 |
| 5 | 07-25..09-14 | 0.58 | 1.44 |
At 10.16 all folds lose; even if a 4.0 spread were guaranteed, full-sample PF of the default is 1.21 (< 1.30 gate).

## 6. Neighbour robustness (sl 2.5 ATR, trail 1.5 ATR; PF at 10.16 / at 4.0)
N=4: 0.32-0.39 / 0.95-1.15; N=6: 0.35-0.45 / 1.05-1.33; N=8: 0.35-0.41 / 1.09-1.35; N=12: 0.30-0.34 / 1.12-1.47
(thr 0.6..0.9). Smooth plateau, negative everywhere at the conservative spread.

## 7. Parameter sets evaluated
lab 636 (16 symbol x family grids) + out-of-time 180 + DSI break-even 6 (x7 spreads) + DSI vol filter 45 +
walk-forward 96 (x2 spreads) + finalist 1 = **964 distinct sets** (~1,300 backtests) plus 4 null-simulation controls x100 paths.

## 8. Why no edge is possible on most of this universe (economic logic)
Volatility, Step and Multi Step indices are generated as zero-drift martingales (verified: Step100 tick statistics match
a fair +/-0.1 walk exactly). For a martingale, any stop/target/time rule has zero expected gross P&L (optional stopping),
so every strategy loses the spread; the best achievable is PF -> 1 from below as targets grow (Step100 with
1-step spread and +/-k-step brackets: PF = (k-1)/(k+1)). VolSwitch adds predictable volatility but no direction, and a
linear CFD cannot monetise volatility. DSI is the only family with a designed non-martingale component, and its spread
is dynamic and drift-linked.

## 9. Failure conditions / weaknesses of the finalist
Negative expectancy whenever the DSI30 spread at entry exceeds ~5 (it does during drift regimes, 4.6-10.16 observed).
Only one afternoon of spread observations exists (VOL 66 + VOLB 2 full rounds + 24 DSI samples); no historical spread data.

## 10. What would change the verdict
A multi-day log of `Symbol.Spread` at every signal on a demo account. VolbBot.cs prints a `SPREADLOG` line on every
M5 bar (spread, ER, ATR) and enforces a 4.0 entry cap; if over >= 2 weeks the spread at ER>0.8 signals were <= ~4
in most cases, the 4.0-spread backtest (PF 1.21, OOS 1.36, WF OOS 1.16-1.95) would become relevant - still below the
1.30 gate. Current evidence says the opposite. Recommendation: no forward test with money; at most a $0-risk demo log.

## 11. Files
strategy.py, specs.json, VolbBot.cs (`bash arena/check_cbot.sh` -> Build succeeded), report_data.json,
research/: universe.py, screen.py (+screen_M_5.csv, screen_H_1.csv), tod.py (+tod.csv), micro.py, vsw.py, dsi_hmm.py,
hmm.py (from VOL), lab.py (+lab_*.csv), control.py, oot.py, dsi_be.py, dsi_vol.py, wf.py (+wf.json), spreads.csv,
dsi_spreads.csv, build_report.py, evaluate2_official.txt, spread_sensitivity.txt.
