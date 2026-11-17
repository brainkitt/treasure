# VOLA (AGENT_03, spike/jump synthetics) - round-3 research log

**Bottom line: NOT QUALIFIED. No validated edge exists in my 65-symbol universe on the pre-holdout data. I am not
asking for a holdout look.** Every family behaves as a compensated (martingale) game; the only statistically
significant structure (volatility clustering on Range Break 200 and Jump 75) has no directional content. The submitted
system is the best in-sample plateau I found (RB200 M5 breakout-follow). It failed two pre-declared confirmations on
months it had never seen, and it fails the official evaluate2 (PF 0.92). It should not be traded.

## 1. Official evaluate2 (RB200 M5, 2026-06-23 -> 2026-09-14, holdout sealed)
```
full   trades=359 PF=0.92 net=$-22.99 t=-0.53 DD=$69.51 worst=$-5.30     is PF 0.78   oos PF 1.27 (109 tr)   stress PF 0.91
folds  PF 1.09 / 0.61 / 0.48 / 1.19 / 1.32        MC DD95 $110        NOT QUALIFIED  score 4.0/100
```
Passes: OOS PF, trade counts, look-ahead, min lot, swap, margin. Fails: PF full/IS/stress, folds, t-stat, DD, MC DD,
worst trade. The OOS PF of 1.27 is noise: the unseen month before the fit window gave PF 0.79 (see 4.3).

## 2. Universe and cost screen (research/universe.py, screen.py, spreads_raw.txt, screen_cost.csv)
65 symbols in scope: Boom/Crash (30), Jump (5), DEX (6), Range Break (2), Vol Boom/Crash (6), Skew Step (4), Trek (2),
Exp Growth (2), Ladder (2), Crash Boom Flip (4), Snap (2). Spreads: get_spot_prices, all 65 at 18:22 UTC 2026-11-17, 8
re-sampled at 18:32. They match CHARLIE's 2026-11-11 21:40 samples to within 3%, so spreads look fixed (no schedule).
* **10 symbols cannot be tested**: Crash 75/250/750/1100/1500 (2678-2682) returned no bars before 2026-09-15. Boom 75-1500 (2683-2687) are their cTrader-exclusive siblings from the same launch and were not pulled. Their whole history is in the sealed period.
  Exp Growth 1 was not pulled (the shared M5 file is all post-holdout). Its sibling Exp Growth 2 stands in for it.
* Cost/M5-range (spread / median M5 high-low, 1000 bars ending 2026-09-14): 0.06-0.13 for Jump, Snap, Ladder, Boom/Crash
  50/150, Trek, Skew Step, RB200, Vol Boom 400, DEX 600 UP. 0.25-0.49 for Boom/Crash 99-1000 and Boom 300, which are
  too expensive at M5. Cost is not the binding constraint here. In a fair game the expectancy is minus the spread
  whatever the ratio.

## 3. Statistics screen (research/stats.py; 8 pre-registered tests per symbol; BH within each run)
| run | data | symbols | tests | raw p<0.05 | expected | BH q<0.10 |
|---|---|---|---|---|---|---|
| discovery | M5 1000 bars, 09-11..09-14 | 54 | 356 | 22 | 18 | 0 |
| H1 | 720 bars, 08-12..09-11 | 36 | 218 | 11 | 11 | 0 |
| deep | M5 8-16k bars, 06-23/08-04..09-14 | 7 | 50 | 9 | 2.5 | 2 (vol clustering RB200, Jump 75) |
Tests: T1 drift, T2 AC1, T3 VR(6), T4 hour-of-day mean, T5 hour-of-day volatility, T6 post-jump drift (3 bars),
T7 jump hazard vs bars since last jump, T8 |r| clustering. Drift t-stats across two samples correlate at 0.00 and
agree in sign 47% of the time. **Total: 628 statistical tests, 0 directional effects survive BH.**
Follow-ups on the leads (each fresh data, pre-declared):
* Vol Crash 550 drift (t -2.2 / -2.3): independent Feb-Aug H1 shorts gave PF 1.19 / 1.53, t 1.3 / 1.7. Not significant.
  A multiplicative martingale's median path falls while its mean stays flat. Rejected.
