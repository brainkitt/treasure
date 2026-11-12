// CharlieBot.cs - cTrader Automate cBot, faithful port of agents/CHARLIE/strategy.py
// Range Break 100 Index "break-continuation" (attach to a Range Break 100 Index M1 chart).
//
// HONEST STATUS: research (agents/CHARLIE/NOTES.md) shows Range Break is a fair game; this system has
// NO statistical edge (official backtest PF 0.90, NOT QUALIFIED). It is delivered for completeness and for
// demo observation only. Do not run it on a funded account.
//
// Logic (evaluated once per closed M1 bar, identical to strategy.py):
//   break bar  : High - Low > BreakThreshold                       (30 price units)
//   up-break   : Close > Open  and  High - Close <= NearBoundary   (2 price units)  -> BUY  at next bar open
//   down-break : Close < Open  and  Close - Low  <= NearBoundary                    -> SELL at next bar open
//   exits      : hard SL StopDistance (25), trailing stop StopDistance ratcheted on bar closes,
//                time exit after MaxBars (30) bars, far "disaster" TP TakeProfitDistance (600).
//   one position per symbol, minimum volume by default, spread filter, daily loss limit, max-drawdown kill switch.
// Distances are in PRICE units (index points), not pips; they are converted with Symbol.PipSize.
using System;
using System.Linq;
using cAlgo.API;
using cAlgo.API.Internals;

namespace cAlgo.Robots
{
    [Robot(TimeZone = TimeZones.UTC, AccessRights = AccessRights.None)]
    public class CharlieBot : Robot
    {
        [Parameter("Break threshold (bar range, price units)", DefaultValue = 30.0, MinValue = 1)]
        public double BreakThreshold { get; set; }

        [Parameter("Near boundary (price units)", DefaultValue = 2.0, MinValue = 0)]
        public double NearBoundary { get; set; }

        [Parameter("Stop / trail distance (price units)", DefaultValue = 25.0, MinValue = 1)]
        public double StopDistance { get; set; }

        [Parameter("Disaster take-profit distance (price units)", DefaultValue = 600.0, MinValue = 1)]
        public double TakeProfitDistance { get; set; }

        [Parameter("Max bars in trade", DefaultValue = 30, MinValue = 1)]
        public int MaxBars { get; set; }

        [Parameter("Volume in units (0 = symbol minimum)", DefaultValue = 0.0, MinValue = 0)]
        public double VolumeUnits { get; set; }

        [Parameter("Max spread (price units)", DefaultValue = 3.9, MinValue = 0)]
        public double MaxSpread { get; set; }

        [Parameter("Daily loss limit (account ccy)", DefaultValue = 1.5, MinValue = 0)]
        public double DailyLossLimit { get; set; }

        [Parameter("Max drawdown kill switch (account ccy)", DefaultValue = 9.0, MinValue = 0)]
        public double MaxDrawdown { get; set; }

        [Parameter("Label", DefaultValue = "CHARLIE-RB")]
        public string Label { get; set; }

        private double _peakEquity;
        private bool _killed;
        private int _entryBarIndex = -1;

        protected override void OnStart()
        {
            _peakEquity = Account.Equity;
            if (TimeFrame != TimeFrame.Minute)
                Print("WARNING: strategy was researched on M1 bars; current timeframe is {0}", TimeFrame);
            var pos = FindPosition();
            if (pos != null)
                _entryBarIndex = Bars.OpenTimes.GetIndexByTime(pos.EntryTime);
            Positions.Closed += OnPositionClosed;
        }

        private Position FindPosition()
        {
            return Positions.FirstOrDefault(p => p.Label == Label && p.SymbolName == SymbolName);
        }

        private void OnPositionClosed(PositionClosedEventArgs args)
        {
            if (args.Position.Label == Label && args.Position.SymbolName == SymbolName)
                _entryBarIndex = -1;
        }

        private double TodayNet()
        {
            var today = Server.Time.Date;
            double closed = History.Where(h => h.Label == Label && h.SymbolName == SymbolName && h.ClosingTime.Date == today)
                                   .Sum(h => h.NetProfit);
            var pos = FindPosition();
            return closed + (pos != null ? pos.NetProfit : 0.0);
        }

