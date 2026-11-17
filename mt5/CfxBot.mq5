//+------------------------------------------------------------------+
//| CfxBot.mq5 - CFX Crypto Momentum Burst (ETHUSD H1, intraday)       |
//|                                                                    |
//| Port of CfxBot.cs - re-verify in the MT5 Strategy Tester before    |
//| live use: contract size, swap and spreads on Deriv MT5 may differ  |
//| from cTrader.                                                      |
//|                                                                    |
//| Strategy (all times UTC, decisions only on CLOSED bars of          |
//| InpTimeframe, tested on ETHUSD H1; reference: strategy.py):        |
//|  ATR = mean(High-Low) of the last AtrPeriod (24) closed H1 bars,   |
//|        including the signal bar.                                   |
//|  If |Close-Open| of the last closed H1 bar > K (2.5) x ATR ->      |
//|  market order in the bar's direction at the open of the next bar.  |
//|  Hard stop = SlAtrMult (2.0) x ATR, no take-profit. Position held  |
//|  for HoldBars (3) H1 bars (entry bar + 2), closed at the close of  |
//|  the 3rd bar (= 3 hours after entry).                              |
//|  Rollover guard: skip any trade whose holding hours touch          |
//|  BlockStartHour..BlockEndHour (20:00-22:59 UTC).                   |
//| Safety: one position per symbol+magic, spread filter, daily loss   |
//|  limit (UTC day), equity kill-switch from peak, consecutive-loss   |
//|  pause, planned-risk cap per trade, volume never below broker min. |
//|                                                                    |
//| Tested: ETHUSD H1, broker minimum volume (0.1 ETH in cTrader).     |
//| Recommended balance: >= 300 USD (BTCUSD works too, needs ~900 USD).|
//|                                                                    |
//| Porting notes:                                                     |
//|  - cTrader units -> MT5 lots: VolumeUnits/MaxVolumeUnits became    |
//|    InpLots (0 = SYMBOL_VOLUME_MIN) and InpMaxLots (default 1.0).   |
//|    Check the MT5 contract size of ETHUSD (1 lot may != 1 ETH).     |
//|  - Label (BotLabel) is used as order comment; positions are        |
//|    identified by symbol + InpMagic.                                |
//|  - Bar times are broker server time; converted to UTC with         |
//|    InpServerUtcOffsetHours (-99 = auto, 0 in the Strategy Tester). |
//|  - SL is attached on the order relative to the current Bid/Ask     |
//|    (cTrader: relative to the fill price) and widened to            |
//|    SYMBOL_TRADE_STOPS_LEVEL if needed; a position without SL is    |
//|    closed at once.                                                 |
//|  - Net result of a closed position (for the loss streak) = sum of  |
//|    profit + swap + commission + fee of all its deals.              |
//|  - Kill-switch stops the EA with ExpertRemove() (cTrader Stop()).  |
//+------------------------------------------------------------------+
#property copyright "CFX port of CfxBot.cs"
#property version   "1.00"
#property description "CFX Crypto Momentum Burst - ETHUSD H1. Port of CfxBot.cs, re-verify in the Strategy Tester."

#include <Trade\Trade.mqh>

//--- inputs
input group "Signal"
input ENUM_TIMEFRAMES InpTimeframe   = PERIOD_H1; // Strategy timeframe (tested: H1)
input double K                       = 2.5;       // Burst threshold K (x ATR)
input int    AtrPeriod               = 24;        // ATR period (H1 bars)
input int    HoldBars                = 3;         // Hold (H1 bars incl. entry bar)
input double SlAtrMult               = 2.0;       // Stop-loss (x ATR)

input group "Session"
input int    BlockStartHour          = 20;        // No-hold window start hour UTC
input int    BlockEndHour            = 22;        // No-hold window end hour UTC (incl.)
input int    InpServerUtcOffsetHours = -99;       // Server UTC offset hours (-99 = auto)

input group "Sizing"
input double InpLots                 = 0.0;       // Volume in lots (0 = broker minimum)
input double RiskPercent             = 0.0;       // Risk % per trade (0 = fixed volume)
input double MaxRiskPercent          = 4.0;       // Max risk % per trade (hard cap)
input double InpMaxLots              = 1.0;       // Max volume in lots (0 = no cap)

