# DELTA research log — indices / crypto / commodities

**Bottom line: NOT QUALIFIED, and I do not believe PF >= 1.7 is honestly reachable on my turf with a $30
account.** The submission is the one effect that survived a 5.5-month pre-sample test *and* a forward test:
fading failed range breakouts of the US SP 500 CFD in the European morning. Honest profit factor ~1.3-1.5.

## Official result (`python -m arena.evaluate agents/DELTA/strategy.py --out submissions/DELTA`)

```
period 2026-09-10 -> 2026-11-11  (OOS from 2026-10-23)
full   trades=  74 PF=1.46 net=$10.56 win=70% DD=$3.67 worst=$-1.40 tr/day=1.4 active=78% wk+=80%
is     trades=  55 PF=1.61 net=$8.97 win=71% DD=$3.67 worst=$-1.40 tr/day=1.5 active=78% wk+=71%
oos    trades=  19 PF=1.19 net=$1.59 win=68% DD=$3.52 worst=$-1.40 tr/day=1.1 active=76% wk+=75%
stress trades=  73 PF=1.38 net=$9.07 win=68% DD=$4.76 worst=$-1.40 tr/day=1.4 active=78% wk+=80%
  [FAIL] pf_full >= 1.7            [FAIL] pf_oos >= 1.5        [PASS] pf_is >= 1.5
  [FAIL] pf under 1.5x spread >= 1.4   [FAIL] trades >= 150    [FAIL] oos trades >= 40
  [FAIL] active days >= 85%        [PASS] max drawdown <= $9   [PASS] worst trade <= $1.50
  [PASS] no look-ahead             [PASS] min lot respected    [PASS] weekly PF >= 1.0 in >= 70% of weeks
NOT QUALIFIED
```

## The strategy ("PreOpenFade", one leg: US SP 500, id 2517)

* Signals on completed M15 bars whose open is between 03:00 and 09:30 New York time (DST-aware).
* Close crosses above the highest high of the previous 32 M15 bars (8 h) -> SHORT; crosses below the lowest
  low -> LONG. Market order at the next M1 open.
* SL = min(2 x ATR14(M15), 14 pts), TP = 1 x ATR14(M15), time exit after 240 min, one position at a time.
* 0.1 units (broker minimum): worst planned loss $1.40; typical SL ~$0.9, TP ~$0.45, win rate ~70%.

**Hypothesis (written before fitting):** in the European morning the S&P CFD has no US cash market and almost
no US news; range breakouts there are liquidity events and revert. Supporting statistic measured first:
variance ratio of 60-min vs 1-min returns in that window = 0.88 (mean-reverting), against 0.98 in US cash
hours and 1.16 in the Asian session (in-sample part of the M1 window).

## Data

| symbol | period | span | use |
|---|---|---|---|
| US SP 500 (2517) | M_1 | 2026-09-10 .. 2026-11-11, 60,803 bars, no holes | official window |
| US SP 500 (2517) | M_15 | 2026-03-26 .. 2026-09-09 (144 trading days) | **pre-sample**, used to choose parameters |
| US SP 500 (2517) | M_5 | 2026-09-29 .. 2026-11-11 | scouting |
| US Tech 100 (2518) | M_5 | 2026-09-29 .. 2026-11-11 | scouting / cross-check |
| BTCUSD (101) | M_5 | 2026-09-10 .. 2026-11-11 | scouting |

