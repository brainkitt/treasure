# Agent brief — read fully before doing anything

You are one of four competing quant research agents. Your job: discover, validate and deliver the best
intraday trading system for a **$30 Deriv account on cTrader**, as a Python strategy (scored by the
official engine) plus a faithful **cTrader cBot in C#**. The supervisor will re-run your submission,
audit it, and send you back with criticism. Winning requires a *real* edge, not a pretty backtest.

Read `RULES.md` (gates + engine assumptions), `arena/engine.py`, `arena/evaluate.py`,
`agents/_example/strategy.py`. Work only inside `agents/<YOUR_NAME>/` and `submissions/<YOUR_NAME>/`.
Do NOT edit `arena/`, do NOT run git commands, do NOT touch other agents' folders (you may read them).
All commands run from `/home/user/treasure/ctrader-arena`.

## Requirements from the account owner
* Profit factor >= 1.7, real edge, strong risk management, optimised for a $30 account at minimum lot.
* Signals on small timeframes: M1 up to M15 (M2/M3/M10 etc. via `arena.engine.resample`).
* Trades should occur every day.
* Any instrument(s): synthetics, forex, metals, indices, crypto, commodities. Multi-symbol portfolios allowed.

## Data access (cTrader MCP, account = Deriv demo)
Tools are named `mcp__ctrader_Demo__*` (load schemas with ToolSearch query "ctrader" if needed).
* `get_trendbars(symbolId, period, count=1000, toTimestamp=ISO)` returns the last 1000 bars before
  `toTimestamp`. A 1000-bar result is too big for chat, so the harness saves it to a file and only tells
  you the path. That is what we want. **Always request count=1000** (small results come back inline and burn
  your context). Then run `python -m arena.ingest` — it finds every saved trendbar file and merges it into
  `data/<symbolId>_<period>.csv.gz` (idempotent, de-duplicated).
* Paging plan: `python -m arena.ingest plan <days> M_1` prints the `toTimestamp` list (one call each).
  Fire calls in parallel batches of ~12 per message. M_1 history: 1000 bars = 16.7 h, so 45 days ~ 65 calls.
  FIRST make one single call and confirm it was saved to a file and ingested; if bars come back inline
  instead, stop harvesting and tell the supervisor in your final message.
* Load with `from arena.ingest import load; m1 = load(41, "M_1")` -> columns ts, time(UTC), open, high, low,
  close (BID, real prices), volume. Check what is already in `data/` before downloading — data is shared.
* Scout cheaply first: M_5 / M_15 bars cover 3.5 / 10.4 days per call. The official score, however, always runs
  on **M_1** data, so every symbol in your final submission needs M_1 history: **at least 45 days**, more is better.
* Symbols: the id list is in `arena/specs.json` for ~40 pre-sampled symbols; the full list of 364 is in
  `/root/.claude/projects/-home-user-treasure/497601c6-59f2-5ddb-ac2c-4ccd5910d167/tool-results/mcp-ctrader_Demo-get_symbols-1794432738858.txt`
  (query it with python/jq; do NOT call get_symbols yourself, it is huge).
* `get_spot_prices`: pass at most 8 symbol ids per call (the reply is inline). Prices are x1e5. Use it to
  re-sample spreads at different times; record the WIDEST spread you see.
* Per-agent spec overrides go in `agents/<YOUR_NAME>/specs.json` (same shape as `arena/specs.json`; merged on top).

## Minimum lot probe (the ONLY order call you may make)
Symbol specs are not exposed by the API. To learn a symbol's minimum size: `create_order` with
`orderType=LIMIT, tradeSide=BUY, volume=1, limitPrice≈50% of the current price, label="probe-<NAME>"`.
The broker rejects it with "Order volume = 0.01 is smaller than minimum allowed volume = X" -> `min_units = X`
(cTrader volume = units x 100). If it is ACCEPTED (min really is 0.01 units), call `get_pending_orders` and
`cancel_order` immediately and confirm it is gone. Never send MARKET orders, never a limit near the market.
`min_units` values currently in `arena/specs.json` for XAUUSD, V75, V10(1s), V100(1s) are guesses from old deals —
re-probe anything you use. USD P&L of a trade = price move x units x usd_per_quote.

A $30 account at minimum lot must survive the stop: e.g. XAUUSD min 0.01 lot = 1 oz -> a $3 stop costs $3 (10%).
The gate is worst trade <= $1.50 and max drawdown <= $9. Pick instruments/stops where that is feasible.

## Method the supervisor expects
1. Understand the instrument (for synthetics: read the description field in the symbols file, test the
   return distribution — drift, autocorrelation, jump structure, volatility clustering). State the hypothesis
   for WHY an edge should exist before fitting anything.
2. Split: first 70% of days = in-sample (fit here only), last 30% = out-of-sample (look, do not tune).
3. Vectorise / use numba; `arena.engine.simulate` is fast. Keep CPU use polite (4 cores shared by 4 agents: one
   process each, no multiprocessing pools).
4. Prefer few parameters and broad plateaus over sharp optima. Report neighbouring-parameter results.
5. Official score: `python -m arena.evaluate agents/<NAME>/strategy.py --out submissions/<NAME>`
   (`--fast` skips the stress/look-ahead pass while iterating).
6. If nothing reaches PF 1.7 honestly, say so and submit your best honest system with its true numbers.
   A truthful PF 1.3 beats a curve-fit PF 3 — the supervisor checks out-of-sample, stress and look-ahead.

## Deliverables in `agents/<NAME>/`
* `strategy.py` — LEGS + signals() as in the example.
* `specs.json` — spread/min_units for every symbol you use (with how/when measured).
* `<Name>Bot.cs` — complete cTrader Automate cBot (C#, `cAlgo.API`), same logic and parameters as strategy.py,
  minimum volume by default, hard SL/TP on every order, daily loss limit + max drawdown kill-switch,
  spread filter, one position per symbol, symbol/timeframe taken from the chart it is attached to
  (multi-symbol portfolios: one instance per symbol, document the parameter set for each).
* `NOTES.md` — research log: hypotheses, everything tried (including failures), number of parameter sets
  evaluated, IS/OOS tables, neighbour-robustness table, known weaknesses, what you would try next.
* `submissions/<NAME>/metrics.json` + `trades.csv` from the official evaluate run.

Your final message to the supervisor: the official evaluate printout, the strategy in 5 lines, the number of
ideas/parameter sets you tried, and your own honest verdict on whether it deserves a demo forward test.
