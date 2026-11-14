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

---
# ROUND 2 — real FX (working log, written as I go)

Turf: FX pairs/sessions ALPHA does not cover. Method: M15 PRE-SAMPLE (2026-03-31 .. 2026-09-15, entirely before the
official M1 window) to choose mechanism and parameters; official M1 window scored untouched.

Findings so far
* Bars are BID. Around the daily FX close (NY 16:45-18:15) the bid dips and recovers as the spread widens
  (USDJPY pre-sample: 16:45 NY bar -2.6 pips t=-7.0, 18:00 NY bar +3.8 pips t=+5.5). The engine uses a constant spread,
  so any strategy that is long across that window books a fake gain. I exclude NY 16:30-18:30 from all research.
  Supervisor: please check other FX submissions for holds across the rollover.
* Spreads frozen at the 22:00 UTC close on 2026-11-11 (rollover-wide): EURGBP 2.4-2.7 pips, EURCHF 2.6, AUDNZD 10.0,
  NZDUSD 3.2, USDCAD 3.0, AUDJPY 2.9, GBPJPY 13.5, EURJPY 5.6, USDCHF 0.9 -> 4.2.
* USDJPY time-of-day drift (96 M15 slots, 145 days): nothing beyond |t|=3 outside the rollover artefact; hourly drift
  of the two half-samples correlates 0.15. Tokyo-fix slot (00:45 UTC) not significant. No seasonality edge.
* USDJPY Donchian-break event study by session (N=16/48, horizons 4/8/16 bars): only "late NY 18:00-20:30 UTC" shows a
  consistent fade (-4.2 +/- 1.4 pips at 8 bars, both halves), 1 of 48 cells, and the horizon runs into the rollover.
* Spreads sampled 2026-11-12 ~07:45 UTC (London): EURUSD 1.3, GBPUSD 1.5, USDJPY 1.4, EURJPY 1.6, AUDUSD 1.0,
  USDCHF 0.9, EURGBP 0.8, EURCHF 1.0 pips.
* Donchian-break event study pooled over EURUSD, GBPUSD, USDJPY pre-sample (N=16/32/64 x horizon 4/8 bars x 8 session
  buckets = 48 cells): largest pooled |z| = 2.7 (Tokyo 00-03 UTC, N=16, 1 h: fade worth 0.8 / 1.9 / -0.2 pips, below the
  1.3-1.5 pip spread). USDJPY late-NY fade does NOT generalise (EURUSD/GBPUSD show the opposite sign). No break edge.
* Bollinger-fade sims on M15 pre-sample (engine, real spread), EURUSD/GBPUSD/USDJPY x Asia/London/NY x 16 sets = 144 sets:
  median PF 0.64-0.97, best cell 1.40 (GBPUSD Asia, n=60). At ZERO spread the same rules give PF 1.2-2.1: short-horizon
  mean reversion is real in mid prices but smaller than the spread.
* Session-to-session continuation/reversal (Asia, early Europe, London, NY, late NY; 8 session pairs x 3 pairs, all days
  and big-move days): largest pooled z = +2.7 (early-Europe move continues in NY on big days, +3.7..+7.5 pips against a
  20-40 pip session sd). Nothing tradable.
* EURGBP Bollinger fade pre-sample: Asia PF 0.36-0.56 at 0.8 pip and only 1.02 at ZERO spread (no Asian reversion at all);
  London 0.72-1.13 (1.40 at zero spread). Bid recovers +3.1 pips at the 22:00 UTC bar (t=12.9) = night spread ~3 pips.
* Pooled market-entry fade ranking over EURUSD+GBPUSD+USDJPY: best pooled PF 1.08 (NY, k=2.5), session medians 0.72-0.92.
  Running total Round 2: 160 market-entry sets, ~90 statistical cells. Next: passive LIMIT-entry fades (coordinator request).

## Round 2 — final

**Bottom line: nothing survives. The submission is NOT QUALIFIED and should not be forward-tested as an edge.**

