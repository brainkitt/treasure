//+------------------------------------------------------------------+
//| IdxBot.mq5 - "IndexDipBuy" (arena v2, agent IDX)                 |
//+------------------------------------------------------------------+
// Port of IdxBot.cs - re-verify in the MT5 Strategy Tester before live use: contract size, swap and spreads on
// Deriv MT5 may differ from cTrader.
//
// Strategy (agents/IDX/strategy.py):
//   * Buys a US equity-index CFD after a short-term washout and exits one session later. Long only.
//   * H1 bars (InpTimeframe), decisions on CLOSED bars only. Attach once per symbol:
//     "US SP 500" and "US Small Cap 2000" (Deriv MT5). Tested 2024-05..2026-11, H1.
//   * A "session" ends with the H1 bar that OPENS at InpSignalHourNY (default 14:00 New York, US DST rule);
//     session close = close of that bar (price at 15:00 NY). Sessions with < InpMinBarsPerSession H1 bars are
//     ignored. All bar times are converted server -> UTC -> New York before any session logic.
//   * Signal: session close <= lowest of the last N (=7) session closes (incl. today) -> BUY at market.
//   * SL = 3.0 x ATR14(sessions), TP = 0.75 x ATR14, time exit at the close of the 22nd H1 bar after the
//     fill bar. ATR14 = simple mean of the last 14 session true ranges.
//   * Volume = broker minimum (SYMBOL_VOLUME_MIN) unless risk-% sizing is enabled.
//   * Safety: hard SL+TP on every order, spread filter, one position per symbol per magic, duplicate-order guard,
//     daily loss limit (UTC day), equity kill-switch from peak, consecutive-loss pause, planned-risk cap.
//   * Recommended balance: >= 700 USD (smallest balance passing every gate at the minimum volume).
//
// Porting notes:
//   * cTrader label "IDX-DipBuy-<symbol>" -> magic number InpMagic + symbol. The daily-loss limit sums the
//     floating P/L of ALL positions with InpMagic (cBot: all labels starting with LabelBase), so use the same
//     magic on both symbols. Floating P/L = POSITION_PROFIT + POSITION_SWAP (MT5 has no position commission).
//   * MaxVolumeUnits (units) -> InpMaxLots (lots); volume is also capped by SYMBOL_VOLUME_MAX.
//   * SL/TP prices are computed from the Ask at send time (cBot: pips from the fill price). If a distance is
//     below SYMBOL_TRADE_STOPS_LEVEL it is widened to the minimum and logged.
//   * Server->UTC offset is one constant (auto-detected live, re-checked each new bar; 0 in the Strategy Tester
//     unless InpServerUtcOffsetHours is set). History bars from before a broker-side DST change would be shifted
//     by 1 h if the broker server time uses DST (Deriv MT5 server time is UTC, so offset 0).
//   * Kill-switch "Stop()" -> ExpertRemove(). Consecutive losses are counted from closed deals (OnTradeTransaction)
//     with our magic on this symbol; net = profit + swap + commission + fee.
//+------------------------------------------------------------------+
#property copyright "arena v2 / IDX"
#property version   "1.00"
#property description "IndexDipBuy: buy US index CFDs after a 7-session closing low, exit next session."

#include <Trade\Trade.mqh>

//--- inputs ---------------------------------------------------------
input group "General"
input ENUM_TIMEFRAMES InpTimeframe            = PERIOD_H1;   // Strategy timeframe (tested on H1)
input int             InpServerUtcOffsetHours = -99;         // Server UTC offset hours (-99 = auto)
input long            InpMagic                = 26111701;    // Magic number (same on every IDX symbol)
input int             InpSlippagePoints       = 50;          // Max deviation (points)

