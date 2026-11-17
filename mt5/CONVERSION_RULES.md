# cBot -> MT5 Expert Advisor conversion rules (shared by all converters)

Goal: a faithful MQL5 port of each cTrader cBot. Same trading logic, same parameters and defaults, same safety
features. Output one complete `.mq5` file per bot in `/home/user/treasure/mt5/`, MQL5 only (no MQL4 functions).

## Must hold
1. **Same decisions on closed bars.** cTrader `OnBar` + `Bars.Last(1)` = MQL5 detect a new bar in `OnTick`
   (compare `iTime(_Symbol, tf, 0)` with the stored time) and use bar index 1 (`CopyRates`/`iClose(..,1)`).
   Use the timeframe the strategy was tested on through an input (`InpTimeframe`, default = tested TF) so the EA
   works whatever chart it is attached to; warn in the Experts log if the chart differs.
2. **Time zones.** cTrader `Server.Time` in these bots is UTC. MT5 bar times are broker SERVER time. Add input
   `InpServerUtcOffsetHours` (default `-99` = auto: `round((TimeTradeServer() - TimeGMT())/3600)`, falling back to
   0 in the Strategy Tester where TimeGMT() is unreliable). Convert every bar time to UTC before any hour/session
   logic. New York time (IDX) = UTC with the US DST rule exactly as the cBot does it.
3. **Volume.** cTrader volume is in units; MT5 is in lots and Deriv MT5 contract sizes can differ from cTrader.
   Default volume = `SYMBOL_VOLUME_MIN`, normalised to `SYMBOL_VOLUME_STEP`, capped by `SYMBOL_VOLUME_MAX` and a
   `InpMaxLots` input. Risk money per lot per 1.0 price move = `SYMBOL_TRADE_TICK_VALUE / SYMBOL_TRADE_TICK_SIZE`
   (use `SYMBOL_TRADE_TICK_VALUE_LOSS` when available). Keep the cBot's planned-risk cap: if stop distance x money
   per price x lots > cap % of balance, SKIP the trade and log why. Optional risk-% sizing exactly as in the cBot.
4. **Orders.** `CTrade` from `<Trade\Trade.mqh>`, `SetExpertMagicNumber(InpMagic)`, deviation/slippage input,
   filling mode from `SYMBOL_FILLING_MODE` (FOK/IOC/RETURN fallback). SL (and TP if used) attached on the order;
   respect `SYMBOL_TRADE_STOPS_LEVEL`; if the position ends up without SL, close it immediately (as the cBot does).
   Check `ResultRetcode()` and log failures. One position per symbol per magic (duplicate-order guard).
5. **Same safety features as the cBot:** spread filter (in price units, `Ask-Bid`), daily loss limit (day by UTC),
   equity kill-switch from peak, consecutive-loss pause (count from closed deals with our magic, using
   `OnTradeTransaction` or `HistorySelect`), rollover/session blocks, time exit counted in bars of the strategy TF,
   trailing stop ratcheted on bar closes only (never per tick, as tested). Spread logging (VolbBot) -> `Print` +
   optional CSV via `FileOpen(..., FILE_COMMON)`.
6. **Hedging vs netting.** Work on both: select positions by symbol + magic (`PositionsTotal`/`PositionGetTicket`).
7. **Inputs** grouped with `input group`, same names/defaults/meaning as the cBot parameters; header comment with
   the strategy summary, tested symbol/timeframe, recommended balance and the note "port of <X>Bot.cs - re-verify
   in the MT5 Strategy Tester before live use: contract size, swap and spreads on Deriv MT5 may differ from cTrader".
8. **No compiler is available** in this environment. Write conservative, standard MQL5 (`#property strict` is NOT
   valid in MQL5 — use `#property copyright/version` only). Re-read the file once at the end checking: every function
   declared, all types correct (datetime/long/ulong/double), arrays set with ArraySetAsSeries where indexed as series,
   no MQL4 calls (OrderSend with old signature, MarketInfo, Bid/Ask globals), every `CopyXxx` return checked.
9. Do not change trading logic or defaults. If something cannot be ported exactly, implement the closest equivalent
   and list it under "Porting notes" in the header comment.
