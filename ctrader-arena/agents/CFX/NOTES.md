# CFX (AGENT_02, Crypto_Forex_Specialist) - research log

**Final: Crypto Momentum Burst on ETHUSD H1, 0.1 ETH, $300 account. QUALIFIED, score 66.0/100.**

```
start balance $300.00  period 2023-05-07 -> 2026-11-17  (OOS from 2025-10-26)
full   trades=192 PF=1.82 net=$157.10 (52%) win=49% exp=$0.818 t=2.66 DD=$18.01 worst=$-8.56 sharpe=1.16 tr/wk=0.7 swap=$0.00
is     trades=123 PF=1.80 net=$96.01  t=2.04 DD=$18.01
oos    trades= 69 PF=1.85 net=$61.09  t=1.70 DD=$16.93
stress trades=192 PF=1.58 net=$123.43 t=2.09
folds  2023-05:42tr PF1.12  2024-01:29tr PF1.83  2024-10:32tr PF1.15  2025-06:44tr PF3.18  2026-03:45tr PF1.43
MC DD  p50=$24.83 p95=$45.46 p99=$57.72   balance technical_min=$107 recommended_min=$285 margin=$49.6
```

## 1. Rule (strategy.py == CfxBot.cs)
All times UTC, decisions only on closed H1 bars.
1. ATR24 = mean(high-low) of the last 24 H1 bars (incl. the signal bar).
2. If the last closed H1 candle has |close-open| > 2.5 x ATR24 -> market order in its direction at the next bar open.
3. Hard stop 2.0 x ATR24, no TP. Position held 3 H1 bars (entry bar + 2), closed at the close of the 3rd bar.
4. Rollover guard: no trade whose 3 held hours touch 20:00-22:59 UTC -> never held through rollover, 0 swap ever.
5. One position, 0.1 ETH (broker minimum).

## 2. Data and costs (measured)
* H1 history pulled via MCP (~370 calls): 10 FX/crypto symbols 2024-10-28 -> 2026-11-17 (EURUSD, GBPUSD, EURJPY, USDJPY,
  AUDUSD, USDCHF, USDCAD, EURGBP, BTCUSD, ETHUSD), XRPUSD/BNBUSD 2024-09 -> 2026-11, and BTC/ETH back-filled to
  2023-05-07 (3.5 years, continuous, max gap 10h). Data before 2024-10-28 was NOT looked at during research and served as a
  pre-sample holdout (section 5).
* Spreads (get_spot_prices, 2026-11-17 14:34/15:16/15:41 UTC): EURUSD 1.4 pip, GBPUSD 1.3, USDJPY 1.4, AUDUSD 1.0,
  USDCHF 0.9, USDCAD 1.3, EURGBP 0.8, EURJPY 1.6, BTC 21.8/19.8/18.4, ETH 1.58 (fixed), SOL 19 bps, XRP 9 bps, BNB 12 bps,
  LTC 42 bps, other coins 17-70 bps. Model: ETH 2.0 (+27%), BTC 25; slip 0.2 x spread on every market and stop fill;
  stress run 1.5x spread + 0.25x spread slip. I could only sample during the London/NY afternoon (the clock does not
  advance much); night/weekend crypto spreads are unverified -> cBot MaxSpread filter = 3.0.
* Commission 0 (account history). Swap: Deriv does not publish cTrader crypto swaps (web search found only MT5
  swap-free admin fees, e.g. $38/lot/night on BTC). The rollover guard means 0 nights in every backtest; specs carry a
  pessimistic bound anyway (0.08% of sample-max price per unit per night, ~29%/yr, triple Friday).
* Min-lot probe (label probe-CFX): BTCUSD LIMIT BUY volume=1 (0.01 BTC) at 32000 was ACCEPTED -> min <= 0.01 BTC; it was
  cancelled at once and get_pending_orders returned []. ETHUSD volume=1 REJECTED "minimum allowed volume = 0.10" -> 0.1
  ETH. No other order action was taken; the XAUUSD "G2" position was never touched.
* Margin: conservative 1:10 on the sample-max price -> ETH $496/unit -> $49.6 for 0.1 ETH (16.5% of $300).
* Cost/volatility: median daily range / spread: BTC 0.96%, ETH 1.65%, FX majors 1.5-3.8% (EURGBP worst).

