//+------------------------------------------------------------------+
//| VolaBot.mq5 - MetaTrader 5 Expert Advisor                         |
//|                                                                  |
//| RESEARCH / DEMO ONLY - this strategy did NOT pass validation      |
//| (negative expectancy after costs); do not trade with real money.  |
//|                                                                  |
//| Port of VolaBot.cs (ctrader-arena/agents/VOLA) - re-verify in the |
//| MT5 Strategy Tester before live use: contract size, swap and      |
//| spreads on Deriv MT5 may differ from cTrader.                     |
//+------------------------------------------------------------------+
// Strategy: "Range Break 200 breakout-follow" (C1), Deriv Range Break 200 Index, M5.
//   Recommended (research) balance: 30 USD at broker-minimum volume (research notes: a responsible minimum
//   would be ~440 USD even if an edge existed). Official evaluation: PF 0.92, NOT QUALIFIED; failed two
//   pre-declared confirmations on unseen months. Delivered for completeness / forward-logging only.
//
// Logic (once per CLOSED bar of InpTimeframe; bar [1] = cTrader Bars.Last(1) = signal bar):
//   HH = highest High of the N closed bars BEFORE the signal bar, LL = lowest Low of those bars
//   ATR = simple mean of True Range over the last AtrPeriod closed bars (signal bar included)
//   BUY  if Close[signal] > HH ; SELL if Close[signal] < LL
//   only if the signal bar CLOSES (open + 5 min) at or before LastEntryHour:59 UTC
//   hard stop = K * ATR attached to the order; trailing stop of the same distance (K * ATR at entry)
//   ratcheted on bar closes only (short SL = Close + spread + dist)
//   time exit after H closed bars in the trade (fill bar is bar 1 of the count, as in the cBot)
//   force-flat during the first 5 minutes of ForceFlatHour UTC (default 21:00, the rollover)
// Safety: one position per symbol+magic (duplicate guard), broker-minimum volume by default (optional risk-%
//   sizing, capped), spread gate, daily loss limit (% of UTC-day start balance, closes the position),
//   equity kill-switch from peak (closes and removes the EA), consecutive-loss pause (hours), retcode checks.
//
// Porting notes:
//   * cTrader volume "units" -> MT5 lots. InpVolumeLots = 0 uses SYMBOL_VOLUME_MIN; risk per lot per 1.0
//     price = TICK_VALUE(_LOSS)/TICK_SIZE. Extra cap input InpMaxLots.
//   * Planned-risk cap: the cBot falls back to minimum volume when risk-% sizing exceeds the cap and would
//     still trade if even the minimum exceeded it; per CONVERSION_RULES the EA SKIPS such a trade and logs it.
//   * cTrader "Label" -> InpMagic (position identity); InpBotLabel is used in logs. The entry ATR is kept in
//     memory and in the order comment ("atr=..."); if neither is readable (e.g. after a restart with a
//     rewritten comment) no trailing is done, exactly as the cBot (ToDoubleOrDefault -> 0).
//   * Bars-in-trade counter lives in memory as in the cBot (restarts at 0 after an EA restart).
//   * Times: bar times are broker server time; converted to UTC with InpServerUtcOffsetHours (-99 = auto).
//     The signal-bar close is open + 300 s on M5 (open + 0 on other timeframes, as the cBot does).
//   * SL computed from Ask/Bid at send and re-aligned to the fill price; distances below
//     SYMBOL_TRADE_STOPS_LEVEL are widened and logged; trailing updates violating stops/freeze level are
//     skipped and logged; a position left without SL is closed immediately. A zero ATR (no SL possible)
//     skips the entry.
//   * Consecutive losses counted from closed deals (OnTradeTransaction), net = profit+swap+commission.
//   * Kill-switch: cBot Stop() -> ExpertRemove().
//+------------------------------------------------------------------+
#property copyright "ctrader-arena VOLA port - research/demo only"
#property version   "1.00"
#property description "RESEARCH / DEMO ONLY - did NOT pass validation (negative expectancy after costs)."
#property description "Range Break 200 Index M5 Donchian close-breakout follower."

