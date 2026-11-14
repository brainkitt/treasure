// CharlieBot (phase 2) - overnight-gap fade on US Small Cap 2000, H1 chart, minimum size.
// Same logic and parameters as agents/CHARLIE/strategy.py (gapfade.py):
//   09:00 New York (close of the 08:00 NY H1 bar):
//       on = ln(close / yesterday's 16:00 NY close);  z = on / stdev(last 20 daily 16:00->16:00 log returns)
//       if |z| > Threshold and today is a normal NYSE session -> market order AGAINST the overnight move
//   hard stop-loss RiskUsd (default $1.50 = 15 index points at 0.1 unit), no profit target
//   16:00 New York: close the position.  Never held overnight / over a weekend.
// Attach to: US Small Cap 2000, timeframe H1 (Hour). One instance. Backtest status: NOT QUALIFIED (see NOTES.md).
using System;
using System.Collections.Generic;
using System.Linq;
using cAlgo.API;
using cAlgo.API.Internals;

namespace cAlgo.Robots
{
    [Robot(TimeZone = TimeZones.UTC, AccessRights = AccessRights.None)]
    public class CharlieBot : Robot
    {
        [Parameter("Volume (units, 0 = symbol minimum)", DefaultValue = 0, MinValue = 0)]
        public double VolumeUnits { get; set; }

        [Parameter("Gap threshold (x daily vol)", DefaultValue = 0.5, MinValue = 0)]
        public double Threshold { get; set; }

        [Parameter("Vol window (days)", DefaultValue = 20, MinValue = 5)]
        public int VolWindow { get; set; }

        [Parameter("Signal bar hour (New York)", DefaultValue = 8, MinValue = 0, MaxValue = 23)]
        public int SignalHourNy { get; set; }

        [Parameter("Exit hour (New York)", DefaultValue = 16, MinValue = 1, MaxValue = 23)]
        public int ExitHourNy { get; set; }

        [Parameter("Stop-loss risk per trade (USD)", DefaultValue = 1.5, MinValue = 0.1)]
        public double RiskUsd { get; set; }

        [Parameter("Max spread (price units)", DefaultValue = 1.0, MinValue = 0)]
        public double MaxSpread { get; set; }

        [Parameter("Daily loss limit (USD)", DefaultValue = 1.6, MinValue = 0)]
        public double DailyLossLimit { get; set; }

        [Parameter("Max drawdown kill-switch (USD)", DefaultValue = 12.0, MinValue = 0)]
        public double MaxDrawdownUsd { get; set; }

        private const string Label = "CharlieBot";
        private TimeZoneInfo _ny;
        private double _peakEquity;
        private bool _killed;
        private DateTime _dayStartDate = DateTime.MinValue;
        private double _dayStartBalance;

        // NYSE full holidays and early-close days (published calendar): no trade.
        private static readonly HashSet<DateTime> NyseOff = new HashSet<DateTime>(new[]
        {
            "2024-01-01","2024-01-15","2024-02-19","2024-03-29","2024-05-27","2024-06-19","2024-07-03","2024-07-04","2024-09-02",
            "2024-11-28","2024-11-29","2024-12-24","2024-12-25",
            "2025-01-01","2025-01-09","2025-01-20","2025-02-17","2025-04-18","2025-05-26","2025-06-19","2025-07-03","2025-07-04",
            "2025-09-01","2025-11-27","2025-11-28","2025-12-24","2025-12-25",
            "2026-01-01","2026-01-19","2026-02-16","2026-04-03","2026-05-25","2026-06-19","2026-07-03","2026-09-07","2026-11-26",
            "2026-11-27","2026-12-24","2026-12-25",
            "2027-01-01","2027-01-18","2027-02-15","2027-03-26","2027-05-31","2027-06-18","2027-07-05","2027-09-06","2027-11-25",
            "2027-11-26","2027-12-24"
        }.Select(s => DateTime.ParseExact(s, "yyyy-MM-dd", System.Globalization.CultureInfo.InvariantCulture)));

