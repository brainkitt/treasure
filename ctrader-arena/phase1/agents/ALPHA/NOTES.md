# ALPHA research log - FX / metals on Deriv cTrader ($30 account, minimum lot)

Final submission: **London-open breakout of the 00:00-08:00 (London time) range on EURUSD + GBPUSD**, 1000 units
(0.01 lot) per trade, hard SL <= 14 pips ($1.40), TP = 2 x SL, flat at 16:00 London.
Official result: **NOT QUALIFIED** - all quality gates pass (PF 2.05 / IS 2.06 / OOS 2.01 / stress 1.94, DD $6.95,
worst trade -$1.40, 75% of weeks profitable, no look-ahead) but the three sample-size gates fail
(60 trades < 150, 18 OOS trades < 40, active days 76% < 85%). I did not pad the system to pass them.

```
period 2026-09-21 -> 2026-11-11  (OOS from 2026-10-27)
full   trades=  60 PF=2.05 net=$35.97 win=55% DD=$6.95 worst=$-1.40 tr/day=1.3 active=76% wk+=75%
is     trades=  42 PF=2.06 net=$24.66 win=55% DD=$6.95 worst=$-1.40 tr/day=1.4 active=74% wk+=83%
oos    trades=  18 PF=2.01 net=$11.31 win=56% DD=$4.92 worst=$-1.40 tr/day=1.3 active=79% wk+=67%
stress trades=  60 PF=1.94 net=$33.73 win=53% DD=$7.29 worst=$-1.43 tr/day=1.3 active=76% wk+=75%
PASS: pf_full, pf_oos, pf_is, stress pf, max DD, worst trade, no look-ahead, min lot, weekly
FAIL: trades >= 150, oos trades >= 40, active days >= 85%
```

## 1. Data and cost facts (measured, not assumed)
| symbol | M1 history | spread used (widest seen) | min size (probed) | $ / pip at min | median daily range | spread / range |
|---|---|---|---|---|---|---|
| EURUSD (1) | 2026-09-21 -> 11-11, 53.8k bars, 45 day-rows | 1.3 pips | 1000 units | $0.10 | 62 pips | 2.1% |
| GBPUSD (2) | same span, 53.7k bars | 1.3 pips | 1000 units | $0.10 | 64 pips | 2.0% |
| USDJPY (4) | same span, 53.7k bars (tested, not traded) | 1.4 pips | 1000 units | $0.063 | 95 pips | 1.5% |
| XAUUSD (41) | M15 only | $0.29 | **1 oz** | $1 per $1 | $73 | 0.4% |
| US SP 500 (2517) | shared M1 from 09-10 | 0.36 pt | 0.1 unit | $0.10 / pt | ~80 pt | 0.45% |

* Spreads were sampled four times between 21:40 and 21:49 UTC on 2026-11-11 (10-20 minutes before the daily
  rollover, so on the wide side). I could not sample London hours: the session clock advanced only ~15 minutes.
  The London-morning spread is therefore unverified, and the cBot has a 2.0-pip spread filter.
* Min-lot probes (label `probe-ALPHA`, LIMIT BUY volume=1 at ~50% of price, all REJECTED, nothing was ever accepted):
  EURUSD/GBPUSD/USDJPY "minimum allowed volume = 1000.00"; XAUUSD "= 1.00"; US SP 500 and US Tech 100 "= 0.10".
* **XAUUSD is not tradable inside the gates**: 1 oz minimum means the $1.50 worst-trade cap is a $1.45 stop on an
  instrument that moves $73 a day. Every gold breakout test lost (PF 0.0-0.5) simply because the stop sits inside noise.
* FX has a daily break 21:00-21:10 UTC (22:00-22:10 after 1 Nov) and a 2-3 hour Sunday-evening session.

## 2. Hypotheses, stated before fitting
* H1 London-open breakout: EUR and GBP consolidate overnight in a thin market, stops rest outside that range, and the
  arrival of European liquidity at 08:00 London tends to carry the first decisive break. Pre-registered symbols: the
  three most liquid majors (EURUSD, GBPUSD, USDJPY) - chosen before any test was run.
* H2 London -> NY range breakout (08:00-13:00 range, break in NY hours).
* H3 quiet-hours mean reversion (fade Bollinger extremes in the Asian session / lunch / late NY).
* H4 momentum continuation after impulsive M5 / M15 bars; H5 the fade of the same bars.
* H6 time-of-day drift; H7 intraday time-series momentum (morning direction -> afternoon); H8 late-day reversal.
* H9 prior-day high/low break; H10 (off-turf) US SP 500 cash-open ORB, pre-market range break, short-horizon
  mean reversion - tested because its spread/range ratio is 5x better than FX.