* Boom 150 drift (t -2.15 / -2.54): 10 months earlier H1 gave t -0.43. Rejected.
* Range Break break-direction persistence: P(same as previous) 0.54 (n 196, p 0.28) RB200; 0.46 RB100. Independent.
* Hazard (T7) flat everywhere: DEX 600 UP p 0.87, Vol Crash 550 p 0.68, RB200 p 0.018 (not significant after BH).

## 4. Strategy families (research/lab.py, families.py; official engine, gap_sl, live spread; IS 70% / OOS 30%)
| family | mechanism hypothesis | symbols | sets | result |
|---|---|---|---|---|
| F1 drift harvest | ride the compensating drift right after a spike (refractory hazard) | Crash150, Boom150, VolCrash550, DEX600UP, TrekUp | 300 | IS PF>1 0-60%, median IS 0.77-1.06; nothing with t>2 in both halves |
| F2 post-spike | fade or follow a 4/6/8-MAD jump bar for 1-12 bars | all 7 | 336 | median PF IS 0.17-0.87, OOS 0.00-0.89 |
| F3 breakout | Donchian 6-48 close breakout follow (trail) or fade (TP) | Jump75, TrekUp, RB200, Crash150 | 192 | only RB200-follow had a plateau (IS 1.2-1.7) |
| F4 RB boundary | fade/follow near the N-bar range edge (M5, vs CHARLIE's M1) | RB200 | 48 | IS PF>1 6%, OOS 0% |
| F6 TS momentum | sign of N-bar return, hold H, follow/fade | all 7 | 126 | median PF 0.86-0.99 / 0.83-0.95 |
| F8 drift lead | short Vol Crash 550 | VolCrash550 H1 | 2 | t 1.3/1.7, rejected |
### 4.3 Trying to disprove the one plateau (RB200 breakout-follow, fit window 08-18..09-14)
* C1 (N24 K2 H48), declared before the test, run on the unseen 07-21..08-18: **PF 0.66, t -2.01**. Same window: only 4%
  of the 24 follow sets had PF>1.
* Anchored WF with a refit per fold over the 48-set grid (data 07-21..09-14): fold OOS PF 0.60 / 1.03 / 1.90 / 1.50 / 1.25.
  The WF-selected rule R2 (N48 K3 H12), declared before the test, run on another unseen month (06-23..07-21):
  **PF 0.89**. C1 on that month: PF 0.79. Killed.
* Neighbour table on the full file (follow, H48): PF 0.88-1.19 full, 0.73-1.03 IS, 1.11-1.60 OOS. All the "edge" sits in
  the last 4 weeks, which is a time effect, not a parameter plateau.

**Data-mining count: 1,201 logged backtests (research/trials.csv), about 1,050 distinct parameter sets, plus 628 statistical tests.**
With roughly 1,000 sets on about 1 month of M5 per symbol, a best in-sample t of about 2.5 is what chance alone produces.

## 5. Costs, lot, swap, margin (specs.json)
Spread 2.0 (RB200, 4 samples). Min lot 0.01 units from CHARLIE's probe (2026-11-11, accepted, cancelled, confirmed gone).
VOLA placed no orders. Commission 0. Swap is not exposed. Entries stop at 16:59 UTC and the max hold is 4 h, so no
21:00 rollover is crossed. A pessimistic bound of 40 USD/unit/night is set anyway. Margin assumes 1:50, giving $14.4 at
0.01 units. Worst trade -$5.30 at the minimum lot: one 530-point range break gap-filled at the bar extreme. The engine's
minimum responsible balance is $440, which makes the system unsuitable for $30 even if it had an edge.

## 6. Holdout hygiene (please read)
I never set ARENA_HOLDOUT_UNLOCK, never read raw files around the loader and never edited data/.holdout. All research
used `arena.ingest.load`. **Disclosure:** the spread sampling the brief requires returns the live price, so I saw the
2026-11-17 level of every symbol. That shows the net holdout move (for example Vol Crash 550 kept falling and Boom 150
rose). I made no selection on it. It is one more reason I do not request a holdout run for anything here.

## 7. Verdict and what would change it
The spike/jump families are fair games net of spread. Three teams across four rounds (CHARLIE M1, VOL, VOLA M5/H1) have
now found the same thing. I recommend no demo forward test and no further parameter search on these families.
Only new information could change this: tick data showing a non-memoryless spike clock, a measured spread schedule
(cBot logging Symbol.Spread for weeks), or Deriv's published swap credits (a positive-carry side would be structural).

Files: strategy.py, specs.json, VolaBot.cs (`bash arena/check_cbot.sh` -> Build succeeded), report_data.json (incl. the
65-row "screen"), research/ (all scripts, csvs, evaluate2_output.txt), submissions/VOLA/{metrics.json,trades.csv}.

## Round 4 - new information only (2026-11-17, about 70k tokens). Result: no edge, NOT QUALIFIED unchanged
| item | new information | result |
|---|---|---|
| 1 Swap/financing | deriv.com synthetic-indices CFD table: swap long = swap short, both NEGATIVE (Boom 50 -3.5, Boom 100/150 -5, Boom 200 -6, Boom 500 -23, Boom 900 -32, Boom 300/600/1000 -36 pts). Owner history: V75 swap -0.07/-0.14/-0.21 per position per hold (10 charged, 0 credited); V10(1s)/V100(1s) intraday 0. Trading 24/7 incl. weekends. "Swap-free weekends" and a swap-free account exist only on Deriv **MT5** (marketing blog/FAQ), not documented for cTrader, and swap-free only removes a cost | **No credited side on any synthetic -> no carry edge.** Overnight holds are a pure cost, so the intraday design is correct |
| 2 M1 microstructure | M1 2026-09-09..09-14 (pre-holdout), 8k bars each: DEX 600 UP (272 spikes), Vol Boom 400 (475), RB200 (50 breaks). 45 tests: AC lag 1-5, VR(2-5), post-spike drift 1-5 min, hazard by minutes-since-spike | 2 raw p<0.05 (2.2 expected), **0 BH**. Hazard flat (VolBoom400 4.4-6.3%/min in all buckets; DEX 1.5% in minute 1 then 3.2-4.2%). Best "lead": DEX600UP fade 2 min after a spike = +0.85 spread gross (p 0.007, BH 0.33), below the 1-spread cost even if real. RB200: no break within 5 min of the previous one (range rebuild), with only 50 breaks and fades inside the range already shown fair. research/m1_micro.py, m1_micro.csv |
| 3 Spread schedule | 4 timed samples (18:22, 18:32, 18:37, 18:38 UTC) on 8 cheapest symbols plus CHARLIE's 21:40 UTC samples six days earlier | Spreads are identical or proportional to price (e.g. Crash 150 0.1498/0.1497, Boom 50 0.12719, RB200 2.0 in all 4 samples; RB100 2.6, DEX600UP 0.43, Boom 500 0.53 matching CHARLIE within 3%). No cheap window. Unlike DSI (VOL), these spreads do not move with regime. Caveat: one evening session; a cBot spread log is the cheap way to settle 24h coverage |
| 4 Product rules | Re-read descriptions: Range Break (break once per 100/200 attempts), Trek (rare large moves, 30% vol), Exp Growth (+/-0.01% of spot per tick), Skew Step (90/10, 80/20 steps), CBF (alternating spikes) | All describe compensated designs: a multiplicative +/-0.01% walk is a martingale; Skew Step's step sizes are documented as zero-mean; CBF alternation tested by CHARLIE (drift paid back). Trek / Exp Growth drift t within +/-1 (round 3). No new testable mechanism |
Verdict unchanged: no structural or statistical edge in the spike/jump families, so no holdout request.
