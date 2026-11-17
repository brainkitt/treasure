// CFX - Crypto Momentum Burst cBot (ETHUSD H1, intraday).  Same logic and defaults as agents/CFX/strategy.py.
//
// Rule (all times UTC, decisions only on CLOSED H1 bars):
//   ATR  = mean(High-Low) of the last AtrPeriod (24) closed H1 bars, including the signal bar.
//   If |Close-Open| of the last closed H1 bar > K (2.5) x ATR  -> market order in the bar's direction at once
//   (= open of the next bar). Hard stop = SlAtrMult (2.0) x ATR, no take-profit, position held for HoldBars (3) H1 bars
//   (entry bar + 2) and closed at the close of the 3rd bar = 3 hours after entry (python: max_bars = hold - 1).
//   Rollover guard: skip any trade whose holding hours touch BlockStartHour..BlockEndHour (20:00-22:59 UTC) so the
//   position is never held through the daily rollover (no swap).
// Safety: one position per symbol (label), spread filter, daily loss limit, equity draw-down kill-switch,
//   consecutive-loss pause, risk cap per trade, volume never below broker minimum, TradeResult error handling.
// Attach to an ETHUSD chart (any timeframe - the bot requests H1 bars itself). BTCUSD works too (needs ~$900).
using System;
using System.Linq;
using cAlgo.API;
using cAlgo.API.Internals;

namespace cAlgo.Robots
{
    [Robot(TimeZone = TimeZones.UTC, AccessRights = AccessRights.None)]
    public class CfxBot : Robot
    {
        // ---- signal ----
        [Parameter("Burst threshold K (x ATR)", Group = "Signal", DefaultValue = 2.5, MinValue = 1.0, MaxValue = 6.0, Step = 0.25)]
        public double K { get; set; }

        [Parameter("ATR period (H1 bars)", Group = "Signal", DefaultValue = 24, MinValue = 5, MaxValue = 200)]
        public int AtrPeriod { get; set; }

        [Parameter("Hold (H1 bars incl. entry bar)", Group = "Signal", DefaultValue = 3, MinValue = 1, MaxValue = 12)]
        public int HoldBars { get; set; }

        [Parameter("Stop-loss (x ATR)", Group = "Signal", DefaultValue = 2.0, MinValue = 0.5, MaxValue = 6.0, Step = 0.25)]
        public double SlAtrMult { get; set; }

        // ---- session / rollover ----
        [Parameter("No-hold window start hour UTC", Group = "Session", DefaultValue = 20, MinValue = 0, MaxValue = 23)]
        public int BlockStartHour { get; set; }

        [Parameter("No-hold window end hour UTC (incl.)", Group = "Session", DefaultValue = 22, MinValue = 0, MaxValue = 23)]
        public int BlockEndHour { get; set; }

        // ---- sizing ----
        [Parameter("Volume in units (0 = broker minimum)", Group = "Sizing", DefaultValue = 0, MinValue = 0)]
        public double VolumeUnits { get; set; }

        [Parameter("Risk % per trade (0 = fixed volume)", Group = "Sizing", DefaultValue = 0, MinValue = 0, MaxValue = 5)]
        public double RiskPercent { get; set; }

        [Parameter("Max risk % per trade (hard cap)", Group = "Sizing", DefaultValue = 4.0, MinValue = 0.1, MaxValue = 10)]
        public double MaxRiskPercent { get; set; }

        [Parameter("Max volume in units", Group = "Sizing", DefaultValue = 1.0, MinValue = 0)]
        public double MaxVolumeUnits { get; set; }

        // ---- risk controls ----
        [Parameter("Max spread (price units)", Group = "Risk", DefaultValue = 3.0, MinValue = 0)]
        public double MaxSpread { get; set; }

        [Parameter("Daily loss limit (% of day-start balance)", Group = "Risk", DefaultValue = 5.0, MinValue = 0.5, MaxValue = 50)]
        public double DailyLossPercent { get; set; }

        [Parameter("Equity draw-down kill-switch (% from peak)", Group = "Risk", DefaultValue = 25.0, MinValue = 1, MaxValue = 90)]
        public double KillDrawdownPercent { get; set; }

        [Parameter("Max consecutive losses before pause", Group = "Risk", DefaultValue = 6, MinValue = 1, MaxValue = 50)]
        public int MaxConsecutiveLosses { get; set; }