#include <Trade\Trade.mqh>

//---- general
input group "General"
input ENUM_TIMEFRAMES InpTimeframe            = PERIOD_M5;    // Strategy timeframe (tested: M5)
input int             InpServerUtcOffsetHours = -99;          // Server UTC offset hours (-99 = auto)
input long            InpMagic                = 450200;       // Magic number (replaces cBot Label)
input int             InpDeviationPoints      = 50;           // Max slippage (points)
input string          InpBotLabel             = "VOLA-RB200"; // Label (log prefix)

//---- signal
input group "Signal"
input int    InpN         = 24;    // Donchian lookback N (bars)
input int    InpAtrPeriod = 24;    // ATR period (bars)

//---- exits
input group "Exits"
input double InpK = 2.0;           // Stop & trail (x ATR)
input int    InpH = 48;            // Max bars in trade (H)

//---- session
input group "Session"
input int    InpLastEntryHour = 16;  // Last entry hour UTC (signal bar close)
input int    InpForceFlatHour = 21;  // Force flat at hour UTC (-1 = off)

//---- sizing
input group "Sizing"
input double InpVolumeLots     = 0.0;   // Volume in lots (0 = broker minimum)
input double InpRiskPercent    = 0.0;   // Risk % of balance per trade (0 = off)
input double InpMaxRiskPercent = 3.0;   // Max risk % per trade (cap)
input double InpMaxLots        = 1.0;   // Max lots (hard cap)

//---- safety
input group "Safety"
input double InpMaxSpread         = 2.5;   // Max spread (price units, Ask-Bid)
input double InpDailyLossPercent  = 10.0;  // Daily loss limit (% of day-start balance)
input double InpKillSwitchPercent = 25.0;  // Equity kill-switch (% drawdown from peak)
input int    InpMaxConsecLosses   = 6;     // Max consecutive losses before pause
input int    InpPauseHours        = 24;    // Pause length after loss streak (hours)

//---- state
CTrade          g_trade;
ENUM_TIMEFRAMES g_tf              = PERIOD_M5;
datetime        g_lastBarTime     = 0;
int             g_barsInTrade     = 0;
double          g_peakEquity      = 0.0;
double          g_dayStartBalance = 0.0;
datetime        g_day             = 0;
int             g_consecLosses    = 0;
datetime        g_pausedUntil     = 0;      // UTC
bool            g_killed          = false;
bool            g_orderInFlight   = false;
double          g_entryAtr        = 0.0;
long            g_posId           = 0;
int             g_utcOffsetSec    = 0;

//+------------------------------------------------------------------+
//| Time helpers                                                     |
//+------------------------------------------------------------------+
void UpdateUtcOffset()
{
   if(InpServerUtcOffsetHours != -99)
   {
      g_utcOffsetSec = InpServerUtcOffsetHours * 3600;
      return;
   }
   if(MQLInfoInteger(MQL_TESTER) || MQLInfoInteger(MQL_OPTIMIZATION))
   {
      g_utcOffsetSec = 0;   // TimeGMT() is not reliable in the Strategy Tester
      return;
   }
   datetime gmt = TimeGMT();
   datetime srv = TimeTradeServer();
   if(gmt <= 0 || srv <= 0) { g_utcOffsetSec = 0; return; }
   g_utcOffsetSec = (int)MathRound((double)(srv - gmt) / 3600.0) * 3600;
}

datetime ToUtc(const datetime serverTime) { return (datetime)(serverTime - g_utcOffsetSec); }
datetime UtcNow()                         { return ToUtc(TimeCurrent()); }
datetime UtcDay(const datetime t)         { return (datetime)(((long)t / 86400) * 86400); }

string FmtTime(const datetime t)
{
   MqlDateTime dt;
   TimeToStruct(t, dt);
   return StringFormat("%04d-%02d-%02d %02d:%02d", dt.year, dt.mon, dt.day, dt.hour, dt.min);
}