### Passive LIMIT-entry fade (coordinator's last task), M15 pre-sample 2026-03-31..2026-09-15, split in two halves
Rule: |z| of Bollinger(20) > k at an M15 close inside the session -> limit order `off` ATR beyond the close (buy limit in
ASK terms, sell limit in BID terms), valid 2 bars, SL 1.5/3 ATR, TP to the band mean, hold 6/16 bars.
Grid: k 2.0/2.5 x off 0/0.25/0.5 x SL 1.5/3 x hold 6/16 = 24 sets per cell. Pass = PF > 1.2 in BOTH halves.

| Pair (spread) | Session | Sets | PF median | PF max | Sets passing both halves | Best by weaker half (PF all, h1, h2, n) |
|---|---|---|---|---|---|---|
| USDJPY (1.4) | London 07-12 UTC | 24 | 0.61 | 0.79 | 0 | 0.79, 0.71, 0.87, n=73 |
| USDJPY (1.4) | NY 12-16 UTC | 24 | 0.94 | 1.23 | 0 | 1.18, 1.05, 1.26, n=38 (worst trade -$6.77) |
| EURGBP (0.8) | London 07-12 UTC | 24 | 0.70 | 1.17 | 0 | 1.17, 1.25, 1.10, n=79 |
| EURGBP (0.8) | NY 12-16 UTC | 24 | 0.93 | 1.28 | 0 | 1.21, 1.09, 1.32, n=35 |

0 of 96 sets pass. A resting limit does not recover the spread: the fills are the adversely selected ones.
Only USDJPY and EURGBP were tested because they are the only non-ALPHA pairs I had pre-sample for; USDCHF, AUDUSD,
EURCHF and EURJPY were NOT tested (no pre-sample downloaded, budget).

### Candidate forwarded once to the official M1 window
Chosen before the forward run: USDJPY, NY morning (08:00-12:00 New York), k=2.0, off=0.5 ATR, SL 1.5 ATR capped at
22 pips, hold 90 min — the only USDJPY set whose worst trade could be capped under $1.50 with a pre-sample PF near 1
(pre-sample PF 1.00, halves 1.08 / 0.96, 88 trades, before the stop cap).

```
period 2026-09-21 -> 2026-11-11  (OOS from 2026-10-27)
full   trades=  26 PF=2.30 net=$9.42 win=62% DD=$4.36 worst=$-1.21 tr/day=0.7 active=61% wk+=75%
is     trades=  15 PF=9.25 net=$12.39 win=80% DD=$0.79 worst=$-0.67 tr/day=0.6 active=58% wk+=100%
oos    trades=  11 PF=0.48 net=$-2.97 win=36% DD=$4.36 worst=$-1.21 tr/day=0.9 active=67% wk+=33%
stress trades=  26 PF=2.22 net=$8.93 win=58% DD=$4.58 worst=$-1.21 tr/day=0.7 active=61% wk+=75%
FAIL pf_oos, trades >= 150, oos trades >= 40, active days;  PASS the other eight.   NOT QUALIFIED
```

How to read it: 26 trades. The headline PF 2.30 is noise — in-sample 9.25 and out-of-sample 0.48 are the same rule, and
$8.97 of the $9.42 came from the 12 long trades. Pre-sample (88 trades, PF 1.00) plus forward (26 trades) is consistent
with zero expectancy. This is the same trap as ALPHA's London breakout: a good official window, nothing behind it.

### Why this file set rather than Round 1
Both are no-edge. The FX candidate is on the requested turf, has pre-sample PF 1.00 against a structurally negative
Range Break system (PF 0.84-0.90), and stays inside the drawdown and worst-trade gates. Round 1 files are kept in
`round1/` (strategy_rangebreak.py, CharlieBot_rangebreak.cs, metrics_rangebreak.json).

### Round 2 trial count
* Backtested parameter sets, all on the pre-sample: 160 market-entry Bollinger fades + 96 limit-entry fades = 256.
* Statistical cells: 96 time-of-day slots x 2 pairs, 48 pooled Donchian-break cells, 16 session-pair cells.
* Forward runs on the official window: 1.