        [Parameter("Pause length (hours)", Group = "Risk", DefaultValue = 48, MinValue = 1, MaxValue = 720)]
        public int PauseHours { get; set; }

        [Parameter("Label", Group = "General", DefaultValue = "CFX-Burst")]
        public string BotLabel { get; set; }

        private Bars _h1;
        private DateTime _lastSignalBar = DateTime.MinValue;
        private DateTime _dayStart = DateTime.MinValue;
        private double _dayStartBalance;
        private double _peakEquity;
        private int _consecLosses;
        private DateTime _pauseUntil = DateTime.MinValue;
        private bool _orderInFlight;
        private bool _dailyBlocked;

        protected override void OnStart()
        {
            _h1 = MarketData.GetBars(TimeFrame.Hour, SymbolName);
            _h1.BarOpened += OnH1BarOpened;
            Positions.Closed += OnPositionClosed;
            _peakEquity = Account.Equity;
            ResetDay(Server.Time);
            Print("CFX start {0}: K={1} ATR={2} hold={3} SLx={4} block {5}-{6} UTC, min volume {7}",
                SymbolName, K, AtrPeriod, HoldBars, SlAtrMult, BlockStartHour, BlockEndHour, Symbol.VolumeInUnitsMin);
        }

        protected override void OnTick()
        {
            CheckKillSwitch();
            CheckDailyLoss();
        }

        protected override void OnBar()
        {
            // chart bars are not used for decisions; the H1 series handler does the work
        }

        private void OnH1BarOpened(BarOpenedEventArgs args)
        {
            try
            {
                if (Server.Time.Date != _dayStart) ResetDay(Server.Time);
                ManageTimeExit();
                if (CheckKillSwitch() || CheckDailyLoss()) return;
                TryEnter();
            }
            catch (Exception ex)
            {
                Print("CFX error in bar handler: {0}", ex.Message);
            }
        }

        private void ResetDay(DateTime now)
        {
            _dayStart = now.Date;
            _dayStartBalance = Account.Balance;
            _dailyBlocked = false;
        }

        // close positions that have been held for HoldBars full H1 bars (exit at the close of the HoldBars-th bar,
        // i.e. at the open of the next bar)
        private void ManageTimeExit()
        {
            DateTime curOpen = _h1.Last(0).OpenTime;
            foreach (var p in Positions.FindAll(BotLabel, SymbolName))
            {
                DateTime entryBar = new DateTime(p.EntryTime.Year, p.EntryTime.Month, p.EntryTime.Day, p.EntryTime.Hour, 0, 0);
                if ((curOpen - entryBar).TotalHours >= HoldBars - 1e-9)
                {
                    var r = ClosePosition(p);
                    Print(r.IsSuccessful ? "CFX time exit {0} pnl {1:F2}" : "CFX time exit FAILED {0}: {1}", p.Id, r.IsSuccessful ? p.NetProfit : 0, r.Error);
                }
            }
        }

        private void TryEnter()
        {
            if (_h1.Count < AtrPeriod + 2) return;
            Bar sig = _h1.Last(1);                         // last CLOSED H1 bar
            if (sig.OpenTime <= _lastSignalBar) return;     // duplicate protection: one decision per bar
            _lastSignalBar = sig.OpenTime;

            double atr = 0;
            for (int j = 1; j <= AtrPeriod; j++) atr += _h1.Last(j).High - _h1.Last(j).Low;
            atr /= AtrPeriod;
            double body = sig.Close - sig.Open;
            if (atr <= 0 || Math.Abs(body) <= K * atr) return;

            TradeType side = body > 0 ? TradeType.Buy : TradeType.Sell;
            for (int j = 0; j < HoldBars; j++)
            {
                int h = (sig.OpenTime.Hour + 1 + j) % 24;
                if (InBlock(h)) { Print("CFX signal {0} skipped: holding window touches rollover block (hour {1})", side, h); return; }
            }
            if (Server.Time < _pauseUntil) { Print("CFX signal skipped: paused until {0}", _pauseUntil); return; }
            if (_orderInFlight || Positions.FindAll(BotLabel, SymbolName).Length > 0) { Print("CFX signal skipped: position already open"); return; }
            if (Symbol.Spread > MaxSpread) { Print("CFX signal skipped: spread {0} > {1}", Symbol.Spread, MaxSpread); return; }

            double slDist = SlAtrMult * atr;
            double slPips = Math.Round(slDist / Symbol.PipSize, 1);
            double vol = ComputeVolume(slPips);
            if (vol <= 0) return;

            _orderInFlight = true;
            var res = ExecuteMarketOrder(side, SymbolName, vol, BotLabel, slPips, null);
            _orderInFlight = false;
            if (res.IsSuccessful)
                Print("CFX ENTRY {0} {1} units @ {2} SL {3} ({4} pips) | body {5:F2} ATR {6:F2}", side, vol, res.Position.EntryPrice,
                    res.Position.StopLoss, slPips, body, atr);
            else
                Print("CFX ENTRY FAILED {0}: {1}", side, res.Error);
        }