        protected override void OnStart()
        {
            try { _ny = TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time"); }
            catch (Exception) { _ny = TimeZoneInfo.FindSystemTimeZoneById("America/New_York"); }
            _peakEquity = Account.Equity;
            _dayStartBalance = Account.Balance;
            if (TimeFrame != TimeFrame.Hour)
                Print("WARNING: CharlieBot is designed for the H1 timeframe.");
            Timer.Start(TimeSpan.FromSeconds(30));
        }

        private DateTime ToNy(DateTime utc)
        {
            return TimeZoneInfo.ConvertTimeFromUtc(DateTime.SpecifyKind(utc, DateTimeKind.Utc), _ny);
        }

        private Position MyPosition()
        {
            return Positions.FirstOrDefault(p => p.Label == Label && p.SymbolName == SymbolName);
        }

        private void CloseMine(string why)
        {
            foreach (var p in Positions.Where(p => p.Label == Label && p.SymbolName == SymbolName).ToArray())
            {
                ClosePosition(p);
                Print("Closed: {0}", why);
            }
        }

        private void RiskChecks()
        {
            var nyNow = ToNy(Server.Time);
            if (nyNow.Date != _dayStartDate)
            {
                _dayStartDate = nyNow.Date;
                _dayStartBalance = Account.Balance;
            }
            if (Account.Equity > _peakEquity) _peakEquity = Account.Equity;
            if (!_killed && MaxDrawdownUsd > 0 && _peakEquity - Account.Equity >= MaxDrawdownUsd)
            {
                _killed = true;
                CloseMine("max drawdown kill-switch");
                Print("KILL-SWITCH: drawdown {0:F2} >= {1:F2}. Bot stops trading.", _peakEquity - Account.Equity, MaxDrawdownUsd);
                Stop();
            }
        }

        private bool DailyLossHit()
        {
            return DailyLossLimit > 0 && _dayStartBalance - Account.Equity >= DailyLossLimit;
        }

        protected override void OnTimer()
        {
            RiskChecks();
            // time exit safety net: flat at/after the exit hour (also covers a missing 15:00 bar)
            var p = MyPosition();
            if (p != null)
            {
                var nyNow = ToNy(Server.Time);
                var nyEntry = ToNy(p.EntryTime);
                if (nyNow.Date > nyEntry.Date || nyNow.Hour >= ExitHourNy)
                    CloseMine("time exit " + ExitHourNy + ":00 New York");
            }
        }

        protected override void OnBar()
        {
            RiskChecks();
            if (_killed) return;
            int last = Bars.Count - 2;                 // the bar that has just closed
            if (last < 30) return;
            var nyOpen = ToNy(Bars.OpenTimes[last]);

            // time exit: the 15:00-16:00 NY bar has closed
            if (nyOpen.Hour == ExitHourNy - 1)
                CloseMine("time exit " + ExitHourNy + ":00 New York");

            if (nyOpen.Hour != SignalHourNy) return;
            var today = nyOpen.Date;
            if (today.DayOfWeek == DayOfWeek.Saturday || today.DayOfWeek == DayOfWeek.Sunday) return;
            if (NyseOff.Contains(today)) return;
            if (MyPosition() != null) return;
            if (DailyLossHit()) { Print("Daily loss limit reached - no trade today."); return; }

            // collect the last VolWindow+1 cash closes (close of the 15:00 NY bar) before today
            var closes = new List<double>();
            DateTime lastCloseDay = DateTime.MinValue;
            for (int i = last - 1; i >= 0 && closes.Count < VolWindow + 1; i--)
            {
                var t = ToNy(Bars.OpenTimes[i]);
                if (t.Hour == ExitHourNy - 1 && t.Date < today)
                {
                    if (closes.Count == 0) lastCloseDay = t.Date;
                    closes.Add(Bars.ClosePrices[i]);
                }
            }
            if (closes.Count < VolWindow + 1) return;
            if ((today - lastCloseDay).TotalDays > 4) return;      // stale reference

            var rets = new double[VolWindow];
            for (int k = 0; k < VolWindow; k++) rets[k] = Math.Log(closes[k] / closes[k + 1]);
            double mean = rets.Average();
            double vol = Math.Sqrt(rets.Sum(r => (r - mean) * (r - mean)) / (VolWindow - 1));   // sample std, as pandas
            if (vol <= 0) return;

            double price = Bars.ClosePrices[last];
            double on = Math.Log(price / closes[0]);
            double z = on / vol;
            if (Math.Abs(z) <= Threshold) return;

            if (Symbol.Spread > MaxSpread)
            {
                Print("Spread {0} > {1} - signal skipped.", Symbol.Spread, MaxSpread);
                return;
            }

            double units = VolumeUnits > 0 ? VolumeUnits : Symbol.VolumeInUnitsMin;
            units = Symbol.NormalizeVolumeInUnits(units, RoundingMode.Down);
            if (units < Symbol.VolumeInUnitsMin) units = Symbol.VolumeInUnitsMin;
            double slDistance = RiskUsd / units;                    // price units (USD-quoted index)
            double slPips = Math.Round(slDistance / Symbol.PipSize, 1);
            var side = on > 0 ? TradeType.Sell : TradeType.Buy;     // fade the overnight move
            var res = ExecuteMarketOrder(side, SymbolName, units, Label, slPips, null);
            if (res.IsSuccessful)
                Print("{0} {1} units, z={2:F2}, SL {3} pips", side, units, z, slPips);
            else
                Print("Order failed: {0}", res.Error);
        }

        protected override void OnStop()
        {
            // positions keep their hard stop; nothing else to do
        }
    }
}
