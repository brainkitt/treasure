// AlphaBot - London-open breakout of the overnight (Asian) range.  cTrader Automate cBot (cAlgo.API).
// Mirrors agents/ALPHA/strategy.py exactly (same rules, same defaults):
//   * Range  = high/low of the M5 bars starting in [RangeStartHour, RangeEndHour) Europe/London time (00:00-08:00).
//   * Entry  = first M5 bar that CLOSES outside the range between RangeEndHour and EntryEndHour (08:00-11:00),
//              market order at the open of the next bar, in the direction of the break. One trade per day.
//   * Stop   = clip(SlRangeMult * range, MinSlPips, MaxSlPips) pips (hard server-side SL)
//   * Target = TpMult * stop (hard server-side TP);  time exit at ExitHour (16:00 London). Never held overnight.
// Attach ONE instance per symbol (any chart timeframe - the bot always reads M5 bars of the chart symbol).
// Validated parameter set (identical for both legs): EURUSD and GBPUSD, all defaults, volume 1000 units (0.01 lot).
// Risk controls: hard SL/TP on every order, spread filter, one position per symbol, daily loss limit,
//                equity draw-down kill-switch (stops the bot), Friday / end-of-session flat.
using System;
using System.Linq;
using cAlgo.API;
using cAlgo.API.Internals;

namespace cAlgo.Robots
{
    [Robot(TimeZone = TimeZones.UTC, AccessRights = AccessRights.None)]
    public class AlphaBot : Robot
    {
        [Parameter("Range start hour (London)", DefaultValue = 0.0, MinValue = 0, MaxValue = 23)]
        public double RangeStartHour { get; set; }

        [Parameter("Range end hour (London)", DefaultValue = 8.0, MinValue = 1, MaxValue = 23)]
        public double RangeEndHour { get; set; }

        [Parameter("Entry window end hour (London)", DefaultValue = 11.0, MinValue = 1, MaxValue = 23)]
        public double EntryEndHour { get; set; }

        [Parameter("Time exit hour (London)", DefaultValue = 16.0, MinValue = 1, MaxValue = 23)]
        public double ExitHour { get; set; }

        [Parameter("SL = this x range", DefaultValue = 0.75, MinValue = 0.1)]
        public double SlRangeMult { get; set; }

        [Parameter("TP = this x SL", DefaultValue = 2.0, MinValue = 0.2)]
        public double TpMult { get; set; }

        [Parameter("Min SL (pips)", DefaultValue = 5.0, MinValue = 1)]
        public double MinSlPips { get; set; }

        [Parameter("Max SL (pips)", DefaultValue = 14.0, MinValue = 1)]
        public double MaxSlPips { get; set; }

        [Parameter("Volume in units (0 = symbol minimum)", DefaultValue = 0, MinValue = 0)]
        public double VolumeUnits { get; set; }

        [Parameter("Max spread (pips)", DefaultValue = 2.0, MinValue = 0.1)]
        public double MaxSpreadPips { get; set; }

        [Parameter("Daily loss limit (account ccy)", DefaultValue = 3.0, MinValue = 0.1)]
        public double DailyLossLimit { get; set; }

        [Parameter("Max draw-down kill-switch (account ccy)", DefaultValue = 9.0, MinValue = 0.5)]
        public double MaxDrawdown { get; set; }

        [Parameter("Label", DefaultValue = "ALPHA-LDN")]
        public string Label { get; set; }

        private const int SignalTfMinutes = 5;
        private Bars _m5;
        private TimeZoneInfo _london;
        private DateTime _day = DateTime.MinValue;   // current London calendar day
        private bool _doneToday;                     // first break already consumed (or skipped) today
        private double _peakEquity;
        private bool _killed;

        protected override void OnStart()
        {
            _m5 = MarketData.GetBars(TimeFrame.Minute5, SymbolName);
            _m5.BarOpened += OnM5BarOpened;
            _london = FindLondon();
            _peakEquity = Account.Equity;
            Timer.Start(TimeSpan.FromSeconds(20));
            Print("AlphaBot started on {0}: range {1}-{2}h, entries until {3}h, exit {4}h London. Volume {5} units.",
                  SymbolName, RangeStartHour, RangeEndHour, EntryEndHour, ExitHour, TradeVolume());
        }

        private static TimeZoneInfo FindLondon()
        {
            foreach (var id in new[] { "Europe/London", "GMT Standard Time" })
            {
                try { return TimeZoneInfo.FindSystemTimeZoneById(id); } catch (Exception) { }
            }
            throw new InvalidOperationException("Europe/London time zone not found on this machine");
        }

        private DateTime ToLondon(DateTime utc)
        {
            return TimeZoneInfo.ConvertTimeFromUtc(DateTime.SpecifyKind(utc, DateTimeKind.Utc), _london);
        }