input group "Risk"
input double MaxSpread               = 3.0;       // Max spread (price units)
input double DailyLossPercent        = 5.0;       // Daily loss limit (% of day-start balance)
input double KillDrawdownPercent     = 25.0;      // Equity draw-down kill-switch (% from peak)
input int    MaxConsecutiveLosses    = 6;         // Max consecutive losses before pause
input int    PauseHours              = 48;        // Pause length (hours)

input group "General"
input string BotLabel                = "CFX-Burst"; // Label (order comment)
input long   InpMagic                = 26111701;  // Magic number
input int    InpSlippagePoints       = 50;        // Max deviation (points)

//--- state
CTrade   g_trade;
datetime g_lastBarTime     = 0;   // server time of the current open bar of InpTimeframe
datetime g_lastSignalBar   = 0;   // server time of the last evaluated signal bar
datetime g_dayStart        = 0;   // UTC date (00:00) of the current trading day
double   g_dayStartBalance = 0.0;
double   g_peakEquity      = 0.0;
int      g_consecLosses    = 0;
datetime g_pauseUntil      = 0;   // UTC
bool     g_orderInFlight   = false;
bool     g_dailyBlocked    = false;
bool     g_stopped         = false;
int      g_utcOffsetHours  = 0;

//+------------------------------------------------------------------+
int ComputeUtcOffset()
{
   if(InpServerUtcOffsetHours != -99)
      return InpServerUtcOffsetHours;
   if(MQLInfoInteger(MQL_TESTER) || MQLInfoInteger(MQL_OPTIMIZATION))
      return 0;
   datetime srv = TimeTradeServer();
   datetime gmt = TimeGMT();
   if(srv <= 0 || gmt <= 0)
      return 0;
   return (int)MathRound((double)(srv - gmt) / 3600.0);
}

datetime ToUtc(const datetime serverTime)
{
   return (datetime)((long)serverTime - (long)g_utcOffsetHours * 3600);
}

datetime NowUtc()
{
   datetime srv = TimeTradeServer();
   if(srv <= 0)
      srv = TimeCurrent();
   return ToUtc(srv);
}

datetime DateOf(const datetime t)
{
   return (datetime)((long)t - ((long)t % 86400));
}

int HourOf(const datetime t)
{
   MqlDateTime s;
   TimeToStruct(t, s);
   return s.hour;
}

//+------------------------------------------------------------------+
ENUM_ORDER_TYPE_FILLING GetFilling()
{
   long mode = SymbolInfoInteger(_Symbol, SYMBOL_FILLING_MODE);
   if((mode & SYMBOL_FILLING_FOK) == SYMBOL_FILLING_FOK)
      return ORDER_FILLING_FOK;
   if((mode & SYMBOL_FILLING_IOC) == SYMBOL_FILLING_IOC)
      return ORDER_FILLING_IOC;
   return ORDER_FILLING_RETURN;
}

//+------------------------------------------------------------------+
int OnInit()
{
   if(AtrPeriod < 1 || HoldBars < 1 || K <= 0.0 || SlAtrMult <= 0.0)
   {
      Print("CFX invalid inputs");
      return INIT_PARAMETERS_INCORRECT;
   }
   g_trade.SetExpertMagicNumber((ulong)InpMagic);
   g_trade.SetDeviationInPoints((ulong)MathMax(0, InpSlippagePoints));
   g_trade.SetTypeFilling(GetFilling());
   g_trade.SetMarginMode();

   g_utcOffsetHours = ComputeUtcOffset();
   if(_Period != InpTimeframe)
      PrintFormat("CFX warning: chart timeframe %s differs from strategy timeframe %s - the EA uses %s bars itself",
                  EnumToString(_Period), EnumToString(InpTimeframe), EnumToString(InpTimeframe));

   g_peakEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   ResetDay(NowUtc());
   g_lastBarTime = iTime(_Symbol, InpTimeframe, 0);   // like BarOpened: act only on bars opening after start

   PrintFormat("CFX start %s: K=%.2f ATR=%d hold=%d SLx=%.2f block %d-%d UTC, UTC offset %d h, min volume %.4f lots",
               _Symbol, K, AtrPeriod, HoldBars, SlAtrMult, BlockStartHour, BlockEndHour, g_utcOffsetHours,
               SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN));
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   PrintFormat("CFX stopped. Equity %.2f, peak %.2f (reason %d)", AccountInfoDouble(ACCOUNT_EQUITY), g_peakEquity, reason);
}