### Things the supervisor should know
* BID-bar rollover artefact (see above): constant-spread engine credits a fake gain to longs held across NY 16:45-18:15.
* Night spreads are about 3x London spreads on crosses (EURGBP 0.8 -> 2.4-2.7 pips), so specs sampled in London hours
  overstate any Asian-session strategy.
* Short-horizon FX mean reversion is real in mid prices (PF 1.2-2.1 at zero spread) and consistently smaller than the
  retail spread on this account, with market or limit entries.

### Known weaknesses of the submission
* No edge; 0.7 trades/day; one leg. The cBot is an untested port (not compiled in cTrader); its time exit is checked
  once a minute and its limit price uses the live spread, where the backtest uses a constant 1.4 pips.
* USDJPY minimum size (1000 units) is taken from ALPHA's probe, not re-probed by me.

---
# Phase 2 (CHARLIE) — small-notional real markets, H1+ bars, multi-year

## Setup facts (2026-11-13/14)
* get_trendbars is now capped at a 30-day window per call (H_1: 720 bars/call, not 1000). Paging grid: toTimestamp =
  2026-11-13T22:00Z - 30d*k.
* Crypto H_1 history exists back to at least Jan 2024 (ETH, SOL, XRP, LTC, BNB, LINK); US Oil / Brent H_1 are empty at
  Jan 2024, present at Nov 2024.
* Spread sample 2026-11-13 22:20 UTC (ask-bid, % of price): ETH 1.58 (0.08%), XRP 0.0011 (0.11%), BNB 0.73 (0.12%),
  XAG 0.06 (0.12%), LINK 0.016 (0.16%), SOL 0.14 (0.18%), US Oil 0.155 (0.18%), Brent 0.155 (0.16%), LTC 0.187 (0.38%),
  BCH 1.05 (0.48%), AVAX 0.042 (0.51%), DOGE 0.00034 (0.53%), ADA 0.00103 (0.62%), DOT 0.006 (0.74%), NGAS 0.055 (1.6%, closed).
* Min-lot probes (LIMIT BUY vol=1 at 50% of price, both rejected): BNBUSD min 0.10 units (~$63), LNKUSD min 6 units (~$59).
* get_trendbars result files are named by millisecond: parallel calls that land in the same ms overwrite each other
  (lost 5 of 18 in one batch). `agents/CHARLIE/gaps.py <ids>` lists missing 30-day windows to re-request.
* More min-lot probes (all rejected, 2026-11-14): DOGE 1500 (~$96), ADA 200 (~$33), TRX 1500 (~$468), DASH 1 (~$40),
  ETC 7 (~$44), DOT 40 (~$32), AVAX 6 (~$49), BCH 0.2 (~$44). The broker sets every crypto minimum at roughly $30-100
  notional, so there is no "tiny notional" coin; and prices were 2-3x higher in 2024-25 (SOL median 129 vs 78 now),
  so at min size a $1.5 stop is only 1-3% of price over most of the history = 1-3 H1 ATRs. Classic multi-day
  trend-following stops (8-15%) are NOT affordable on $30. Everything below is constrained to that.
* More spreads (% of price): DASH 0.145, UNI 0.14, XMR 0.08, TRX 0.30, BAT 0.30, XLM 0.31, ETC 0.36, ALGO 0.72, IOTA 1.5,
  NEO 2.4, FIL 4.4.
* Data: ETH and SOL H_1 complete 2023-12-29 -> 2026-11-13 (25,172 bars each). Real flash-crash hours present
  (e.g. 2024-01-03 12:00 SOL low -20% inside one bar) -> stops can slip a long way; engine fills at stop unless the bar opens beyond.

## Trial log
T1 (16 sets, IS = first 70%): H1 Donchian close-breakout N in 24/48/96/168 h, SL = k*ATR48 (k 2,3), trail = SL, no $ cap.
   ETH PF 0.85-1.13 (one cell 1.42 at N=168,k=3, 149 trades); SOL PF 0.63-0.85 everywhere. Holds 11-29 h, win 30-40%.
   -> short-horizon breakout with tight trailing stop is whipsawed; no edge.
