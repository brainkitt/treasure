# Phase 2 brief — read fully before doing anything

Phase 1 (archived in `phase1/`) ended with no qualifying system under very strict gates (PF 1.7, M1-M15 only,
trades every day). The account owner has now relaxed the brief:

> "It doesn't necessarily need to hit 1.7 PF, but something sustainable and profitable over a long period.
> Free to use whatever logic and method, adjust any parameter. Small account, least lot size. Realistic backtest."

So the goal of phase 2 is ONE thing: a system whose profitability holds over **a long history** (a year or more),
at the broker minimum lot on a **$30 account**, under realistic costs. PF 1.7 is the stretch target; PF >= 1.3
that is stable across years/months is a success. Any timeframe (M1 to D1), any holding period, any instrument,
any logic. Daily trading is preferred but no longer required.

## What changed in the tooling (arena/)
* **Any base timeframe.** A leg may declare `"period": "M_5" | "M_15" | "M_30" | "H_1" | "H_4" | "D_1"` (default
  `"M_1"`). The leg is then simulated on that bar series, and `signals(bars, params, spec)` receives those bars
  (use `arena.engine.resample` only from M_1). History per 1000-bar call: M_5 3.5 days, M_15 10.4 days,
  H_1 41 days, H_4 166 days, D_1 ~4 years. Choose the finest series you can afford for the history you need:
  intrabar ambiguity is resolved pessimistically (SL before TP), so coarse bars with tight stops are punished.
  Rule of thumb: SL and TP should be several times the typical bar range of your base series.
* **Financing is charged.** Each 22:00 UTC rollover a position is held across costs `swap_per_night` x notional
  (default 0.00025 = 0.025% per night, ~9%/yr, on longs AND shorts). Put a per-symbol value in your specs.json if
  you have evidence (the account's `get_deals` history may show real swap amounts); for synthetics use >= 0.0006.
* **New order column `prove`** (int bars, 0 = off): if the trade is not in profit at the close of the `prove`-th
  bar after the fill bar, it is closed there (conditional time-stop).
* **New gates** (all must pass for QUALIFIED; see `arena/evaluate.py`):
  history >= 300 calendar days | PF >= 1.3 full | PF >= 1.15 on first 70% AND on last 30% of days |
  PF >= 1.15 at 1.5x spread | >= 200 trades, >= 50 in the last 30% | profitable in >= 60% of calendar months |
  max drawdown <= $12 | worst trade >= -$1.80 | no look-ahead | min lot respected.
* Everything else in `BRIEF.md` still applies: data harvesting via `get_trendbars` (count=1000, saved to file,
  `python -m arena.ingest`, `python -m arena.ingest plan <days> <period>` for the toTimestamp list), min-lot probe
  rules (far LIMIT order, volume 1, cancel if accepted — the only order call allowed), work only inside
  `agents/<NAME>/` and `submissions/<NAME>/`, no git, do not edit `arena/`. Check `data/` before downloading.

## What phase 1 established (do not rediscover it)
* Spread is the enemy at M1-M15: FX mean reversion is real in mid prices but smaller than 1.2-1.4 pips; simple
  breakouts are noise. Costs shrink relative to the move on higher timeframes — that is the main new freedom.
* Boom/Crash/Jump/DEX/Range Break: memoryless jumps, no edge. Plain Volatility indices: driftless by design.
* A 2-month window lies: ALPHA's London breakout scored PF 2.04 on 7 weeks and 0.95 on the 9 months before.
  Every claim must therefore be shown on the long history, by year/half-year/month.
* Minimum sizes (units): FX 1000; US SP 500 / US Tech 100 / Wall Street 30 / US Small Cap 2000 / Germany 40 /
  UK 100 / ETH 0.1; BTC 0.01; SOL 0.5; LTC, US Oil, Brent 1; XRP 100; XAUUSD 1 oz; Drift Switch 0.1.
  Notional at minimum size matters: S&P ~ $760, Small Cap 2000 ~ $250, FX $1000, SOL ~ $42, LTC ~ $50, oil ~ $85.
* Best honest lead: DELTA's S&P 500 pre-US-open breakout fade, PF ~1.45 over 7.5 months, one symbol.
* Open question: Drift Switch regime-following scores PF 2.8 at spread 1.5 and 0.66 at spread 9; the live spread
  varies 1.5-9 and appeared widest when the system buys.

## Method the supervisor will check
1. Hypothesis first, with a reason someone is on the other side (risk premium, session liquidity, trend persistence).
2. Long history: >= 300 days is the gate, 2+ years where the API has it. Fit on the first 70% of days only; keep
   parameters few; show a plateau, not a peak. Report PF by calendar year and half-year.
3. Report how many parameter sets you tried. A PF of 1.3 from 20 trials is worth more than 1.6 from 2,000.
4. $30 reality: max drawdown <= $12 and worst trade >= -$1.80 at minimum size, including gaps (weekend gaps on
   real markets show up in the bars; stops fill at the open beyond the stop).
5. Deliver in `agents/<NAME>/`: `strategy.py`, `specs.json`, `<Name>Bot.cs` (complete cTrader cBot, same logic,
   hard SL/TP, min volume default, spread filter, daily loss limit, drawdown kill-switch; it must compile —
   `dotnet` 8 is installed: copy the pattern in
   `/tmp/claude-0/-home-user-treasure/497601c6-59f2-5ddb-ac2c-4ccd5910d167/scratchpad/build/DeltaBot/DeltaBot.csproj`
   into a scratch folder and run `dotnet build -c Release -v q`), `NOTES.md` (append a "Phase 2" section as you go),
   and run `python -m arena.evaluate agents/<NAME>/strategy.py --out submissions/<NAME>`.
6. Budget: usage limits interrupted phase 1 twice. Be economical: batch downloads (~12 calls per message), keep
   script output short, write NOTES.md early and often so an interruption loses nothing.
7. If the honest answer is still "no", say so with numbers. Do not loosen anything to get a pass.

Final message: official evaluate printout, strategy in 5 lines, PF by year/half-year, trials count, honest verdict.
