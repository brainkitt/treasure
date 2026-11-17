// VolbBot.cs - cTrader Automate cBot, port of agents/VOLB/strategy.py
// "DSI30 long-only regime follower with entry-spread cap" (Deriv Drift Switch Index 30, M5 chart).
// STATUS: NOT QUALIFIED (negative expectancy at the widest observed DSI30 spread). Intended use: DEMO ONLY,
// to log the live spread at every signal (SPREADLOG lines) - the one missing piece of evidence.
//
// Logic (evaluated once per CLOSED bar of the chart timeframe, identical to strategy.py):
//   er    = (Close[1] - Close[1+N]) / sum_{k=1..N} |Close[k] - Close[k+1]|      (efficiency ratio of last N closed bars)
//   ATR   = mean(High - Low) of the last AtrPeriod closed bars (simple average of bar ranges, as in strategy.py)
//   BUY   if er >  Threshold   (long-only: the spread is paid once, at entry; exits fill on the bid)
//   stop  = StopAtr  * ATR  (hard stop attached to the order)
//   trail = TrailAtr * ATR  (stop ratcheted on bar closes only: long SL = max(SL, Close - trail))
//   exit  = after MaxBars closed bars (time exit)
//   No signal when the window contains a data gap (> 1.5 bar periods between consecutive bars).
// Safety: one position per symbol/label, minimum volume by default (optional risk-% sizing capped),
//   live spread gate (the edge only survives when the dynamic DSI spread is narrow), daily loss limit,
//   equity drawdown kill-switch, consecutive-loss pause, rollover no-entry window, TradeResult error handling.
using System;
using System.Linq;
using cAlgo.API;
using cAlgo.API.Internals;

namespace cAlgo.Robots
{
    [Robot(TimeZone = TimeZones.UTC, AccessRights = AccessRights.None)]
    public class VolbBot : Robot
    {
        // ---- signal ----
        [Parameter("ER lookback N (bars)", Group = "Signal", DefaultValue = 6, MinValue = 2, MaxValue = 50)]
        public int N { get; set; }

        [Parameter("ER threshold", Group = "Signal", DefaultValue = 0.8, MinValue = 0.1, MaxValue = 1.0, Step = 0.05)]
        public double Threshold { get; set; }

        [Parameter("ATR period (bars)", Group = "Signal", DefaultValue = 20, MinValue = 2, MaxValue = 200)]
        public int AtrPeriod { get; set; }

        // ---- exits ----
        [Parameter("Stop (x ATR)", Group = "Exits", DefaultValue = 2.5, MinValue = 0.5, MaxValue = 10)]
        public double StopAtr { get; set; }

        [Parameter("Trailing stop (x ATR, 0 = off)", Group = "Exits", DefaultValue = 1.5, MinValue = 0, MaxValue = 10)]
        public double TrailAtr { get; set; }

        [Parameter("Max bars in trade", Group = "Exits", DefaultValue = 24, MinValue = 1, MaxValue = 500)]
        public int MaxBars { get; set; }

        // ---- sizing ----
        [Parameter("Volume in units (0 = broker minimum)", Group = "Sizing", DefaultValue = 0.0, MinValue = 0)]
        public double VolumeUnits { get; set; }

        [Parameter("Risk % of balance per trade (0 = off)", Group = "Sizing", DefaultValue = 0.0, MinValue = 0, MaxValue = 5)]
        public double RiskPercent { get; set; }

        [Parameter("Max risk % per trade (cap)", Group = "Sizing", DefaultValue = 3.0, MinValue = 0.1, MaxValue = 10)]
        public double MaxRiskPercent { get; set; }

        // ---- filters / safety ----
        [Parameter("Max entry spread (price units)", Group = "Safety", DefaultValue = 4.0, MinValue = 0)]
        public double MaxSpread { get; set; }

        [Parameter("No entries from (UTC minute of day, signal bar open)", Group = "Safety", DefaultValue = 1130, MinValue = 0, MaxValue = 1439)]
        public int NoEntryFromMin { get; set; }

