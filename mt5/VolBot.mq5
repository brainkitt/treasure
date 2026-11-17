//+------------------------------------------------------------------+
//| VolBot.mq5 - MetaTrader 5 Expert Advisor                          |
//|                                                                  |
//| RESEARCH / DEMO ONLY - this strategy did NOT pass validation      |
//| (negative expectancy after costs); do not trade with real money.  |
//|                                                                  |
//| Port of VolBot.cs (ctrader-arena/agents/VOL) - re-verify in the   |
//| MT5 Strategy Tester before live use: contract size, swap and      |
//| spreads on Deriv MT5 may differ from cTrader.                     |
//+------------------------------------------------------------------+
// Strategy: "Drift Switch regime-trend follower" (efficiency ratio), default Deriv Drift Switch Index 20, M5.
//   Recommended (research) balance: 30 USD, broker-minimum volume.
//   Official evaluation at the widest observed DSI20 spread (4.05): PF 0.65, all folds negative, NOT QUALIFIED.
//
// Logic (evaluated once per CLOSED bar of InpTimeframe; bar [1] = cTrader Bars.Last(1)):
//   er    = (Close[1] - Close[1+N]) / sum_{k=1..N} |Close[k] - Close[k+1]|   (efficiency ratio)
//   ATR   = simple mean of (High - Low) of the last AtrPeriod closed bars
//   BUY   if er > Threshold   (SELL if er < -Threshold and AllowShorts = true)
//   stop  = StopAtr * ATR (hard SL on the order)
//   trail = TrailAtr * ATR(at entry), ratcheted on bar closes only: long SL = max(SL, Close - trail);
//           never ratcheted on the close of the fill bar
//   exit  = time exit once MaxBars closed bars have elapsed after the fill bar
//   No signal when the window contains a data gap (> 1.5 bar periods between consecutive bars).
//   No new entries when the UTC hour of the new (fill) bar's open is inside [NoEntryFromHour, NoEntryToHour)
//   (default 19:00-21:00 UTC, before the 21:00 UTC rollover).
// Safety: one position per symbol+magic (duplicate guard), broker-minimum volume by default (optional risk-%
//   sizing, planned-risk cap -> skip), live spread gate, daily loss limit (account ccy, UTC day), equity
//   drawdown kill-switch (closes and removes the EA), consecutive-loss pause, retcode checks, no-SL guard.
//
// Porting notes:
//   * cTrader volume "units" -> MT5 lots. InpVolumeLots = 0 uses SYMBOL_VOLUME_MIN (cBot: VolumeInUnitsMin);
//     risk per lot per 1.0 price = TICK_VALUE(_LOSS)/TICK_SIZE. Extra cap input InpMaxLots.
//   * cTrader "Label" -> InpMagic (position identity). InpLabel is kept for log lines only. The order
//     comment is "er=..;atr=.." as in the cBot; the entry ATR is also kept in memory (brokers may rewrite
//     comments). After a restart the comment is parsed; if unreadable the current ATR is used (as the cBot).
//   * Bar counting (time exit / pause) uses bar open times (iBarShift) instead of cTrader bar indices.
//     On restart with an open position the time-exit clock restarts at the current bar (as the cBot).
//   * Times: bar times are broker server time; converted to UTC with InpServerUtcOffsetHours (-99 = auto).
//   * SL is computed from Ask/Bid at send and then re-aligned to the actual fill price (cTrader relative SL
//     is measured from the fill). SL distances below SYMBOL_TRADE_STOPS_LEVEL are widened and logged; a
//     trailing update that would violate stops/freeze level is skipped and logged. A position found without
//     SL is closed immediately.
//   * Consecutive losses are counted from closed deals (OnTradeTransaction); net = profit+swap+commission of
//     all deals of the position (cTrader NetProfit).
//   * Kill-switch: cBot Stop() -> ExpertRemove().
//   * The rollover no-entry window exists in VolBot.cs but not in strategy.py; the cBot is followed.
//+------------------------------------------------------------------+
#property copyright "ctrader-arena VOL port - research/demo only"
#property version   "1.00"
#property description "RESEARCH / DEMO ONLY - did NOT pass validation (negative expectancy after costs)."
#property description "Drift Switch Index 20 M5 efficiency-ratio regime follower."

