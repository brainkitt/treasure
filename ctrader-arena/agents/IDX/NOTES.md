# IDX (AGENT_01, US indices) — research log

**Bottom line.** QUALIFIED (score 72.4/100) with **IndexDipBuy**. It buys US SP 500 and US Small Cap 2000 after a 7-session
closing low and exits one session later, at a 0.75-ATR target or a 3-ATR stop. The edge is real in this sample. It
replicates on US Tech 100 with frozen parameters. It survives re-fitting in an anchored walk-forward and sits on a
broad parameter plateau. It is **not a $30 system**: the smallest balance that passes every gate at the 0.1-unit broker
minimum is **$700** (evaluator-recommended $1,128). A small-account variant (US Small Cap 2000 only) qualifies at **$250**.
The big caveat is that the whole sample (May 2024 to Nov 2026) is one bull market. Dip-buying is long-only and has
not been tested on data from a sustained bear market.

## Official result (`python -m arena.evaluate2 agents/IDX/strategy.py --out submissions/IDX`)
```
start balance $700.00  period 2024-05-02 -> 2026-11-17  (OOS from 2026-02-13)
full   trades=  220 PF=1.81 net=$243.47 (35%) win=63% exp=$1.107 t=3.25 DD=$48.58 worst=$-33.84 sharpe=1.56 tr/wk=1.7 swap=$-45.24
is     trades=  144 PF=1.64 net=$130.94 (19%) win=62% exp=$0.909 t=2.04 DD=$48.58 worst=$-33.84 sharpe=1.16 tr/wk=1.6 swap=$-28.55
oos    trades=   76 PF=2.19 net=$112.53 (16%) win=66% exp=$1.481 t=2.91 DD=$16.80 worst=$-12.24 sharpe=2.71 tr/wk=1.9 swap=$-16.69
stress trades=  220 PF=1.78 net=$237.35 (34%) win=63% exp=$1.079 t=3.17 DD=$52.61 worst=$-33.85 sharpe=1.52 tr/wk=1.7 swap=$-45.24
folds  2024-05-02:34tr PF0.99 $-0.38  2024-11-01:61tr PF1.41 $45.11  2025-05-09:28tr PF3.50 $43.05  2025-11-10:45tr PF1.92 $62.40  2026-05-15:52tr PF3.21 $93.27
MC DD  p50=$40.39 p95=$76.68 p99=$100.49
balance technical_min=$120.79 recommended_min=$1128.05 operating=$1692.08 margin=20.3
all 15 gates PASS -> QUALIFIED   score=72.4/100
```
At 3x spread the full-sample PF is 1.76. With the swap doubled (to ~15%/yr) it is 1.63.

## Strategy (identical in strategy.py and IdxBot.cs)
* H1 bars of the leg's own symbol. A **session** ends with the H1 bar that opens at 14:00 New York time (DST-aware).
  The session close is therefore the price at 15:00 NY, one hour before the cash close, while spreads are normal.
* **Signal:** the session close is <= the lowest of the last N=7 session closes (today included). LONG only.
* **Entry:** market order at the open of the next H1 bar (15:00 NY).
* **Exits:** SL = 3.0 x ATR14 and TP = 0.75 x ATR14. ATR14 is computed on session bars (session high/low and the
  previous session close). The time exit is the close of the 22nd H1 bar after the fill, i.e. the next session's
  15:00 NY close. Typical hold is ~1 day, one rollover; Friday entries hold through the weekend (3x swap).
* One position per index; volume 0.1 unit (broker minimum) on each.
* Legs: US SP 500 (2517) and US Small Cap 2000 (2521). They share parameters.

