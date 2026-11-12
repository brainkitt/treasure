# CHARLIE — research log (Deriv jump / spike synthetic indices)

**Bottom line: no edge found. The submission is NOT QUALIFIED (official PF 0.90) and should not be forward-tested.**
Every instrument in the jump/spike family that I tested behaves as a fair game (compensated jump martingale with
memoryless jumps). Net of spread every strategy has negative expectancy. I am reporting that rather than a curve-fit.

Data: 2026-09-26 → 2026-11-11. In-sample = first 70 % of days, out-of-sample from 2026-10-28.

## 1. Official result of the submitted system

```
period 2026-09-26 -> 2026-11-11  (OOS from 2026-10-28)
full   trades= 360 PF=0.90 net=$-8.07 win=21% DD=$16.94 worst=$-1.48 tr/day=7.7 active=100% wk+=50%
is     trades= 224 PF=0.84 net=$-8.28 win=18% DD=$16.47 worst=$-1.13 tr/day=7.0 active=100% wk+=50%
oos    trades= 136 PF=1.01 net=$0.21 win=25% DD=$5.91 worst=$-1.48 tr/day=9.1 active=100% wk+=33%
stress trades= 360 PF=0.83 net=$-14.55 win=20% DD=$21.83 worst=$-1.49 tr/day=7.7 active=100% wk+=50%
FAIL pf_full, pf_oos, pf_is, stress pf, max drawdown, weekly consistency
PASS trades, oos trades, active days, worst trade, no look-ahead, min lot
NOT QUALIFIED
```

Submitted system (Range Break 100, id 2449, M1, 0.01 units = broker minimum):
a break bar (range > 30) that closes within 2 points of its extreme → enter with the break at the next open;
SL 25 points, trailing 25 on bar closes, time exit 30 bars, far disaster TP 600 (never hit).
It is a bounded-risk lottery ticket on the next break, not an edge. Parameters were picked on in-sample only, as the best
in-sample PF among parameter sets whose worst trade stayed above −$1.50.

## 2. Hypothesis before fitting

Deriv describes these indices as random generators with asymmetric structure (Boom: slow down-drift + up-spikes
"on average every N ticks"; Crash mirror; DEX; Range Break; Crash Boom Flip; Skew Step; Snap; Vol Boom/Crash; Trek).
An edge can only exist if one of the following holds, so each was tested:

1. the drift between spikes is not exactly compensated by the spikes (non-zero mean);
2. spikes are not memoryless (hazard depends on time since last spike, clock time, or previous spike);
3. spike size is predictable;
4. a state-dependent rule is mis-calibrated (Range Break boundaries, Crash Boom Flip regimes);
5. instruments share a random source (lead-lag).

## 3. What was tested and what came out

| # | Test | Data | Result |
|---|---|---|---|
| 1 | Long-run drift, H1 returns, t-stat of mean | 12 symbols × 29 days (Boom/Crash 300/500/1000, RB100/200, DEX 600/900 UP/DOWN) | t between −1.5 and +1.5 for 11 of 12; RB200 t=+2.4 (1 of 12, not significant after multiple testing) |
| 2 | Drift vs spike balance per M1 bar | Boom 500/1000/300, Crash 500, DEX 900 U/D, DEX 600 UP, 1000 bars each | Boom 500: drift −1.07 bp/bar × 92.6 % + spike 13.1 bp × 7.4 % = −0.02 ± 0.13 bp. All others within 1 σ of zero except DEX 600 UP (+2.3 σ in 17 h, not confirmed on 29-day H1: t=1.5) |
| 3 | Hazard vs bars since last spike (9 buckets, chi-square) | same 7 symbols, M1 | z = 0.0, 0.8, 0.2, 0.5, −0.4, 0.3, −0.5. Pooled chi2 54.9 on 52 dof. Memoryless |
| 4 | Powered hazard test | DEX 900 UP and DOWN, M5, 3690 bars, 602 and 653 spikes | hazard flat 0.14–0.20 across all buckets, both halves; inter-spike CV 0.88 / 0.94 vs geometric 0.91. Memoryless |
| 5 | Spike size vs time since last spike; lag-1 of spike indicator | 7 symbols | correlations −0.17…+0.17 on 40–78 spikes, none significant |
| 6 | Spike clock: minute-of-quarter-hour, hour of day | DEX 900 U/D, DEX 600 UP, Boom 500, RB100 (964 breaks) | RB100 chi2 13.9 (14 dof) and 24.0 (23 dof): uniform. DEX cells too small, no repeated pattern across siblings |
| 7 | Generic: M1 autocorrelation lags 1–10, signed return after a big move | CBFlip 150/500, Skew Step 5 Up / 4 Down, Snap 50, Vol Boom 550, Trek Up, Jump 10/50/100, Boom 50/150 | nothing beyond 2 σ that is not the documented compensating drift |
| 8 | Crash Boom Flip regime persistence: return after 1,2,3,5,8 "clean drift" bars | CBFlip 150 and 500 | drift continues 63–90 % of bars but is exactly paid back by adverse spikes: next-bar mean in drift direction −0.11 ± 0.05 / +0.06 ± 0.04 (CBF150), +0.2 ± 0.2 (CBF500) |
| 9 | Range Break mechanics | RB100, 47 days, 964 breaks | after an up-break the bar high IS the new upper boundary (142/150); break size mean 110, unpredictable (corr with width +0.04, duration −0.03, previous size −0.01); segment duration exponential (mean 68, std 72, median 45 vs 47) |
| 10 | Range Break boundary expectancy: forward return toward the break when price sits ≤2 points from a known boundary | RB100, 47 days, 2202 + 2056 bar-samples | +0.16 ± 0.55 and +0.42 ± 0.58 points per bar; spread is 2.6. Fair. (On the first 12 days this looked like +11.9 ± 2.7 over 10 bars; it shrank to +2.2 ± 1.3 and −0.6 ± 1.2 with the full sample — a small-sample artefact I am glad I did not fit) |
| 11 | Range Break hazard of a break vs bars since last break | RB100 | 2.5 % on the break bar (price is on the boundary), 0.9 % at 5–10 bars, 1.5 % afterwards: consistent with a memoryless per-attempt break |
| 12 | Cross-instrument lead-lag, 11 pairs (Boom/Crash, DEX U/D, RB100/200, Jump, CBFlip, Skew) | M1 | lag correlations all within 2 σ. RB100/RB200 show −0.15 contemporaneous correlation driven by one coincident break; −0.04 without it |

