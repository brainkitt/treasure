# cBots from the arena (13 Nov 2026)

Five cBots, one per result the agents produced. Each `.cs` is the source; each `.algo` is the built file
(compiled against cTrader.Automate 1.0.21, .NET 6, zero errors). **None has been run inside cTrader yet**, and
**none passed the qualification gates**, so use the demo account only.

## Install
* Easiest: double-click the `.algo` file on a PC with cTrader Desktop; it appears under Algo > cBots.
* Or: Algo > cBots > New, paste the `.cs` source, Build.
* Attach to the chart listed below, leave every parameter at its default, press Start.
  "Volume = 0" means the bot uses the broker's minimum size.

| File | Agent | Attach to | Backtest result | Status |
|---|---|---|---|---|
| `DeltaBot` | DELTA | US SP 500, M15, one instance | PF 1.43 on 95 trades; 1.47 on 5.5 earlier months; worst trade $1.40 | Best honest result. Demo observation only. |
| `BravoBot` | BRAVO | Drift Switch Index 30, M1 | PF 0.66 at the widest spread seen, 2.82 at the narrowest | Unresolved: depends on live spread. Default 2.5 max-spread filter makes it skip most signals. |
| `AlphaBot` | ALPHA | EURUSD and GBPUSD, any timeframe, one instance each | PF 2.04 on 60 trades, but 0.95 on 285 trades Jan-Sep | Rejected. Do not fund. |
| `CharlieBot` | CHARLIE | USDJPY, M15 | PF 2.30 on 26 trades, 1.00 on 88 earlier trades | No edge. Demo observation only. |
| `CharlieBot_rangebreak` | CHARLIE (round 1) | Range Break 100 Index, M1 | PF 0.90 on 360 trades | Losing. Kept for the record. |

## Built-in protection (all bots)
Hard stop-loss and take-profit on every order, one position per symbol, spread filter, daily loss limit,
and a drawdown kill-switch (default $9) that stops the bot.

## Known differences from the backtest
* The backtest assumes one constant spread; the bots see the live spread.
* `CharlieBot` checks its time exit once a minute.
* `DeltaBot` and `AlphaBot` have a daily loss limit and kill-switch that the backtest does not model
  (neither would have triggered in the scored window).