//+------------------------------------------------------------------+
//| Symbol / trade helpers                                           |
//+------------------------------------------------------------------+
ENUM_ORDER_TYPE_FILLING FillingMode()
{
   long fm = SymbolInfoInteger(_Symbol, SYMBOL_FILLING_MODE);
   if((fm & SYMBOL_FILLING_FOK) == SYMBOL_FILLING_FOK) return ORDER_FILLING_FOK;
   if((fm & SYMBOL_FILLING_IOC) == SYMBOL_FILLING_IOC) return ORDER_FILLING_IOC;
   return ORDER_FILLING_RETURN;
}

double TickSize()
{
   double ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   return (ts > 0.0 ? ts : _Point);
}

double NormPrice(const double p)
{
   double ts = TickSize();
   return NormalizeDouble(MathRound(p / ts) * ts, _Digits);
}

double StopsLevelDist()
{
   return (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;
}

double ModifyMinDist()
{
   long sl = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   long fl = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL);
   return (double)MathMax(sl, fl) * _Point;
}

double CurrentSpread()
{
   MqlTick tk;
   if(!SymbolInfoTick(_Symbol, tk)) return 0.0;
   return tk.ask - tk.bid;
}

// account currency lost per 1.0 lot per 1.0 price move
double MoneyPerPricePerLot()
{
   double tv = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE_LOSS);
   if(tv <= 0.0) tv = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tv <= 0.0 || ts <= 0.0) return 0.0;
   return tv / ts;
}

double FloorToStep(const double v)
{
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(step <= 0.0) step = 0.01;
   int digits = (int)MathMax(0.0, MathCeil(-MathLog10(step) - 1e-9));
   return NormalizeDouble(MathFloor(v / step + 1e-9) * step, digits);
}

bool RetcodeOk(const uint rc)
{
   return (rc == TRADE_RETCODE_DONE || rc == TRADE_RETCODE_DONE_PARTIAL || rc == TRADE_RETCODE_PLACED);
}

ulong MyPositionTicket()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong t = PositionGetTicket(i);
      if(t == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagic)
         return t;
   }
   return 0;
}

bool ClosePos(const ulong ticket, const string what)
{
   if(!g_trade.PositionClose(ticket) || !RetcodeOk(g_trade.ResultRetcode()))
   {
      PrintFormat("%s close (%s) FAILED: retcode %u %s", InpBotLabel, what, g_trade.ResultRetcode(),
                  g_trade.ResultRetcodeDescription());
      return false;
   }
   PrintFormat("%s closed position #%I64u (%s)", InpBotLabel, ticket, what);
   return true;
}

void CloseMine(const string why)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong t = PositionGetTicket(i);
      if(t == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagic)
         ClosePos(t, why);
   }
}

bool ModifySL(const ulong ticket, const double sl, const string what)
{
   if(!PositionSelectByTicket(ticket)) return false;
   long   type = PositionGetInteger(POSITION_TYPE);
   double tp   = PositionGetDouble(POSITION_TP);
   MqlTick tk;
   if(!SymbolInfoTick(_Symbol, tk)) { PrintFormat("%s %s: no tick", InpBotLabel, what); return false; }
   double minD = ModifyMinDist();
   if(type == POSITION_TYPE_BUY && sl >= tk.bid - minD)
   {
      PrintFormat("%s %s skipped: SL %.5f not below bid %.5f - stops/freeze level %.5f", InpBotLabel, what, sl, tk.bid, minD);
      return false;
   }
   if(type == POSITION_TYPE_SELL && sl <= tk.ask + minD)
   {
      PrintFormat("%s %s skipped: SL %.5f not above ask %.5f + stops/freeze level %.5f", InpBotLabel, what, sl, tk.ask, minD);
      return false;
   }
   if(!g_trade.PositionModify(ticket, sl, tp) || !RetcodeOk(g_trade.ResultRetcode()))
   {
      PrintFormat("%s %s FAILED: retcode %u %s", InpBotLabel, what, g_trade.ResultRetcode(), g_trade.ResultRetcodeDescription());
      return false;
   }
   return true;
}

