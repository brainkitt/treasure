# cTrader Arena

Four research agents competed to build a cTrader cBot for a $30 Deriv account
(profit factor >= 1.7, trades every day, M1-M15 signals, minimum lot).

**Outcome (13 Nov 2026): no system qualified.** Full report: `report/index.html`.

| Agent | System | Profit factor (scored window) | Earlier months | Gates |
|---|---|---|---|---|
| ALPHA | London-open breakout, EURUSD + GBPUSD | 2.04 | 0.95 (285 trades) - rejected | 10/12 |
| BRAVO | Drift Switch 30 regime filter | 0.66 at widest spread (2.82 at narrowest) | n/a | 6/12 |
| CHARLIE | USDJPY limit-order fade (round 1: Range Break 100, 0.90) | 2.30 on 26 trades | 1.00 (88 trades) - noise | 8/12 |
| DELTA | S&P 500 pre-US-open breakout fade | 1.43 | 1.47 (168 trades) | 6/12 |

## Layout
* `RULES.md`, `BRIEF.md` - gates, engine assumptions, agent instructions
* `arena/` - ingest, backtest engine, official scoring, leaderboard
* `agents/<NAME>/` - strategy.py, cBot source, specs.json, NOTES.md research log
* `submissions/<NAME>/` - official metrics.json and trades.csv
* `cbots/` - all five cBots as .cs source and built .algo files, with install notes
* `report/` - report page (`template.html` + `data.json` -> `index.html`)
* `data/` - downloaded candles (not committed)

Re-score everything: `python -m arena.leaderboard`
