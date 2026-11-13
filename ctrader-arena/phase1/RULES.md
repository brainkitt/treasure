# cTrader Arena — rules of the competition

Four research agents (ALPHA, BRAVO, CHARLIE, DELTA) compete to build the best cTrader cBot for a
**$30 Deriv account**. A supervisor scores every submission with the same engine and decides whether
anything is good enough for a forward test on the demo account.

## Target
* Profit factor >= 1.7, trades every day, signals on M1..M15, minimum lot, tight risk.
* Any Deriv cTrader symbol(s). A submission may be a portfolio of several symbols ("legs").

## Official gates (arena/evaluate.py — all must pass to be QUALIFIED)
| gate | why |
|---|---|
| PF >= 1.7 on the full sample | the user's hallmark |
| PF >= 1.5 on in-sample (first 70% of days) AND on out-of-sample (last 30%) | an edge must survive unseen data |
| PF >= 1.4 with spread x1.5 | must survive worse execution |
| >= 150 trades, >= 40 of them out-of-sample | statistical weight |
| trades on >= 85% of market days | "trades every day" |
| max drawdown <= $9 (30% of $30) at the traded size | small-account survival |
| worst single trade >= -$1.50 (5% of $30) | per-trade risk cap |
| profitable in >= 70% of calendar weeks | consistency |
| no look-ahead (signals identical on truncated history) | honesty |
| every leg trades >= the broker minimum lot, and the minimum lot is known | tradable on $30 |

## Engine assumptions (arena/engine.py) — pessimistic on purpose
* Bars are BID. Longs pay the spread on entry, shorts on exit. Zero commission (matches account deal history).
* SL and TP in one bar -> SL. Pending orders: TP not credited on the fill bar.
* `gap_sl` symbols (Boom/Crash/Jump/DEX/Range Break/Step-family with jumps): a stopped trade fills at the bar extreme.
* Swaps/overnight financing are NOT modelled -> keep holds short; `overnight_trades` is reported.
* Spread is the live sampled value in specs.json (constant). FX spreads widen around 21:00-22:00 UTC rollover.

## Honesty rules
* Deriv synthetic indices are produced by a random generator. Many are driftless by construction;
  a backtest "edge" there is usually curve-fit noise unless it exploits a documented structural
  feature AND survives costs out-of-sample. Prove it statistically or drop it.
* Keep a research log (agents/<name>/NOTES.md): every idea tried, how many parameter sets were
  evaluated, what failed. The number of trials matters when judging a PF.
* Parameters are chosen on in-sample data only. Out-of-sample is looked at, not optimised on.
* Never loosen the engine or the gates. Report suspected engine bugs to the supervisor.
* No real orders. The only permitted order call is the minimum-lot probe described in the brief.
