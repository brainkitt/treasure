# BRAVO research log — Deriv continuous synthetics (Volatility / Step / VolSwitch / Drift Switch ...)

## Headline
The only statistically real structure I found is on the **Drift Switch indices** (DS10 2464, DS20 2469, DS30 2470):
the BID bar series has a "calm, rising" state and a "volatile, falling" state, extremely stable over 61 days.
A regime filter that buys the calm state back-tests at PF 2-4 with a constant 1.48 spread.
**That edge is not tradable**: the live bid/ask spread on these symbols is not constant. It widens to 6-9 px
(DS30) exactly while the bid is in the calm-rising state and collapses to ~1.5-2 px when the bid drops.
The predictable drift of the bid is the bid catching up with an ask that has already moved. With the spread
actually observed at signal time the system loses money. The official engine assumes ask = bid + constant, so
it cannot see this; I therefore put the WIDEST observed spread into specs.json, as the brief requires, and the
submission honestly fails the gates.

## Minimum lots (probed with far-away LIMIT orders, all rejected, nothing left pending)
| symbol | min_units |
|---|---|
| Drift Switch 10 (2464) | 0.10 |
| Drift Switch 20 (2469) | 0.10 |
| Drift Switch 30 (2470) | 0.10 |

## Structure tests (M1 BID closes; acf = return autocorrelation, VR = variance ratio)
| symbol | bars | result |
|---|---|---|
| DS30 2470 | 86,398 (61 d) | VR(30)=1.33, VR(120)=1.5; 5-min block acf 0.08 (5 se); |r| acf(1)=0.16. Real. |
| DS10 2464 | 3,934 | VR(60)=1.58, same two-state shape. Real. |
| DS20 2469 | 3,934 | VR(60)=1.40, same shape. Real. |
| VolSwitch Low 2616 | 2,975 | strong vol clustering (|r| acf 0.42) but return acf(1)=+0.06 -> ~0.3 px predictable vs 0.89 spread. No directional edge. |
| VolSwitch Med 2617 | 4,934 | VR<1 at long lags driven by one outlier bar (kurtosis 172); acf within noise. Nothing. |
| VolSwitch High 2618 | 4,934 | vol clustering only, acf within 1-3 se, nothing after spread. |
| Ladder Vol Down 2624 | 2,975 | VR(30)=1.15, not significant (se ~0.15). Nothing. |
| Exp Growth 1 2621, Ladder Up 2623, Trek Up 2606, Trek Down 2607 | 1,000 each | acf/VR inside noise. Nothing. |
Plain Volatility / Step / HF Vol indices were not downloaded at depth: they are documented constant-vol
driftless walks, VolSwitch (their regime-switching cousin) showed no directional structure, and CHARLIE
found the jump family fair. No hypothesis for an edge there, so I did not fit anything.

## Drift Switch 30 — the regime model (hmm.py, fit1.py)
2-state Gaussian HMM on M1 log returns (bp), fitted on in-sample (first 70% of days, to 2026-10-23):
| state | mean /min | sd /min | mean duration |
|---|---|---|---|
| calm-up | +0.56 bp | 1.39 bp | 25 min |
| volatile-down | -0.42 bp | 3.42 bp | 33.5 min |
OOS log-likelihood +2,833 nats over iid Gaussian. Re-fitting on 4 separate chunks gives the same numbers
(means 0.55-0.58 / -0.39..-0.43, sds 1.36-1.42 / 3.40-3.46): a property of the generator, not noise.
DS10: +1.5 / -1.07 bp, sd 1.5 / 5.0, durations 8.6 / 16.9. DS20: similar with ~15 min durations.

## The naive (invalid) backtest, constant spread 1.48, 0.1 units, IN-SAMPLE only
Long when causal filter P(calm) >= hi, trailing stop, hard SL:
| hi | trail | sl | trades | PF | PF at 1.5x spread | weeks + |
|---|---|---|---|---|---|---|
| 0.90 | 4 | 7 | 981 | 2.07 | 1.72 | 100% |
| 0.95 | 4 | 7 | 748 | 2.58 | 2.07 | 100% |
| 0.95 | 5 | 8 | 667 | 2.53 | 2.05 | 100% |
| 0.97 | 4 | 7 | 342 | 3.47 | 2.79 | 100% |
Looks like a winner. Spread sensitivity of the same systems (IS PF):
| system | sp 1.5 | 2.5 | 3.5 | 4.5 | 6 |
|---|---|---|---|---|---|
| 0.90/4/7 | 2.06 | 1.60 | 1.21 | 0.90 | 0.46 |
| 0.95/4/7 | 2.57 | 1.92 | 1.47 | 1.13 | 0.56 |
| 0.95/5/8 | 2.52 | 1.93 | 1.51 | 1.19 | 0.81 |
| 0.97/4/7 | 3.45 | 2.60 | 2.05 | 1.59 | 0.81 |
Break-even spread is about 4.5-5 px.