## 3. Everything tried (about 390 parameter sets in 12 idea families)
Split: in-sample = first 70% of days (to 2026-10-26), OOS = 2026-10-27 onward. Costs always included.
| # | idea | data | sets | in-sample result | verdict |
|---|---|---|---|---|---|
| 1 | Impulse-bar continuation / fade, M5 (H4/H5) | EURUSD M5 | 9 | mean follow-through -0.9..+0.2 pips vs 1.3 pip cost, |t| < 1.3 | dead |
| 2 | Bollinger mean reversion in 6 hour-windows (H3) | EURUSD M5 | 24 | PF 0.38-1.02 | dead: target is the size of the spread |
| 3 | Session ORB, 7 window definitions x 4 exits | EURUSD M5 | 28 | London PF 1.1-2.3; NY-range break PF 0.14-0.38 | London kept; NY dead |
| 4 | London ORB variants on M1 engine | EURUSD M1 | 27 | PF 1.26-3.1 for 0-7 / 0-8 ranges | kept |
| 5 | London / NY / Asian ORB across 9 symbols | M15 | 63 | EUR, GBP positive; JPY marginal; CHF, GBPJPY, EURJPY, CAD negative; all 8 FX pooled PF 1.1-1.3 | edge is specific to EUR/GBP majors |
| 6 | Intraday momentum A->B windows, pooled 8 pairs (H7) | M15 | 19 | 07-12 -> 12-16 gross +5 pips, t=2.7, net PF 1.42 | not robust, see 7 |
| 7 | Neighbours of 6, strength buckets, per symbol | M15 | 46 | 07-11, 07-13 and 08-12 starts all drop to PF 0.6-1.0 | dead: a sharp peak, not a plateau |
| 8 | Late-day reversal (H8) | M15 | 6 | PF 1.07-1.45 IS, 0.36-0.92 OOS | dead |
| 9 | Big M15 bar follow-through; prior-day H/L break (H9) | M15 | 8 | net PF 0.5-0.7 | dead |
| 10 | Hour-of-day drift (H6) | M15, 8 pairs | - | only persistent effect is 21:00-23:00 London (t up to 5.7) | **rejected as an artifact**, see below |
| 11 | US SP 500: NY ORB 5/15/30/60 min, pre-market, London range | 2517 M1 | 41 | PF 0.6-1.5, mostly ~1.0 | dead; M1/M5 autocorrelation flips sign between IS and OOS |
| 12 | Pooled London ORB grid: majors, then EUR+GBP on M1; neighbours; USDJPY | M15 + M1 | 54 + 30 + 33 + 8 | EUR+GBP PF 1.68-3.1 in all 30 IS combinations | **final** |

Two rejections worth spelling out:
* **Rollover drift is a bid-bar artifact.** GBPUSD, GBPJPY and EURJPY "rise" in the hour after the daily break with
  t-stats of 4-5 in both halves. Bars are BID only and the spread widens at rollover, so the bid dips and recovers.
  The engine's constant spread would let a strategy buy that dip at a normal ask. That is exploiting a simplification
  of the engine, not a market edge, so no entry of the final system is anywhere near those hours.
* **USDJPY dropped on in-sample evidence only.** With the identical rule on M1 data its IS PF is 1.04 (0.90-1.27
  across 8 neighbours, n=15). The M15 proxy had flattered it (1.2-2.3). It also fits the hypothesis: Tokyo is JPY's
  active session, so its 00:00-08:00 range is not a quiet consolidation. I did not look at its OOS result.

## 4. Final rule and how the parameters were chosen
All times Europe/London (DST handled by time-zone conversion), identical for both legs:
1. Range = high/low of the M5 bars starting in [00:00, 08:00).
2. Between 08:00 and 11:00 the first M5 bar that closes outside the range triggers a market order in that direction
   at the next bar open. One trade per symbol per day.
3. SL = clip(0.75 x range, 5, 14) pips; TP = 2 x SL; time exit 16:00. No overnight holds (0 overnight trades).

Parameters come from the in-sample grid on M1 data (30 combinations of signal TF 5/15, range end 07:00/08:00, entry
end 10:00/11:00, five SL/TP pairs). **Every one of the 30 has IS PF between 1.68 and 3.12.** I took a central setting
(IS PF 2.07), not the best one (3.12).

