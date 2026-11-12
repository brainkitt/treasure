// DeltaBot - "PreOpenFade" for cTrader Automate (cAlgo.API)
// ---------------------------------------------------------------------------------------------
// Same logic and parameters as agents/DELTA/strategy.py (arena engine).
//
// ATTACH TO:  US SP 500 (Deriv cTrader), timeframe M15.  One instance, one position at a time.
//
// Logic (evaluated once per completed M15 bar):
//   * Only bars that OPEN between 03:00 and 09:30 New York time (DST-aware) may signal.
//   * Fresh upside breakout  : Close[i] >  Highest High of the previous N bars (i-N .. i-1)
//                              and Close[i-1] <= Highest High of (i-1-N .. i-2)          -> SELL (fade)
//   * Fresh downside breakout: Close[i] <  Lowest Low of the previous N bars
//                              and Close[i-1] >= Lowest Low of (i-1-N .. i-2)            -> BUY  (fade)
//   * Market order at the open of the next bar, hard SL = min(SlAtr x ATR, SlCap), hard TP = TpAtr x ATR,
//     ATR = simple mean of True Range over the last AtrPeriod completed M15 bars (incl. the signal bar).
//   * Time exit HoldMinutes after entry.
// Risk management:
//   * Minimum volume by default (0.1 units = 0.10 lot on Deriv "US SP 500"): worst planned loss 14 pts = $1.40.
//   * Spread filter, daily loss limit (realised + floating, UTC day), equity draw-down kill switch,
//     one position per symbol, no entries without a valid SL.
//
// Default parameter set (the only one documented / validated):
//   Lookback=32  AtrPeriod=14  SlAtr=2.0  TpAtr=1.0  SlCap=14.0  HoldMinutes=240
//   StartHourNY=3.0  EndHourNY=9.5  VolumeUnits=0 (=broker minimum)  MaxSpread=0.80
//   DailyLossLimit=3.00  MaxDrawdown=9.00
// ---------------------------------------------------------------------------------------------
using System;
using cAlgo.API;
using cAlgo.API.Internals;

namespace cAlgo.Robots
{
    [Robot(TimeZone = TimeZones.UTC, AccessRights = AccessRights.None)]
    public class DeltaBot : Robot
    {
        [Parameter("Lookback bars (N)", Group = "Signal", DefaultValue = 32, MinValue = 4)]
        public int Lookback { get; set; }

        [Parameter("ATR period", Group = "Signal", DefaultValue = 14, MinValue = 2)]
        public int AtrPeriod { get; set; }

        [Parameter("Session start hour (New York)", Group = "Signal", DefaultValue = 3.0, MinValue = 0, MaxValue = 24)]
        public double StartHourNY { get; set; }

        [Parameter("Session end hour (New York)", Group = "Signal", DefaultValue = 9.5, MinValue = 0, MaxValue = 24)]
        public double EndHourNY { get; set; }

        [Parameter("Stop loss (x ATR)", Group = "Exits", DefaultValue = 2.0, MinValue = 0.1)]
        public double SlAtr { get; set; }

        [Parameter("Take profit (x ATR)", Group = "Exits", DefaultValue = 1.0, MinValue = 0.1)]
        public double TpAtr { get; set; }

        [Parameter("Stop loss cap (price units)", Group = "Exits", DefaultValue = 14.0, MinValue = 0.1)]
        public double SlCap { get; set; }

        [Parameter("Max hold (minutes)", Group = "Exits", DefaultValue = 240, MinValue = 1)]
        public int HoldMinutes { get; set; }

        [Parameter("Volume in units (0 = broker minimum)", Group = "Risk", DefaultValue = 0, MinValue = 0)]
        public double VolumeUnits { get; set; }

        [Parameter("Max spread (price units)", Group = "Risk", DefaultValue = 0.8, MinValue = 0)]
        public double MaxSpread { get; set; }

        [Parameter("Daily loss limit (account ccy)", Group = "Risk", DefaultValue = 3.0, MinValue = 0)]
        public double DailyLossLimit { get; set; }

        [Parameter("Max equity drawdown kill-switch (account ccy)", Group = "Risk", DefaultValue = 9.0, MinValue = 0)]
        public double MaxDrawdown { get; set; }

        [Parameter("Label", Group = "Misc", DefaultValue = "DELTA-PreOpenFade")]
        public string Label { get; set; }