        private static double HourOf(DateTime t) { return t.Hour + t.Minute / 60.0; }

        private double TradeVolume()
        {
            var v = VolumeUnits <= 0 ? Symbol.VolumeInUnitsMin : VolumeUnits;
            return Symbol.NormalizeVolumeInUnits(Math.Max(v, Symbol.VolumeInUnitsMin), RoundingMode.Down);
        }

        private Position MyPosition()
        {
            return Positions.FirstOrDefault(p => p.Label == Label && p.SymbolName == SymbolName);
        }

        // Called at the open of every new M5 bar; the bar that just closed is _m5.Last(1).
        private void OnM5BarOpened(BarOpenedEventArgs args)
        {
            if (_killed) return;
            var closedIdx = _m5.Count - 2;
            if (closedIdx < 1) return;
            var lt = ToLondon(_m5.OpenTimes[closedIdx]);
            if (lt.Date != _day) { _day = lt.Date; _doneToday = false; }

            var h = HourOf(lt);
            if (_doneToday || h < RangeEndHour || h >= EntryEndHour) return;
            if (MyPosition() != null) return;                         // one position per symbol

            // --- overnight range from completed M5 bars of the same London day ---
            double hi = double.MinValue, lo = double.MaxValue; int n = 0;
            for (int i = closedIdx - 1; i >= 0; i--)
            {
                var t = ToLondon(_m5.OpenTimes[i]);
                if (t.Date != _day) break;
                var hh = HourOf(t);
                if (hh < RangeStartHour || hh >= RangeEndHour) continue;
                hi = Math.Max(hi, _m5.HighPrices[i]); lo = Math.Min(lo, _m5.LowPrices[i]); n++;
            }
            var need = (RangeEndHour - RangeStartHour) * 60.0 / SignalTfMinutes * 0.7;
            if (n < need) return;                                     // holiday / data gap -> no trade

            var close = _m5.ClosePrices[closedIdx];
            TradeType? side = close > hi ? TradeType.Buy : (close < lo ? TradeType.Sell : (TradeType?)null);
            if (side == null) return;
            _doneToday = true;                                        // only the FIRST break of the day is traded

            if (DailyLossHit()) { Print("Daily loss limit reached - signal skipped"); return; }
            var spreadPips = Symbol.Spread / Symbol.PipSize;
            if (spreadPips > MaxSpreadPips) { Print("Spread {0:F1} pips > max {1:F1} - signal skipped", spreadPips, MaxSpreadPips); return; }

            var rangePips = (hi - lo) / Symbol.PipSize;
            var slPips = Math.Round(Math.Min(Math.Max(SlRangeMult * rangePips, MinSlPips), MaxSlPips), 1);
            var tpPips = Math.Round(TpMult * slPips, 1);
            var res = ExecuteMarketOrder(side.Value, SymbolName, TradeVolume(), Label, slPips, tpPips);
            if (!res.IsSuccessful) Print("Order failed: {0}", res.Error);
            else Print("{0} {1} range {2:F1}p SL {3}p TP {4}p", side, SymbolName, rangePips, slPips, tpPips);
        }

        private bool DailyLossHit()
        {
            var today = Server.Time.Date;                             // UTC day (robot time zone is UTC)
            var closed = History.Where(t => t.Label == Label && t.ClosingTime.Date == today).Sum(t => t.NetProfit);
            var open = Positions.Where(p => p.Label == Label).Sum(p => p.NetProfit);
            return closed + open <= -DailyLossLimit;
        }

        protected override void OnTimer() { Manage(); }
        protected override void OnTick() { Manage(); }

        private void Manage()
        {
            if (_killed) return;
            // --- equity draw-down kill-switch (account level) ---
            _peakEquity = Math.Max(_peakEquity, Account.Equity);
            if (_peakEquity - Account.Equity >= MaxDrawdown)
            {
                _killed = true;
                foreach (var p in Positions.Where(p => p.Label == Label).ToArray()) ClosePosition(p);
                Print("KILL-SWITCH: draw-down {0:F2} >= {1:F2}. Bot stopped.", _peakEquity - Account.Equity, MaxDrawdown);
                Stop();
                return;
            }
            // --- time exit (16:00 London) and Friday-close safety ---
            var pos = MyPosition();
            if (pos == null) return;
            var lt = ToLondon(Server.Time);
            var opened = ToLondon(pos.EntryTime);
            if (HourOf(lt) >= ExitHour || lt.Date != opened.Date) ClosePosition(pos);
        }

        protected override void OnStop()
        {
            if (_m5 != null) _m5.BarOpened -= OnM5BarOpened;
        }
    }
}