//+------------------------------------------------------------------+
void OnTick()
{
   if(g_stopped)
      return;

   datetime t0 = iTime(_Symbol, InpTimeframe, 0);
   if(t0 > 0)
   {
      if(g_lastBarTime == 0)
         g_lastBarTime = t0;                 // first bar seen: no decision, wait for the next bar open
      else if(t0 != g_lastBarTime)
      {
         g_lastBarTime = t0;
         OnNewBar(t0);
         if(g_stopped)
            return;
      }
   }

   CheckKillSwitch();
   if(!g_stopped)
      CheckDailyLoss();
}

void OnNewBar(const datetime curOpenServer)
{
   if(InpServerUtcOffsetHours == -99)
      g_utcOffsetHours = ComputeUtcOffset();   // follow server DST changes
   if(DateOf(NowUtc()) != g_dayStart)
      ResetDay(NowUtc());
   ManageTimeExit(curOpenServer);
   if(CheckKillSwitch() || CheckDailyLoss())
      return;
   TryEnter();
}

void ResetDay(const datetime nowUtc)
{
   g_dayStart        = DateOf(nowUtc);
   g_dayStartBalance = AccountInfoDouble(ACCOUNT_BALANCE);
   g_dailyBlocked    = false;
}

//+------------------------------------------------------------------+
int CountOurPositions()
{
   int n = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      if(PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagic)
         n++;
   }
   return n;
}

// close positions held for HoldBars full bars (exit at the open of the next bar)
void ManageTimeExit(const datetime curOpenServer)
{
   long period = PeriodSeconds(InpTimeframe);
   if(period <= 0)
      return;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol || PositionGetInteger(POSITION_MAGIC) != InpMagic)
         continue;
      datetime entry    = (datetime)PositionGetInteger(POSITION_TIME);
      datetime entryBar = (datetime)((long)entry - ((long)entry % period));
      double   barsHeld = (double)((long)curOpenServer - (long)entryBar) / (double)period;
      if(barsHeld >= HoldBars - 1e-9)
      {
         double pnl = PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
         if(g_trade.PositionClose(ticket) &&
            (g_trade.ResultRetcode() == TRADE_RETCODE_DONE || g_trade.ResultRetcode() == TRADE_RETCODE_PLACED))
            PrintFormat("CFX time exit %I64u pnl %.2f", ticket, pnl);
         else
            PrintFormat("CFX time exit FAILED %I64u: retcode %u %s", ticket, g_trade.ResultRetcode(), g_trade.ResultRetcodeDescription());
      }
   }
}

//+------------------------------------------------------------------+
bool InBlock(const int hour)
{
   if(BlockStartHour <= BlockEndHour)
      return (hour >= BlockStartHour && hour <= BlockEndHour);
   return (hour >= BlockStartHour || hour <= BlockEndHour);   // window wrapping midnight
}