        private bool RiskOk()
        {
            if (_killed) return false;
            _peakEquity = Math.Max(_peakEquity, Account.Equity);
            if (MaxDrawdown > 0 && _peakEquity - Account.Equity >= MaxDrawdown)
            {
                _killed = true;
                Print("KILL SWITCH: drawdown {0:F2} >= {1:F2}. Closing and stopping.", _peakEquity - Account.Equity, MaxDrawdown);
                var pos = FindPosition();
                if (pos != null) ClosePosition(pos);
                Stop();
                return false;
            }
            if (DailyLossLimit > 0 && TodayNet() <= -DailyLossLimit)
                return false;   // no new trades today (open position keeps its hard SL / trail / time exit)
            return true;
        }

        protected override void OnTick()
        {
            // equity-based kill switch is checked on every tick
            if (!_killed) { _peakEquity = Math.Max(_peakEquity, Account.Equity); if (MaxDrawdown > 0 && _peakEquity - Account.Equity >= MaxDrawdown) RiskOk(); }
        }

        protected override void OnBar()
        {
            // Called at the open of a new bar; Bars.Last(1) is the bar that has just closed.
            int lastClosed = Bars.Count - 2;
            if (lastClosed < 1) return;
            double o = Bars.OpenPrices[lastClosed], h = Bars.HighPrices[lastClosed];
            double l = Bars.LowPrices[lastClosed], c = Bars.ClosePrices[lastClosed];

            // 1) manage the open position: time exit, then trailing stop on the closed bar
            var pos = FindPosition();
            if (pos != null)
            {
                if (_entryBarIndex < 0) _entryBarIndex = Bars.OpenTimes.GetIndexByTime(pos.EntryTime);
                if (lastClosed - _entryBarIndex >= MaxBars)
                {
                    ClosePosition(pos);
                    pos = null;
                }
                else
                {
                    double newSl;
                    if (pos.TradeType == TradeType.Buy)
                    {
                        newSl = Math.Round(c - StopDistance, Symbol.Digits);                    // long stop works on BID
                        if (!pos.StopLoss.HasValue || newSl > pos.StopLoss.Value + Symbol.TickSize / 2)
                            ModifyPosition(pos, newSl, pos.TakeProfit);
                    }
                    else
                    {
                        newSl = Math.Round(c + Symbol.Spread + StopDistance, Symbol.Digits);     // short stop works on ASK
                        if (!pos.StopLoss.HasValue || newSl < pos.StopLoss.Value - Symbol.TickSize / 2)
                            ModifyPosition(pos, newSl, pos.TakeProfit);
                    }
                }
            }

            // 2) new signal on the bar that just closed (one position per symbol)
            if (pos != null) return;
            if (!RiskOk()) return;
            if (h - l <= BreakThreshold) return;
            bool up = c > o && (h - c) <= NearBoundary;
            bool dn = c < o && (c - l) <= NearBoundary;
            if (!up && !dn) return;
            if (Symbol.Spread > MaxSpread)
            {
                Print("Signal skipped: spread {0} > {1}", Symbol.Spread, MaxSpread);
                return;
            }
            double vol = VolumeUnits > 0 ? Symbol.NormalizeVolumeInUnits(VolumeUnits, RoundingMode.Down) : Symbol.VolumeInUnitsMin;
            if (vol < Symbol.VolumeInUnitsMin) vol = Symbol.VolumeInUnitsMin;
            double slPips = StopDistance / Symbol.PipSize;
            double tpPips = TakeProfitDistance / Symbol.PipSize;
            var res = ExecuteMarketOrder(up ? TradeType.Buy : TradeType.Sell, SymbolName, vol, Label, slPips, tpPips);
            if (res.IsSuccessful)
                _entryBarIndex = Bars.Count - 1;      // fill bar = the bar that has just opened
            else
                Print("Order failed: {0}", res.Error);
        }

        protected override void OnStop()
        {
            Positions.Closed -= OnPositionClosed;
        }
    }
}
