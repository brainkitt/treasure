// VolaBot.cs - cTrader Automate cBot, exact port of agents/VOLA/strategy.py
// "Range Break 200 breakout-follow" (C1), Deriv Range Break 200 Index, M5 chart.
//
// WARNING: research found NO edge for this logic (official evaluate2: PF 0.92, NOT QUALIFIED; failed two
// pre-declared confirmations on unseen months). It is delivered for completeness/forward-logging only.
// Do NOT run it with real money.
//
// Logic (once per CLOSED bar, identical to strategy.py):
//   HH = highest High of the N closed bars BEFORE the signal bar, LL = lowest Low of those bars
//   ATR = simple mean of True Range over the last AtrPeriod closed bars (signal bar included)
//   BUY  if Close[signal] > HH ; SELL if Close[signal] < LL
//   only if the signal bar CLOSES at or before LastEntryHour:59 UTC (flat before the 21:00 UTC rollover)
//   hard stop = K * ATR attached to the order; trailing stop of the same distance ratcheted on bar closes
//   time exit after H closed bars in the trade (fill bar excluded, as in the engine)
// Safety: one position per symbol+label, broker-minimum volume by default (optional risk-% sizing, capped),
//   spread gate, daily loss limit, equity drawdown kill-switch, consecutive-loss pause, force-flat before
//   rollover, duplicate-order prevention, TradeResult error handling.
using System;
using System.Linq;
using cAlgo.API;
using cAlgo.API.Internals;

namespace cAlgo.Robots
{
    [Robot(TimeZone = TimeZones.UTC, AccessRights = AccessRights.None)]
    public class VolaBot : Robot
    {
        // ---- signal ----
        [Parameter("Donchian lookback N (bars)", Group = "Signal", DefaultValue = 24, MinValue = 2, MaxValue = 500)]
        public int N { get; set; }

        [Parameter("ATR period (bars)", Group = "Signal", DefaultValue = 24, MinValue = 2, MaxValue = 500)]
        public int AtrPeriod { get; set; }

        // ---- exits ----
        [Parameter("Stop & trail (x ATR)", Group = "Exits", DefaultValue = 2.0, MinValue = 0.2, MaxValue = 20, Step = 0.1)]
        public double K { get; set; }

        [Parameter("Max bars in trade (H)", Group = "Exits", DefaultValue = 48, MinValue = 1, MaxValue = 1000)]
        public int H { get; set; }

        // ---- session ----
        [Parameter("Last entry hour UTC (signal bar close)", Group = "Session", DefaultValue = 16, MinValue = 0, MaxValue = 23)]
        public int LastEntryHour { get; set; }

        [Parameter("Force flat at hour UTC (-1 = off)", Group = "Session", DefaultValue = 21, MinValue = -1, MaxValue = 23)]
        public int ForceFlatHour { get; set; }

        // ---- sizing ----
        [Parameter("Volume in units (0 = broker minimum)", Group = "Sizing", DefaultValue = 0.0, MinValue = 0)]
        public double VolumeUnits { get; set; }

        [Parameter("Risk % of balance per trade (0 = off)", Group = "Sizing", DefaultValue = 0.0, MinValue = 0, MaxValue = 5)]
        public double RiskPercent { get; set; }

        [Parameter("Max risk % per trade (cap)", Group = "Sizing", DefaultValue = 3.0, MinValue = 0.1, MaxValue = 10)]
        public double MaxRiskPercent { get; set; }

        // ---- safety ----
        [Parameter("Max spread (price units)", Group = "Safety", DefaultValue = 2.5, MinValue = 0)]
        public double MaxSpread { get; set; }

        [Parameter("Daily loss limit (% of day-start balance)", Group = "Safety", DefaultValue = 10.0, MinValue = 0.5, MaxValue = 100)]
        public double DailyLossPercent { get; set; }

        [Parameter("Equity kill-switch (% drawdown from peak)", Group = "Safety", DefaultValue = 25.0, MinValue = 1, MaxValue = 100)]
        public double KillSwitchPercent { get; set; }

        [Parameter("Max consecutive losses before pause", Group = "Safety", DefaultValue = 6, MinValue = 1, MaxValue = 100)]
        public int MaxConsecLosses { get; set; }