## Hypotheses (written before fitting) and what happened
| # | hypothesis / why an edge might exist | sets | result |
|---|---|---|---|
| A | **Overnight drift**: index returns accrue outside cash hours (inventory/risk premium). Long 18:00 NY -> 04/08/09 NY | 36 | SP PF 1.09-1.17, RUT 1.05-1.13, MID < 1. Real but tiny and pure beta. Rejected. |
| B | **Intraday momentum** (Gao et al.): return since prior cash close predicts the last cash hours | 27 | PF 0.79-1.04, if anything mild reversal. Dead. |
| C | **Generic H1 mean reversion** (z-score vs SMA, trend filter, both sides, 3 indices) | 216 | SP ~1.0, RUT 1.1-1.4 but unstable across folds. Rejected. |
| D | **Pre-US-open fade**. Correlation scan (~770 cells, IS/OOS): the move into 05-07 NY reverses into 08:00 NY, corr -0.15..-0.30 in BOTH halves and on all 3 indices. Turned into trades: | 432 | SP PF 1.2-1.3, RUT ~1.0, MID < 0.8. The correlation comes from a few big days and the tradable PF is weak. Rejected. |
| D' | **DELTA's round-1 PreOpenFade, frozen rules**, on 2.5 yr of SP M15. 2024-05..2026-03 is data DELTA never saw | 1 | **PF 0.74-0.86 in every pre-2026 half-year, 1.45 only in Mar-Nov 2026.** The round-1 edge was regime-specific. This disproves it as a durable edge. |
| E | **Overnight long after a down cash session** | 144 | SP PF up to 1.28, RUT 1.1-1.2. MID loses badly at the 18:00 reopen (quote artifact, see weaknesses). Rejected as too weak. |
| F | **European-session breakout fade** with a volatility filter (H1) | 1728 | Medians ~1.1 IS and OOS. Rejected. |
| G | **High-volatility US-session momentum** (corr +0.14..0.23 IS) | 1728 | Medians < 1 once traded. Rejected. |
| **H** | **Short-horizon reversal after selling pressure (dip-buy)**. Liquidity providers are paid for absorbing forced/impatient selling (Lehmann 1990, Nagel 2012 "evaporating liquidity"). The premium is larger when volatility is high, and the long side adds the equity drift | d1 288, d2 432, d3 875, d4 180 | Positive on all 3 indices, IS and OOS; see below. **Adopted.** |

## Trying to disprove H (the adopted idea)
1. **Is it just beta?** I used the same exits but entered EVERY day: SP PF 1.06-1.15, RUT 0.89-1.01, MID 0.73-0.77, NAS
   1.03. Dip-day entries give PF 1.3-2.9. The conditioning adds a real edge on top of the drift.
2. **Replication on an index never used for fitting:** US Tech 100 with frozen params gives PF 1.64 (IS 1.97 / OOS 1.26)
   on 109 trades, and all 5 folds are > 1 (1.45 / 1.96 / 4.01 / 1.64 / 1.15). Neighbours N=6/8 give 1.54/1.64.
3. **Mirror test:** shorting 7-session highs gives PF 0.62-0.72 (SP, RUT, NAS). The effect is asymmetric, as the
   literature says (reversal is strongest after declines). It is not a symmetric artefact of the exits.
4. **Timing / timeframe:** a signal at the 16:00 NY cash close gives the same PF (1.86). At 12:00 NY it gives 1.51.
   An M15-built version on SP gives 1.89 vs 2.01 on H1. The result is not tied to one bar.
5. **First fold is flat** (2024-05..11, PF 0.99, 34 trades). The edge is not present in every half-year.
6. **Correlation of legs:** 68 of 152 entry days have both legs. The trade-level t of 3.25 overstates independence; the
   t-stat of the entry-day-clustered sum is **2.63** (152 days).

## In-sample fit (first 70%) and choice of parameters
I chose parameters on the first 70% only, pooling all three indices in %-of-price units. The plateau medians
(grid d4, 180 sets) were:
N 5/6/7/8/10 -> IS PF 1.24/1.21/1.30/1.31/1.14; TP 0/0.75/1.5 ATR -> 1.17/1.27/1.24; SL 2/3/4 ATR -> 1.21/1.28/1.24; hold
1-4 sessions -> 1.20-1.26. I picked N=7, TP 0.75, SL 3, hold 1. That is the middle of the plateau and gives the most
trades and the least swap; it is not the IS peak (N=8, SL=4: 1.52). US Mid Cap 400 was dropped **on IS evidence only**
(its IS PF was 1.15 < 1.20, and its 1.22-pt spread is 3.4 bp, ~4x the SP/RUT cost). After that the OOS was looked at once.

