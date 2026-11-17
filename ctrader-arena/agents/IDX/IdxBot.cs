// IdxBot - "IndexDipBuy" (arena v2, agent IDX)
// -----------------------------------------------------------------------------------------------
// Buys a US equity-index CFD after a short-term washout and exits one session later.
// Exactly the logic of agents/IDX/strategy.py:
//   * Attach to an H1 chart of "US SP 500" or "US Small Cap 2000" (one instance per symbol).
//   * A "session" ends with the H1 bar that OPENS at SignalHourNY (default 14:00 New York, DST-aware);
//     session close = close of that bar (price at 15:00 NY, one hour before the cash close).
//   * Signal (evaluated once, when that bar has closed): session close <= lowest of the last N (=7) session
//     closes (including today) -> BUY at market.
//   * SL = SlAtr (3.0) x ATR14(sessions), TP = TpAtr (0.75) x ATR14, time exit at the close of the
//     HoldBars-th (22nd) H1 bar after the fill bar (= next session's 15:00 NY close). Long only.
//     ATR14 = simple mean of the last 14 session true ranges (session high/low vs previous session close).
//   * Volume = broker minimum (Symbol.VolumeInUnitsMin, 0.1 unit) unless risk-% sizing is enabled.
// Safety (none of these triggered in the 2024-05..2026-11 backtest, so they do not change the tested logic):
//   hard SL+TP on every order, spread filter, one position per symbol per label, duplicate-order guard,
//   daily loss limit, equity drawdown kill-switch, consecutive-loss pause, planned-risk cap.
// All times are handled in UTC (TimeZone = UTC); New York time is computed with the US DST rule.
// -----------------------------------------------------------------------------------------------
using System;
using System.Collections.Generic;
using System.Linq;
using cAlgo.API;
using cAlgo.API.Internals;

namespace cAlgo.Robots
{
    [Robot(TimeZone = TimeZones.UTC, AccessRights = AccessRights.None)]
    public class IdxBot : Robot
    {
        // ---- strategy -------------------------------------------------------------------------
        [Parameter("Lookback sessions N", Group = "Strategy", DefaultValue = 7, MinValue = 3, MaxValue = 20)]
        public int LookbackN { get; set; }

        [Parameter("ATR period (sessions)", Group = "Strategy", DefaultValue = 14, MinValue = 5, MaxValue = 50)]
        public int AtrPeriod { get; set; }

        [Parameter("Stop loss (x ATR)", Group = "Strategy", DefaultValue = 3.0, MinValue = 1.0, MaxValue = 6.0, Step = 0.25)]
        public double SlAtr { get; set; }

        [Parameter("Take profit (x ATR, 0 = none)", Group = "Strategy", DefaultValue = 0.75, MinValue = 0.0, MaxValue = 3.0, Step = 0.25)]
        public double TpAtr { get; set; }

        [Parameter("Time exit after H1 bars", Group = "Strategy", DefaultValue = 22, MinValue = 1, MaxValue = 200)]
        public int HoldBars { get; set; }

        [Parameter("Signal bar open hour (New York)", Group = "Strategy", DefaultValue = 14, MinValue = 0, MaxValue = 23)]
        public int SignalHourNY { get; set; }

        [Parameter("Min H1 bars per session", Group = "Strategy", DefaultValue = 10, MinValue = 1, MaxValue = 24)]
        public int MinBarsPerSession { get; set; }

        // ---- sizing ---------------------------------------------------------------------------
        [Parameter("Use risk-% sizing", Group = "Sizing", DefaultValue = false)]
        public bool UseRiskSizing { get; set; }

        [Parameter("Risk per trade (% balance)", Group = "Sizing", DefaultValue = 2.0, MinValue = 0.1, MaxValue = 10.0)]
        public double RiskPercent { get; set; }

        [Parameter("Max volume (units)", Group = "Sizing", DefaultValue = 1.0, MinValue = 0.01)]
        public double MaxVolumeUnits { get; set; }

        [Parameter("Skip if planned risk > % balance", Group = "Sizing", DefaultValue = 12.0, MinValue = 0.5, MaxValue = 50.0)]
        public double MaxRiskCapPercent { get; set; }

        // ---- protection -----------------------------------------------------------------------
        [Parameter("Max spread (price units)", Group = "Protection", DefaultValue = 1.0, MinValue = 0.0)]
        public double MaxSpread { get; set; }