input group "Strategy"
input int    InpLookbackN         = 7;      // Lookback sessions N (3..20)
input int    InpAtrPeriod         = 14;     // ATR period (sessions) (5..50)
input double InpSlAtr             = 3.0;    // Stop loss (x ATR)
input double InpTpAtr             = 0.75;   // Take profit (x ATR, 0 = none)
input int    InpHoldBars          = 22;     // Time exit after H1 bars
input int    InpSignalHourNY      = 14;     // Signal bar open hour (New York)
input int    InpMinBarsPerSession = 10;     // Min H1 bars per session

input group "Sizing"
input bool   InpUseRiskSizing     = false;  // Use risk-% sizing
input double InpRiskPercent       = 2.0;    // Risk per trade (% balance)
input double InpMaxLots           = 1.0;    // Max volume (lots)
input double InpMaxRiskCapPercent = 12.0;   // Skip if planned risk > % balance

input group "Protection"
input double InpMaxSpread                = 1.0;   // Max spread (price units, 0 = off)
input double InpDailyLossLimitPercent    = 8.0;   // Daily loss limit (% balance)
input double InpMaxEquityDrawdownPercent = 25.0;  // Equity kill-switch DD (% of peak)
input int    InpMaxConsecutiveLosses     = 7;     // Pause after consecutive losses
input int    InpPauseSessions            = 5;     // Pause length (sessions)
input string InpLabel                    = "IDX-DipBuy"; // Label (order comment)

//--- session record -------------------------------------------------
struct SessionRec
  {
   datetime          key;
   double            high;
   double            low;
   double            close;
   int               lastIndex;
   int               lastHourNY;
   int               count;
  };

//--- state ----------------------------------------------------------
CTrade   g_trade;
int      g_utcOffsetHours   = 0;
datetime g_lastBarTime      = 0;
double   g_peakEquity       = 0.0;
bool     g_killed           = false;
bool     g_orderInFlight    = false;
int      g_consecLosses     = 0;
datetime g_pauseUntilUtc    = 0;
datetime g_lastSignalBarTime= 0;
datetime g_dayStartUtc      = 0;
double   g_dayStartBalance  = 0.0;

//+------------------------------------------------------------------+
//| Time helpers                                                     |
//+------------------------------------------------------------------+
int DetectUtcOffset()
  {
   if(InpServerUtcOffsetHours != -99)
      return InpServerUtcOffsetHours;
   if(MQLInfoInteger(MQL_TESTER) != 0)
      return 0;
   double diff = (double)((long)TimeTradeServer() - (long)TimeGMT());
   return (int)MathRound(diff / 3600.0);
  }

datetime ToUtc(const datetime serverTime)
  {
   return (datetime)((long)serverTime - (long)g_utcOffsetHours * 3600);
  }

datetime NowUtc()
  {
   return ToUtc(TimeTradeServer());
  }

datetime DateOf(const datetime t)
  {
   return (datetime)((long)t - ((long)t % 86400));
  }

int HourOf(const datetime t)
  {
   return (int)(((long)t % 86400) / 3600);
  }

datetime MakeDate(const int year, const int month, const int day)
  {
   MqlDateTime s;
   ZeroMemory(s);
   s.year = year;
   s.mon  = month;
   s.day  = day;
   s.hour = 0;
   s.min  = 0;
   s.sec  = 0;
   return StructToTime(s);
  }

// US Eastern time from UTC (rule since 2007: DST from 2nd Sunday of March 02:00 to 1st Sunday of November 02:00)
datetime ToNewYork(const datetime utc)
  {
   MqlDateTime s;
   TimeToStruct(utc, s);
   int y = s.year;

   datetime mar1 = MakeDate(y, 3, 1);
   MqlDateTime m;
   TimeToStruct(mar1, m);
   datetime dstStart = (datetime)((long)mar1 + (long)(((7 - m.day_of_week) % 7) + 7) * 86400 + 7 * 3600); // 02:00 EST = 07:00 UTC

   datetime nov1 = MakeDate(y, 11, 1);
   MqlDateTime n;
   TimeToStruct(nov1, n);
   datetime dstEnd = (datetime)((long)nov1 + (long)((7 - n.day_of_week) % 7) * 86400 + 6 * 3600);         // 02:00 EDT = 06:00 UTC

   bool dst = (utc >= dstStart && utc < dstEnd);
   return (datetime)((long)utc - (dst ? 4 : 5) * 3600);
  }