        [Parameter("Pause length after loss streak (hours)", Group = "Safety", DefaultValue = 24, MinValue = 1, MaxValue = 720)]
        public int PauseHours { get; set; }

        [Parameter("Label", Group = "Safety", DefaultValue = "VOLA-RB200")]
        public string BotLabel { get; set; }

        private int _barsInTrade;
        private double _peakEquity, _dayStartBalance;
        private DateTime _day;
        private int _consecLosses;
        private DateTime _pausedUntil = DateTime.MinValue;
        private bool _killed;
        private bool _orderInFlight;

        protected override void OnStart()
        {
            _peakEquity = Account.Equity;
            _dayStartBalance = Account.Balance;
            _day = Server.Time.Date;
            Positions.Closed += OnPositionClosed;
            if (Bars.TimeFrame != TimeFrame.Minute5)
                Print("WARNING: designed and validated on M5 bars; current timeframe is {0}", Bars.TimeFrame);
            Print("VolaBot started on {0} {1}. NOTE: no validated edge (see NOTES.md). min volume {2}",
                  SymbolName, Bars.TimeFrame, Symbol.VolumeInUnitsMin);
        }

        private Position MyPosition()
        {
            return Positions.FirstOrDefault(p => p.Label == BotLabel && p.SymbolName == SymbolName);
        }

        private void OnPositionClosed(PositionClosedEventArgs args)
        {
            var p = args.Position;
            if (p.Label != BotLabel || p.SymbolName != SymbolName) return;
            _consecLosses = p.NetProfit < 0 ? _consecLosses + 1 : 0;
            Print("Closed {0} net {1:F2} reason {2} consecLosses {3}", p.TradeType, p.NetProfit, args.Reason, _consecLosses);
            if (_consecLosses >= MaxConsecLosses)
            {
                _pausedUntil = Server.Time.AddHours(PauseHours);
                Print("Loss streak {0}: entries paused until {1:u}", _consecLosses, _pausedUntil);
                _consecLosses = 0;
            }
        }

        protected override void OnTick()
        {
            // kill-switch and daily loss are checked intrabar as well
            CheckRisk();
            var pos = MyPosition();
            if (pos != null && ForceFlatHour >= 0 && Server.Time.Hour == ForceFlatHour && Server.Time.Minute < 5)
                ClosePos(pos, "force-flat before rollover");
        }

        private bool CheckRisk()
        {
            if (Server.Time.Date != _day) { _day = Server.Time.Date; _dayStartBalance = Account.Balance; }
            _peakEquity = Math.Max(_peakEquity, Account.Equity);
            if (!_killed && Account.Equity < _peakEquity * (1 - KillSwitchPercent / 100.0))
            {
                _killed = true;
                Print("KILL-SWITCH: equity {0:F2} < {1:F0}% below peak {2:F2}. Closing and stopping.", Account.Equity, KillSwitchPercent, _peakEquity);
                var p = MyPosition(); if (p != null) ClosePos(p, "kill-switch");
                Stop();
                return false;
            }
            double dayPnl = Account.Equity - _dayStartBalance;
            if (dayPnl < -_dayStartBalance * DailyLossPercent / 100.0)
            {
                var p = MyPosition();
                if (p != null) ClosePos(p, "daily loss limit");
                return false;
            }
            return !_killed;
        }

        private void ClosePos(Position p, string why)
        {
            var r = ClosePosition(p);
            if (!r.IsSuccessful) Print("Close failed ({0}): {1}", why, r.Error);
            else Print("Closed position: {0}", why);
        }

        private double Atr(int last)
        {
            // simple mean of True Range of closed bars last-AtrPeriod+1 .. last (Bars index)
            double s = 0;
            for (int i = last - AtrPeriod + 1; i <= last; i++)
            {
                double pc = Bars.ClosePrices[i - 1];
                double tr = Math.Max(Bars.HighPrices[i] - Bars.LowPrices[i],
                            Math.Max(Math.Abs(Bars.HighPrices[i] - pc), Math.Abs(Bars.LowPrices[i] - pc)));
                s += tr;
            }
            return s / AtrPeriod;
        }