#include <Trade\Trade.mqh>

//---- general
input group "General"
input ENUM_TIMEFRAMES InpTimeframe            = PERIOD_M5;   // Strategy timeframe (tested: M5)
input int             InpServerUtcOffsetHours = -99;         // Server UTC offset hours (-99 = auto)
input long            InpMagic                = 470020;      // Magic number (replaces cBot Label)
input int             InpDeviationPoints      = 50;          // Max slippage (points)
input string          InpLabel                = "VOL-DSI";   // Label (log prefix)

//---- signal
input group "Signal"
input int    InpN         = 6;     // ER lookback N (bars)
input double InpThreshold = 0.8;   // ER threshold
input int    InpAtrPeriod = 20;    // ATR period (bars)
input bool   InpAllowShorts = false; // Allow shorts

//---- exits
input group "Exits"
input double InpStopAtr  = 3.0;    // Stop (x ATR)
input double InpTrailAtr = 1.5;    // Trailing stop (x ATR, 0 = off)
input int    InpMaxBars  = 24;     // Max bars in trade

//---- sizing
input group "Sizing"
input double InpVolumeLots     = 0.0;   // Volume in lots (0 = broker minimum)
input double InpRiskPercent    = 0.0;   // Risk % of balance per trade (0 = off)
input double InpMaxRiskPercent = 3.0;   // Max risk % per trade (cap)
input double InpMaxLots        = 1.0;   // Max lots (hard cap)

//---- safety
input group "Safety"
input double InpMaxSpread            = 1.0;   // Max spread (price units, Ask-Bid)
input int    InpNoEntryFromHour      = 19;    // No new entries from (UTC hour)
input int    InpNoEntryToHour        = 21;    // No new entries until (UTC hour)
input double InpDailyLossLimit       = 1.5;   // Daily loss limit (account ccy, 0 = off)
input double InpMaxDrawdownPercent   = 25.0;  // Equity drawdown kill-switch (% of peak, 0 = off)
input int    InpMaxConsecutiveLosses = 8;     // Pause after N consecutive losses (0 = off)
input int    InpPauseBars            = 12;    // Pause length (bars)