## Neighbour robustness (SP+RUT pooled, $ at 0.1 unit; IS = first 70%, OOS = last 30%)
| variant | trades | PF | IS | OOS |
|---|---|---|---|---|
| **final N7 TP.75 SL3 hold1** | 220 | 1.86 | 1.68 | 2.25 |
| N=5 / 6 / 8 / 10 | 275/246/201/176 | 1.62/1.77/1.80/1.72 | 1.57/1.60/1.62/1.49 | 1.74/2.19/2.19/2.21 |
| TP 0 / 0.5 / 1.0 / 1.5 ATR | 220 | 1.72/1.90/2.00/1.79 | 1.48/1.64/1.82/1.52 | 2.31/2.49/2.40/2.43 |
| SL 2 / 2.5 / 4 ATR | 220 | 1.73/1.89/1.88 | 1.51/1.72/1.70 | 2.25 |
| hold 2 / 3 sessions | 163/144 | 1.70/1.80 | 1.39/1.33 | 2.66/5.27 |
All 13 neighbours have IS >= 1.33 and OOS >= 1.74. The pooled PFs differ slightly from the official run because this
table uses slip 0.25 and spreads 0.40/0.33.

## Anchored walk-forward (re-fit per fold on all data before the fold; 135-set grid; SP+RUT)
| fold | train | test | chosen (N,TP,SL,hold) | train PF | test trades | **test PF** | test net | final params on same test |
|---|---|---|---|---|---|---|---|---|
| 2 | 2024-05..2024-11 | 2024-11..2025-05 | (5,0.75,3,1) | 1.17 | 75 | **1.24** | +$34 | 1.44 |
| 3 | 2024-05..2025-05 | 2025-05..2025-11 | (8,0.75,4,1) | 1.31 | 24 | **3.26** | +$38 | 3.62 |
| 4 | 2024-05..2025-11 | 2025-11..2026-05 | (7,0.75,4,1) | 1.52 | 46 | **1.85** | +$60 | 1.85 |
| 5 | 2024-05..2026-05 | 2026-05..2026-11 | (8,0,3,3) | 1.66 | 28 | **3.64** | +$81 | 3.70 |
All 4 out-of-sample folds are profitable with re-fitted parameters. The re-fit choices stay inside the plateau (N 5-8, SL 3-4).

## Timeframe comparison
| version | PF | trades | note |
|---|---|---|---|
| H1, session close 15:00 NY (final) | 1.86 | 220 | liquid entry/exit hour |
| H1, session close 16:00 NY (cash close) | 1.86 | 208 | same edge; fills at 16:00 NY are near the spread-widening window |
| H1, session close 12:00 NY | 1.51 | 228 | weaker |
| M15, SP only | 1.89 | 101 | vs H1 SP-only 2.01: no intrabar benefit |
| H1 intraday families (A-G) | 0.8-1.3 | 200-650 | no robust intraday edge found |

## Costs
* **Spread:** get_spot_prices on 2026-11-17 at 14:34 and 14:46 UTC (just after the US cash open) gave the same values
  both times: SP 0.36, RUT 0.30, MID 1.22, NAS 0.90, DJ 1.50. The session clock barely moved, so I could not sample
  15:00 NY. specs.json uses SP 0.40 / RUT 0.33 (+~10%). The x1.5 stress gives PF 1.78 and x3 gives 1.76. Spread costs
  ~$0.04 per trade against an average |trade| of ~$5, so the system is not spread-sensitive.
* **Commission:** 0 (Deriv cTrader history).
* **Swap:** every trade holds ≥1 rollover. Deriv's spec table (deriv.com/markets/stock-indices, fetched 2026-11-17)
  lists index long swaps as benchmark+markup (-4.49 EU indices, -6.91 AU200). The US rows were not visible, so I used a
  **conservative 7.5%/yr of price /360** per unit per night: SP 1.54, RUT 0.57 USD/unit/night, x3 on Friday. Total swap is
  -$45 (16% of gross profit). With swap doubled, PF is 1.63.
* **Slippage:** 0.25 pt per stop fill, plus the evaluator stress. The engine fills gaps through the stop at the bar open
  (the Apr-2025 SL filled ~0.25 below the stop).