S1 (statistics, IS only; ETH + SOL H1, 17,620 bars each): hour-of-day mean returns (24 cells), day-of-week (7), and
   sign(past k h) -> future j h for k in 1,4,12,24,72,168,336 and j in 1,4,24,72,168 (35 cells per symbol).
   No cell reaches |t| > 2.1 on both symbols; signs differ between ETH and SOL (SOL mildly mean-reverting at every
   horizon, ETH flat). Best hour effect (21-22 UTC, ETH t 2.7 / SOL 1.8) is ~0.06%/h = below the spread.
   -> no time-series momentum, no usable seasonality in the two most liquid coins. Did not download the other
   four coins (130+ calls) because the alt-coins are one correlated bet with wider spreads.
* XAGUSD min = 50 oz (~$2,430 notional) -> unusable. Softs spreads 0.25-0.64% + short sessions -> not pursued.
* US Oil H_1: 2024-04-28 -> 2026-11-13 (14.4k bars). Price range 55-112. Weekend gaps: mean |1.08%|, max 12.1%
  => at 1 unit a weekend gap alone can cost $1-10, so oil must be flat over weekends on a $30 account.
S2 (statistics, IS only; oil, 445 days): hour-of-day (24), six intraday continuation pairs (Asia->rest, pre-open->US,
   US first 3h -> last 2h ...), daily momentum 1/2/3/5/10/20 d -> next day, four yesterday->session cells.
   All |t| < 2; hit rates 45-52%. Mild 1-day reversal (-15 bp, t -1.65) is smaller than the 22 bp spread.
   -> no intraday or daily momentum in WTI on this sample.
* US Small Cap 2000 (id 2521) H_1: 2024-04-28 -> 2026-11-13, 15,065 bars, price 1708-3070 (0.1 unit = $170-307 notional).
  Weekend gaps mean |0.36%|, q95 1.19%, max 3.83% (= up to $11 at 0.1 unit) -> must be flat over weekends.
  Daily-break gap mean 0.05%. Spread: 0.76 pts at the Friday close (my sample), 0.30 in session (DELTA) -> spec uses 0.76.

S3 (statistics, IS only = 2024-04-28 -> 2026-02-11, 442 days; Small Cap): hour-of-day in New York time (24), six session
   means, seven intraday continuation pairs, daily momentum 1/2/3/5/10 d, day-of-week (5)  (~47 cells).
   What stood out, each with a textbook reason:
   - overnight drift 16:00 -> 09:00 NY +8.1 bp (t 1.8) - but spread 3 bp + financing 2.5 bp leaves ~2 bp: not tradable.
   - overnight move -> first cash hour: corr -0.154, fade earns 6.2 bp gross (t 2.7, hit 56%)  <- liquidity provision /
     overreaction of thin pre-market small-cap pricing; someone who must trade the open pays for it.
   - yesterday's return -> today's 09:00-16:00: fade 9.8 bp (t 1.7).
   No intraday momentum (first hour -> last hour t 0.0).
S4 (IS, 30 conditional cells): fade the overnight move at 09:00 NY when |overnight| > thr x 20-day daily vol, net of spread.
   Hold to 16:00: thr 0 / .25 / .5 / .75 / 1.0 -> PF 1.21 / 1.42 / 1.66 / 2.34 / 2.11 (n 420 / 260 / 143 / 88 / 39).
   Monotone in the size of the gap = what a liquidity effect should look like. "Long after a down day" also positive
   (z<-1: PF 2.4, n 57) but "short after an up day" is not -> not used.