//---- state
CTrade          g_trade;
ENUM_TIMEFRAMES g_tf             = PERIOD_M5;
datetime        g_lastBarTime    = 0;
double          g_peakEquity     = 0.0;
bool            g_killed         = false;
datetime        g_day            = 0;
double          g_dayStartBalance= 0.0;
int             g_consecLosses   = 0;
datetime        g_pauseUntil     = 0;      // entries blocked while closed-bar open time < this
datetime        g_entryBarTime   = 0;      // open time of the fill bar (0 = unknown, cBot _entryBar = -1)
bool            g_orderInFlight  = false;
double          g_entryAtr       = 0.0;
long            g_posId          = 0;
int             g_utcOffsetSec   = 0;

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
      PrintFormat("%s close (%s) FAILED: retcode %u %s", InpLabel, what, g_trade.ResultRetcode(),
                  g_trade.ResultRetcodeDescription());
      return false;
   }
   PrintFormat("%s closed position #%I64u (%s)", InpLabel, ticket, what);
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
   if(!SymbolInfoTick(_Symbol, tk)) { PrintFormat("%s %s: no tick", InpLabel, what); return false; }
   double minD = ModifyMinDist();
   if(type == POSITION_TYPE_BUY && sl >= tk.bid - minD)
   {
      PrintFormat("%s %s skipped: SL %.5f not below bid %.5f - stops/freeze level %.5f", InpLabel, what, sl, tk.bid, minD);
      return false;
   }
   if(type == POSITION_TYPE_SELL && sl <= tk.ask + minD)
   {
      PrintFormat("%s %s skipped: SL %.5f not above ask %.5f + stops/freeze level %.5f", InpLabel, what, sl, tk.ask, minD);
      return false;
   }
   if(!g_trade.PositionModify(ticket, sl, tp) || !RetcodeOk(g_trade.ResultRetcode()))
   {
      PrintFormat("%s %s FAILED: retcode %u %s", InpLabel, what, g_trade.ResultRetcode(), g_trade.ResultRetcodeDescription());
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

// number of closed bars after the fill bar (cBot: last - _entryBar)
int BarsSinceFill()
{
   if(g_entryBarTime == 0) return 1000000;
   int shift = iBarShift(_Symbol, g_tf, g_entryBarTime, false);
   if(shift < 0) return 1000000;
   return shift - 1;
}

//+------------------------------------------------------------------+
//| Indicator helpers (r[] is series: r[0] = last closed bar)        |
//+------------------------------------------------------------------+
double AtrRange(const MqlRates &r[])
{
   double s = 0.0;
   for(int j = 0; j < InpAtrPeriod; j++) s += r[j].high - r[j].low;
   return s / InpAtrPeriod;
}

double EfficiencyRatio(const MqlRates &r[])
{
   double path = 0.0;
   for(int j = 0; j < InpN; j++) path += MathAbs(r[j].close - r[j + 1].close);
   double net = r[0].close - r[InpN].close;
   return (path > 0.0 ? net / path : 0.0);
}

bool WindowClean(const MqlRates &r[])
{
   double nominal = (double)PeriodSeconds(g_tf);
   long   barSec  = (long)(r[0].time - r[1].time);
   int    w       = MathMax(InpN, InpAtrPeriod);
   for(int j = 0; j < w; j++)
      if((double)(r[j].time - r[j + 1].time) > 1.5 * nominal) return false;
   return (barSec > 0);
}

bool InNoEntryWindow(const int hour)
{
   if(InpNoEntryFromHour == InpNoEntryToHour) return false;
   if(InpNoEntryFromHour < InpNoEntryToHour) return (hour >= InpNoEntryFromHour && hour < InpNoEntryToHour);
   return (hour >= InpNoEntryFromHour || hour < InpNoEntryToHour);
}

//+------------------------------------------------------------------+
//| Sizing (cBot Volume(), in lots)                                  |
//+------------------------------------------------------------------+
double CalcLots(const double stopDist)
{
   double vmin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double vmax = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(step <= 0.0) step = vmin;
   double maxLots = (InpMaxLots > 0.0 ? MathMin(vmax, InpMaxLots) : vmax);
   double mpp  = MoneyPerPricePerLot();
   double bal  = AccountInfoDouble(ACCOUNT_BALANCE);
   if(mpp <= 0.0) { PrintFormat("%s tick value/size unknown - skip", InpLabel); return 0.0; }

   double vol = (InpVolumeLots > 0.0 ? InpVolumeLots : vmin);
   if(InpRiskPercent > 0.0 && stopDist > 0.0)
   {
      double riskCash = bal * InpRiskPercent / 100.0;
      double perLot   = stopDist * mpp;
      if(perLot > 0.0) vol = riskCash / perLot;
   }
   vol = FloorToStep(MathMax(vol, vmin));
   if(vol < vmin) vol = vmin;
   if(vol > maxLots) vol = FloorToStep(maxLots);
   if(vol < vmin)
   {
      PrintFormat("%s InpMaxLots %.4f is below the broker minimum %.4f - skip", InpLabel, InpMaxLots, vmin);
      return 0.0;
   }
   // never exceed the max-risk cap; if even the minimum exceeds it, do not trade
   double capCash   = bal * InpMaxRiskPercent / 100.0;
   double riskAtVol = stopDist * mpp * vol;
   while(riskAtVol > capCash && vol > vmin + 1e-9)
   {
      vol = FloorToStep(vol - step);
      if(vol < vmin) vol = vmin;
      riskAtVol = stopDist * mpp * vol;
   }
   if(riskAtVol > capCash)
   {
      PrintFormat("%s risk at minimum volume %.2f exceeds cap %.2f - skip", InpLabel, riskAtVol, capCash);
      return 0.0;
   }
   return vol;
}

//+------------------------------------------------------------------+
//| Risk state                                                       |
//+------------------------------------------------------------------+
void RollDay()
{
   datetime d = UtcDay(UtcNow());
   if(d != g_day)
   {
      g_day = d;
      g_dayStartBalance = AccountInfoDouble(ACCOUNT_BALANCE);
   }
}

bool DailyLossHit()
{
   if(InpDailyLossLimit <= 0.0) return false;
   double lost = g_dayStartBalance - AccountInfoDouble(ACCOUNT_EQUITY);
   if(lost >= InpDailyLossLimit)
   {
      PrintFormat("%s daily loss limit reached (%.2f >= %.2f) - no new entries today", InpLabel, lost, InpDailyLossLimit);
      return true;
   }
   return false;
}

//+------------------------------------------------------------------+
//| Entry                                                            |
//+------------------------------------------------------------------+
bool OpenPosition(const int side, const double lots, const double stopDist, const double er, const double atr)
{
   MqlTick tk;
   if(!SymbolInfoTick(_Symbol, tk)) { PrintFormat("%s open: no tick", InpLabel); return false; }
   string cmt  = StringFormat("er=%.2f;atr=%.4f", er, atr);
   string sname = (side > 0 ? "BUY" : "SELL");
   bool sent;
   if(side > 0) sent = g_trade.Buy(lots, _Symbol, 0.0, NormPrice(tk.ask - stopDist), 0.0, cmt);
   else         sent = g_trade.Sell(lots, _Symbol, 0.0, NormPrice(tk.bid + stopDist), 0.0, cmt);
   uint rc = g_trade.ResultRetcode();
   if(!sent || !RetcodeOk(rc))
   {
      PrintFormat("%s open %s FAILED: retcode %u %s", InpLabel, sname, rc, g_trade.ResultRetcodeDescription());
      return false;
   }
   ulong ticket = MyPositionTicket();
   if(ticket == 0 || !PositionSelectByTicket(ticket))
   {
      PrintFormat("%s open %s sent (retcode %u) but position not visible yet - will be managed on next bar", InpLabel, sname, rc);
      return true;
   }
   g_posId = PositionGetInteger(POSITION_IDENTIFIER);
   double open = PositionGetDouble(POSITION_PRICE_OPEN);
   double sl   = PositionGetDouble(POSITION_SL);
   // cTrader relative SL is measured from the fill price: re-align
   double want = NormPrice(side > 0 ? open - stopDist : open + stopDist);
   if(sl <= 0.0 || MathAbs(want - sl) > TickSize() * 0.5)
   {
      if(!ModifySL(ticket, want, "align SL to fill") && sl <= 0.0)
      {
         PrintFormat("%s position #%I64u has no SL - closing immediately", InpLabel, ticket);
         ClosePos(ticket, "no SL");
         return false;
      }
   }
   if(PositionSelectByTicket(ticket)) sl = PositionGetDouble(POSITION_SL);
   PrintFormat("%s OPEN %s %.2f lots @ %.5f SL %.5f (er %.2f, ATR %.3f, spread %.2f)", InpLabel, sname, lots, open, sl,
               er, atr, CurrentSpread());
   return true;
}

//+------------------------------------------------------------------+
//| Per closed bar (cBot OnBar)                                      |
//+------------------------------------------------------------------+
void OnNewBar(const datetime formingTime)
{
   if(g_killed) return;
   UpdateUtcOffset();
   RollDay();

   int need = MathMax(InpN, InpAtrPeriod) + 3;
   MqlRates r[];
   ArraySetAsSeries(r, true);
   int got = CopyRates(_Symbol, g_tf, 1, need, r);
   if(got < need) return;                         // not enough history yet

   ulong  ticket = MyPositionTicket();
   double atr    = AtrRange(r);
   double er     = EfficiencyRatio(r);
   double spread = CurrentSpread();

   //---- manage open position on bar close: time exit, then trailing stop
   if(ticket > 0)
   {
      if(!PositionSelectByTicket(ticket)) return;
      long   type = PositionGetInteger(POSITION_TYPE);
      double sl   = PositionGetDouble(POSITION_SL);
      if(g_posId == 0) g_posId = PositionGetInteger(POSITION_IDENTIFIER);
      if(sl <= 0.0)
      {
         PrintFormat("%s position #%I64u has no SL - closing immediately", InpLabel, ticket);
         ClosePos(ticket, "no SL");
         return;
      }
      int since = BarsSinceFill();
      if(g_entryBarTime > 0 && since >= InpMaxBars)
      {
         PrintFormat("%s time exit after %d bars", InpLabel, since);
         ClosePos(ticket, "time");
         return;
      }
      if(InpTrailAtr > 0.0 && atr > 0.0 && since > 0)   // never ratchet on the fill bar's close
      {
         double trail = InpTrailAtr * EntryAtr(ticket, atr);
         double close = r[0].close;
         if(type == POSITION_TYPE_BUY)
         {
            double ns = NormPrice(close - trail);
            if(ns > sl + TickSize()) ModifySL(ticket, ns, "trail long");
         }
         else
         {
            double ns = NormPrice(close + spread + trail);
            if(ns < sl - TickSize()) ModifySL(ticket, ns, "trail short");
         }
      }
      return; // one position at a time
   }

   //---- entry filters
   if(g_orderInFlight) return;
   if(r[0].time < g_pauseUntil) return;
   if(DailyLossHit()) return;
   MqlDateTime dt;
   TimeToStruct(ToUtc(formingTime), dt);          // cBot: Bars.OpenTimes[last + 1].Hour (UTC)
   if(InNoEntryWindow(dt.hour)) return;
   if(!WindowClean(r)) return;
   if(atr <= 0.0) return;

   int side = 0;
   if(er > InpThreshold) side = 1;
   else if(InpAllowShorts && er < -InpThreshold) side = -1;
   if(side == 0) return;

   if(spread > InpMaxSpread)
   {
      PrintFormat("%s signal %s er=%.2f skipped: spread %.2f > %.2f", InpLabel, (side > 0 ? "BUY" : "SELL"), er,
                  spread, InpMaxSpread);
      return;
   }

   double stopDist = InpStopAtr * atr;
   double minStop  = StopsLevelDist();
   if(minStop > 0.0 && stopDist <= minStop)
   {
      PrintFormat("%s stop distance %.5f below broker stops level %.5f - widened", InpLabel, stopDist, minStop);
      stopDist = minStop + TickSize();
   }
   double lots = CalcLots(stopDist);
   if(lots <= 0.0) { PrintFormat("%s volume could not be determined - no trade", InpLabel); return; }
   if(MyPositionTicket() != 0) return;            // duplicate-order guard

   g_orderInFlight = true;
   bool ok = OpenPosition(side, lots, stopDist, er, atr);
   g_orderInFlight = false;
   if(ok)
   {
      g_entryBarTime = formingTime;               // cBot: _entryBar = last + 1 (the fill bar)
      g_entryAtr     = atr;
   }
}

//+------------------------------------------------------------------+
//| Expert initialization                                            |
//+------------------------------------------------------------------+
int OnInit()
{
   if(InpN < 2 || InpAtrPeriod < 2 || InpMaxBars < 1 || InpStopAtr <= 0.0 || InpPauseBars < 1 ||
      InpNoEntryFromHour < 0 || InpNoEntryFromHour > 23 || InpNoEntryToHour < 0 || InpNoEntryToHour > 23)
   {
      Print("VolBot: invalid input parameters");
      return INIT_PARAMETERS_INCORRECT;
   }
   g_tf = (InpTimeframe == PERIOD_CURRENT ? (ENUM_TIMEFRAMES)_Period : InpTimeframe);
   if((ENUM_TIMEFRAMES)_Period != g_tf)
      PrintFormat("WARNING: chart timeframe %s differs from strategy timeframe %s - the EA uses %s bars",
                  EnumToString((ENUM_TIMEFRAMES)_Period), EnumToString(g_tf), EnumToString(g_tf));

   g_trade.SetExpertMagicNumber((ulong)InpMagic);
   g_trade.SetDeviationInPoints((ulong)MathMax(0, InpDeviationPoints));
   g_trade.SetTypeFilling(FillingMode());
   g_trade.SetAsyncMode(false);

   UpdateUtcOffset();
   g_peakEquity      = AccountInfoDouble(ACCOUNT_EQUITY);
   g_day             = UtcDay(UtcNow());
   g_dayStartBalance = AccountInfoDouble(ACCOUNT_BALANCE);
   g_lastBarTime     = iTime(_Symbol, g_tf, 0);

   ulong ticket = MyPositionTicket();
   if(ticket > 0 && PositionSelectByTicket(ticket))
   {
      g_entryBarTime = iTime(_Symbol, g_tf, 0);   // conservative: restart the time-exit clock on restart
      g_posId        = PositionGetInteger(POSITION_IDENTIFIER);
      g_entryAtr     = ParseAtrFromComment(PositionGetString(POSITION_COMMENT));
   }

   PrintFormat("VolBot start %s %s: N=%d thr=%.2f atr=%d sl=%.2fxATR trail=%.2fxATR maxBars=%d shorts=%s maxSpread=%.2f "
               "minVol=%.2f utcOffset=%dh. RESEARCH / DEMO ONLY - negative expectancy after costs.",
               _Symbol, EnumToString(g_tf), InpN, InpThreshold, InpAtrPeriod, InpStopAtr, InpTrailAtr, InpMaxBars,
               (InpAllowShorts ? "true" : "false"), InpMaxSpread, SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN), g_utcOffsetSec / 3600);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   PrintFormat("VolBot stopped (reason %d). Equity %.2f, peak %.2f", reason, AccountInfoDouble(ACCOUNT_EQUITY), g_peakEquity);
}