double ParseAtrFromComment(const string c)
{
   int i = StringFind(c, "atr=");
   if(i < 0) return 0.0;
   return StringToDouble(StringSubstr(c, i + 4));
}

// ATR at entry (trail distance fixed at entry, as in strategy.py)
double EntryAtr(const ulong ticket, const double fallback)
{
   if(g_entryAtr > 0.0) return g_entryAtr;
   if(PositionSelectByTicket(ticket))
   {
      double a = ParseAtrFromComment(PositionGetString(POSITION_COMMENT));
      if(a > 0.0) return a;
   }
   return fallback;
}

//+------------------------------------------------------------------+
//| ATR: simple mean of True Range (r[] series, r[0] = last closed)  |
//+------------------------------------------------------------------+
double AtrTR(const MqlRates &r[])
{
   double s = 0.0;
   for(int j = 0; j < InpAtrPeriod; j++)
   {
      double pc = r[j + 1].close;
      double tr = MathMax(r[j].high - r[j].low, MathMax(MathAbs(r[j].high - pc), MathAbs(r[j].low - pc)));
      s += tr;
   }
   return s / InpAtrPeriod;
}

//+------------------------------------------------------------------+
//| Sizing (cBot inline sizing, in lots)                             |
//+------------------------------------------------------------------+
double CalcLots(const double stopDist)
{
   double vmin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double vmax = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double maxLots = (InpMaxLots > 0.0 ? MathMin(vmax, InpMaxLots) : vmax);
   double mpp  = MoneyPerPricePerLot();
   double bal  = AccountInfoDouble(ACCOUNT_BALANCE);
   if(mpp <= 0.0) { PrintFormat("%s tick value/size unknown - skip", InpBotLabel); return 0.0; }

   double vol = (InpVolumeLots > 0.0 ? InpVolumeLots : vmin);
   if(InpRiskPercent > 0.0)
   {
      double riskUsd = bal * MathMin(InpRiskPercent, InpMaxRiskPercent) / 100.0;
      double perLot  = stopDist * mpp;
      if(perLot > 0.0) vol = riskUsd / perLot;
   }
   vol = FloorToStep(MathMax(vol, vmin));
   vol = MathMax(vol, vmin);
   if(vol > maxLots) vol = FloorToStep(maxLots);
   if(vol < vmin)
   {
      PrintFormat("%s InpMaxLots %.4f is below the broker minimum %.4f - skip", InpBotLabel, InpMaxLots, vmin);
      return 0.0;
   }
   double capUsd    = bal * InpMaxRiskPercent / 100.0;
   double riskAtVol = stopDist * mpp * vol;
   if(InpRiskPercent > 0.0 && riskAtVol > capUsd && vol > vmin) vol = vmin;
   riskAtVol = stopDist * mpp * vol;
   if(riskAtVol > capUsd)
   {
      PrintFormat("%s planned risk %.2f at %.2f lots exceeds cap %.2f (%.1f%% of balance) - skip", InpBotLabel,
                  riskAtVol, vol, capUsd, InpMaxRiskPercent);
      return 0.0;
   }
   return vol;
}

//+------------------------------------------------------------------+
//| Risk: day roll, kill-switch, daily loss (cBot CheckRisk)         |
//+------------------------------------------------------------------+
bool CheckRisk()
{
   datetime d = UtcDay(UtcNow());
   if(d != g_day) { g_day = d; g_dayStartBalance = AccountInfoDouble(ACCOUNT_BALANCE); }
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   g_peakEquity = MathMax(g_peakEquity, eq);
   if(!g_killed && eq < g_peakEquity * (1.0 - InpKillSwitchPercent / 100.0))
   {
      g_killed = true;
      PrintFormat("%s KILL-SWITCH: equity %.2f < %.0f%% below peak %.2f. Closing and stopping.", InpBotLabel, eq,
                  InpKillSwitchPercent, g_peakEquity);
      CloseMine("kill-switch");
      ExpertRemove();
      return false;
   }
   double dayPnl = eq - g_dayStartBalance;
   if(dayPnl < -g_dayStartBalance * InpDailyLossPercent / 100.0)
   {
      ulong t = MyPositionTicket();
      if(t > 0) ClosePos(t, "daily loss limit");
      return false;
   }
   return !g_killed;
}