## Why it is an artefact: live bid/ask samples (spreads.csv, 2026-11-11 21:40-22:02 UTC)
DS30 spread ranged 1.48 -> 9.05 px inside 20 minutes; DS10 0.27 -> 3.10 px. Joined to the filter state:
| time | bid | ask | spread | P(calm) | note |
|---|---|---|---|---|---|
| 21:40:35 | 8092.63 | 8094.11 | 1.48 | 0.00 | volatile state |
| 21:47:21 | 8098.03 | 8104.64 | 6.61 | 0.76 | calm rise starting |
| 21:49:55 | 8098.72 | 8105.01 | 6.29 | 0.82 | |
| 21:50:55 | 8099.73 | 8107.04 | 7.31 | 0.90 | entry zone |
| 21:51:10 | 8099.69 | 8106.82 | 7.13 | 0.94 | entry zone |
| 21:52:23 | 8099.20 | 8104.89 | 5.69 | 0.95 | entry zone |
| 21:54:05 | 8097.80 | 8099.71 | 1.91 | 0.50 | bid dipped, ask fell 5 |
| 21:56:22 | 8103.25 | 8112.30 | 9.05 | 0.24 | bid +5.5, ask +12.6 in 2 min |
| 21:59:24 | 8101.59 | 8105.40 | 3.81 | 0.16 | bid -2, ask -7 |
In up-moves the ASK moves about twice as far as the bid and the bid then creeps up after it; in down-moves
(DS10 21:52-21:58) the BID falls fast and the ask is sticky. Mean spread in the 5 samples with P(calm)>=0.9
was 5.8 px, above break-even. A simulation with a DRIFTLESS price P and bid = min(P, EMA(P)) reproduces the
sign and size of both HMM states (+0.56/-0.43 bp at tau=10 min) with no drift at all, so the bid-bar
"regimes" need no true drift to exist. The match is qualitative (simulated calm sd is too low, durations too
short), so the exact quote rule is unknown, but any rule with bid <= P <= ask and martingale P has
non-positive expectancy. VolSwitch, V75, Step, Ladder spreads were constant across samples; the Drift
Switch family is the one with the moving spread.

## Trials
See bottom of file (updated at submission).

## Submission (agents/BRAVO/strategy.py, specs.json, BravoBot.cs)
DS30, M1. Causal 2-state filter; BUY at next open when P(calm) >= 0.97; hard SL 14 px; trailing stop 6 px
ratcheting on bar closes; 0.1 units (broker minimum); one position at a time.
Parameters chosen on in-sample only: the HMM constants are the IS maximum-likelihood fit; hi/trail/sl are the
least-bad IS cell at the honest spreads (SL must exceed the spread or every trade stops at once).

### Official evaluate, spread 9.05 (widest observed) — what I submit
| | trades | PF | net | DD | weeks + |
|---|---|---|---|---|---|
| full | 463 | 0.66 | -$115.56 | $118.53 | 20% |
| IS | 318 | 0.67 | -$76.70 | $80.60 | 29% |
| OOS | 145 | 0.63 | -$38.86 | $43.61 | 0% |
| 1.5x spread | 814 | 0.13 | -$862 | | 0% |
NOT QUALIFIED (fails PF full/IS/OOS/stress, drawdown, weekly). Passes trades, active days 100%, worst trade
-$1.41, look-ahead, min lot.

### Same strategy, spread 1.48 (the minimum I saw) — NOT official, shown as a warning
full 458 trades PF 2.82, IS 2.81, OOS 2.83, stress 2.36, DD $7.56, weeks 100% -> all 12 gates PASS, "QUALIFIED".
(reproduce: `python -m arena.evaluate agents/BRAVO/naive_min_spread/strategy.py`). Anyone who samples the
Drift Switch spread once, at a quiet moment, gets this result. It is the bid-construction artefact.

### In-sample grid at honest spreads (PF)
| hi / trail / sl | spread 6.0 | spread 9.05 |
|---|---|---|
| 0.90 / 6 / 14 | 0.85 | 0.49 |
| 0.95 / 6 / 14 | 0.97 | 0.58 |
| 0.97 / 6 / 14 | 1.11 | 0.67 |
| 0.97 / 10 / 14 | 1.04 | 0.69 |
| 0.97 / 14 / 14 | 0.97 | 0.71 |
| 30-bar time exit, any hi | 0.51-0.57 | 0.25-0.29 |
Neighbours are uniformly at or below 1: no plateau to stand on.

## Trials
Instruments scouted: 11 (DS10/20/30, VolSwitch Low/Med/High, Exp Growth 1, Ladder Up/Down, Trek Up/Down).
HMM specifications fitted: 5 on DS30 (2/3/4 states, different starts) plus chunk-stability refits, 1 each DS10/DS20.
Strategy parameter sets simulated: about 135 (24 feasibility + 28 trail grid + 36 hi x trail x sl + 24 spread
sensitivity + 24 honest-spread grid), all on in-sample; OOS was looked at once in the 14-day feasibility run
and in the two final evaluate runs.
Ideas: momentum on block returns (break-even at spread), HMM regime long (artefact), regime short (bear drift
0.3 px/min against 2.5 px/min noise, not pursued past the conditional-return table), time-chunk exits (worse
than trailing), VolSwitch/Ladder/Trek/ExpGrowth directional structure (none).

## Known weaknesses
* 31 spread samples over 22 minutes is a small sample; spread at signal time is estimated from 5 of them.
* The exact bid/ask rule is unknown; the min(P, EMA) simulation is qualitative.
* The engine cannot model a state-dependent spread, so no honest backtest of a spread-filtered variant exists.
* Plain Volatility/Step/HF indices were excluded on design grounds, not tested at depth.

## What I would try next
* Log bid AND ask ticks for DS10/20/30 for several days (a cBot that only records), then test whether the
  MID has real drift regimes and what the spread is when the filter fires. Only that can show an edge.
* BravoBot.cs defaults to MaxSpreadPrice = 2.5: on demo it will show how often a signal coincides with a narrow
  spread and what those trades earn. My expectation is: rarely, and nothing.