## 3. Hypotheses (written before testing) and results
| # | hypothesis / why an edge could exist | test | result | verdict |
|---|---|---|---|---|
| H1 | London-open breakout of Asian range (ALPHA round-1, PF 2.0 on 60 trades): overnight stops get run at London open | EURUSD+GBPUSD 2y H1, default + 108-set grid, 6 other pairs | default PF 0.85 / 0.92 (n=295/319); all 108 IS sets PF 0.63-0.94; gross follow-through to 16:00 -0.03 pip EUR, +3.4 GBP vs 1.4 spread | **rejected** - round-1 result was small-sample luck (caveat: H1 signal vs ALPHA's M5) |
| H2 | FX time-series momentum (trend persistence, vol-targeted) | daily signs, lookback 1-60d, 10 symbols, IS t-stats | pooled IS t -0.9..+0.1, variance ratios 0.87-0.95 | **rejected** (and stops would need ~$100/trade) |
| H3 | Asian-session FX mean reversion (thin market, no news) | fade z-score extremes 23-05 UTC, 8 pairs | gross mostly negative; JPY pairs continue (t -2.4..-3.1) | **rejected** |
| H4 | **crypto momentum burst**: liquidation cascades / stop runs / momentum-chasing in 24/7 leveraged crypto make order flow autocorrelated for a few hours after a shock candle | conditional scan, then grids | scan: crypto continuation +0.21 ATR at 1h (t 3.6), FX ~0 | **finalist** |
| H5 | crypto weekend-gap fade | Fri 20:00 -> Sun 23:00 move faded on Monday | t -0.5..+1.9 (n=106) | rejected |
| - | hour-of-day drift FX/crypto | 24 hours x 8 symbols | only 21-23 UTC (rollover) significant | artefact of bid bars + rollover spread, rejected |

## 4. Developing H4 (all fitting on data 2024-10-28 -> 2026-03, IS = first 70% of days)
* Grid 1 (120 sets, BTC+ETH): median IS PF rises monotonically with k (1.09 @1.5 -> 1.51 @3.0): bigger shock, stronger
  follow-through - the expected shape.
* Generalisation check on XRP/BNB (disproval attempt): net PF 0.96-1.07. Gross PF: BNB 1.48, XRP 1.06 -> the effect
  exists gross in 3 of 4 coins but alt spreads (9-12 bps) eat it. Universe restricted to BTC/ETH.
* Grid 2 (432 sets: k x ATR window x hold x stop x close-location x 24h-trend filter x volume filter): 75% of sets IS
  PF > 1.22. Filters added nothing robust -> dropped. Central simple set chosen BEFORE looking at OOS: k=2.5, n=24,
  hold 3 bars, stop 2 ATR.
* BTC vs ETH: BTC PF 1.40 (t 1.66), ETH 1.74 (t 2.67) over 3.5y. ETH's IS was also stronger (1.87 vs 1.29 in the
  2y research sample) and its dollar risk per trade is 1/3 of BTC's (0.1 ETH vs 0.01 BTC minimum). BTC+ETH qualifies
  only at $900 (worst trade -$26; score 57.3) -> submitted ETH only, BTC documented as an optional second instance.
* Correction after first official run (disclosed): the engine holds max_bars+1 bars, so my first rollover guard missed
  the last held hour (exit at 21:00 = rollover). Fixing it removed signal hour 17 UTC: 210 -> 192 trades, PF 1.74 -> 1.82.
  This was a safety fix, not a search; both versions qualify.

## 5. Validation
* **Official OOS (2025-10-26 ->)**: 69 trades PF 1.85 (IS 1.80).
* **Pre-sample holdout 2023-05 -> 2024-10 (never seen during research)**: ETH PF 1.30 (78 tr), BTC 1.50 (90 tr). The
  calendar year 2023 alone is negative (PF 0.74, 40 tr).
* **Anchored walk-forward, re-fit per fold** (54-set grid, pick max train t-stat, >=60 train trades):

| train to | picked | test | n | PF | fixed BASE PF |
|---|---|---|---|---|---|
| 2024-06 | k2.5 n48 hold3 sl1.5 | 2024-06..12 | 35 | 0.97 | 1.34 |
| 2024-12 | k2.5 n24 hold4 sl3.0 | 2024-12..2025-06 | 18 | 2.01 | 2.11 |
| 2025-06 | k2.5 n24 hold4 sl3.0 | 2025-06..12 | 26 | 2.76 | 2.29 |
| 2025-12 | k2.5 n24 hold4 sl3.0 | 2025-12..2026-06 | 33 | 2.45 | 3.70 |
| 2026-06 | k2.5 n24 hold3 sl3.0 | 2026-06..11 | 31 | 1.01 | 1.04 |
| stitched | | | 143 | **1.67** (t 2.07) | |

  k=2.5 is chosen in every fold and n=24 in 4/5 -> parameters are stable. BTC+ETH stitched WF: PF 1.43 (281 tr).
* **Neighbour robustness** (ETH, full 3.5y, one parameter at a time; "hold" = H+1):