//+------------------------------------------------------------------+
//| Tick: kill-switch intrabar, new-bar detection                    |
//+------------------------------------------------------------------+
void OnTick()
{
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   if(eq > g_peakEquity) g_peakEquity = eq;
   if(!g_killed && InpMaxDrawdownPercent > 0.0 && g_peakEquity > 0.0 &&
      (g_peakEquity - eq) / g_peakEquity * 100.0 >= InpMaxDrawdownPercent)
   {
      g_killed = true;
      PrintFormat("%s KILL-SWITCH: equity drawdown %.1f%% >= %.1f%%. Closing and stopping.", InpLabel,
                  (g_peakEquity - eq) / g_peakEquity * 100.0, InpMaxDrawdownPercent);
      CloseMine("kill-switch");
      ExpertRemove();
      return;
   }
   if(g_killed) return;

   datetime t0 = iTime(_Symbol, g_tf, 0);
   if(t0 == 0) return;
   if(g_lastBarTime == 0) { g_lastBarTime = t0; return; }
   if(t0 == g_lastBarTime) return;
   g_lastBarTime = t0;
   OnNewBar(t0);
}

//+------------------------------------------------------------------+
//| Closed deals -> consecutive-loss pause (cBot Positions.Closed)   |
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

   g_entryBarTime = 0;
   g_entryAtr     = 0.0;
   g_posId        = 0;
   if(net < 0.0) g_consecLosses++; else g_consecLosses = 0;
   PrintFormat("%s CLOSED net %.2f (%s); consecutive losses %d", InpLabel, net,
               EnumToString((ENUM_DEAL_REASON)reason), g_consecLosses);
   if(InpMaxConsecutiveLosses > 0 && g_consecLosses >= InpMaxConsecutiveLosses)
   {
      g_pauseUntil   = (datetime)(iTime(_Symbol, g_tf, 0) + InpPauseBars * PeriodSeconds(g_tf));
      g_consecLosses = 0;
      PrintFormat("%s pausing entries for %d bars after %d consecutive losses", InpLabel, InpPauseBars,
                  InpMaxConsecutiveLosses);
   }
}
//+------------------------------------------------------------------+
