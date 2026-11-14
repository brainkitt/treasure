// CharlieBot.cs - cTrader Automate cBot, port of agents/CHARLIE/strategy.py (round 2).
// USDJPY New-York-morning passive band fade. Attach to a USDJPY M15 chart.
// HONEST STATUS: no statistical edge (pre-sample PF 1.00 over 88 trades; forward PF 2.30 on only 26 trades with
// out-of-sample PF 0.48). Demo observation only. The Round 1 Range Break bot is kept in round1/.
//
// On every closed M15 bar that STARTED 08:00 <= t < 12:00 New York time (Mon-Fri):
//   z = (close - SMA20(close)) / stdev20(close)   (sample stdev), ATR = simple mean of true range over 14 bars
//   |z| > 2.0 -> fade with a LIMIT order 0.5 ATR beyond the close:
//       z < 0: BUY limit  at  bidClose - 0.5 ATR            (fills when the ASK trades down to it)
//       z > 0: SELL limit at  bidClose + spread + 0.5 ATR   (fills when the BID trades up to it)
//   order valid 30 minutes; SL = min(1.5 ATR, 22 pips); TP = max(|close - SMA20|, 0.3 ATR); time exit 90 min after fill.
// One position / one pending order per symbol, minimum volume by default, hard SL and TP on every order,
// spread filter, daily loss limit, max-drawdown kill switch. All prices in price units; converted with Symbol.PipSize.
using System;
using System.Linq;
using cAlgo.API;
using cAlgo.API.Internals;

namespace cAlgo.Robots
{
    [Robot(TimeZone = TimeZones.UTC, AccessRights = AccessRights.None)]
    public class CharlieBot : Robot
    {
        [Parameter("Band period", DefaultValue = 20, MinValue = 5)] public int BandPeriod { get; set; }
        [Parameter("ATR period", DefaultValue = 14, MinValue = 2)] public int AtrPeriod { get; set; }
        [Parameter("Z threshold", DefaultValue = 2.0, MinValue = 0.5)] public double ZThreshold { get; set; }
        [Parameter("Limit offset (ATR)", DefaultValue = 0.5, MinValue = 0)] public double OffsetAtr { get; set; }
        [Parameter("Stop (ATR)", DefaultValue = 1.5, MinValue = 0.1)] public double StopAtr { get; set; }
        [Parameter("Stop cap (pips)", DefaultValue = 22.0, MinValue = 1)] public double StopCapPips { get; set; }
        [Parameter("Min take-profit (ATR)", DefaultValue = 0.3, MinValue = 0)] public double TpMinAtr { get; set; }
        [Parameter("Order valid (minutes)", DefaultValue = 30, MinValue = 1)] public int ValidMinutes { get; set; }
        [Parameter("Max hold (minutes)", DefaultValue = 90, MinValue = 1)] public int HoldMinutes { get; set; }
        [Parameter("Session start (NY hour)", DefaultValue = 8.0)] public double StartHour { get; set; }
        [Parameter("Session end (NY hour)", DefaultValue = 12.0)] public double EndHour { get; set; }
        [Parameter("Volume in units (0 = symbol minimum)", DefaultValue = 0.0, MinValue = 0)] public double VolumeUnits { get; set; }
        [Parameter("Max spread (pips)", DefaultValue = 2.1, MinValue = 0)] public double MaxSpreadPips { get; set; }
        [Parameter("Daily loss limit (account ccy)", DefaultValue = 1.5, MinValue = 0)] public double DailyLossLimit { get; set; }
        [Parameter("Max drawdown kill switch (account ccy)", DefaultValue = 9.0, MinValue = 0)] public double MaxDrawdown { get; set; }
        [Parameter("Label", DefaultValue = "CHARLIE-FX")] public string Label { get; set; }

        private double _peakEquity;
        private bool _killed;
        private TimeZoneInfo _ny;