        [Parameter("Daily loss limit (% balance)", Group = "Protection", DefaultValue = 8.0, MinValue = 0.5, MaxValue = 50.0)]
        public double DailyLossLimitPercent { get; set; }

        [Parameter("Equity kill-switch DD (% of peak)", Group = "Protection", DefaultValue = 25.0, MinValue = 2.0, MaxValue = 90.0)]
        public double MaxEquityDrawdownPercent { get; set; }

        [Parameter("Pause after consecutive losses", Group = "Protection", DefaultValue = 7, MinValue = 1, MaxValue = 50)]
        public int MaxConsecutiveLosses { get; set; }

        [Parameter("Pause length (sessions)", Group = "Protection", DefaultValue = 5, MinValue = 1, MaxValue = 60)]
        public int PauseSessions { get; set; }

        [Parameter("Label", Group = "Protection", DefaultValue = "IDX-DipBuy")]
        public string LabelBase { get; set; }

        // ---- state ----------------------------------------------------------------------------
        private string _label;
        private double _peakEquity;
        private bool _killed;
        private bool _orderInFlight;
        private int _consecLosses;
        private DateTime _pauseUntilUtc = DateTime.MinValue;
        private DateTime _lastSignalBarTime = DateTime.MinValue;
        private DateTime _dayStartUtc = DateTime.MinValue;
        private double _dayStartBalance;

        private class Session
        {
            public DateTime Key;
            public double High, Low, Close;
            public int LastIndex, LastHourNY, Count;
        }

        protected override void OnStart()
        {
            _label = LabelBase + "-" + SymbolName;
            _peakEquity = Account.Equity;
            _dayStartUtc = Server.Time.Date;
            _dayStartBalance = Account.Balance;

            if (TimeFrame != TimeFrame.Hour)
                Print("WARNING: IdxBot was designed and tested on H1 bars; current timeframe = {0}.", TimeFrame);

            // make sure enough history for N + ATR sessions (~23 bars per session)
            int needBars = (LookbackN + AtrPeriod + 5) * 24;
            int guard = 0;
            while (Bars.Count < needBars && guard++ < 20)
            {
                int loaded = Bars.LoadMoreHistory();
                if (loaded <= 0) break;
            }

            Positions.Closed += OnPositionClosed;
            Print("IdxBot started on {0} {1}. Label={2}, bars={3}, volume min={4} units, N={5}, SL={6}xATR, TP={7}xATR, hold={8} bars, signal hour NY={9}",
                  SymbolName, TimeFrame, _label, Bars.Count, Symbol.VolumeInUnitsMin, LookbackN, SlAtr, TpAtr, HoldBars, SignalHourNY);
        }

        protected override void OnStop()
        {
            Positions.Closed -= OnPositionClosed;
            Print("IdxBot stopped. Open positions with label {0}: {1}", _label, Positions.FindAll(_label, SymbolName).Length);
        }

        protected override void OnTick()
        {
            CheckEquityKillSwitch();
        }

        protected override void OnBar()
        {
            // OnBar fires when a new bar opens; Bars.Last(1) is the bar that just closed.
            RollDay();
            CheckEquityKillSwitch();
            ManageTimeExit();
            if (_killed) return;

            int closedIdx = Bars.Count - 2;
            if (closedIdx < 1) return;
            DateTime closedOpenUtc = Bars.OpenTimes[closedIdx];
            if (ToNewYork(closedOpenUtc).Hour != SignalHourNY) return;
            if (closedOpenUtc == _lastSignalBarTime) return;          // duplicate guard (one decision per bar)
            _lastSignalBarTime = closedOpenUtc;

            List<Session> ses = BuildSessions(closedIdx);
            if (ses.Count < Math.Max(LookbackN, AtrPeriod + 1) + 1)
            {
                Print("Not enough complete sessions ({0}) - no decision.", ses.Count);
                return;
            }
            Session today = ses[ses.Count - 1];
            if (today.LastIndex != closedIdx) return;                 // the closed bar must end a valid session

            double atr = SessionAtr(ses);
            double lowest = double.MaxValue;
            for (int k = ses.Count - LookbackN; k < ses.Count; k++)
                lowest = Math.Min(lowest, ses[k].Close);
            bool signal = today.Close <= lowest && atr > 0;
            Print("Session {0:yyyy-MM-dd} close={1} lowest{2}={3} ATR={4:F2} -> {5}", today.Key, today.Close, LookbackN, lowest, atr,
                  signal ? "SIGNAL" : "no signal");
            if (!signal) return;

            TryEnter(atr);
        }