        private TimeZoneInfo _ny;
        private double _peakEquity;
        private bool _killed;
        private DateTime _lossDay = DateTime.MinValue;   // UTC day on which the daily loss limit was hit

        protected override void OnStart()
        {
            _ny = FindNewYorkZone();
            _peakEquity = Account.Equity;

            if (TimeFrame != TimeFrame.Minute15)
                Print("WARNING: DeltaBot was validated on M15 only. Current timeframe: {0}", TimeFrame);
            if (_ny == null)
                Print("WARNING: New York time zone not found on this machine - falling back to a built-in US DST rule.");

            Positions.Closed += OnPositionClosed;
            Timer.Start(TimeSpan.FromSeconds(30));
            Print("DeltaBot started on {0} {1}. Min volume {2}, pip size {3}.", SymbolName, TimeFrame,
                  Symbol.VolumeInUnitsMin, Symbol.PipSize);
        }

        protected override void OnStop()
        {
            Positions.Closed -= OnPositionClosed;
            Timer.Stop();
        }

        private void OnPositionClosed(PositionClosedEventArgs args)
        {
            var p = args.Position;
            if (p.Label == Label && p.SymbolName == SymbolName)
                Print("Closed {0} {1}: net {2:F2} ({3})", p.TradeType, p.SymbolName, p.NetProfit, args.Reason);
        }

        // ---- risk supervision on every timer tick and every tick -------------------------------------------
        protected override void OnTimer()
        {
            Supervise();
        }

        protected override void OnTick()
        {
            CheckKillSwitch();      // cheap equity check on every tick; the rest runs on the timer / on bar
        }

        private void Supervise()
        {
            if (_killed) return;
            CheckKillSwitch();
            if (_killed) return;

            // 2) daily loss limit (realised today + floating), UTC day
            if (DailyLossLimit > 0 && _lossDay != Server.Time.Date && TodayPnl() <= -DailyLossLimit)
            {
                Print("Daily loss limit hit ({0:F2}). Flat until next UTC day.", TodayPnl());
                CloseAll();
                _lossDay = Server.Time.Date;
            }

            // 3) time exit
            foreach (var pos in Positions.FindAll(Label, SymbolName))
            {
                if (Server.Time >= pos.EntryTime.AddMinutes(HoldMinutes))
                    ClosePosition(pos);
            }
        }

        // 1) equity draw-down kill switch (peak-to-current equity since the bot was started)
        private void CheckKillSwitch()
        {
            if (_killed) return;
            if (Account.Equity > _peakEquity) _peakEquity = Account.Equity;
            if (MaxDrawdown > 0 && _peakEquity - Account.Equity >= MaxDrawdown)
            {
                Print("KILL SWITCH: equity draw-down {0:F2} >= {1:F2}. Closing everything and stopping.",
                      _peakEquity - Account.Equity, MaxDrawdown);
                CloseAll();
                _killed = true;
                Stop();
            }
        }

        private double TodayPnl()
        {
            var day = Server.Time.Date;
            double pnl = 0;
            foreach (var h in History)
            {
                if (h.Label == Label && h.SymbolName == SymbolName && h.ClosingTime >= day)
                    pnl += h.NetProfit;
            }
            foreach (var pos in Positions.FindAll(Label, SymbolName))
                pnl += pos.NetProfit;
            return pnl;
        }

        private void CloseAll()
        {
            foreach (var pos in Positions.FindAll(Label, SymbolName))
                ClosePosition(pos);
        }