void TryEnter()
{
   if(Bars(_Symbol, InpTimeframe) < AtrPeriod + 2)
      return;

   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int got = CopyRates(_Symbol, InpTimeframe, 1, AtrPeriod, rates);   // rates[0] = last CLOSED bar
   if(got != AtrPeriod)
   {
      PrintFormat("CFX CopyRates failed (%d of %d), error %d", got, AtrPeriod, GetLastError());
      return;
   }

   datetime sigOpen = rates[0].time;                      // server time
   if(sigOpen <= g_lastSignalBar)
      return;                                             // duplicate protection: one decision per bar
   g_lastSignalBar = sigOpen;

   double atr = 0.0;
   for(int j = 0; j < AtrPeriod; j++)
      atr += rates[j].high - rates[j].low;
   atr /= AtrPeriod;
   double body = rates[0].close - rates[0].open;
   if(atr <= 0.0 || MathAbs(body) <= K * atr)
      return;

   bool   isBuy   = (body > 0.0);
   string sideStr = isBuy ? "Buy" : "Sell";

   int sigHourUtc = HourOf(ToUtc(sigOpen));
   for(int j = 0; j < HoldBars; j++)
   {
      int h = (sigHourUtc + 1 + j) % 24;
      if(InBlock(h))
      {
         PrintFormat("CFX signal %s skipped: holding window touches rollover block (hour %d)", sideStr, h);
         return;
      }
   }
   if(NowUtc() < g_pauseUntil)
   {
      PrintFormat("CFX signal skipped: paused until %s UTC", TimeToString(g_pauseUntil, TIME_DATE | TIME_MINUTES));
      return;
   }
   if(g_orderInFlight || CountOurPositions() > 0)
   {
      Print("CFX signal skipped: position already open");
      return;
   }

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(ask <= 0.0 || bid <= 0.0)
   {
      Print("CFX signal skipped: no quote");
      return;
   }
   double spread = ask - bid;
   if(spread > MaxSpread)
   {
      PrintFormat("CFX signal skipped: spread %.5f > %.5f", spread, MaxSpread);
      return;
   }

   double slDist   = SlAtrMult * atr;
   double point    = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double minStop  = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * point;
   if(minStop > 0.0 && slDist < minStop + point)
   {
      PrintFormat("CFX SL distance %.5f widened to broker stops level %.5f", slDist, minStop + point);
      slDist = minStop + point;
   }

   double lots = ComputeVolume(slDist);
   if(lots <= 0.0)
      return;

   int    digits   = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   double tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double sl       = isBuy ? ask - slDist : bid + slDist;
   if(tickSize > 0.0)
      sl = MathRound(sl / tickSize) * tickSize;
   sl = NormalizeDouble(sl, digits);

   g_orderInFlight = true;
   bool sent = isBuy ? g_trade.Buy(lots, _Symbol, 0.0, sl, 0.0, BotLabel)
                     : g_trade.Sell(lots, _Symbol, 0.0, sl, 0.0, BotLabel);
   g_orderInFlight = false;
   uint rc = g_trade.ResultRetcode();
   if(!sent || (rc != TRADE_RETCODE_DONE && rc != TRADE_RETCODE_PLACED && rc != TRADE_RETCODE_DONE_PARTIAL))
   {
      PrintFormat("CFX ENTRY FAILED %s: retcode %u %s", sideStr, rc, g_trade.ResultRetcodeDescription());
      return;
   }
   PrintFormat("CFX ENTRY %s %.4f lots @ %.5f SL %.5f (dist %.5f) | body %.2f ATR %.2f",
               sideStr, lots, g_trade.ResultPrice(), sl, slDist, body, atr);
   EnsureStopLoss();
}

// if a position of ours ended up without a stop-loss, close it immediately
void EnsureStopLoss()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol || PositionGetInteger(POSITION_MAGIC) != InpMagic)
         continue;
      if(PositionGetDouble(POSITION_SL) <= 0.0)
      {
         Print("CFX position ", ticket, " has no stop-loss - closing it");
         if(!g_trade.PositionClose(ticket))
            PrintFormat("CFX close FAILED %I64u: retcode %u %s", ticket, g_trade.ResultRetcode(), g_trade.ResultRetcodeDescription());
      }
   }
}

//+------------------------------------------------------------------+
double MoneyPerPricePerLot()
{
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE_LOSS);
   if(tickValue <= 0.0)
      tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   if(tickSize <= 0.0 || tickValue <= 0.0)
      return 0.0;
   return tickValue / tickSize;
}

double ComputeVolume(const double slDist)
{
   double vmin  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double vmax  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double vstep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);

   double lots       = InpLots > 0.0 ? InpLots : vmin;
   double riskPerLot = slDist * MoneyPerPricePerLot();      // account currency lost per lot at the stop
   if(RiskPercent > 0.0 && riskPerLot > 0.0)
      lots = balance * RiskPercent / 100.0 / riskPerLot;
   if(InpMaxLots > 0.0)
      lots = MathMin(lots, InpMaxLots);
   if(vstep > 0.0)
      lots = MathFloor(lots / vstep + 1e-9) * vstep;       // round down to step
   if(lots < vmin)
      lots = vmin;                                          // never below broker minimum
   if(vmax > 0.0 && lots > vmax)
      lots = vmax;
   lots = NormalizeDouble(lots, 8);

   if(riskPerLot <= 0.0)
   {
      Print("CFX signal skipped: cannot compute risk (tick value/size unavailable)");
      return 0.0;
   }
   double risk = lots * riskPerLot;
   if(risk > balance * MaxRiskPercent / 100.0)
   {
      PrintFormat("CFX signal skipped: risk %.2f at %.4f lots exceeds cap %.2f%% of balance", risk, lots, MaxRiskPercent);
      return 0.0;
   }
   return lots;
}