        // ------------------------------------------------------------------------------------
        private void TryEnter(double atr)
        {
            if (_orderInFlight) { Print("Order already in flight - skip."); return; }
            if (Positions.FindAll(_label, SymbolName).Length > 0) { Print("Position already open for {0} - skip.", _label); return; }
            if (Server.Time < _pauseUntilUtc) { Print("Paused after {0} consecutive losses until {1:u} - skip.", MaxConsecutiveLosses, _pauseUntilUtc); return; }
            if (DailyLossHit()) { Print("Daily loss limit reached - skip."); return; }

            double spread = Symbol.Ask - Symbol.Bid;
            if (MaxSpread > 0 && spread > MaxSpread) { Print("Spread {0} > max {1} - skip.", spread, MaxSpread); return; }

            double slDist = SlAtr * atr;
            double tpDist = TpAtr * atr;
            double valuePerUnitPerPrice = Symbol.TickValue / Symbol.TickSize;   // account currency per 1 unit per 1.0 price
            double volume = Symbol.VolumeInUnitsMin;
            if (UseRiskSizing)
            {
                double riskMoney = Account.Balance * RiskPercent / 100.0;
                double raw = riskMoney / (slDist * valuePerUnitPerPrice);
                volume = Math.Min(raw, MaxVolumeUnits);
                volume = Symbol.NormalizeVolumeInUnits(volume, RoundingMode.Down);
                if (volume < Symbol.VolumeInUnitsMin) volume = Symbol.VolumeInUnitsMin;
            }
            double plannedRisk = slDist * valuePerUnitPerPrice * volume;
            if (plannedRisk > Account.Balance * MaxRiskCapPercent / 100.0)
            {
                Print("Planned risk {0:F2} > cap {1}% of balance {2:F2} - skip.", plannedRisk, MaxRiskCapPercent, Account.Balance);
                return;
            }

            double slPips = Math.Round(slDist / Symbol.PipSize, 1);
            double? tpPips = tpDist > 0 ? Math.Round(tpDist / Symbol.PipSize, 1) : (double?)null;
            _orderInFlight = true;
            TradeResult res = ExecuteMarketOrder(TradeType.Buy, SymbolName, volume, _label, slPips, tpPips, "IndexDipBuy");
            _orderInFlight = false;
            if (!res.IsSuccessful || res.Position == null)
            {
                Print("ORDER FAILED: {0}", res.Error);
                return;
            }
            Position p = res.Position;
            if (p.StopLoss == null)
            {
                Print("Position {0} has no stop loss attached - closing for safety.", p.Id);
                ClosePosition(p);
                return;
            }
            Print("BUY {0} units @ {1} SL={2} TP={3} (ATR={4:F2}, planned risk {5:F2})", volume, p.EntryPrice, p.StopLoss, p.TakeProfit, atr, plannedRisk);
        }

        private void ManageTimeExit()
        {
            int cur = Bars.Count - 1;   // index of the bar that just opened
            foreach (Position p in Positions.FindAll(_label, SymbolName))
            {
                int entryIdx = Bars.OpenTimes.GetIndexByTime(p.EntryTime);
                if (entryIdx < 0) continue;
                // close at the close of the HoldBars-th bar after the fill bar == open of bar entryIdx + HoldBars + 1
                if (cur - entryIdx >= HoldBars + 1)
                {
                    TradeResult r = ClosePosition(p);
                    if (r.IsSuccessful) Print("Time exit position {0} after {1} bars, net {2:F2}", p.Id, cur - entryIdx - 1, p.NetProfit);
                    else Print("Time exit FAILED for {0}: {1}", p.Id, r.Error);
                }
            }
        }

        private void OnPositionClosed(PositionClosedEventArgs args)
        {
            Position p = args.Position;
            if (p.Label != _label || p.SymbolName != SymbolName) return;
            if (p.NetProfit < 0) _consecLosses++; else _consecLosses = 0;
            Print("Closed {0}: net {1:F2} ({2}); consecutive losses = {3}", p.Id, p.NetProfit, args.Reason, _consecLosses);
            if (_consecLosses >= MaxConsecutiveLosses)
            {
                _pauseUntilUtc = Server.Time.AddDays(PauseSessions * 7.0 / 5.0);
                _consecLosses = 0;
                Print("Consecutive-loss limit hit: pausing new entries until {0:u}", _pauseUntilUtc);
            }
        }