The 5.5 months of M15 history cost 12 API calls and turned out to be the most valuable thing I did: it killed
my best-looking idea (below) and is where the submitted parameters come from. Because the pre-sample lies
entirely before the official window, **the whole official window is effectively out-of-sample for this
strategy** (with the caveat in "Known weaknesses" #2).

## Minimum lots probed (LIMIT BUY, volume=1, ~50% below market, 2026-11-11)

| symbol | min units | $ per 1.0 price move | verdict for a $30 account |
|---|---|---|---|
| US SP 500 | 0.1 | $0.10 | OK: 14-pt stop = $1.40 |
| US Tech 100 | 0.1 | $0.10 | too coarse: M5 range ~25-50 pts, cap is 15 pts |
| Wall Street 30 | 0.1 | $0.10 | too coarse: 15 pts = 0.03% |
| US Small Cap 2000 | 0.1 | $0.10 | affordable, but spread 0.30 is ~12% of an M15 ATR |
| Germany 40 | 0.1 | ~$0.12 | too coarse |
| UK 100 | 0.1 | ~$0.13 | not tested |
| Japan 225 | 10 | ~$0.06 | spread 38.7 off-hours, infeasible |
| BTCUSD | 0.01 (order was ACCEPTED, cancelled at once, confirmed no pending orders) | $0.01 | $150 stop = $1.50; see below |
| ETHUSD | 0.1 | $0.10 | spread 1.83 (8.8 bp) too wide |
| SOLUSD 0.5, XRPUSD 100, LTCUSD 1 | | | spreads 10-37 bp, rejected on cost |
| US Oil / UK Brent | 1 | $1.00 | spread 0.105 (12 bp) |
| NGAS | 1000 | $1000 | infeasible ($1.50 = 0.0015, spread is 0.03) |

Spreads sampled (price units, 2026-11-11 21:40 and 21:49 UTC): SP500 0.36, NAS 0.90, DJ 1.80, RUT 0.30,
DE40 8.8, UK100 3.36, JP225 38.7, BTC 18.4-19.1, ETH 1.60-1.83, SOL 0.14, XRP 0.0011, LTC 0.187, Oil 0.105,
Brent 0.105, NGAS 0.03.

## Everything tried (about 3,440 parameter sets across 14 ideas)

| # | idea | data | sets | outcome |
|---|---|---|---|---|
| 1 | US cash-open ORB (5/15/30 min), breakout and fade, TP 0/2R/4R | SP, NAS M5 | 36 | ~32 trades each, IS and OOS disagree in sign. Noise. |
| 2 | Nasdaq -> S&P lead-lag and residual mean reversion | M5 | 4 stats | lag-1 cross-correlation 0.03-0.04, residual z-score predicts nothing. Dead. |
| 3 | Time-of-day drift, first-30-min -> last-30-min, overnight -> day | SP M1 + 114 days of M15 | stats | no hour with stable sign in both halves; f30->l30 sign agreement 40%. Dead. |
| 4 | BTC M5 Donchian breakout / fade, z-score fade, time-series momentum | BTC M5 | 216 | best family (fade 8-24 h extremes) PF 1.25-1.30 IS and OOS, but drawdown $27-46 at 0.01 BTC. Unusable on $30. |
| 5 | SP Donchian trend/fade + z-score fade/trend x 6 sessions x M5/M15 | SP M1 | 576 | median IS PF 0.89; correlation between IS and OOS PF across 344 sets = 0.02 (pure noise) except one cluster -> #6 |
| 6 | **Asian-session breakout momentum** (18:00-03:00 NY) | SP M1 | ~110 | Looked like the winner: PF 1.78 (IS 1.74 / OOS 1.83), 96% active days incl. Sundays, positive in 9 of 10 weeks, survives 3x spread. **Rejected**: on the pre-sample (Mar 26 - Sep 9, 300 trades) PF = 0.83, negative in 4 of 7 calendar months; all 30 neighbours 0.69-1.05. Profit was 86% from longs in a rising two-month tape; NAS cross-check PF 1.05. |
| 7 | Fade families on the pre-sample, 8 sessions | SP M15 pre | 1,944 | only the European-morning fade is stable in both halves -> submitted idea |
| 8 | Trend families on the pre-sample, 6 sessions | SP M15 pre | 360 | medians 0.67-1.11, nothing stable in both halves |
| 9 | Limit-order fade at the range edge (European morning) | SP M15 pre | 48 | PF 1.0-1.26, weaker than waiting for the close. Dropped. |
| 10 | Volatility filter (skip when ATR > 1.2x its 5-day median) | SP M15 pre | 33 | pre-sample PF 1.47 -> 1.75. **Forward test: PF 0.92.** Overfit, dropped. This is recorded as a failure of mine: it was the one refinement I tried and it did not survive. |
| 11 | Breakout-size, 2-day trend context, day-of-week filters | SP M15 pre | 18 | unstable between halves, not used |
| 12 | Exit variants (SL 1-4 ATR, TP 0.5-2 ATR, hold 1-8 h) | SP M15 pre | 30 | broad plateau, see table |
| 13 | Pre-open fade on Nasdaq as cross-check | NAS M5 | 3 | PF 1.10 / 0.89 / 1.85 on 28-41 trades: inconclusive |
| 14 | Sim granularity check (M15-bar sim vs M1 sim, same window) | SP | 3 | identical within 0.02 PF, so pre-sample numbers are comparable |

## Pre-sample (2026-03-26 .. 2026-09-09, M15 bars) — where the parameters come from

Halves split at 2026-06-18. SL 2 ATR, TP 1 ATR, hold 4 h:

| N | trades | PF | first half | second half | max DD |
|---|---|---|---|---|---|
| 12 | 276 | 1.24 | 1.23 | 1.26 | $7.1 |
| 20 | 217 | 1.48 | 1.38 | 1.62 | $5.5 |
| 24 | 198 | 1.62 | 1.55 | 1.71 | $5.7 |
| 28 | 178 | 1.58 | 1.58 | 1.58 | $6.0 |
| **32** | 168 | 1.47 | 1.44 | 1.50 | $6.0 |
| 36 | 158 | 1.49 | 1.41 | 1.57 | $6.4 |
| 40 | 154 | 1.46 | 1.35 | 1.60 | $5.7 |
| 48 | 140 | 1.56 | 1.36 | 1.79 | $5.7 |
| 64 | 104 | 1.56 | 1.35 | 1.78 | $3.7 |

N = 32 was taken as the middle of the 20-64 plateau, not the peak (24). Spread stress on the pre-sample
(N = 32): x1.5 -> 1.43, x2 -> 1.36, x3 -> 1.23. Session edges: 04:00 start 1.48, 09:00 end 1.43, extending to
10:00 or 11:00 (into the US open) drops it to 1.20 / 1.15, which fits the hypothesis.

## Neighbour robustness: pre-sample vs official window

| variant | pre-sample PF / n | official window PF / n | IS | OOS |
|---|---|---|---|---|
| N=20 | 1.48 / 217 | 1.12 / 88 | 1.34 | 0.81 |
| N=24 | 1.62 / 198 | 1.13 / 85 | 1.37 | 0.81 |
| N=28 | 1.58 / 178 | 1.35 / 78 | 1.53 | 1.07 |
| **N=32 (submitted)** | 1.47 / 168 | **1.46 / 74** | 1.61 | 1.19 |
| N=36 | 1.49 / 158 | 1.41 / 72 | 1.51 | 1.25 |
| N=40 | 1.46 / 154 | 1.52 / 69 | 1.54 | 1.48 |
| N=48 | 1.56 / 140 | 1.36 / 63 | 1.34 | 1.41 |
| SL 1.5 ATR | 1.37 / 174 | 1.36 / 75 | 1.47 | 1.17 |
| SL 3 ATR | 1.44 / 160 | 1.18 / 70 | 1.18 | 1.19 |
| TP 0.75 ATR | 1.27 / 177 | 1.44 / 75 | 1.53 | 1.29 |
| TP 1.5 ATR | 1.51 / 160 | 1.43 / 69 | 1.34 | 1.66 |
| hold 2 h | 1.44 / 170 | 1.34 / 74 | 1.45 | 1.15 |
| hold 6 h | 1.47 / 168 | 1.34 / 74 | 1.38 | 1.25 |

Every one of the 13 neighbours is above 1.0 on both samples; none reaches 1.7 on both.

## Combined evidence (pre-sample + official window, 7.5 months, 242 trades)

PF 1.47, win rate 71%, net +$35.5 at 0.1 units. By month: Mar 1.28, Apr 1.22, May 2.42, Jun 1.36, Jul 1.96,
**Aug 0.85**, Sep 1.90, Oct 1.20, Nov 1.46 (8 of 9 positive). Trade-level bootstrap of the PF:
5% / 50% / 95% = 1.16 / 1.47 / 1.89; P(PF <= 1) = 0.2%; **P(PF >= 1.7) = 17%**.

## Known weaknesses

1. **Does not meet the brief.** PF 1.46 not 1.7; 74 trades not 150; it only trades the European morning, so
   it cannot trade on the Sunday-evening session that the engine counts as a market day (9 of 54 days). It
   traded on 42 of 45 weekdays. With one index leg the 85% gate is unreachable by construction.
2. **The official window is not perfectly clean.** I ran families #5 and #6 on it before I had the
   pre-sample, and I picked N = 32 (plateau middle) after having seen that N = 24 (pre-sample best) did
   poorly forward (1.13). Treat 1.46 as slightly optimistic; the neighbour average on the window is ~1.33.
3. **OOS slice is 19 trades** (PF 1.19). That is not evidence of anything on its own.
4. **Spread was only sampled at ~21:45 UTC** (0.36, twice). The session clock did not advance during my run,
   so I could not sample the 08:00-14:30 UTC window in which the strategy trades. If the real spread there
   is 2x, expect PF ~1.3.
5. Losses are ~1.6x the size of wins (win rate carries it). Three losses in a row cost ~$3; worst day -$2.42.
6. Scheduled US data at 08:30 NY falls inside the window; a large surprise gaps through the stop
   (worst observed -$1.43 on the pre-sample vs -$1.40 planned).
7. One instrument, one regime family (mean reversion). August 2026 was a losing month.
8. Swaps are irrelevant here (average hold 47 min, 0 overnight trades).

## cBot

`DeltaBot.cs` — attach to US SP 500, M15, defaults as in the header comment. Not compiled here (no cTrader
toolchain in the sandbox); it uses only `cAlgo.API` calls. Differences from the Python engine: the time exit
fires at 240 min after entry (engine: close of the 240th M1 bar); the daily loss limit ($3) and the $9 equity
kill switch do not exist in strategy.py — neither would have triggered in the official window
(worst day -$2.42, max drawdown $3.67).

## What I would try next

* A second, weakly correlated leg with the same "off-home-session fade" logic, validated the same way
  (cheap M15 history first, M1 only if it survives): UK 100 or Germany 40 in the US afternoon, gold in the
  late-US session. This is the only honest route I see to 150 trades and more active days.
* Sample the SP 500 spread between 08:00 and 14:30 UTC before any forward test.
* Skip entries in the 15 minutes before 08:30 NY on scheduled-release days.
* Forward test at 0.1 units for 8+ weeks before believing anything beyond PF 1.2.

Research scripts are in `research/` (s1-s17, in the order run); `lib.py` and `fam.py` are helpers.

---

# Round 2 (supervisor objectives 1-4)

**Outcome: nothing new was adopted. The strategy, parameters and cBot are unchanged from round 1; only the
M1 history is longer. Round 2 made me *less* confident in the edge, not more.**

## Official result after round 2

```
period 2026-08-25 -> 2026-11-11  (OOS from 2026-10-19)
full   trades=  95 PF=1.43 net=$12.76 win=71% DD=$3.67 worst=$-1.40 tr/day=1.7 active=93% wk+=83%
is     trades=  70 PF=1.43 net=$8.79 win=70% DD=$3.67 worst=$-1.40 tr/day=1.8 active=92% wk+=75%
oos    trades=  25 PF=1.41 net=$3.98 win=72% DD=$3.52 worst=$-1.40 tr/day=1.4 active=94% wk+=100%
stress trades=  94 PF=1.37 net=$11.27 win=69% DD=$4.76 worst=$-1.40 tr/day=1.6 active=93% wk+=83%
FAIL: pf_full, pf_oos, pf_is, stress pf, trades >= 150, oos trades >= 40.   PASS: the other six.
NOT QUALIFIED
```

## 1. Siblings — the effect does NOT replicate (rules frozen: N=32, SL 2 ATR, TP 1 ATR, 4 h, no refit)

SL cap per index = $1.40 / (0.1 units x USD per point): S&P and Russell 14.0 pts, UK 100 10.7 pts (GBPUSD 1.31).

| index | window (NY) | pre-sample | spread used | trades | PF | halves | verdict |
|---|---|---|---|---|---|---|---|
| US SP 500 | 03:00-09:30 | Mar 26 - Sep 9 | 0.36 | 168 | 1.47 | 1.44 / 1.50 | (submitted) |
| US Small Cap 2000 | 03:00-09:30 | Mar 26 - Sep 9 | 0.30 | 212 | **1.02** | 0.98 / 1.08 | fails |
| US Small Cap 2000 | same, zero spread | | 0 | 214 | 1.08 | 1.04 / 1.14 | fails even gross |
| US Small Cap 2000 | N = 20 / 24 / 48 / 64 | | 0.30 | 121-256 | 0.96 / 0.91 / 0.94 / 1.07 | | fails |
| UK 100 | 18:00-03:00 (Asian session) | Jun 18 - Sep 9 | 3.36 | 100 | **0.51** | | fails |
| UK 100 | same, hypothetical 1.0 spread | | 1.0 | 99 | 0.79 | | fails |
| UK 100 | 03:00-09:30 and 12:00-18:00 | | 3.36 | 99 / 25 | 0.49 / 0.61 | | fails |

Not tested, ruled out by arithmetic at 0.1 units: US Tech 100 (M15 ATR ~45 pts pre-open, 2 ATR = $9),
Wall Street 30 (~32 pts, 2 ATR = $6.4), Germany 40 (spread 8.8 pts off-hours, sampled twice). UK 100's
off-hours spread (3.36 pts, sampled twice) is half of its quiet-session M15 ATR (~7 pts), so a fade there
cannot work regardless.

**What this means.** I predicted that a real effect should show up on siblings. Russell is ~0.8 correlated
with the S&P in those hours and shows nothing, even before costs. So either the effect is specific to the
S&P contract, or the S&P result is partly luck from the ~4,900 parameter sets I have now run. I cannot tell
which. No multi-leg portfolio is possible; trade count stays single-leg.

## 2. Exits — the exit is not the weak part; the edge itself is thin

Excursion profile after a fade entry, S&P pre-sample, 195 signals, in ATR units, signed in trade direction:

| M15 bars held | mean | median | % positive | mean MFE | mean MAE |
|---|---|---|---|---|---|
| 1 | +0.09 | +0.05 | 51% | +0.74 | -0.65 |
| 2 | +0.17 | +0.10 | 54% | +1.04 | -0.94 |
| 4 | +0.06 | +0.11 | 53% | +1.49 | -1.33 |
| 8 | +0.08 | +0.35 | 59% | +2.22 | -2.14 |
| 16 | -0.21 | 0.00 | 50% | +3.43 | -3.47 |
| 24 | -0.46 | -0.36 | 47% | +4.60 | -4.89 |

The reversion is worth about 0.1-0.17 ATR (0.5-0.8 pts, against a 0.36 spread), peaks after 30 minutes and
is gone within two hours. MFE and MAE are symmetric. The 1 ATR target / 2 ATR stop harvests that small drift
with a high hit rate; it does not create edge.

Exit variants expressible in the engine, pre-sample vs forward (official window before extension):

| exit | pre-sample PF (halves) | forward PF (IS / OOS) | adopted |
|---|---|---|---|
| **TP 1 ATR, SL 2 ATR, 4 h (baseline)** | 1.47 (1.44 / 1.50) | 1.46 (1.61 / 1.19) | kept |
| TP at 25% / 33% / 50% / 100% of distance to range midpoint | 1.34 / 1.41 / 1.38 / 1.38 | 1.49 / 1.69 / 1.27 / 0.97 | no |
| hold 30 min / 1 h / 2 h | 1.17 / 1.27 / 1.44 | 1.43 / 1.55 / 1.34 | no |
| trailing stop 1 / 1.5 / 2 ATR, no TP | 1.13 / 1.12 / 1.19 | 1.02 / 0.91 / 1.50 | no |
| SL/TP 1/1, 1.5/1.5, 2/2, 3/1.5, 1/0.5, 1.5/2 ATR | 1.12 / 1.35 / 1.32 / 1.47 / 0.96 / 1.17 | 1.17 / 1.37 / 1.21 / 1.30 / 1.19 / 1.19 | no |
| ATR-expansion filter (round 1, threshold 1.2) | 1.75 | 0.92 | no (overfit) |

Nothing beats the baseline on the pre-sample, so nothing is adopted. "Midpoint 33%" scores 1.69 forward but
1.41 on the pre-sample; picking it would be choosing on the official window. A conditional time-stop ("exit
if not in profit after N bars") cannot be expressed in the arena engine (only SL / TP / max_bars / trail), so
it could not be scored officially; the profile shows trades that are negative after 2 bars end at -1.08 ATR on
average versus +0.55 for the rest, so it is the one idea here I would still test in a forward run.

## 3. Spreads

Three samples for the S&P (21:40, 21:49, 21:58 UTC on 2026-11-11): 0.36 each time. Russell 0.30 (x3),
UK 100 3.36 (x2), Germany 40 8.8 (x2). The session clock advanced only ~20 minutes over both rounds, so I
still have no sample inside 08:00-14:30 UTC. specs.json unchanged (0.36). At 2x spread the window PF is 1.30,
at 3x 1.27.

## 4. M1 history

Extended the S&P M1 series back from 2026-09-10 to 2026-08-25 (17 calls; 77,226 bars, one 5-hour hole on
2026-09-07, the US Labor Day early close). The API still returned data, so more is available; I stopped
there. **Caveat:** Aug 25 - Sep 9 lies inside the pre-sample the parameters came from, so about 16% of the
new official window is no longer out-of-sample. The clean forward segment is still Sep 10 - Nov 11
(74 trades, PF 1.46).

## Trials

Round 2 added about 45 parameter sets (15 sibling, 30 exit). Running total ~3,490 sets, 16 ideas.

## Round-2 verdict

Honest PF estimate is unchanged at roughly 1.3-1.5 on the S&P alone, but the failed Russell replication is
real evidence against it being a structural effect. Not qualified; not a candidate for more than a
small-size observational forward test. Round-2 scripts: `research/r2_1.py`, `research/r2_2.py`.

---

# Phase 2 (long-history brief, BRIEF2.md)

## P2.1 Frozen PreOpenFade on unseen history — IT FAILS

Data: US SP 500 (2517) M_15 downloaded as far back as the API has it: **2024-04-08 -> 2026-11-13**, 60,667 bars
(API returns nothing earlier; one hole 2024-04-08..04-19; ~70 calls, several lost to result-file name collisions
in parallel batches and re-fetched; `agents/DELTA/gaps.py` lists holes). The previously missing M_15 stretch
2026-09-11..10-28 was filled too.

Rule frozen exactly as phase 1 (N=32, 03:00-09:30 NY, SL min(2 ATR, 14), TP 1 ATR, 16 M15 bars), simulated on M_15
bars with the phase-2 engine, spread 0.36, 0.1 units. Everything before 2026-03-26 had never been looked at.

| segment | trades | PF | net $ | win | max DD $ | months + |
|---|---|---|---|---|---|---|
| **unseen 2024-04 .. 2026-03-25** | 848 | **0.89** | -34.12 | 61% | 42.17 | 33% |
| seen 2026-03-26 .. 2026-11-13 | 249 | 1.42 | +33.70 | 70% | 5.99 | 89% |
| unseen, zero spread | 852 | 1.01 | +2.75 | 65% | | 46% |
| unseen, 1.5x / 2x spread | 849 / 847 | 0.85 / 0.82 | | | | |

By half-year (entry date): 2024H1 0.94 (97) | 2024H2 0.79 (236) | 2025H1 1.10 (222) | 2025H2 0.81 (194) |
2026H1 1.03 (192) | 2026H2 1.37 (156).

**Verdict: the phase-1 lead was a 7-month artefact.** On two unseen years it has no edge even before costs
(PF 1.01 at zero spread). The failed Russell replication in round 2 was the correct warning. The rule is dropped;
no `prove`/session tweaks were tried on it (improving a rule with gross PF 1.0 would be curve fitting).
Script: `p2/a1.py` (core in `p2/core.py`). Trials so far in phase 2: 1 frozen rule (+3 spread levels).