//+------------------------------------------------------------------+
//| Entry                                                            |
//+------------------------------------------------------------------+
bool OpenPosition(const int side, const double lots, const double stopDist, const double atr,
                  const double hh, const double ll)
{
   MqlTick tk;
   if(!SymbolInfoTick(_Symbol, tk)) { PrintFormat("%s open: no tick", InpBotLabel); return false; }
   // the ATR at entry is stored in the comment so the trailing distance stays constant (as in strategy.py)
   string cmt   = "atr=" + DoubleToString(atr, 8);
   string sname = (side > 0 ? "BUY" : "SELL");
   bool sent;
   if(side > 0) sent = g_trade.Buy(lots, _Symbol, 0.0, NormPrice(tk.ask - stopDist), 0.0, cmt);
   else         sent = g_trade.Sell(lots, _Symbol, 0.0, NormPrice(tk.bid + stopDist), 0.0, cmt);
   uint rc = g_trade.ResultRetcode();
   if(!sent || !RetcodeOk(rc))
   {
      PrintFormat("%s order failed: %s retcode %u %s", InpBotLabel, sname, rc, g_trade.ResultRetcodeDescription());
      return false;
   }
   ulong ticket = MyPositionTicket();
   if(ticket == 0 || !PositionSelectByTicket(ticket))
   {
      PrintFormat("%s %s sent (retcode %u) but position not visible yet - will be managed on next bar", InpBotLabel, sname, rc);
      return true;
   }
   g_posId = PositionGetInteger(POSITION_IDENTIFIER);
   double open = PositionGetDouble(POSITION_PRICE_OPEN);
   double sl   = PositionGetDouble(POSITION_SL);
   double want = NormPrice(side > 0 ? open - stopDist : open + stopDist);
   if(sl <= 0.0 || MathAbs(want - sl) > TickSize() * 0.5)
   {
      if(!ModifySL(ticket, want, "align SL to fill") && sl <= 0.0)
      {
         PrintFormat("%s position #%I64u has no SL - closing immediately", InpBotLabel, ticket);
         ClosePos(ticket, "no SL");
         return false;
      }
   }
   PrintFormat("%s %s %.2f lots at %.5f, SL dist %.2f (K %.2f x ATR %.2f), HH %.5f LL %.5f", InpBotLabel, sname, lots,
               open, stopDist, InpK, atr, hh, ll);
   return true;
}