Disclosure: OOS columns were printed alongside IS in the scouting runs (families 3-7), so I had seen that the London
ORB was positive out-of-sample on EURUSD before the final grid. The final grid itself was printed IS-only. The OOS
figure is therefore a confirmation I had partly anticipated, not a blind test.

## 5. Robustness (EURUSD + GBPUSD, M1 engine, one parameter changed at a time)
| change | IS n | IS PF | OOS n | OOS PF |
|---|---|---|---|---|
| **BASE** | 42 | 2.06 | 18 | 2.01 |
| range end 07:00 (entries to 10:00) | 42 | 2.08 | 22 | **1.16** |
| range end 07:30 | 42 | 1.93 | 20 | **1.33** |
| range end 08:30 | 41 | 1.90 | 18 | **1.11** |
| range end 09:00 | 39 | 1.68 | 18 | **0.77** |
| range start 01:00 / 02:00 / 03:00 | 43 / 45 / 46 | 2.39 / 2.31 / 2.00 | 19 / 21 / 21 | 2.31 / 1.85 / 1.83 |
| entry end 10:00 / 12:00 / 13:00 | 38 / 44 / 45 | 2.06 / 2.08 / 2.12 | 18 / 19 / 23 | 2.01 / 1.79 / 2.04 |
| exit 14:00 / 15:00 / 17:00 / 18:00 / 20:00 | 42 | 2.16 / 2.12 / 1.96 / 1.97 / 2.13 | 18 | 2.12 / 2.09 / 2.03 / 1.94 / 1.90 |
| SL mult 0.5 / 0.6 / 0.9 / 1.0 / 1.25 | 42 | 2.73 / 2.15 / 2.03 / 2.03 / 2.03 | 18 | 1.95 / 1.97 / 2.01 / 2.01 / 2.01 |
| TP mult 1.0 / 1.5 / 2.5 / 3.0 / 4.0 | 42 | 1.76 / 2.19 / 2.25 / 2.26 / 2.17 | 18 | 2.00 / 1.75 / 1.34 / 1.55 / 1.79 |
| signal TF 1 / 3 / 10 / 15 min | 42 / 41 / 40 / 39 | 2.23 / 1.86 / 1.78 / 2.06 | 19 / 18 / 18 / 18 | 1.98 / 2.23 / 1.33 / 1.25 |
| break buffer 0.5 / 1 / 2 pips | 40 | 2.15 / 1.77 / 1.69 | 18 / 18 / 17 | 1.52 / 1.51 / 1.47 |

In-sample the plateau is broad (1.68-2.73 in all 33 rows). Out-of-sample it is not: moving the range end by 30-60
minutes takes OOS PF from 2.01 to 0.77-1.33. On 18 trades that is what noise looks like, and it means the headline
OOS PF of 2.01 is the top of its neighbourhood. The SL multiplier is inert above 0.9 because the 14-pip cap binds.

The table and the checks below were produced with the research harness (`research/s9.py`), whose time exit is one
M1 bar later than the official strategy; its totals differ from the official run by a few cents (IS net 24.71 vs 24.66).

Other checks on the base system (60 trades):
* long 26 trades PF 1.95, short 34 trades PF 2.12; EURUSD 29 trades PF 2.14, GBPUSD 31 trades PF 1.98.
* exits: 21 TP (+$58.14), 24 SL (-$32.88), 15 time exits (+$10.80). Max 6 consecutive losses. Mean hold 3.5 h.
* weekly net (official trades.csv): +8.02, +1.52, +8.40, +8.69, -4.93, -1.97, +4.47, +11.76 (6 of 8 positive).
* placebo: same entry times and stops with the direction reversed gives PF 0.43; random direction (20 seeds) median
  PF 1.00, max 1.34. The result comes from the breakout direction, not from the SL/TP geometry.
* mean trade +$0.60, t = 2.50 per trade, but the two legs are the same bet (they trade the same day 26 times, same
  direction 73%, P&L correlation 0.54). At day level: 34 days, t = 2.03, worst day -$2.80.
* bootstrap of trade P&L: PF 5% / 50% / 95% = 1.29 / 2.03 / 3.26; P(PF < 1.7) = 26%, P(PF < 1.0) = 0.5%.

