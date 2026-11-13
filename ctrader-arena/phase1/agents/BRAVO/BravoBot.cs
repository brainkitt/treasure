// BravoBot — Drift Switch 30 regime follower (long only). Mirror of agents/BRAVO/strategy.py.
// Attach to: Drift Switch Index 30, M1 chart. One instance per symbol.
// READ NOTES.md FIRST: the live spread on Drift Switch indices widens to 6-9 px in the state this bot buys.
// With MaxSpreadPrice at its default the bot will skip most signals; that is the point of a forward test.
using System;
using cAlgo.API;
using cAlgo.API.Internals;

namespace cAlgo.Robots
{
    [Robot(TimeZone = TimeZones.UTC, AccessRights = AccessRights.None)]
    public class BravoBot : Robot
    {
        // --- regime model (fitted on in-sample M1 bid returns, basis points per minute) ---
        [Parameter("Calm state mean (bp/min)", DefaultValue = 0.56)] public double MuCalm { get; set; }
        [Parameter("Calm state sd (bp/min)", DefaultValue = 1.39)] public double SdCalm { get; set; }
        [Parameter("Calm state duration (min)", DefaultValue = 25.0)] public double DurCalm { get; set; }
        [Parameter("Volatile state mean (bp/min)", DefaultValue = -0.42)] public double MuVol { get; set; }
        [Parameter("Volatile state sd (bp/min)", DefaultValue = 3.42)] public double SdVol { get; set; }
        [Parameter("Volatile state duration (min)", DefaultValue = 33.5)] public double DurVol { get; set; }
        [Parameter("Entry threshold P(calm)", DefaultValue = 0.97)] public double EntryProb { get; set; }

        // --- orders / risk ---
        [Parameter("Stop loss (price units)", DefaultValue = 14.0)] public double StopLossPrice { get; set; }
        [Parameter("Trailing distance (price units)", DefaultValue = 6.0)] public double TrailPrice { get; set; }
        [Parameter("Safety take profit (price units)", DefaultValue = 200.0)] public double TakeProfitPrice { get; set; }
        [Parameter("Volume in units (0 = symbol minimum)", DefaultValue = 0.0)] public double VolumeUnits { get; set; }
        [Parameter("Max spread to enter (price units)", DefaultValue = 2.5)] public double MaxSpreadPrice { get; set; }
        [Parameter("Daily loss limit ($)", DefaultValue = 3.0)] public double DailyLossLimit { get; set; }
        [Parameter("Max drawdown kill-switch ($)", DefaultValue = 9.0)] public double MaxDrawdown { get; set; }
        [Parameter("Warm-up bars", DefaultValue = 300)] public int WarmupBars { get; set; }

        private const string Label = "BRAVO-DS30";
        private double _pCalm = 0.5;
        private double _peakEquity;
        private double _dayStartBalance;
        private DateTime _day;
        private bool _killed;

        protected override void OnStart()
        {
            if (TimeFrame != TimeFrame.Minute)
                Print("WARNING: BravoBot is designed for the M1 timeframe.");
            _peakEquity = Account.Equity;
            _dayStartBalance = Account.Balance;
            _day = Server.Time.Date;
            // replay history so the filter state matches the backtest (it forgets the start within ~100 bars)
            int n = Bars.Count - 1;                       // last index = forming bar
            int from = Math.Max(1, n - WarmupBars);
            for (int i = from; i < n; i++)
                UpdateFilter(Bars.ClosePrices[i - 1], Bars.ClosePrices[i]);
            Print("BravoBot started. P(calm) = {0:F3}, min volume = {1}", _pCalm, Symbol.VolumeInUnitsMin);
        }

        private void UpdateFilter(double prevClose, double close)
        {
            double r = Math.Log(close / prevClose) * 1e4;
            double stayCalm = 1.0 - 1.0 / DurCalm, stayVol = 1.0 - 1.0 / DurVol;
            double prior = _pCalm * stayCalm + (1.0 - _pCalm) * (1.0 - stayVol);
            double lc = Math.Exp(-0.5 * Math.Pow((r - MuCalm) / SdCalm, 2)) / SdCalm;
            double lv = Math.Exp(-0.5 * Math.Pow((r - MuVol) / SdVol, 2)) / SdVol;
            double a = prior * lc, b = (1.0 - prior) * lv;
            _pCalm = a / (a + b + 1e-300);
        }

        protected override void OnBar()
        {
            // called at the open of a new bar: Last(1) is the bar that just closed
            double close = Bars.ClosePrices.Last(1);
            UpdateFilter(Bars.ClosePrices.Last(2), close);

            if (Server.Time.Date != _day)
            {
                _day = Server.Time.Date;
                _dayStartBalance = Account.Balance;
            }
            _peakEquity = Math.Max(_peakEquity, Account.Equity);
            if (!_killed && _peakEquity - Account.Equity >= MaxDrawdown)
            {
                _killed = true;
                foreach (var p in Positions.FindAll(Label, SymbolName)) ClosePosition(p);
                Print("KILL-SWITCH: drawdown {0:F2} >= {1:F2}. Bot stops trading.", _peakEquity - Account.Equity, MaxDrawdown);
                Stop();
                return;
            }

            var pos = Positions.Find(Label, SymbolName, TradeType.Buy);
            if (pos != null)
            {
                // trailing stop ratchets on bar closes (same rule as the arena engine)
                double newSl = Math.Round(close - TrailPrice, Symbol.Digits);
                if (!pos.StopLoss.HasValue || newSl > pos.StopLoss.Value)
                    ModifyPosition(pos, newSl, pos.TakeProfit);
                return;                                    // one position per symbol
            }

            if (_killed) return;
            if (Account.Equity - _dayStartBalance <= -DailyLossLimit) return;   // daily loss limit
            if (_pCalm < EntryProb) return;
            double spread = Symbol.Ask - Symbol.Bid;
            if (spread > MaxSpreadPrice) return;           // spread filter
            if (StopLossPrice <= spread) return;

            double vol = VolumeUnits > 0 ? Symbol.NormalizeVolumeInUnits(VolumeUnits, RoundingMode.Down) : Symbol.VolumeInUnitsMin;
            if (vol < Symbol.VolumeInUnitsMin) vol = Symbol.VolumeInUnitsMin;
            double slPips = StopLossPrice / Symbol.PipSize;
            double tpPips = TakeProfitPrice / Symbol.PipSize;
            var res = ExecuteMarketOrder(TradeType.Buy, SymbolName, vol, Label, slPips, tpPips);
            if (!res.IsSuccessful)
                Print("Order failed: {0}", res.Error);
        }

        protected override void OnStop()
        {
            Print("BravoBot stopped. Equity {0:F2}", Account.Equity);
        }
    }
}