| set | n | PF | IS PF | OOS n | OOS PF | t |
|---|---|---|---|---|---|---|
| BASE k2.5 n24 hold3 sl2.0 | 192 | 1.82 | 1.80 | 69 | 1.85 | 2.67 |
| k=2.0 / 2.25 / 2.75 / 3.0 | 394/266/143/94 | 1.18/1.42/2.04/1.94 | 1.00/1.28/2.37/2.49 | 135/91/54/36 | 1.67/1.75/1.60/1.38 | 1.13/1.91/2.63/2.02 |
| n=12 / 18 / 36 / 48 | 156/177/225/239 | 1.79/2.17/1.46/1.41 | 1.90/2.10/1.28/1.30 | 52/64/82/85 | 1.62/2.27/1.88/1.64 | 2.40/3.32/1.86/1.77 |
| hold=2 / 4 / 5 | 212/184/160 | 1.68/1.69/1.75 | 1.43/1.73/1.81 | 72/67/55 | 2.30/1.61/1.63 | 2.48/2.37/2.33 |
| sl=1.0 / 1.5 / 2.5 / 3.0 | 193/192/192/192 | 1.38/1.79/1.95/1.91 | 1.24/1.65/2.01/1.99 | 70/69/69/69 | 1.69/2.05/1.87/1.81 | 1.46/2.62/2.94/2.85 |
| spread x2 | 192 | 1.55 | 1.51 | 69 | 1.61 | 1.99 |

  Every neighbour has PF >= 1.18 and OOS PF >= 1.38. The base is not the peak (n=18 and sl=2.5 score higher).
* **Disproval tests** (ETH): reversed direction PF 0.38; random direction on the same entries/stops: median PF 0.82,
  max of 200 = 1.20, P(>= 1.82) = 0; random entry times with candle direction: median 0.76, P = 0. Edge comes from
  conditioning on shock candles, not from stop/exit geometry.
* Timeframe: H1 PF 1.51 (no guard) vs H2 0.87, H4 1.15, D1 1.75 (n=8). The continuation lasts ~3h; coarser bars miss it.
* Breakdown: long PF 2.12 (101) / short 1.59 (91); weekday 1.97 / weekend 1.33; exits 167 time (+$262), 25 stop (-$105);
  max 5 consecutive losses; by year 2023 0.74, 2024 1.57, 2025 2.55, 2026 1.79.

## 6. Data-mining accounting
~830 strategy parameter sets evaluated (LOB 120, burst grids 120 + 432, ~160 neighbour/WF/pre-sample/variant runs)
plus ~340 statistical scan cells. A t of 2.66 alone would NOT survive a Bonferroni correction for that many tries.
The case rests instead on: (a) a monotone, broad plateau; (b) a holdout of 1.5 years never used in research (PF 1.30);
(c) OOS PF 1.85; (d) WF re-fit picking the same k every fold; (e) placebo p < 0.005. Honest expectation forward:
PF 1.2-1.5, not 1.8.

## 7. Balance
* $30 is not responsibly feasible with anything I found: the only sub-$100 vehicle is FX at 1000 units ($0.10/pip),
  and every FX hypothesis failed on 2 years of data. ETH's 0.1-lot minimum means a typical stop costs $5-8.
* Evaluator: technical_min $107, recommended_min $285 (= worst trade / 3%). **Chosen START_BALANCE $300**: worst trade
  2.9%, max DD 6%, MC95 DD 15%, MC99 19%, margin 16.5%. Operating balance suggested $430.

## 8. Known weaknesses / failure regimes
1. Fat-tailed: PF 1.82 -> 1.40 without the best 5 trades, 1.11 without the best 10; long flat periods are normal
   (2026-06..11 flat, 2023 negative).
2. One instrument; low frequency (0.7 trades/week, ~37/yr) -> a forward test needs 6+ months to say anything.
3. Night/weekend spreads and slippage on shock candles are unverified (spread x2 still PF 1.55).
4. Execution timing matters: entry must happen right at the H1 close.
5. Selection of ETH over BTC used full-sample per-leg numbers (justified by IS evidence and capital, but disclosed).
6. Rollover hour assumed inside 20:00-22:59 UTC; if Deriv's cTrader rollover is elsewhere, adjust the block window.

## 9. cBot (CfxBot.cs, compiles: `bash arena/check_cbot.sh` -> Build succeeded, 0 errors)
Runs on an ETHUSD chart of any timeframe, requests H1 bars itself, TimeZone UTC. Defaults = strategy.py. Hard SL on every
order, MaxSpread 3.0, label-based single position, duplicate-bar guard, daily loss limit 5%, equity kill-switch 25% from
peak (closes and stops), 48h pause after 6 straight losses, optional risk-% sizing clamped to [broker min, MaxVolume] with a
4% per-trade risk cap (trade skipped if even the minimum exceeds it), every TradeResult checked and logged.

## 10. Files
research/: lib.py (helpers), h1_lob*.py (H1), scan_daily.py (H2), scan_asian.py (H3), scan_hour.py, scan_impulse.py,
h4_burst.py / h4b.py (grids), h4_presample.py, neigh.py, wf.py, tfcomp.py, placebo.py, variants/ (eth_only, btc_eth).