//+------------------------------------------------------------------+
//| Position helpers (hedging + netting)                             |
//+------------------------------------------------------------------+
int CountOurPositions()
  {
   int cnt = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      if(PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagic)
         cnt++;
     }
   return cnt;
  }

void CloseOurPositions(const string reason)
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol || PositionGetInteger(POSITION_MAGIC) != InpMagic)
         continue;
      if(!g_trade.PositionClose(ticket, (ulong)InpSlippagePoints))
         PrintFormat("%s close FAILED for %I64u: retcode %u (%s)", reason, ticket, g_trade.ResultRetcode(), g_trade.ResultRetcodeDescription());
      else if(g_trade.ResultRetcode() != TRADE_RETCODE_DONE && g_trade.ResultRetcode() != TRADE_RETCODE_DONE_PARTIAL)
         PrintFormat("%s close FAILED for %I64u: retcode %u (%s)", reason, ticket, g_trade.ResultRetcode(), g_trade.ResultRetcodeDescription());
     }
  }

//+------------------------------------------------------------------+
//| Filling mode                                                     |
//+------------------------------------------------------------------+
ENUM_ORDER_TYPE_FILLING PickFilling()
  {
   long fm = SymbolInfoInteger(_Symbol, SYMBOL_FILLING_MODE);
   if((fm & SYMBOL_FILLING_FOK) == SYMBOL_FILLING_FOK)
      return ORDER_FILLING_FOK;
   if((fm & SYMBOL_FILLING_IOC) == SYMBOL_FILLING_IOC)
      return ORDER_FILLING_IOC;
   return ORDER_FILLING_RETURN;
  }

//+------------------------------------------------------------------+
//| Expert initialization                                            |
//+------------------------------------------------------------------+
int OnInit()
  {
   g_utcOffsetHours = DetectUtcOffset();
   g_trade.SetExpertMagicNumber((ulong)InpMagic);
   g_trade.SetDeviationInPoints((ulong)InpSlippagePoints);
   g_trade.SetTypeFilling(PickFilling());

   g_peakEquity      = AccountInfoDouble(ACCOUNT_EQUITY);
   g_dayStartUtc     = DateOf(NowUtc());
   g_dayStartBalance = AccountInfoDouble(ACCOUNT_BALANCE);
   g_lastBarTime     = iTime(_Symbol, InpTimeframe, 0);

   if(InpTimeframe != PERIOD_H1)
      Print("WARNING: IdxBot was designed and tested on H1 bars; InpTimeframe = ", EnumToString(InpTimeframe));
   if(Period() != InpTimeframe)
      PrintFormat("WARNING: chart timeframe %s differs from strategy timeframe %s (the EA uses %s data).",
                  EnumToString(Period()), EnumToString(InpTimeframe), EnumToString(InpTimeframe));

   PrintFormat("IdxBot started on %s %s. Magic=%I64d, bars=%d, volume min=%.2f lots, N=%d, SL=%.2fxATR, TP=%.2fxATR, hold=%d bars, signal hour NY=%d, server UTC offset=%d h",
               _Symbol, EnumToString(InpTimeframe), InpMagic, iBars(_Symbol, InpTimeframe),
               SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN), InpLookbackN, InpSlAtr, InpTpAtr, InpHoldBars,
               InpSignalHourNY, g_utcOffsetHours);
   return INIT_SUCCEEDED;
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   PrintFormat("IdxBot stopped (reason %d). Open positions with magic %I64d on %s: %d", reason, InpMagic, _Symbol, CountOurPositions());
  }