        [Parameter("No entries until (UTC minute of day)", Group = "Safety", DefaultValue = 1265, MinValue = 0, MaxValue = 1440)]
        public int NoEntryToMin { get; set; }

        [Parameter("Log spread every bar", Group = "Safety", DefaultValue = true)]
        public bool LogSpread { get; set; }

        [Parameter("Daily loss limit (account ccy, 0 = off)", Group = "Safety", DefaultValue = 1.5, MinValue = 0)]
        public double DailyLossLimit { get; set; }

        [Parameter("Equity drawdown kill-switch (% of peak, 0 = off)", Group = "Safety", DefaultValue = 25.0, MinValue = 0, MaxValue = 100)]
        public double MaxDrawdownPercent { get; set; }

        [Parameter("Pause after N consecutive losses (0 = off)", Group = "Safety", DefaultValue = 8, MinValue = 0)]
        public int MaxConsecutiveLosses { get; set; }

        [Parameter("Pause length (bars)", Group = "Safety", DefaultValue = 12, MinValue = 1)]
        public int PauseBars { get; set; }

        [Parameter("Label", Group = "Safety", DefaultValue = "VOLB-DSI30")]
        public string Label { get; set; }

        private double _peakEquity;
        private bool _killed;
        private DateTime _day;
        private double _dayStartBalance;
        private int _consecLosses;
        private int _pauseUntilBar = -1;
        private int _entryBar = -1;
        private bool _orderInFlight;

        protected override void OnStart()
        {
            _peakEquity = Account.Equity;
            _day = Server.Time.Date;
            _dayStartBalance = Account.Balance;
            Positions.Closed += OnPositionClosed;
            var open = MyPosition();
            if (open != null)
                _entryBar = Bars.Count - 1; // conservative: restart the time-exit clock on restart
            Print("VolbBot start {0} {1}: N={2} thr={3} atr={4} sl={5}xATR trail={6}xATR maxBars={7} long-only maxSpread={8} minVol={9}",
                  SymbolName, TimeFrame, N, Threshold, AtrPeriod, StopAtr, TrailAtr, MaxBars, MaxSpread,
                  Symbol.VolumeInUnitsMin);
        }

        protected override void OnStop()
        {
            Positions.Closed -= OnPositionClosed;
            Print("VolbBot stopped. Equity {0:F2}, peak {1:F2}", Account.Equity, _peakEquity);
        }

        protected override void OnTick()
        {
            // equity kill-switch is checked intrabar
            if (Account.Equity > _peakEquity) _peakEquity = Account.Equity;
            if (!_killed && MaxDrawdownPercent > 0 && _peakEquity > 0 &&
                (_peakEquity - Account.Equity) / _peakEquity * 100.0 >= MaxDrawdownPercent)
            {
                _killed = true;
                Print("KILL-SWITCH: equity drawdown {0:F1}% >= {1}%. Closing and stopping.",
                      (_peakEquity - Account.Equity) / _peakEquity * 100.0, MaxDrawdownPercent);
                CloseMine("kill-switch");
                Stop();
            }
        }