//+------------------------------------------------------------------+
//| Per closed bar (cBot OnBar)                                      |
//+------------------------------------------------------------------+
void OnNewBar()
{
   UpdateUtcOffset();
   int need = MathMax(InpN, InpAtrPeriod) + 3;
   MqlRates r[];
   ArraySetAsSeries(r, true);
   int got = CopyRates(_Symbol, g_tf, 1, need, r);
   if(got < need) return;                         // not enough history yet

   bool riskOk = CheckRisk();
   if(g_killed) return;
   double atr   = AtrTR(r);
   double close = r[0].close;

   //---- manage open position (trail on closes, time exit)
   ulong ticket = MyPositionTicket();
   if(ticket > 0)
   {
      if(!PositionSelectByTicket(ticket)) return;
      long   type = PositionGetInteger(POSITION_TYPE);
      double sl   = PositionGetDouble(POSITION_SL);
      if(g_posId == 0) g_posId = PositionGetInteger(POSITION_IDENTIFIER);
      g_barsInTrade++;
      if(g_barsInTrade >= InpH) { ClosePos(ticket, "time exit"); return; }
      double dist = InpK * EntryAtr(ticket, 0.0);
      if(dist > 0.0)
      {
         double newSl  = (type == POSITION_TYPE_BUY ? close - dist : close + CurrentSpread() + dist);
         bool   better = (sl <= 0.0 || (type == POSITION_TYPE_BUY ? newSl > sl : newSl < sl));
         if(better) ModifySL(ticket, NormPrice(newSl), "trail");
      }
      if(PositionSelectByTicket(ticket) && PositionGetDouble(POSITION_SL) <= 0.0)
      {
         PrintFormat("%s position #%I64u has no SL - closing immediately", InpBotLabel, ticket);
         ClosePos(ticket, "no SL");
      }
      return;
   }
   g_orderInFlight = false;
   if(!riskOk || UtcNow() < g_pausedUntil) return;

   //---- entry
   datetime sigCloseUtc = ToUtc(r[0].time) + (g_tf == PERIOD_M5 ? 300 : 0);
   MqlDateTime dt;
   TimeToStruct(sigCloseUtc, dt);
   if(dt.hour > InpLastEntryHour) return;
   double hh = -DBL_MAX, ll = DBL_MAX;
   for(int j = 1; j <= InpN; j++) { hh = MathMax(hh, r[j].high); ll = MathMin(ll, r[j].low); }
   int side = 0;
   if(close > hh) side = 1;
   else if(close < ll) side = -1;
   if(side == 0 || g_orderInFlight) return;
   double spread = CurrentSpread();
   if(spread > InpMaxSpread) { PrintFormat("%s spread %.2f > max %.2f: skip", InpBotLabel, spread, InpMaxSpread); return; }

   double stopDist = InpK * atr;
   if(stopDist <= 0.0) { PrintFormat("%s ATR is zero - no stop possible, skip", InpBotLabel); return; }
   double minStop = StopsLevelDist();
   if(minStop > 0.0 && stopDist <= minStop)
   {
      PrintFormat("%s stop distance %.5f below broker stops level %.5f - widened", InpBotLabel, stopDist, minStop);
      stopDist = minStop + TickSize();
   }
   double lots = CalcLots(stopDist);
   if(lots <= 0.0) return;
   if(MyPositionTicket() != 0) return;            // duplicate-order guard

   g_orderInFlight = true;
   if(OpenPosition(side, lots, stopDist, atr, hh, ll))
   {
      g_barsInTrade = 0;
      g_entryAtr    = atr;
   }
   else
      g_orderInFlight = false;
}

//+------------------------------------------------------------------+
//| Expert initialization                                            |
//+------------------------------------------------------------------+
int OnInit()
{
   if(InpN < 2 || InpAtrPeriod < 2 || InpK <= 0.0 || InpH < 1 || InpLastEntryHour < 0 || InpLastEntryHour > 23 ||
      InpForceFlatHour < -1 || InpForceFlatHour > 23 || InpKillSwitchPercent <= 0.0 || InpDailyLossPercent <= 0.0 ||
      InpMaxConsecLosses < 1 || InpPauseHours < 1)
   {
      Print("VolaBot: invalid input parameters");
      return INIT_PARAMETERS_INCORRECT;
   }
   g_tf = (InpTimeframe == PERIOD_CURRENT ? (ENUM_TIMEFRAMES)_Period : InpTimeframe);
   if(g_tf != PERIOD_M5)
      PrintFormat("WARNING: designed and validated on M5 bars; strategy timeframe is %s", EnumToString(g_tf));
   if((ENUM_TIMEFRAMES)_Period != g_tf)
      PrintFormat("WARNING: chart timeframe %s differs from strategy timeframe %s - the EA uses %s bars",
                  EnumToString((ENUM_TIMEFRAMES)_Period), EnumToString(g_tf), EnumToString(g_tf));

   g_trade.SetExpertMagicNumber((ulong)InpMagic);
   g_trade.SetDeviationInPoints((ulong)MathMax(0, InpDeviationPoints));
   g_trade.SetTypeFilling(FillingMode());
   g_trade.SetAsyncMode(false);

   UpdateUtcOffset();
   g_peakEquity      = AccountInfoDouble(ACCOUNT_EQUITY);
   g_dayStartBalance = AccountInfoDouble(ACCOUNT_BALANCE);
   g_day             = UtcDay(UtcNow());
   g_lastBarTime     = iTime(_Symbol, g_tf, 0);

   ulong ticket = MyPositionTicket();
   if(ticket > 0 && PositionSelectByTicket(ticket))
   {
      g_barsInTrade = 0;
      g_posId       = PositionGetInteger(POSITION_IDENTIFIER);
      g_entryAtr    = ParseAtrFromComment(PositionGetString(POSITION_COMMENT));
   }
   PrintFormat("VolaBot started on %s %s. NOTE: no validated edge - RESEARCH / DEMO ONLY. min volume %.2f, utcOffset %dh",
               _Symbol, EnumToString(g_tf), SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN), g_utcOffsetSec / 3600);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   PrintFormat("VolaBot stopped (reason %d).", reason);
}