## 4. Backtests run (official engine, gap_sl=true)

Total **672 parameter sets**, all on Range Break 100, plus the ~12 statistical hypotheses above on ~25 symbols.

| Grid | Sets | In-sample PF range | Comment |
|---|---|---|---|
| Post-break momentum and fade, SL 8/15/25/none × TP 0/10/20/60 × hold 5/20/60 (first 12 days) | 96 | 0.05 – 1.15 | any TP caps the jump and destroys the momentum side; fade loses the spread and has −$2.6…−$4 worst trades |
| Boundary continuation and fade, near 1/2/4/8 × SL 6/10/15/25 × hold 3–60 × trail on/off (47 days) | 320 | continuation 0.30 – 0.81, fade 0.33 – 1.04 | best fade (hold 60) PF 1.04 IS / 0.98 OOS with DD $27 and −$4.95 worst trade |
| Break-side only, entry age 0/3/10/any × near 2/8 × SL 10/15/25/40 × hold 10–120 × trail on/off | 256 | 0.44 – 1.10 | PF rises toward 1.0 only as stop and hold widen, exactly what a fair game with a fixed spread cost predicts |

In-sample and out-of-sample PF are correlated 0.92–0.94 across the grids because they share the structural cost, not because of an edge.

### Neighbour table around the submitted set (entry on the break bar, trailing on; PF in-sample / out-of-sample, worst trade $)

| near | SL | hold 10 | hold 30 | hold 60 | hold 120 |
|---|---|---|---|---|---|
| 2 | 10 | 0.54 / 0.66, −0.30 | 0.53 / 0.66, −0.30 | 0.53 / 0.66, −0.30 | 0.53 / 0.66, −0.30 |
| 2 | 15 | 0.58 / 0.62, −0.35 | 0.61 / 0.62, −0.35 | 0.60 / 0.62, −0.85 | 0.60 / 0.62, −0.85 |
| 2 | 25 | 0.54 / 0.76, −0.41 | **0.84 / 1.01, −1.48** | 0.83 / 0.96, −1.74 | 0.83 / 1.06, −1.74 |
| 2 | 40 | 0.59 / 0.81, −0.58 | 0.95 / 1.15, −3.05 | 1.02 / 1.07, −3.05 | 1.10 / 1.09, −3.05 |
| 8 | 25 | 0.55 / 0.87, −0.46 | 0.79 / 1.19, −2.25 | 0.84 / 1.14, −2.25 | 0.81 / 1.15, −2.25 |
| 8 | 40 | 0.58 / 0.90, −1.64 | 0.82 / 1.27, −3.09 | 0.95 / 1.12, −3.09 | 0.89 / 1.07, −3.41 |

No plateau above 1.0 that respects the $1.50 worst-trade cap.

## 5. Minimum lots and what one spike costs (probed 2026-11-11, LIMIT BUY volume=1 at 50 % of price)