        // ---- signal: once per completed bar ---------------------------------------------------------------
        protected override void OnBar()
        {
            if (_killed) return;
            Supervise();
            if (_killed) return;

            int i = Bars.Count - 2;                       // last COMPLETED bar
            if (i < Lookback + AtrPeriod + 2) return;

            if (_lossDay == Server.Time.Date) return;     // daily loss limit active
            if (Positions.FindAll(Label, SymbolName).Length > 0) return;   // one position per symbol

            // session filter on the signal bar's OPEN time, New York clock
            double nyHour = NewYorkHour(Bars.OpenTimes[i]);
            if (!(nyHour >= StartHourNY && nyHour < EndHourNY)) return;

            // ATR = simple mean of true range over the last AtrPeriod completed bars
            double atr = 0;
            for (int k = i - AtrPeriod + 1; k <= i; k++)
            {
                double pc = Bars.ClosePrices[k - 1];
                double tr = Math.Max(Bars.HighPrices[k] - Bars.LowPrices[k],
                            Math.Max(Math.Abs(Bars.HighPrices[k] - pc), Math.Abs(Bars.LowPrices[k] - pc)));
                atr += tr;
            }
            atr /= AtrPeriod;
            if (!(atr > 0)) return;

            // Donchian levels from the N bars BEFORE bar i, and before bar i-1
            double hi = double.MinValue, lo = double.MaxValue, hiPrev = double.MinValue, loPrev = double.MaxValue;
            for (int k = i - Lookback; k <= i - 1; k++)
            {
                hi = Math.Max(hi, Bars.HighPrices[k]);
                lo = Math.Min(lo, Bars.LowPrices[k]);
            }
            for (int k = i - 1 - Lookback; k <= i - 2; k++)
            {
                hiPrev = Math.Max(hiPrev, Bars.HighPrices[k]);
                loPrev = Math.Min(loPrev, Bars.LowPrices[k]);
            }

            double c = Bars.ClosePrices[i], c1 = Bars.ClosePrices[i - 1];
            bool up = c > hi && c1 <= hiPrev;             // fresh upside breakout   -> SELL
            bool dn = c < lo && c1 >= loPrev;             // fresh downside breakout -> BUY
            if (!up && !dn) return;

            // spread filter
            double spread = Symbol.Ask - Symbol.Bid;
            if (MaxSpread > 0 && spread > MaxSpread)
            {
                Print("Signal skipped: spread {0:F2} > {1:F2}", spread, MaxSpread);
                return;
            }

            double slDist = Math.Min(SlAtr * atr, SlCap);
            double tpDist = TpAtr * atr;
            double slPips = Math.Round(slDist / Symbol.PipSize, 1);
            double tpPips = Math.Round(tpDist / Symbol.PipSize, 1);
            if (slPips <= 0 || tpPips <= 0) return;

            double vol = VolumeUnits > 0 ? Symbol.NormalizeVolumeInUnits(VolumeUnits, RoundingMode.Down)
                                         : Symbol.VolumeInUnitsMin;
            if (vol < Symbol.VolumeInUnitsMin) vol = Symbol.VolumeInUnitsMin;

            var side = up ? TradeType.Sell : TradeType.Buy;
            var res = ExecuteMarketOrder(side, SymbolName, vol, Label, slPips, tpPips);
            if (!res.IsSuccessful)
            {
                Print("Order failed: {0}", res.Error);
                return;
            }
            // safety: never hold a position without a protective stop
            if (res.Position != null && !res.Position.StopLoss.HasValue)
            {
                Print("No stop loss attached - closing position.");
                ClosePosition(res.Position);
                return;
            }
            Print("{0} {1} units @ {2}  SL {3:F1} pips  TP {4:F1} pips  ATR {5:F2}  NY hour {6:F2}",
                  side, vol, res.Position != null ? res.Position.EntryPrice : 0, slPips, tpPips, atr, nyHour);
        }

        // ---- New York clock --------------------------------------------------------------------------------
        private static TimeZoneInfo FindNewYorkZone()
        {
            foreach (var id in new[] { "Eastern Standard Time", "America/New_York" })
            {
                try { return TimeZoneInfo.FindSystemTimeZoneById(id); }
                catch (Exception) { }
            }
            return null;
        }

        private double NewYorkHour(DateTime utc)
        {
            DateTime ny;
            if (_ny != null)
                ny = TimeZoneInfo.ConvertTimeFromUtc(DateTime.SpecifyKind(utc, DateTimeKind.Utc), _ny);
            else
                ny = utc.AddHours(IsUsDst(utc) ? -4 : -5);
            return ny.Hour + ny.Minute / 60.0;
        }

        // US DST: second Sunday of March 07:00 UTC .. first Sunday of November 06:00 UTC
        private static bool IsUsDst(DateTime utc)
        {
            var start = NthSunday(utc.Year, 3, 2).AddHours(7);
            var end = NthSunday(utc.Year, 11, 1).AddHours(6);
            return utc >= start && utc < end;
        }

        private static DateTime NthSunday(int year, int month, int n)
        {
            var d = new DateTime(year, month, 1, 0, 0, 0, DateTimeKind.Utc);
            while (d.DayOfWeek != DayOfWeek.Sunday) d = d.AddDays(1);
            return d.AddDays(7 * (n - 1));
        }
    }
}