        protected override void OnBar()
        {
            int sig = Bars.Count - 2; // last CLOSED bar
            if (sig < Math.Max(N, AtrPeriod) + 2) return;
            bool riskOk = CheckRisk();
            double atr = Atr(sig);
            double close = Bars.ClosePrices[sig];

            // ---- manage open position (trail on closes, time exit) ----
            var pos = MyPosition();
            if (pos != null)
            {
                _barsInTrade++;
                if (_barsInTrade >= H) { ClosePos(pos, "time exit"); return; }
                double dist = K * pos.Comment.ToDoubleOrDefault();
                if (dist > 0)
                {
                    double newSl = pos.TradeType == TradeType.Buy ? close - dist : close + Symbol.Spread + dist;
                    bool better = pos.StopLoss == null ||
                                  (pos.TradeType == TradeType.Buy ? newSl > pos.StopLoss.Value : newSl < pos.StopLoss.Value);
                    if (better)
                    {
                        var r = ModifyPosition(pos, Math.Round(newSl, Symbol.Digits), pos.TakeProfit, ProtectionType.Absolute);
                        if (!r.IsSuccessful) Print("Trail modify failed: {0}", r.Error);
                    }
                }
                return;
            }
            _orderInFlight = false;
            if (!riskOk || Server.Time < _pausedUntil) return;

            // ---- entry ----
            DateTime sigClose = Bars.OpenTimes[sig].Add(TimeSpan.FromMinutes(Bars.TimeFrame == TimeFrame.Minute5 ? 5 : 0));
            if (sigClose.Hour > LastEntryHour) return;
            double hh = double.MinValue, ll = double.MaxValue;
            for (int i = sig - N; i < sig; i++) { hh = Math.Max(hh, Bars.HighPrices[i]); ll = Math.Min(ll, Bars.LowPrices[i]); }
            TradeType? side = null;
            if (close > hh) side = TradeType.Buy;
            else if (close < ll) side = TradeType.Sell;
            if (side == null || _orderInFlight) return;
            if (Symbol.Spread > MaxSpread) { Print("Spread {0} > max {1}: skip", Symbol.Spread, MaxSpread); return; }

            double stopDist = K * atr;
            double vol = VolumeUnits > 0 ? VolumeUnits : Symbol.VolumeInUnitsMin;
            if (RiskPercent > 0)
            {
                double riskUsd = Account.Balance * Math.Min(RiskPercent, MaxRiskPercent) / 100.0;
                double perUnit = stopDist / Symbol.TickSize * Symbol.TickValue;
                if (perUnit > 0) vol = riskUsd / perUnit;
            }
            vol = Symbol.NormalizeVolumeInUnits(Math.Max(vol, Symbol.VolumeInUnitsMin), RoundingMode.Down);
            vol = Math.Max(vol, Symbol.VolumeInUnitsMin);
            double capUsd = Account.Balance * MaxRiskPercent / 100.0;
            double riskAtVol = stopDist / Symbol.TickSize * Symbol.TickValue * vol;
            if (RiskPercent > 0 && riskAtVol > capUsd && vol > Symbol.VolumeInUnitsMin)
                vol = Symbol.NormalizeVolumeInUnits(Symbol.VolumeInUnitsMin, RoundingMode.Up);

            double slPips = stopDist / Symbol.PipSize;
            _orderInFlight = true;
            // the ATR at entry is stored in the comment so the trailing distance stays constant (as in strategy.py)
            var res = ExecuteMarketOrder(side.Value, SymbolName, vol, BotLabel, slPips, null, atr.ToString("R", System.Globalization.CultureInfo.InvariantCulture));
            if (res.IsSuccessful)
            {
                _barsInTrade = 0;
                Print("{0} {1} units at {2}, SL dist {3:F2} (K {4} x ATR {5:F2}), HH {6} LL {7}", side, vol, res.Position.EntryPrice, stopDist, K, atr, hh, ll);
            }
            else
            {
                _orderInFlight = false;
                Print("Order failed: {0}", res.Error);
            }
        }

        protected override void OnStop()
        {
            Positions.Closed -= OnPositionClosed;
            Print("VolaBot stopped.");
        }
    }

    internal static class Ext
    {
        public static double ToDoubleOrDefault(this string s)
        {
            double v;
            return double.TryParse(s, System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out v) ? v : 0.0;
        }
    }
}