//+------------------------------------------------------------------+
bool CheckDailyLoss()
{
   if(g_dailyBlocked)
      return true;
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   if(g_dayStartBalance - equity >= g_dayStartBalance * DailyLossPercent / 100.0)
   {
      g_dailyBlocked = true;
      CloseAll("daily loss limit");
      Print("CFX daily loss limit hit: no new trades until next UTC day");
      return true;
   }
   return false;
}

bool CheckKillSwitch()
{
   if(g_stopped)
      return true;
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   g_peakEquity = MathMax(g_peakEquity, equity);
   if(equity <= g_peakEquity * (1.0 - KillDrawdownPercent / 100.0))
   {
      CloseAll("equity kill-switch");
      PrintFormat("CFX KILL-SWITCH: equity %.2f is %.1f%% below peak %.2f. EA stopped.", equity, KillDrawdownPercent, g_peakEquity);
      g_stopped = true;
      ExpertRemove();
      return true;
   }
   return false;
}

void CloseAll(const string why)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol || PositionGetInteger(POSITION_MAGIC) != InpMagic)
         continue;
      if(g_trade.PositionClose(ticket))
         PrintFormat("CFX closed %I64u (%s)", ticket, why);
      else
         PrintFormat("CFX close FAILED %I64u (%s): retcode %u %s", ticket, why, g_trade.ResultRetcode(), g_trade.ResultRetcodeDescription());
   }
}

//+------------------------------------------------------------------+
// consecutive-loss counter from closing deals of our magic/symbol
void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest &request,
                        const MqlTradeResult &result)
{
   if(trans.type != TRADE_TRANSACTION_DEAL_ADD || trans.deal == 0)
      return;
   if(!HistoryDealSelect(trans.deal))
      return;
   if(HistoryDealGetString(trans.deal, DEAL_SYMBOL) != _Symbol)
      return;
   if(HistoryDealGetInteger(trans.deal, DEAL_MAGIC) != InpMagic)
      return;
   long entryType = HistoryDealGetInteger(trans.deal, DEAL_ENTRY);
   if(entryType != DEAL_ENTRY_OUT && entryType != DEAL_ENTRY_OUT_BY && entryType != DEAL_ENTRY_INOUT)
      return;

   long   posId = HistoryDealGetInteger(trans.deal, DEAL_POSITION_ID);
   long   dtype = HistoryDealGetInteger(trans.deal, DEAL_TYPE);
   long   reason = HistoryDealGetInteger(trans.deal, DEAL_REASON);
   double net = 0.0;
   if(HistorySelectByPosition(posId))
   {
      int n = HistoryDealsTotal();
      for(int i = 0; i < n; i++)
      {
         ulong d = HistoryDealGetTicket(i);
         if(d == 0)
            continue;
         net += HistoryDealGetDouble(d, DEAL_PROFIT) + HistoryDealGetDouble(d, DEAL_SWAP)
              + HistoryDealGetDouble(d, DEAL_COMMISSION) + HistoryDealGetDouble(d, DEAL_FEE);
      }
   }
   else
   {
      net = HistoryDealGetDouble(trans.deal, DEAL_PROFIT) + HistoryDealGetDouble(trans.deal, DEAL_SWAP)
          + HistoryDealGetDouble(trans.deal, DEAL_COMMISSION) + HistoryDealGetDouble(trans.deal, DEAL_FEE);
   }

   g_consecLosses = (net < 0.0) ? g_consecLosses + 1 : 0;
   // closing deal of a long is a SELL deal
   PrintFormat("CFX closed %s position %I64d net %.2f reason %s; consecutive losses %d",
               (dtype == DEAL_TYPE_SELL ? "Buy" : "Sell"), posId, net,
               EnumToString((ENUM_DEAL_REASON)reason), g_consecLosses);
   if(g_consecLosses >= MaxConsecutiveLosses)
   {
      g_pauseUntil   = (datetime)((long)NowUtc() + (long)PauseHours * 3600);
      g_consecLosses = 0;
      PrintFormat("CFX pause: %d consecutive losses, no entries until %s UTC", MaxConsecutiveLosses,
                  TimeToString(g_pauseUntil, TIME_DATE | TIME_MINUTES));
   }
}
//+------------------------------------------------------------------+