//+------------------------------------------------------------------+
void OnTick()
  {
   CheckEquityKillSwitch();
   if(g_killed)
      return;

   datetime t0 = iTime(_Symbol, InpTimeframe, 0);
   if(t0 == 0)
      return;
   if(g_lastBarTime == 0)
     {
      g_lastBarTime = t0;   // first known bar: wait for the next bar open (like cTrader OnBar)
      return;
     }
   if(t0 == g_lastBarTime)
      return;
   g_lastBarTime = t0;
   OnNewBar();
  }

//+------------------------------------------------------------------+
//| Equivalent of cTrader OnBar: bar index 1 has just closed          |
//+------------------------------------------------------------------+
void OnNewBar()
  {
   if(InpServerUtcOffsetHours == -99 && MQLInfoInteger(MQL_TESTER) == 0)
      g_utcOffsetHours = DetectUtcOffset();

   RollDay();
   CheckEquityKillSwitch();
   ManageTimeExit();
   if(g_killed)
      return;

   datetime closedOpenServer = iTime(_Symbol, InpTimeframe, 1);
   if(closedOpenServer == 0)
      return;
   datetime closedOpenUtc = ToUtc(closedOpenServer);
   if(HourOf(ToNewYork(closedOpenUtc)) != InpSignalHourNY)
      return;
   if(closedOpenServer == g_lastSignalBarTime)
      return;                                     // duplicate guard (one decision per bar)
   g_lastSignalBarTime = closedOpenServer;

   //--- copy closed bars, oldest first; last element = bar index 1
   int need = (InpLookbackN + InpAtrPeriod + 5) * 24;
   MqlRates rates[];
   ArraySetAsSeries(rates, false);
   int got = CopyRates(_Symbol, InpTimeframe, 1, need + 1, rates);
   if(got < 2)
     {
      PrintFormat("CopyRates failed or too little history (%d, error %d) - no decision.", got, GetLastError());
      return;
     }
   int closedIdx = got - 1;
   if(rates[closedIdx].time != closedOpenServer)
     {
      PrintFormat("Closed bar mismatch (%s vs %s) - no decision.", TimeToString(rates[closedIdx].time), TimeToString(closedOpenServer));
      return;
     }

   SessionRec ses[];
   int nSes = BuildSessions(rates, closedIdx, ses);
   int minNeeded = MathMax(InpLookbackN, InpAtrPeriod + 1) + 1;
   if(nSes < minNeeded)
     {
      PrintFormat("Not enough complete sessions (%d) - no decision.", nSes);
      return;
     }
   SessionRec today = ses[nSes - 1];
   if(today.lastIndex != closedIdx)
      return;                                     // the closed bar must end a valid session

   double atr = SessionAtr(ses, nSes);
   double lowest = DBL_MAX;
   for(int k = nSes - InpLookbackN; k < nSes; k++)
      lowest = MathMin(lowest, ses[k].close);
   bool signal = (today.close <= lowest && atr > 0.0);
   PrintFormat("Session %s close=%s lowest%d=%s ATR=%.2f -> %s",
               TimeToString(today.key, TIME_DATE), DoubleToString(today.close, _Digits), InpLookbackN,
               DoubleToString(lowest, _Digits), atr, signal ? "SIGNAL" : "no signal");
   if(!signal)
      return;

   TryEnter(atr);
  }