        private void RollDay()
        {
            if (Server.Time.Date != _dayStartUtc)
            {
                _dayStartUtc = Server.Time.Date;
                _dayStartBalance = Account.Balance;
            }
        }

        private bool DailyLossHit()
        {
            double floating = Positions.Where(x => x.Label != null && x.Label.StartsWith(LabelBase)).Sum(x => x.NetProfit);
            double dayPnl = Account.Balance - _dayStartBalance + floating;
            return dayPnl <= -_dayStartBalance * DailyLossLimitPercent / 100.0;
        }

        private void CheckEquityKillSwitch()
        {
            if (_killed) return;
            if (Account.Equity > _peakEquity) _peakEquity = Account.Equity;
            if (Account.Equity < _peakEquity * (1.0 - MaxEquityDrawdownPercent / 100.0))
            {
                _killed = true;
                Print("EQUITY KILL-SWITCH: equity {0:F2} < {1}% below peak {2:F2}. Closing positions and stopping.", Account.Equity, MaxEquityDrawdownPercent, _peakEquity);
                foreach (Position p in Positions.FindAll(_label, SymbolName))
                {
                    TradeResult r = ClosePosition(p);
                    if (!r.IsSuccessful) Print("Kill-switch close FAILED for {0}: {1}", p.Id, r.Error);
                }
                Stop();
            }
        }

        // ---- sessions / indicators ------------------------------------------------------------
        private List<Session> BuildSessions(int lastIdx)
        {
            // session key = New-York date of (bar time + (24 - (SignalHourNY + 1)) hours): the session ending with
            // the SignalHourNY bar starts with the bar opening at SignalHourNY+1 NY on the previous day.
            int need = (LookbackN + AtrPeriod + 5) * 24;
            int start = Math.Max(0, lastIdx - need);
            var list = new List<Session>();
            Session cur = null;
            for (int i = start; i <= lastIdx; i++)
            {
                DateTime ny = ToNewYork(Bars.OpenTimes[i]);
                DateTime key = ny.AddHours(24 - (SignalHourNY + 1)).Date;
                if (cur == null || key != cur.Key)
                {
                    if (cur != null) list.Add(cur);
                    cur = new Session { Key = key, High = Bars.HighPrices[i], Low = Bars.LowPrices[i], Close = Bars.ClosePrices[i], LastIndex = i, LastHourNY = ny.Hour, Count = 1 };
                }
                else
                {
                    cur.High = Math.Max(cur.High, Bars.HighPrices[i]);
                    cur.Low = Math.Min(cur.Low, Bars.LowPrices[i]);
                    cur.Close = Bars.ClosePrices[i];
                    cur.LastIndex = i;
                    cur.LastHourNY = ny.Hour;
                    cur.Count++;
                }
            }
            if (cur != null) list.Add(cur);
            if (list.Count > 0) list.RemoveAt(0);   // first session may be truncated by the history window
            return list.Where(s => s.Count >= MinBarsPerSession && s.LastHourNY == SignalHourNY).ToList();
        }

        private double SessionAtr(List<Session> s)
        {
            int n = s.Count;
            double sum = 0;
            for (int k = n - AtrPeriod; k < n; k++)
            {
                double pc = s[k - 1].Close;
                double tr = Math.Max(s[k].High - s[k].Low, Math.Max(Math.Abs(s[k].High - pc), Math.Abs(s[k].Low - pc)));
                sum += tr;
            }
            return sum / AtrPeriod;
        }

        // US Eastern time from UTC (rule since 2007: DST from 2nd Sunday of March 02:00 to 1st Sunday of November 02:00)
        private static DateTime ToNewYork(DateTime utc)
        {
            int y = utc.Year;
            DateTime mar1 = new DateTime(y, 3, 1);
            DateTime dstStart = mar1.AddDays(((7 - (int)mar1.DayOfWeek) % 7) + 7).AddHours(7);   // 02:00 EST = 07:00 UTC
            DateTime nov1 = new DateTime(y, 11, 1);
            DateTime dstEnd = nov1.AddDays((7 - (int)nov1.DayOfWeek) % 7).AddHours(6);            // 02:00 EDT = 06:00 UTC
            bool dst = utc >= dstStart && utc < dstEnd;
            return utc.AddHours(dst ? -4 : -5);
        }
    }
}