        protected override void OnBar()
        {
            if (_killed) return;
            RollDay();
            int last = Bars.Count - 2;          // index of the bar that just CLOSED (Bars.Last(1))
            if (last < Math.Max(N, AtrPeriod) + 2) return;

            var pos = MyPosition();
            double atr = Atr(last);
            if (LogSpread)
                Print("SPREADLOG {0:yyyy-MM-dd HH:mm} spread={1:F2} er={2:F3} atr={3:F3} pos={4}", Bars.OpenTimes[last],
                      Symbol.Spread, EfficiencyRatio(last), atr, pos != null ? "1" : "0");

            // ---- manage open position on bar close: time exit, then trailing stop ----
            if (pos != null)
            {
                if (_entryBar >= 0 && last - _entryBar >= MaxBars)   // engine: close at the close of the MaxBars-th bar after the fill bar
                {
                    Print("Time exit after {0} bars", last - _entryBar);
                    CheckResult(ClosePosition(pos), "close (time)");
                    return;
                }
                if (TrailAtr > 0 && atr > 0 && pos.StopLoss.HasValue && last > _entryBar)   // engine never ratchets on the fill bar's close
                {
                    double trail = TrailAtr * EntryAtr(pos, atr);
                    double close = Bars.ClosePrices[last];
                    if (pos.TradeType == TradeType.Buy)
                    {
                        double ns = Math.Round(close - trail, Symbol.Digits);
                        if (ns > pos.StopLoss.Value + Symbol.TickSize)
                            CheckResult(ModifyPosition(pos, ns, pos.TakeProfit, ProtectionType.Absolute), "trail long");
                    }
                    else
                    {
                        double ns = Math.Round(close + Symbol.Spread + trail, Symbol.Digits);
                        if (ns < pos.StopLoss.Value - Symbol.TickSize)
                            CheckResult(ModifyPosition(pos, ns, pos.TakeProfit, ProtectionType.Absolute), "trail short");
                    }
                }
                return; // one position at a time
            }

            // ---- entry filters ----
            if (_orderInFlight) return;
            if (last < _pauseUntilBar) return;
            if (DailyLossHit()) return;
            var t = Bars.OpenTimes[last];          // strategy.py tests the signal bar's open time
            if (InNoEntryWindow(t.Hour * 60 + t.Minute)) return;
            if (!WindowClean(last)) return;
            if (atr <= 0) return;

            double er = EfficiencyRatio(last);
            TradeType? side = null;
            if (er > Threshold) side = TradeType.Buy;
            if (side == null) return;

            if (Symbol.Spread > MaxSpread)
            {
                Print("Signal {0} er={1:F2} skipped: spread {2:F2} > {3}", side, er, Symbol.Spread, MaxSpread);
                return;
            }

            double stopDist = StopAtr * atr;
            double vol = Volume(stopDist);
            if (vol <= 0) { Print("Volume could not be determined - no trade"); return; }

            double slPips = stopDist / Symbol.PipSize;
            _orderInFlight = true;
            var res = ExecuteMarketOrder(side.Value, SymbolName, vol, Label, slPips, null,
                                         string.Format("er={0:F2};atr={1:F4}", er, atr));
            _orderInFlight = false;
            if (CheckResult(res, "open " + side))
            {
                _entryBar = last + 1;
                Print("OPEN {0} {1} units @ {2} SL {3} (er {4:F2}, ATR {5:F3}, spread {6:F2})", side, vol,
                      res.Position.EntryPrice, res.Position.StopLoss, er, atr, Symbol.Spread);
            }
        }

        // ---------- helpers ----------
        private Position MyPosition()
        {
            return Positions.FirstOrDefault(p => p.Label == Label && p.SymbolName == SymbolName);
        }

        private void CloseMine(string why)
        {
            foreach (var p in Positions.Where(p => p.Label == Label && p.SymbolName == SymbolName).ToList())
                CheckResult(ClosePosition(p), "close (" + why + ")");
        }

        private double Atr(int last)
        {
            double s = 0;
            for (int k = last - AtrPeriod + 1; k <= last; k++) s += Bars.HighPrices[k] - Bars.LowPrices[k];
            return s / AtrPeriod;
        }

        // ATR at entry is stored in the comment so that the trail distance matches strategy.py (fixed at entry)
        private double EntryAtr(Position p, double fallback)
        {
            try
            {
                var c = p.Comment ?? "";
                int i = c.IndexOf("atr=", StringComparison.Ordinal);
                if (i >= 0) return double.Parse(c.Substring(i + 4), System.Globalization.CultureInfo.InvariantCulture);
            }
            catch (Exception) { }
            return fallback;
        }

        private double EfficiencyRatio(int last)
        {
            double path = 0;
            for (int k = last - N + 1; k <= last; k++) path += Math.Abs(Bars.ClosePrices[k] - Bars.ClosePrices[k - 1]);
            double net = Bars.ClosePrices[last] - Bars.ClosePrices[last - N];
            return path > 0 ? net / path : 0;
        }