## 6. Why the three gates fail, and why I left them failing
* One trade per symbol per day on two symbols gives 60 trades in 7.5 weeks. Trades occurred on 34 of 38 weekdays.
* **Active days >= 85% is unreachable for any weekday-only FX system on this sample**: the Sunday-evening session
  counts as a market day, so 38 weekdays / 45 day-rows = 84.4% even with a trade every weekday. Passing would need
  Sunday-evening entries, which are the widest-spread hours of the week and outside the hypothesis.
* More trades would have to come from adding legs. The legs I could add all have in-sample PF near or below 1
  (USDJPY 1.04 on M1; on the M15 proxy USDCHF 0.5-0.8, GBPJPY 0.5-0.7, EURJPY 0.8-1.1, USDCAD 0.8-1.7, AUDUSD 1.1-2.0), so they would
  buy the trade count with noise and lower the PF.

## 7. Known weaknesses
1. Small sample: 60 trades, 34 effective days, one 7.5-week market regime. The honest PF expectation is roughly
   1.3-1.8, not 2.05.
2. OOS result is sensitive to the range-end time (section 5).
3. Symbol selection: 2 of 8 scanned FX pairs are traded. EUR and GBP were named in the hypothesis beforehand and
   USDJPY was dropped in-sample, but the pooled all-pairs PF of 1.1-1.3 shows how much of the edge is pair-specific.
4. London-hours spread is unverified (section 1). At 1.5 x spread the PF is 1.94, so there is headroom.
5. Both legs are long/short USD together: a wrong day costs up to $2.80, a bad week about $5.
6. Engine does not model slippage on the market entry at a volatile open, nor swaps (irrelevant: no overnight holds).

## 8. cBot
`AlphaBot.cs` - one instance per symbol (EURUSD and GBPUSD charts, any timeframe; the bot reads M5 bars itself), all
default parameters. Hard SL/TP on every order, 2.0-pip spread filter, one position per symbol, $3 daily loss limit,
$9 equity draw-down kill-switch that closes positions and stops the bot, 16:00 London time exit.

## 9. What I would try next
* Forward-test on demo for 8+ weeks before believing the PF; log the real 08:00-11:00 London spread.
* Download 6-12 months of M1 for EURUSD/GBPUSD: the rule has 5 parameters and one trade a day, so only more calendar
  time can validate it. Re-check the range-end sensitivity on that sample.
* Test the same rule on EURGBP, EURCHF and GBPCHF only if their London-hours spread is under 1.5 pips.
* US SP 500 at 0.1 unit has the best cost structure on this account; it needs a regime-aware idea, since simple
  momentum and mean reversion each worked in only one half of the sample.

---
# Round 2 - pre-sample validation: the London breakout is REJECTED

Method: 52 M_5 calls per symbol gave EURUSD and GBPUSD M5 history back to 2025-12-31. The exact round-1 rule,
parameters frozen, was run through `arena.engine.simulate` on the M5 frame (entry at the next M5 open) for
2026-01-01 .. 2026-09-20 (`research/r2.py`, `research/r3.py`). The M5 engine reproduces the official M1 result on
the official window (EURUSD PF 2.12 vs 2.14 on M1), so the comparison is like for like.

| pre-sample 2026-01-01..09-20 | trades | PF | net | max DD |
|---|---|---|---|---|
| EURUSD | 137 | 1.02 | +$2.32 | $20.56 |
| EURUSD long / short | 67 / 70 | 1.18 / 0.89 | | |
| GBPUSD (1.4-pip spread) | 148 | 0.90 | -$12.88 | $28.40 |
| GBPUSD long / short | 74 / 74 | 1.10 / 0.73 | | |
| **portfolio** | **285** | **0.95** | **-$10.56** | **$47.57** |
| portfolio at 2.0-pip spread | 285 | 0.88 | -$28.27 | $47.85 |

Monthly portfolio PF Jan..Sep: 0.42 / 0.55 / 0.75 / 1.45 / 1.39 / 1.24 / 1.30 / 1.11 / 0.58. Day-level t = -0.31 (164 days).

Sensitivity surface on the pre-sample (portfolio PF; rows = range end, columns = entry-window length 1/2/3/5 h):
```
06:00  0.88 0.94 0.96 0.92      08:00  0.97 0.99 0.95 1.03
06:30  0.84 0.88 1.00 0.97      08:30  1.15 0.99 0.96 0.95
07:00  0.90 0.96 0.96 0.94      09:00  1.03 0.98 0.92 0.91
07:30  0.85 1.00 0.92 0.95      10:00  0.61 0.71 0.83 0.75
```
Other knobs: SL mult 0.5/1.0 -> 0.93/0.92; TP mult 1/1.5/3 -> 0.87/0.86/0.90; exit 13:00/20:00 -> 0.72/0.92;
range start 02:00/04:00 -> 1.05/0.97. Fading the break instead: PF 0.76.