        private bool InBlock(int hour)
        {
            if (BlockStartHour <= BlockEndHour) return hour >= BlockStartHour && hour <= BlockEndHour;
            return hour >= BlockStartHour || hour <= BlockEndHour;   // window wrapping midnight
        }

        private double ComputeVolume(double slPips)
        {
            double min = Symbol.VolumeInUnitsMin;
            double vol = VolumeUnits > 0 ? VolumeUnits : min;
            double riskPerUnit = slPips * Symbol.PipValue;           // account currency lost per unit at the stop
            if (RiskPercent > 0 && riskPerUnit > 0)
                vol = Account.Balance * RiskPercent / 100.0 / riskPerUnit;
            if (MaxVolumeUnits > 0) vol = Math.Min(vol, MaxVolumeUnits);
            vol = Symbol.NormalizeVolumeInUnits(vol, RoundingMode.Down);
            if (vol < min) vol = min;                                  // never below broker minimum
            double risk = vol * riskPerUnit;
            if (risk > Account.Balance * MaxRiskPercent / 100.0)
            {
                Print("CFX signal skipped: risk {0:F2} at {1} units exceeds cap {2}% of balance", risk, vol, MaxRiskPercent);
                return 0;
            }
            return vol;
        }

        private bool CheckDailyLoss()
        {
            if (_dailyBlocked) return true;
            if (_dayStartBalance - Account.Equity >= _dayStartBalance * DailyLossPercent / 100.0)
            {
                _dailyBlocked = true;
                CloseAll("daily loss limit");
                Print("CFX daily loss limit hit: no new trades until next UTC day");
                return true;
            }
            return false;
        }

        private bool CheckKillSwitch()
        {
            _peakEquity = Math.Max(_peakEquity, Account.Equity);
            if (Account.Equity <= _peakEquity * (1 - KillDrawdownPercent / 100.0))
            {
                CloseAll("equity kill-switch");
                Print("CFX KILL-SWITCH: equity {0:F2} is {1}% below peak {2:F2}. Bot stopped.", Account.Equity, KillDrawdownPercent, _peakEquity);
                Stop();
                return true;
            }
            return false;
        }

        private void CloseAll(string why)
        {
            foreach (var p in Positions.FindAll(BotLabel, SymbolName))
            {
                var r = ClosePosition(p);
                Print(r.IsSuccessful ? "CFX closed {0} ({1})" : "CFX close FAILED {0} ({1}): {2}", p.Id, why, r.Error);
            }
        }

        private void OnPositionClosed(PositionClosedEventArgs args)
        {
            var p = args.Position;
            if (p.Label != BotLabel || p.SymbolName != SymbolName) return;
            _consecLosses = p.NetProfit < 0 ? _consecLosses + 1 : 0;
            Print("CFX closed {0} {1} net {2:F2} reason {3}; consecutive losses {4}", p.TradeType, p.Id, p.NetProfit, args.Reason, _consecLosses);
            if (_consecLosses >= MaxConsecutiveLosses)
            {
                _pauseUntil = Server.Time.AddHours(PauseHours);
                _consecLosses = 0;
                Print("CFX pause: {0} consecutive losses, no entries until {1}", MaxConsecutiveLosses, _pauseUntil);
            }
        }

        protected override void OnStop()
        {
            Print("CFX stopped. Equity {0:F2}, peak {1:F2}", Account.Equity, _peakEquity);
        }
    }
}