## Candidate: overnight-gap fade on US Small Cap 2000 (hypothesis fixed before any engine run)
Rule: at 09:00 New York (close of the 08:00 NY H1 bar) compute on = ln(price / yesterday's 16:00 NY price) and
z = on / std(last 20 daily 16:00->16:00 returns). If |z| > thr: market order against the overnight move, 0.1 unit,
hard stop $1.50 (15 pts), close at 16:00 NY (6 H1 bars). No trade on NYSE holidays / early-close days (calendar).
T2 (engine, IS, 24 sets): thr 0/.25/.5/.75 x hold 1/3/6 bars x stop 0.5/1.0 vol (capped $1.5). Hold-to-close best at every
   thr: PF 1.20 / 1.38 / 1.48 / 1.65. 1-bar and 3-bar holds PF 1.1-1.3.
T3 (engine, IS, 18 sets): risk cap 0.75/1.0/1.5 x gap-fill target 0/0.5/1.0 x thr .25/.5. A profit target HURTS (PF 0.87-1.24):
   the profit is in the days that keep reversing to the close (TIME exits avg +$1.6; 43-58% of trades stop out).
T4 (engine, IS, 19 sets) neighbours of thr .5 / risk 1.5 / hold 6 / W 20 / entry 09:00 NY, base PF 1.50 (143 trades, DD 11.3):
   thr .3/.4/.6/.7 -> 1.38/1.44/1.40/1.64 | risk 1.0/1.25/1.75 -> 1.64/1.42/1.44 | hold 4/5/7 -> 1.41/1.44/1.41 |
   W 10/30/60 -> 1.30/1.58/1.45 | entry 08:00/10:00 NY -> 1.57/1.23 | long only 1.44 (59) | short only 1.54 (84).
   IS quarters (2024Q2..2026Q1) PF: 1.62 0.58 1.78 2.18 2.21 1.52 1.32 0.22(7 trades).
   Same rule on US Oil (1 unit), thr .25/.5: PF 0.66 / 0.54 -> NOT a cross-asset effect; equity-index specific. Oil dropped.
   Chosen before looking at OOS: thr 0.5, stop $1.50, hold to 16:00, W 20. (thr 0.5 rather than 0.7 only because the
   gate needs >= 200 trades; IS drawdown $11.3 is already close to the $12 gate - expected to be the weak point.)

## Phase 2 result - official run (one forward look at the last 30%, nothing tuned afterwards)
```
period 2024-04-29 -> 2026-11-13  (OOS from 2026-02-10)
full   trades= 223 PF=1.31 net=$54.17 win=43% DD=$18.87 worst=$-1.50 tr/day=0.3 active=34% wk+=51%
is     trades= 143 PF=1.45 net=$49.22 win=43% DD=$14.69 worst=$-1.50 tr/day=0.3 active=31% wk+=55%
oos    trades=  80 PF=1.07 net=$4.95 win=41% DD=$18.87 worst=$-1.50 tr/day=0.4 active=40% wk+=42%
stress trades= 223 PF=1.28 net=$49.88 win=42% DD=$19.79 worst=$-1.50 tr/day=0.3 active=34% wk+=51%
FAIL pf_oos >= 1.15 (1.07) and max drawdown <= $12 ($18.87).  PASS the other ten.   NOT QUALIFIED
```
| period | trades | net $ | PF |   | period | trades | net $ | PF |
|---|---|---|---|---|---|---|---|---|
| 2024 (May-Dec) | 49 | +4.5 | 1.11 | | 2024H1 | 13 | +4.1 | 1.61 |
| 2025 | 87 | +51.7 | 1.84 | | 2024H2 | 36 | +0.4 | 1.01 |
| 2026 (Jan-Nov) | 87 | -2.1 | 0.97 | | 2025H1 | 50 | +40.0 | 2.19 |
| | | | | | 2025H2 | 37 | +11.7 | 1.42 |
| | | | | | 2026H1 | 46 | +5.3 | 1.12 |
| | | | | | 2026H2 | 41 | -7.4 | 0.76 |

Quarters 2024Q2..2026Q4 PF: 1.61 0.47 1.78 2.18 2.20 1.51 1.32 1.32 0.80 0.73 0.80 (last three all below 1).
Shorts 129 trades PF 1.38, longs 94 trades PF 1.22. Exits: 110 stops (-$165.00), 113 time exits (+$219.17, avg +$1.94).
68% of months profitable, 9 max consecutive losses, lowest equity $19.38, no overnight holds, zero financing.

How to read it:
* $51.7 of the $54.2 comes from calendar 2025. 2024 and 2026 are flat. An effect that is "on" for one year in three
  is not something to put a $30 account behind.
* OOS neighbours (looked at, not used): thr 0/.25/.3/.4/.5/.6/.7/.75/1.0 -> PF 0.99/1.15/1.11/1.08/1.07/1.09/0.89/1.01/1.47;
  risk 1.0/1.25/1.75 -> 1.04/1.06/1.09; hold 1/3/4/5/7 bars -> 1.28/1.13/1.05/1.04/1.07; W 10/30/60 -> 1.10/1.20/1.06;
  entry 08:00/10:00 NY -> 0.98/1.16. The IS dose-response (bigger gap -> bigger reversal) is gone out of sample, so the
  most persuasive piece of IS evidence did not replicate. OOS is "slightly better than zero" everywhere, nowhere >= 1.3
  with a meaningful trade count.
* Drawdown $18.87 = 63% of the account. This is structural, not a tuning problem: 0.1 unit is $170-300 of index, a
  $1.50 stop is 0.5-0.8% and is hit on ~49% of trades, and the edge per trade ($0.24) is small against a per-trade
  swing of about +/-$1.7. Tighter stops (IS: $0.75 / $1.00) did not lower the drawdown.
* Costs are not the problem here (stress PF 1.28 vs 1.31, spec spread 0.76 is 2.5x the in-session 0.30).
* H1 bars + "SL first" pessimism: some of the 110 stop-outs would have survived on M1 bars; the real PF is probably a
  little higher than shown, but not enough to change the verdict.

## Phase 2 trial count
* Engine parameter sets, all on the first 70%: T1 16 (crypto Donchian) + T2 24 + T3 18 + T4 19 (gap fade) + 2 (oil
  generalisation) = 79.
* Statistical cells, all on the first 70%: S1 132 (ETH, SOL) + S2 ~44 (oil) + S3 ~47 + S4 30 (Small Cap) = ~250.
* Looks at the last 30%: 1 official run of the pre-chosen set, then 22 neighbour sets for description only.

## Phase 2 verdict
No qualifying system on my turf.
* Crypto (ETH, SOL, 2.9 years of H1): no time-series momentum at any horizon from 1 h to 14 days, no seasonality bigger
  than the spread, H1 breakouts lose. Every coin's minimum is $30-100 notional and was 2-3x that in 2024-25, so real
  trend-following stops are unaffordable anyway.
* US Oil (2.5 years): no intraday or daily momentum; weekend gaps up to 12% rule out holding; the gap-fade rule loses.
* US Small Cap 2000 (2.5 years): the only effect with a reason and an IS plateau (overnight-gap fade, IS PF 1.45,
  all 16 neighbours 1.23-1.64) came out at PF 1.07 on the unseen 9 months and needs a $19 drawdown to earn $54.
The submitted files are that system with its true numbers. It does NOT deserve a demo forward test on a $30 account;
at most it is a weak lead worth re-testing on M1/M5 bars and on a larger account where 0.1 unit is a small position.

## Known weaknesses / what I would try next
* One symbol, 0.24 trades/day. The same idea on S&P 500 / Nasdaq needs $760+ notional at minimum size.
* Holiday handling is a hard-coded NYSE calendar (2024-2027) in gapfade.py and CharlieBot.cs; extend it yearly.
* cBot compiles (dotnet build, 0 warnings) but has not been run in cTrader. Its time exit fires on the close of the
  15:00 NY bar plus a 30 s timer safety net; the backtest exits at that bar's close.
* If continued: (1) M5 bars for the 09:00-16:00 window to remove the H1 stop pessimism, (2) condition on the cash-open
  direction (enter 09:35 only if the first 5 minutes do not extend the gap), (3) test on a 5-10 year small-cap futures
  history from another source - 2.5 years with one good year cannot settle it.
* Tooling note for the supervisor: parallel get_trendbars calls overwrite each other's result file when they land in the
  same millisecond; always re-check for missing windows (agents/CHARLIE/gaps.py).

Files: strategy.py + gapfade.py (signals), specs.json, CharlieBot.cs, lab.py / gaps.py (research helpers),
phase1_files/ and round1/ (phase-1 material), submissions/CHARLIE/metrics.json + trades.csv (official run above).
