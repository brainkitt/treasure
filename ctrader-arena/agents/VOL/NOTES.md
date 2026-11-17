# VOL (AGENT_03) — Deriv synthetic indices research log

**Bottom line: NOT QUALIFIED. I found one genuine, documented structural effect (regime persistence in the
Drift Switch Indices, gross momentum t > 7), but Deriv's *dynamic* DSI spread widens exactly during drift regimes
and consumes the edge. Net of the spread actually quoted when the signal fires there is no edge. Do not forward-test
for money.** Every other synthetic family tested behaves as a fair game (random walk / compensated jumps).

## 1. Official result (DSI20, M5, widest observed spread 4.05)
```
full   trades=1298 PF=0.65 net=$-201.59 t=-6.11 DD=$205 worst=$-1.39   is PF 0.68   oos PF 0.60   stress PF 0.18
folds  PF 0.54 / 0.77 / 0.80 / 0.52 / 0.65 (all negative)       NOT QUALIFIED  score 0/100
```
Same system at lower assumed constant spreads (evaluate2 --fast --spread-mult): 0.81 -> PF 1.66 (OOS 1.50, t 6.4);
1.01 -> PF 1.55 (OOS 1.40); 2.11 (median spread observed *while trending*) -> PF 1.10 (OOS 1.01); 4.05 -> PF 0.65.

## 2. Hypotheses (written before fitting) and results
| # | Hypothesis / why an edge could exist | Data | Result |
|---|---|---|---|
| H1 | Drift Switch 10/20/30 switch between +drift/-drift/flat regimes with mean 10/20/30 min (Deriv). A regime already detected persists (memoryless durations) -> trend following has positive expectancy | DSI30 M5 2026-01-02..11-17 (91.5k bars), DSI20 M5 06-28..11-17 (40.7k), DSI10 M5 21 days, M1 samples | **Gross effect real**: VR(2..60) 1.1-1.7, AC1 0.10-0.14 (SE 0.006); sign-momentum t 8-12 in both halves; DSI30 long trades positive in 11/11 months incl. falling months (long side structurally stronger: HMM up-regime long/low-vol, down-regime short/sharp); DSI20 IS grid at spread 1.0: 324/324 sets PF>1, 99% PF>1.2; anchored WF at spread 1.0: OOS PF 1.51-1.66 in 5/5 folds. **Killed by cost (section 3).** |
| H2 | Long-run drift / VR in Trek Up/Down, Exponential Growth 1/2, Ladder Up/Down, VolSwitch | H1 30 days each; M5 1000 bars Step, Multi Step 2, VolSwitch Low/High, ExpGrowth 1 | all drift |t|<1.8, VR~1, AC within 2 SE. Fair games. |
| H3 | Volatility 75 (owner's profitable history, 28 trades PF 1.81) has exploitable autocorrelation | V75 H1 1 year (8606 bars) | mean t=0.03, AC lags1-10 |r|<0.013, VR 0.90-1.03. 50 momentum cells: none replicated across halves. Owner's 28 trades are ~12 decisions (3 positions closed together), dominated by 4 outcomes; not evidence. |
| H4 | Jump/Boom/Crash/DEX/Range Break | — | not repeated (CHARLIE round 1: fair games). |

## 3. The decisive finding: regime-dependent dynamic spread
66 live samples (agents/VOL/research/spreads.csv), each labelled with the M1 efficiency ratio of the prior 10 minutes
(research/spread_label.py, spread_labels.txt):

| symbol | spread when sideways (|ER10|<=0.5) median/max | spread when trending (|ER10|>0.5) median/max | corr(spread,|ER10|) |
|---|---|---|---|
| DSI10 | 3.19 / 3.64 | 1.17 / 3.29 (n=5) | -0.52 |
| DSI20 | 0.86 / 3.38 | 2.12 / 4.05 | +0.82 |
| DSI30 | 0.55-6.9 (n=2) | 9.32 / 10.16 | +0.85 |

Deriv states DSI spreads are "dynamic". The data say the spread grows when the index drifts (DSI30: 0.55 in a choppy
phase, 9-10 during a clean up-drift of ~1 pt/min). Gross capture per trade is ~2.5 pts (DSI20) / ~5.5 pts (DSI30 longs);
break-even spread ~2.5 / ~6. A spread gate (enter only when spread is narrow) does not rescue it: narrow spread coincides
with driftless regimes, so admitted signals would be mostly false positives. Caveat: samples cover ~1.5 hours of one day;
the correlation is strong but n is small. I used the widest observed spread as the brief requires.

## 4. Costs
* min volume 0.10 units for DSI10/20/30 (probed: LIMIT BUY volume=1 rejected "minimum allowed volume = 0.10"; nothing was accepted, no order left).
* commission 0. Swap not exposed; bound 1.5 USD/unit/night (3x the V75 rate scaled by price) — immaterial vs spread.
* margin: 1:50 assumption -> $5.42 at 0.1 units DSI20. slip 0.1.
* Balance: at 0.1 units the worst trade is $1.39 (< 5% of $30) so $30 would be *technically* feasible; irrelevant since expectancy is negative.

## 5. Parameter sets evaluated (data-mining count)
~2,900 backtests over ~600 distinct parameter sets: DSI30 IS grid 162, DSI20 grids 324 (spread 1.0) + 576 at each of
4.05 / 2.12, DSI10 576, DSI30 576, ~40 exploratory, walk-forward 5x324 refits. The default (N6 thr0.8 sl3 trail1.5 H24
long-only) was fixed from the first exploratory DSI30 run, not optimised on DSI20.

## 6. Deliverables
strategy.py (DSI20 M5 trend follower), specs.json (measured), VolBot.cs (compiles: `bash arena/check_cbot.sh` -> Build
succeeded; includes the live spread gate, kill-switch, daily loss, consec-loss pause, rollover no-entry window),
report_data.json, submissions/VOL/{metrics.json,trades.csv}. Research scripts in research/ (lab.py, grid.py, wf.py,
er.py, mom5.py, vr.py, hmm.py, spread_label.py).

## 7. What would change the verdict
A multi-day spread log (cBot logging Symbol.Spread every bar on DSI10/20/30). If DSI10's trending spread really is ~1.2
(it was the only one with negative correlation, n=5) the gross edge (break-even ~3) could survive there; needs months of
DSI10 M5 data plus a week of spread logging before any money.