//+------------------------------------------------------------------+
void TryEnter(const double atr)
  {
   if(g_orderInFlight)
     { Print("Order already in flight - skip."); return; }
   if(CountOurPositions() > 0)
     { PrintFormat("Position already open for %s magic %I64d - skip.", _Symbol, InpMagic); return; }
   if(NowUtc() < g_pauseUntilUtc)
     { PrintFormat("Paused after %d consecutive losses until %s UTC - skip.", InpMaxConsecutiveLosses, TimeToString(g_pauseUntilUtc)); return; }
   if(DailyLossHit())
     { Print("Daily loss limit reached - skip."); return; }

   MqlTick tick;
   if(!SymbolInfoTick(_Symbol, tick))
     { PrintFormat("SymbolInfoTick failed (%d) - skip.", GetLastError()); return; }
   double spread = tick.ask - tick.bid;
   if(InpMaxSpread > 0.0 && spread > InpMaxSpread)
     { PrintFormat("Spread %s > max %s - skip.", DoubleToString(spread, _Digits), DoubleToString(InpMaxSpread, _Digits)); return; }

   double slDist = InpSlAtr * atr;
   double tpDist = InpTpAtr * atr;

   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE_LOSS);
   if(tickValue <= 0.0)
      tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   if(tickSize <= 0.0 || tickValue <= 0.0)
     { PrintFormat("Invalid tick size/value (%g / %g) - skip.", tickSize, tickValue); return; }
   double valuePerLotPerPrice = tickValue / tickSize;    // account currency per 1 lot per 1.0 price

   double vMin  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double vMax  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double vStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(vStep <= 0.0)
      vStep = vMin;
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);

   double volume = vMin;
   if(InpUseRiskSizing)
     {
      double riskMoney = balance * InpRiskPercent / 100.0;
      double raw = riskMoney / (slDist * valuePerLotPerPrice);
      volume = MathMin(raw, InpMaxLots);
      volume = MathFloor(volume / vStep + 1e-9) * vStep;  // round down to step
      if(volume < vMin)
         volume = vMin;
     }
   if(vMax > 0.0 && volume > vMax)
      volume = MathFloor(vMax / vStep + 1e-9) * vStep;
   volume = NormalizeDouble(volume, 8);

   double plannedRisk = slDist * valuePerLotPerPrice * volume;
   if(plannedRisk > balance * InpMaxRiskCapPercent / 100.0)
     {
      PrintFormat("Planned risk %.2f > cap %.2f%% of balance %.2f - skip.", plannedRisk, InpMaxRiskCapPercent, balance);
      return;
     }

   //--- respect broker minimum stop distance
   double point    = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   long   stopsLvl = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   double minDist  = (double)stopsLvl * point;
   if(minDist > 0.0 && slDist < minDist)
     { PrintFormat("SL distance %.5f < stops level %.5f - widened.", slDist, minDist); slDist = minDist; }
   if(tpDist > 0.0 && minDist > 0.0 && tpDist < minDist)
     { PrintFormat("TP distance %.5f < stops level %.5f - widened.", tpDist, minDist); tpDist = minDist; }

   double ask = tick.ask;
   double sl  = NormalizeDouble(MathRound((ask - slDist) / tickSize) * tickSize, _Digits);
   double tp  = 0.0;
   if(tpDist > 0.0)
      tp = NormalizeDouble(MathRound((ask + tpDist) / tickSize) * tickSize, _Digits);

   g_orderInFlight = true;
   bool ok = g_trade.Buy(volume, _Symbol, 0.0, sl, tp, InpLabel);
   g_orderInFlight = false;
   uint rc = g_trade.ResultRetcode();
   if(!ok || (rc != TRADE_RETCODE_DONE && rc != TRADE_RETCODE_DONE_PARTIAL && rc != TRADE_RETCODE_PLACED))
     {
      PrintFormat("ORDER FAILED: retcode %u (%s), error %d", rc, g_trade.ResultRetcodeDescription(), GetLastError());
      return;
     }

   //--- verify the stop loss is attached; close for safety otherwise
   bool found = false;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol || PositionGetInteger(POSITION_MAGIC) != InpMagic)
         continue;
      found = true;
      double pSl = PositionGetDouble(POSITION_SL);
      if(pSl <= 0.0)
        {
         PrintFormat("Position %I64u has no stop loss attached - closing for safety.", ticket);
         if(!g_trade.PositionClose(ticket, (ulong)InpSlippagePoints))
            PrintFormat("Safety close FAILED for %I64u: retcode %u (%s)", ticket, g_trade.ResultRetcode(), g_trade.ResultRetcodeDescription());
         continue;
        }
      PrintFormat("BUY %.2f lots @ %s SL=%s TP=%s (ATR=%.2f, planned risk %.2f)", volume,
                  DoubleToString(PositionGetDouble(POSITION_PRICE_OPEN), _Digits), DoubleToString(pSl, _Digits),
                  DoubleToString(PositionGetDouble(POSITION_TP), _Digits), atr, plannedRisk);
     }
   if(!found)
      PrintFormat("Order sent (retcode %u) but no position found yet for %s magic %I64d.", rc, _Symbol, InpMagic);
  }