//+------------------------------------------------------------------+
//| Tick: risk checks intrabar, force-flat, new-bar detection        |
//+------------------------------------------------------------------+
void OnTick()
{
   if(g_killed) return;
   CheckRisk();                                   // kill-switch and daily loss are checked intrabar as well
   if(g_killed) return;
   ulong ticket = MyPositionTicket();
   if(ticket > 0 && InpForceFlatHour >= 0)
   {
      MqlDateTime dt;
      TimeToStruct(UtcNow(), dt);
      if(dt.hour == InpForceFlatHour && dt.min < 5) ClosePos(ticket, "force-flat before rollover");
   }

   datetime t0 = iTime(_Symbol, g_tf, 0);
   if(t0 == 0) return;
   if(g_lastBarTime == 0) { g_lastBarTime = t0; return; }
   if(t0 == g_lastBarTime) return;
   g_lastBarTime = t0;
   OnNewBar();
}

//+------------------------------------------------------------------+
//| Closed deals -> consecutive-loss pause (cBot OnPositionClosed)   |
//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction &trans, const MqlTradeRequest &request, const MqlTradeResult &result)
{
   if(trans.type != TRADE_TRANSACTION_DEAL_ADD || trans.deal == 0) return;
   if(!HistoryDealSelect(trans.deal)) return;
   if(HistoryDealGetString(trans.deal, DEAL_SYMBOL) != _Symbol) return;
   long magic = HistoryDealGetInteger(trans.deal, DEAL_MAGIC);
   long posId = HistoryDealGetInteger(trans.deal, DEAL_POSITION_ID);
   if(magic != InpMagic && (g_posId == 0 || posId != g_posId)) return;
   long entry = HistoryDealGetInteger(trans.deal, DEAL_ENTRY);
   if(entry != DEAL_ENTRY_OUT && entry != DEAL_ENTRY_OUT_BY && entry != DEAL_ENTRY_INOUT) return;
   if(MyPositionTicket() != 0) return;            // partial close: position still open
   long reason = HistoryDealGetInteger(trans.deal, DEAL_REASON);

   double net = 0.0;
   if(HistorySelectByPosition(posId))
   {
      int n = HistoryDealsTotal();
      for(int i = 0; i < n; i++)
      {
         ulong d = HistoryDealGetTicket(i);
         if(d == 0) continue;
         net += HistoryDealGetDouble(d, DEAL_PROFIT) + HistoryDealGetDouble(d, DEAL_SWAP) +
                HistoryDealGetDouble(d, DEAL_COMMISSION);
      }
   }

   g_entryAtr = 0.0;
   g_posId    = 0;
   g_consecLosses = (net < 0.0 ? g_consecLosses + 1 : 0);
   PrintFormat("%s closed net %.2f reason %s consecLosses %d", InpBotLabel, net,
               EnumToString((ENUM_DEAL_REASON)reason), g_consecLosses);
   if(g_consecLosses >= InpMaxConsecLosses)
   {
      g_pausedUntil = (datetime)(UtcNow() + InpPauseHours * 3600);
      PrintFormat("%s loss streak %d: entries paused until %s UTC", InpBotLabel, g_consecLosses, FmtTime(g_pausedUntil));
      g_consecLosses = 0;
   }
}
//+------------------------------------------------------------------+