        protected override void OnStart()
        {
            _peakEquity = Account.Equity;
            try { _ny = TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time"); }
            catch (Exception) { _ny = TimeZoneInfo.FindSystemTimeZoneById("America/New_York"); }
            if (TimeFrame != TimeFrame.Minute15) Print("WARNING: researched on M15 bars; current timeframe is {0}", TimeFrame);
            Timer.Start(60);
        }

        private Position Pos() { return Positions.FirstOrDefault(p => p.Label == Label && p.SymbolName == SymbolName); }
        private PendingOrder Pend() { return PendingOrders.FirstOrDefault(o => o.Label == Label && o.SymbolName == SymbolName); }

        private void CheckKill()
        {
            if (_killed) return;
            _peakEquity = Math.Max(_peakEquity, Account.Equity);
            if (MaxDrawdown > 0 && _peakEquity - Account.Equity >= MaxDrawdown)
            {
                _killed = true;
                Print("KILL SWITCH: drawdown {0:F2} >= {1:F2}", _peakEquity - Account.Equity, MaxDrawdown);
                var o = Pend(); if (o != null) CancelPendingOrder(o);
                var p = Pos(); if (p != null) ClosePosition(p);
                Stop();
            }
        }

        private double TodayNet()
        {
            var today = Server.Time.Date;
            double closed = History.Where(h => h.Label == Label && h.SymbolName == SymbolName && h.ClosingTime.Date == today).Sum(h => h.NetProfit);
            var p = Pos();
            return closed + (p != null ? p.NetProfit : 0.0);
        }

        protected override void OnTick() { CheckKill(); }

        protected override void OnTimer()
        {
            // time exit: 90 minutes after the fill
            var p = Pos();
            if (p != null && (Server.Time - p.EntryTime).TotalMinutes >= HoldMinutes) ClosePosition(p);
        }

        protected override void OnBar()
        {
            CheckKill();
            if (_killed) return;
            int i = Bars.Count - 2;                                   // bar that has just closed
            if (i < Math.Max(BandPeriod, AtrPeriod) + 1) return;
            if (Pos() != null || Pend() != null) return;              // one position / order at a time
            if (DailyLossLimit > 0 && TodayNet() <= -DailyLossLimit) return;

            DateTime ny = TimeZoneInfo.ConvertTimeFromUtc(DateTime.SpecifyKind(Bars.OpenTimes[i], DateTimeKind.Utc), _ny);
            double hour = ny.Hour + ny.Minute / 60.0;
            if (ny.DayOfWeek == DayOfWeek.Saturday || ny.DayOfWeek == DayOfWeek.Sunday) return;
            if (hour < StartHour || hour >= EndHour) return;

            double sum = 0, sum2 = 0;
            for (int j = i - BandPeriod + 1; j <= i; j++) { double x = Bars.ClosePrices[j]; sum += x; sum2 += x * x; }
            double mean = sum / BandPeriod;
            double sd = Math.Sqrt(Math.Max(0.0, (sum2 - BandPeriod * mean * mean) / (BandPeriod - 1)));   // sample stdev (pandas default)
            if (sd <= 0) return;
            double atr = 0;
            for (int j = i - AtrPeriod + 1; j <= i; j++)
            {
                double pc = Bars.ClosePrices[j - 1];
                atr += Math.Max(Bars.HighPrices[j] - Bars.LowPrices[j], Math.Max(Math.Abs(Bars.HighPrices[j] - pc), Math.Abs(Bars.LowPrices[j] - pc)));
            }
            atr /= AtrPeriod;
            double c = Bars.ClosePrices[i];
            double z = (c - mean) / sd;
            if (Math.Abs(z) <= ZThreshold) return;
            if (Symbol.Spread > MaxSpreadPips * Symbol.PipSize) { Print("Signal skipped: spread {0}", Symbol.Spread); return; }

            double vol = VolumeUnits > 0 ? Symbol.NormalizeVolumeInUnits(VolumeUnits, RoundingMode.Down) : Symbol.VolumeInUnitsMin;
            if (vol < Symbol.VolumeInUnitsMin) vol = Symbol.VolumeInUnitsMin;
            double slPips = Math.Min(StopAtr * atr / Symbol.PipSize, StopCapPips);
            double tpPips = Math.Max(Math.Abs(c - mean), TpMinAtr * atr) / Symbol.PipSize;
            DateTime expiry = Server.Time.AddMinutes(ValidMinutes);
            TradeResult res;
            if (z < 0)
                res = PlaceLimitOrder(TradeType.Buy, SymbolName, vol, Math.Round(c - OffsetAtr * atr, Symbol.Digits), Label, slPips, tpPips, expiry);
            else
                res = PlaceLimitOrder(TradeType.Sell, SymbolName, vol, Math.Round(c + Symbol.Spread + OffsetAtr * atr, Symbol.Digits), Label, slPips, tpPips, expiry);
            if (!res.IsSuccessful) Print("Order failed: {0}", res.Error);
        }
    }
}