//+------------------------------------------------------------------+
//| Close at the close of the HoldBars-th bar after the fill bar      |
//+------------------------------------------------------------------+
void ManageTimeExit()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol || PositionGetInteger(POSITION_MAGIC) != InpMagic)
         continue;
      datetime entryTime = (datetime)PositionGetInteger(POSITION_TIME);
      int shift = iBarShift(_Symbol, InpTimeframe, entryTime, false);   // bars between fill bar and current bar
      if(shift < 0)
         continue;
      if(shift >= InpHoldBars + 1)
        {
         double net = PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
         bool ok = g_trade.PositionClose(ticket, (ulong)InpSlippagePoints);
         uint rc = g_trade.ResultRetcode();
         if(ok && (rc == TRADE_RETCODE_DONE || rc == TRADE_RETCODE_DONE_PARTIAL))
            PrintFormat("Time exit position %I64u after %d bars, net ~%.2f", ticket, shift - 1, net);
         else
            PrintFormat("Time exit FAILED for %I64u: retcode %u (%s)", ticket, rc, g_trade.ResultRetcodeDescription());
        }
     }
  }

//+------------------------------------------------------------------+
//| Consecutive-loss counter from closed deals                       |
//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest &request,
                        const MqlTradeResult &result)
  {
   if(trans.type != TRADE_TRANSACTION_DEAL_ADD)
      return;
   ulong deal = trans.deal;
   if(deal == 0)
      return;
   if(!HistoryDealSelect(deal))
     {
      datetime now = TimeTradeServer();
      if(!HistorySelect(now - 7 * 86400, now + 86400) || !HistoryDealSelect(deal))
         return;
     }
   if(HistoryDealGetString(deal, DEAL_SYMBOL) != _Symbol)
      return;
   if(HistoryDealGetInteger(deal, DEAL_MAGIC) != InpMagic)
      return;
   long entry = HistoryDealGetInteger(deal, DEAL_ENTRY);
   if(entry != DEAL_ENTRY_OUT && entry != DEAL_ENTRY_OUT_BY && entry != DEAL_ENTRY_INOUT)
      return;

   double net = HistoryDealGetDouble(deal, DEAL_PROFIT) + HistoryDealGetDouble(deal, DEAL_SWAP)
                + HistoryDealGetDouble(deal, DEAL_COMMISSION) + HistoryDealGetDouble(deal, DEAL_FEE);
   if(net < 0.0)
      g_consecLosses++;
   else
      g_consecLosses = 0;
   long reason = HistoryDealGetInteger(deal, DEAL_REASON);
   PrintFormat("Closed deal %I64u (position %I64d): net %.2f (reason %s); consecutive losses = %d",
               deal, HistoryDealGetInteger(deal, DEAL_POSITION_ID), net,
               EnumToString((ENUM_DEAL_REASON)reason), g_consecLosses);
   if(g_consecLosses >= InpMaxConsecutiveLosses)
     {
      g_pauseUntilUtc = (datetime)((long)NowUtc() + (long)MathRound(InpPauseSessions * 7.0 / 5.0 * 86400.0));
      g_consecLosses = 0;
      PrintFormat("Consecutive-loss limit hit: pausing new entries until %s UTC", TimeToString(g_pauseUntilUtc));
     }
  }