| Symbol | Min units | Spread | One adverse jump at minimum size |
|---|---|---|---|
| Range Break 100 (2449) | 0.01 (accepted, cancelled, confirmed gone) | 2.6 | mean 110 points = $1.10, max seen 432 = $4.32 |
| Range Break 200 (2450) | 0.01 (accepted, cancelled, confirmed gone) | 2.0 | mean 179 = $1.79, max seen 357 = $3.57 |
| Boom 500 (2442) | 0.20 | 0.53 | mean 13 bp = 7.7 points = $1.55, max seen 28 bp = $3.30 |
| Crash 500 (2443) | 0.20 | 0.33 | mean 13 bp = 4.1 points = $0.81, max seen 35 bp = $2.15 |
| Boom 1000 (2444) | 0.20 | 1.72 | mean 12 bp = 17.8 points = $3.56 |
| DEX 900 UP (2462) | 0.10 | 0.53 | mean 44 bp = 10.4 points = $1.04, max seen 223 bp = $5.23 |

So the drift-side position (short Boom, long Crash, fade a Range Break boundary) cannot meet the $1.50 worst-trade gate
at minimum lot on any of them: a stop cannot help because the loss is one tick. Only the spike-side position has bounded
losses, and it pays the spread plus the drift for a fair lottery ticket.

Other spreads sampled (price units): CBFlip 150 0.17, CBFlip 500 1.02, Skew Step 5 Up 0.8, Skew Step 4 Down 0.6,
Snap 50 8.71, Vol Boom 550 1.09, Trek Up 1.05, Jump 50 9.5, DEX 600 UP 0.43, DEX 600 DOWN 0.54, DEX 1500 UP 0.45,
DEX 1500 DOWN 3.85, Boom 300 0.50, Crash 300 1.10, Boom 600 0.77, Crash 600 3.28.

## 6. Suspected engine bug — please check other submissions for it

On `gap_sl` instruments a **pending stop order (kind=2) fills at the stop price in the middle of a single-tick jump**.
Demonstration (not a strategy): a buy-stop 2 points above the ask on Boom 500, re-placed every bar, SL 6, hold 1 bar →
85 trades, **PF 20.0**, +$68 on 1000 bars. In reality that order fills at the post-spike price and earns nothing.
The same artefact would let a buy-stop just above a Range Break boundary "capture" the 100-point break.
Any submission using stop entries on Boom/Crash/DEX/Range Break/Jump should be treated as invalid until the engine
fills such orders at the bar extreme. I did not use stop or limit entries anywhere.

Related, in the conservative direction: a TP on the spike side is filled at the TP price, not at the better post-jump
price, so the engine understates spike-side wins when a TP is used. The submitted system therefore uses only a far
disaster TP and a trailing stop.

## 7. Known weaknesses of the submission

* Negative expectancy: about one spread (2.6 points = $0.026) per trade plus reflection losses, by construction.
* Drawdown $16.94 on a $30 account; only 50 % of weeks profitable.
* Worst trade −$1.48 came from a break through the opposite boundary gapping the 25-point stop; a larger gap is possible
  (range can be narrower than 25 points).
* M1 bars hide the tick path; the break bar's close can already be several points off the boundary.
* Data has 16 gaps (1658 missing minutes in 47 days, the largest about 24.6 h on 7–8 Nov); the logic only uses single
  completed bars so gaps do not corrupt state.
* Swap is not modelled. Holds are at most 30 minutes, so financing exposure is small, but trades that straddle 00:00 UTC exist.

## 8. What I would try next

* Tick data for Range Break to measure the exact per-attempt break probability and reflected step. The M1 evidence says
  fair to within ±0.5 points per bar, far inside the 2.6 spread, so I expect confirmation rather than an edge.
* Nothing else on this family. The honest conclusion is that Boom, Crash, DEX, Range Break, Jump, Skew Step, Snap,
  Crash Boom Flip, Vol Boom/Crash and Trek are fair games with a spread, and the account owner should not trade them
  systematically. Effort is better spent on instruments with a documented conditional drift or on real markets.

## 9. Files

* `strategy.py` — submitted system. `specs.json` — spreads and probed minimum lots. `CharlieBot.cs` — cTrader cBot.
* `scout.py`, `hazard.py`, `gen.py`, `cbf.py` — distribution, hazard and regime tests.
* `rb_explore.py`, `rb_touch.py`, `rb_grid.py`, `rb_grid2.py`, `rb_grid3.py`, `rbcore.py` — Range Break research;
  `grid_2449.csv`, `grid3_2449.csv` — full grid results.
* `submissions/CHARLIE/metrics.json`, `trades.csv` — official evaluate output.