* **Margin:** 1:50 assumed (2% of price), vs Deriv's advertised 1:100-1:400. Both legs open = $20.3.

## Balance (why not $30)
At 0.1 unit, one daily ATR is ~$8 on SP and ~$4.5 on RUT. The reversal needs a wide stop (3 ATR; capping the stop
in $ kills the edge: PF 1.07-1.17 with $10-15 caps). The planned risk per trade is therefore $12-74 on SP (median $24)
and $9-31 on RUT (median $13). The binding gate is the worst trade: SP -$33.84 on the 2025-04-03 tariff crash, and
it must be <= 5% of balance, so the balance must be at least **$677, hence $700**. The evaluator's recommended minimum
is $1,128 (worst trade <= 3%), with $1,690 to operate. **Small-account mode:** running only US Small Cap 2000 qualifies at
$250 (PF 1.60, IS 1.33, OOS 2.37, t 2.07, worst -$11.1, MC95 $40, score 57.5). That is the honest floor for this edge.
**$30 is not responsibly feasible:** every intraday idea that fits $1.5 stops failed (table above).

## Failure conditions / known weaknesses
1. **Bear markets.** Long-only dip-buying in a persistent downtrend buys falling knives. The sample has no 2022-style
   year. The worst cluster is in the sample (Aug-2024 unwind: -$27.5 that month; Apr-2025 tariff crash: -$45 on one day,
   recovered within days). The kill-switch (25% DD) and the consecutive-loss pause are the protection.
2. **Gap risk:** the stop can be gapped at the Sunday/daily reopen. The worst SL fill was 0.25 beyond the stop, but a
   larger weekend gap is possible.
3. **Correlated legs:** both legs often enter on the same day (68/152). The realistic t is ~2.6, not 3.25.
4. **Data mining:** ~6,300 backtested parameter sets in total, plus ~770 correlation cells, across 8 idea families.
   The dip family alone is ~1,800 sets. A naive Bonferroni over all 6,300 would demand t ≈ 4. The defence: the trials
   are highly correlated, the dip-buy idea is a literature prior, it replicates on an untouched index (NAS PF 1.64), a
   random-entry baseline fails, and the walk-forward and plateau results are clean. Expect a forward PF nearer 1.3-1.5
   than 1.8.
5. **Swap rates are a bound, not a measurement.** Read the real rate in the cTrader symbol info before going live.
6. **US Mid Cap 400 quote artifact:** its H1 bars systematically fall 16:00-17:00 NY and jump at the 18:00 reopen
   (mean -5.6 bp / +4.6 bp). That is consistent with bid-only quoting after the cash close. Avoid trading MID around the
   break. The final system does not trade MID.
7. 15:00 NY spreads were not sampled (see Costs).

## cBot
`IdxBot.cs` compiles: `bash arena/check_cbot.sh agents/IDX/IdxBot.cs` gives "Build succeeded, 0 Error(s)". Run one
instance per symbol (SP 500 and Small Cap 2000) on an H1 chart. Defaults equal strategy.py. Safety guards are on by
default and were all non-binding in the backtest: daily loss limit 8% (worst day -$45 = 6.4%), equity kill-switch 25%
from peak (max DD 7%), pause after 7 consecutive losses (max was 5), skip if planned risk > 12% of balance (max was
10.6%), max spread 1.0, label-based single position and duplicate guard. Risk-% sizing is optional and never goes
below the broker minimum or above MaxVolumeUnits. The time exit closes at the open of the bar after the 22nd bar
post-fill, which is the same moment as the engine's "close of bar entry+22". A window-based Python re-implementation
of the cBot's session builder reproduces strategy.py's RUT signals (the 4 differences are history warm-up at the start).

## Scripts (agents/IDX/research/, in order)
a1_stats.py (hourly drift), h_a_d.py (A, B), h_b.py (C), corr scans (inline), h_e.py (D), h_f.py (E), m15lib.py
(DELTA re-test), s1.py (F), s2.py (G), d1.py-d4.py (H), variants.py (legs/caps/balance), wf.py (walk-forward + neighbours).