        private bool WindowClean(int last)
        {
            double barSec = (Bars.OpenTimes[last] - Bars.OpenTimes[last - 1]).TotalSeconds;
            double nominal = TimeFrameSeconds();
            int w = Math.Max(N, AtrPeriod);
            for (int k = last - w + 1; k <= last; k++)
                if ((Bars.OpenTimes[k] - Bars.OpenTimes[k - 1]).TotalSeconds > 1.5 * nominal) return false;
            return barSec > 0;
        }

        private double TimeFrameSeconds()
        {
            if (TimeFrame == TimeFrame.Minute) return 60;
            if (TimeFrame == TimeFrame.Minute5) return 300;
            if (TimeFrame == TimeFrame.Minute15) return 900;
            if (TimeFrame == TimeFrame.Minute30) return 1800;
            if (TimeFrame == TimeFrame.Hour) return 3600;
            return 300;
        }

        private bool InNoEntryWindow(int minuteOfDay)
        {
            if (NoEntryFromMin == NoEntryToMin) return false;
            if (NoEntryFromMin < NoEntryToMin) return minuteOfDay >= NoEntryFromMin && minuteOfDay < NoEntryToMin;
            return minuteOfDay >= NoEntryFromMin || minuteOfDay < NoEntryToMin;
        }

        private double Volume(double stopDist)
        {
            double min = Symbol.VolumeInUnitsMin;
            double vol = VolumeUnits > 0 ? VolumeUnits : min;
            if (RiskPercent > 0 && stopDist > 0)
            {
                double riskCash = Account.Balance * RiskPercent / 100.0;
                double perUnit = stopDist / Symbol.TickSize * Symbol.TickValue; // account ccy lost per unit at the stop
                if (perUnit > 0) vol = riskCash / perUnit;
            }
            vol = Symbol.NormalizeVolumeInUnits(Math.Max(vol, min), RoundingMode.Down);
            if (vol < min) vol = min;
            // never exceed the max-risk cap; if even the minimum exceeds it, do not trade
            double capCash = Account.Balance * MaxRiskPercent / 100.0;
            double riskAtVol = stopDist / Symbol.TickSize * Symbol.TickValue * vol;
            while (riskAtVol > capCash && vol > min)
            {
                vol = Symbol.NormalizeVolumeInUnits(vol - Symbol.VolumeInUnitsStep, RoundingMode.Down);
                riskAtVol = stopDist / Symbol.TickSize * Symbol.TickValue * vol;
            }
            if (riskAtVol > capCash)
            {
                Print("Risk at minimum volume {0:F2} exceeds cap {1:F2} - skip", riskAtVol, capCash);
                return 0;
            }
            return vol;
        }

        private void RollDay()
        {
            if (Server.Time.Date != _day)
            {
                _day = Server.Time.Date;
                _dayStartBalance = Account.Balance;
            }
        }

        private bool DailyLossHit()
        {
            if (DailyLossLimit <= 0) return false;
            double lost = _dayStartBalance - Account.Equity;
            if (lost >= DailyLossLimit)
            {
                Print("Daily loss limit reached ({0:F2} >= {1}) - no new entries today", lost, DailyLossLimit);
                return true;
            }
            return false;
        }

        private void OnPositionClosed(PositionClosedEventArgs e)
        {
            var p = e.Position;
            if (p.Label != Label || p.SymbolName != SymbolName) return;
            _entryBar = -1;
            if (p.NetProfit < 0) _consecLosses++; else _consecLosses = 0;
            Print("CLOSED {0} net {1:F2} ({2}); consecutive losses {3}", p.TradeType, p.NetProfit, e.Reason, _consecLosses);
            if (MaxConsecutiveLosses > 0 && _consecLosses >= MaxConsecutiveLosses)
            {
                _pauseUntilBar = Bars.Count - 1 + PauseBars;
                _consecLosses = 0;
                Print("Pausing entries for {0} bars after {1} consecutive losses", PauseBars, MaxConsecutiveLosses);
            }
        }

        private bool CheckResult(TradeResult r, string what)
        {
            if (r == null) { Print("{0}: null result", what); return false; }
            if (!r.IsSuccessful) { Print("{0} FAILED: {1}", what, r.Error); return false; }
            return true;
        }
    }
}