Conclusion: there is no plateau anywhere and no edge in either direction. The PF 2.05 on the official window was
seven lucky weeks; a $30 account running this rule from January would have drawn down $47. **The London breakout is
rejected.** Breadth to other pairs and a portfolio risk rule were not pursued: the rule fails on its home pairs.

Spreads sampled 2026-11-12 ~07:45 UTC (London morning, the session traded): EURUSD 1.2 pips (twice),
GBPUSD 1.4 pips (twice), USDJPY 1.4, AUDUSD 1.0. GBPUSD is wider than the 1.3 used in round 1 -> specs.json now 1.4.

---
# Final round - one pre-sample-first search for passive (limit-order) mean reversion: nothing survives TRAIN

Split fixed in advance: TRAIN 2026-01-01..06-30, VALIDATE 2026-07-01..09-20, FORWARD = official M1 window (untouched).
Data: the EURUSD / GBPUSD M5 history already downloaded. Spreads 1.3 / 1.4 pips. 1000 units, stop <= 14 pips.

Hypothesis: short-horizon FX mean reversion exists in mid prices (CHARLIE's finding) but is smaller than the spread
for a market entry. A resting LIMIT order at a band or range extreme is filled only when the ask trades down to it
(engine `kind=1`), so the entry is not chased and the engine supplies the adverse selection. No order may hold
across 20:45-22:30 UTC (rollover artifact). Long and short sides simulated as separate books.

| family (script) | grid on TRAIN | configs | PF > 1.0 | PF > 1.2 | median PF | best PF | zero-spread check |
|---|---|---|---|---|---|---|---|
| A: fade MA(20) +/- k x mean-range band, TP toward the mean (`research/r4.py`) | TF 5/15 x k 1.5/2/3 x TP 0.5/1 x SL 2/4 x 3 hour-windows | 72 | 0 | 0 | 0.68 | 0.94 | reference config PF 0.97 at zero spread |
| B: fade the rolling 4h/12h/24h range extreme on M15 (`research/r5.py`) | N 16/48/96 x offset 0/3 pips x TP 0.25/0.5 range x SL 8/14 x 3 hour-windows | 72 | 6 | 0 | 0.82 | 1.12 (98 trades) | best config PF 1.37 at zero spread |

| stage | result |
|---|---|
| TRAIN | 144 configurations, none above PF 1.2; the best (1.12 on 98 trades) is what the top of 72 noisy draws looks like |
| VALIDATE | not run - nothing earned it |
| FORWARD | not run for these families - the official window was left untouched |

Reading: in this engine a limit buy fills when the bid is already one spread below the limit, so a passive entry
still starts one spread under water; the fills are the adversely selected ones. Family A has no edge even at zero
spread (0.97). Family B shows the mid-price effect (1.37 at zero spread) but 1.3-1.4 pips eats all of it.

## Final state of the submission
* Nothing survived, so the submission of record is still the London breakout (strategy.py, AlphaBot.cs, specs.json
  consistent with each other), **marked REJECTED** in both file headers. It must not be traded.
* Official re-run with the supervisor's new day definition and GBPUSD at 1.4 pips:
  full 60 trades PF 2.04, IS 2.06, OOS 2.01, stress 1.94, DD $6.96, active 89%, weekly 75%; fails trades >= 150 and
  OOS trades >= 40 -> NOT QUALIFIED. At spread x1.55 (2.0 / 2.2 pips): full PF 1.94, IS 1.91, OOS 1.99.
* Those numbers describe 7.5 weeks. The same rule over the previous 8.7 months: 285 trades, PF 0.95, DD $47.57.

## Trials, all rounds
Round 1 ~390 parameter sets in 12 families; round 2 pre-sample check ~45 (surface + knobs, diagnostic only);
final round 144 in 2 families. Total ~580. Zero survive out-of-sample at the costs of this account.

## Verdict
No FX or metals system from this research deserves a forward test. At 1.2-1.4 pips on EURUSD/GBPUSD and a 1-oz
minimum on gold, every M1-M15 idea tested is either flat before costs or smaller than the spread. The one thing
with a favourable cost structure on this account is US SP 500 at 0.1 unit (spread about 0.45% of the daily range
versus 2% for EURUSD); it showed no stable edge in round 1 and would need its own pre-sample-first study.