//+------------------------------------------------------------------+
void RollDay()
  {
   datetime d = DateOf(NowUtc());
   if(d != g_dayStartUtc)
     {
      g_dayStartUtc = d;
      g_dayStartBalance = AccountInfoDouble(ACCOUNT_BALANCE);
     }
  }

bool DailyLossHit()
  {
   double floating = 0.0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic)
         continue;                                      // all IDX symbols (cBot: label prefix)
      floating += PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
     }
   double dayPnl = AccountInfoDouble(ACCOUNT_BALANCE) - g_dayStartBalance + floating;
   return (dayPnl <= -g_dayStartBalance * InpDailyLossLimitPercent / 100.0);
  }

void CheckEquityKillSwitch()
  {
   if(g_killed)
      return;
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   if(eq > g_peakEquity)
      g_peakEquity = eq;
   if(eq < g_peakEquity * (1.0 - InpMaxEquityDrawdownPercent / 100.0))
     {
      g_killed = true;
      PrintFormat("EQUITY KILL-SWITCH: equity %.2f < %.2f%% below peak %.2f. Closing positions and stopping.",
                  eq, InpMaxEquityDrawdownPercent, g_peakEquity);
      CloseOurPositions("Kill-switch");
      ExpertRemove();
     }
  }

//+------------------------------------------------------------------+
//| Sessions / indicators                                            |
//+------------------------------------------------------------------+
// Session key = New-York date of (bar time + (24 - (SignalHourNY + 1)) hours): the session ending with the
// SignalHourNY bar starts with the bar opening at SignalHourNY+1 NY on the previous day.
int BuildSessions(const MqlRates &rates[], const int lastIdx, SessionRec &out[])
  {
   int need  = (InpLookbackN + InpAtrPeriod + 5) * 24;
   int start = MathMax(0, lastIdx - need);
   SessionRec all[];
   int nAll = 0;
   bool have = false;
   SessionRec cur;
   ZeroMemory(cur);
   long shift = (long)(24 - (InpSignalHourNY + 1)) * 3600;

   for(int i = start; i <= lastIdx; i++)
     {
      datetime ny  = ToNewYork(ToUtc(rates[i].time));
      datetime key = DateOf((datetime)((long)ny + shift));
      int hourNY   = HourOf(ny);
      if(!have || key != cur.key)
        {
         if(have)
           {
            ArrayResize(all, nAll + 1, 64);
            all[nAll] = cur;
            nAll++;
           }
         cur.key        = key;
         cur.high       = rates[i].high;
         cur.low        = rates[i].low;
         cur.close      = rates[i].close;
         cur.lastIndex  = i;
         cur.lastHourNY = hourNY;
         cur.count      = 1;
         have = true;
        }
      else
        {
         cur.high       = MathMax(cur.high, rates[i].high);
         cur.low        = MathMin(cur.low, rates[i].low);
         cur.close      = rates[i].close;
         cur.lastIndex  = i;
         cur.lastHourNY = hourNY;
         cur.count++;
        }
     }
   if(have)
     {
      ArrayResize(all, nAll + 1, 64);
      all[nAll] = cur;
      nAll++;
     }

   //--- drop the first (possibly truncated) session, keep valid ones
   ArrayResize(out, 0);
   int nOut = 0;
   for(int k = 1; k < nAll; k++)
     {
      if(all[k].count >= InpMinBarsPerSession && all[k].lastHourNY == InpSignalHourNY)
        {
         ArrayResize(out, nOut + 1, 64);
         out[nOut] = all[k];
         nOut++;
        }
     }
   return nOut;
  }

double SessionAtr(const SessionRec &s[], const int n)
  {
   double sum = 0.0;
   for(int k = n - InpAtrPeriod; k < n; k++)
     {
      double pc = s[k - 1].close;
      double tr = MathMax(s[k].high - s[k].low, MathMax(MathAbs(s[k].high - pc), MathAbs(s[k].low - pc)));
      sum += tr;
     }
   return sum / InpAtrPeriod;
  }
//+------------------------------------------------------------------+
