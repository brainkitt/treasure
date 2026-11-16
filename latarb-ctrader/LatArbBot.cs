// LatArbBot.cs - cTrader Automate cBot: BTC "lagging quote" strategy (the Polymarket idea moved to a CFD).
//
// Attach to the broker's BTCUSD chart (Deriv cTrader: symbol "BTCUSD"). Needs Full Access because it
// opens a WebSocket to OKX for the leading BTC price.
//
// HONEST STATUS (see REPORT in this folder): measured on 16 Nov 2026, Deriv's BTCUSD quote trails the
// exchanges by only 0-0.5 s and costs $18.42 to cross. In replay the strategy loses money unless your
// orders reach the broker faster than the broker's own feed lag, which a retail connection cannot do.
// The bot therefore starts in PAPER mode: it logs every signal, what it would have earned using the
// broker's real quotes, and the lag it observes. Only switch PaperMode off on a demo account, and only
// if the paper log on YOUR machine shows a positive average after costs.
//
// Logic
//   lead   = OKX BTC-USDT best bid/ask mid (bbo-tbt channel, tick by tick)
//   basis  = slow EWMA of (lead - broker mid), updated only when the lead has been still, so a fast
//            move is not absorbed into the basis
//   gap    = (lead - basis) - broker mid           (how far the broker quote is behind)
//   entry  : |gap| >= broker spread + MarginUsd, no open position, cooldown passed, limits OK
//            -> market order in the gap's direction at the minimum volume, with a protective stop
//   exit   : after HoldMs, or at the stop / take-profit
//   limits : one position at a time, MaxTradesPerDay, DailyLossLimit, MaxDrawdown kill switch,
//            MaxSpreadUsd filter, stale-feed filter
using System;
using System.Net.WebSockets;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using cAlgo.API;
using cAlgo.API.Internals;

namespace cAlgo.Robots
{
    [Robot(TimeZone = TimeZones.UTC, AccessRights = AccessRights.FullAccess)]
    public class LatArbBot : Robot
    {
        [Parameter("Paper mode (log only, no orders)", DefaultValue = true)]
        public bool PaperMode { get; set; }

        [Parameter("Extra edge over spread (USD)", DefaultValue = 5.0, MinValue = 0)]
        public double MarginUsd { get; set; }

        [Parameter("Hold time (ms)", DefaultValue = 3000, MinValue = 100)]
        public int HoldMs { get; set; }

        [Parameter("Protective stop (USD of price)", DefaultValue = 60.0, MinValue = 1)]
        public double StopUsd { get; set; }

        [Parameter("Take profit (USD of price, 0 = none)", DefaultValue = 0.0, MinValue = 0)]
        public double TakeProfitUsd { get; set; }

        [Parameter("Volume in units (0 = symbol minimum)", DefaultValue = 0.0, MinValue = 0)]
        public double VolumeUnits { get; set; }

        [Parameter("Max spread (USD)", DefaultValue = 25.0, MinValue = 0)]
        public double MaxSpreadUsd { get; set; }

        [Parameter("Cooldown between trades (ms)", DefaultValue = 2000, MinValue = 0)]
        public int CooldownMs { get; set; }

        [Parameter("Max trades per day", DefaultValue = 30, MinValue = 1)]
        public int MaxTradesPerDay { get; set; }

        [Parameter("Daily loss limit (account ccy)", DefaultValue = 1.5, MinValue = 0)]
        public double DailyLossLimit { get; set; }

        [Parameter("Max drawdown kill switch (account ccy)", DefaultValue = 4.5, MinValue = 0)]
        public double MaxDrawdown { get; set; }

        [Parameter("Lead feed stale after (ms)", DefaultValue = 1500, MinValue = 100)]
        public int StaleMs { get; set; }

        [Parameter("Basis EWMA weight", DefaultValue = 0.01, MinValue = 0.0001, MaxValue = 1)]
        public double BasisAlpha { get; set; }

        [Parameter("OKX instrument", DefaultValue = "BTC-USDT")]
        public string LeadInstrument { get; set; }

        [Parameter("Label", DefaultValue = "LATARB")]
        public string Label { get; set; }

        // lead feed state (written by the socket thread, read on the main thread)
        private readonly object _lock = new object();
        private double _leadMid;
        private DateTime _leadTimeUtc = DateTime.MinValue;
        private double _leadMidOneSecAgo;
        private DateTime _leadAnchorUtc = DateTime.MinValue;

        private double _basis = double.NaN;
        private DateTime _lastTradeUtc = DateTime.MinValue;
        private DateTime _dayUtc = DateTime.MinValue.Date;
        private int _tradesToday;
        private double _dayStartEquity, _peakEquity;
        private bool _killed;
        private CancellationTokenSource _cts;

        // paper bookkeeping
        private bool _paperOpen;
        private int _paperSide;
        private double _paperEntry;
        private DateTime _paperExitUtc;
        private int _paperTrades, _paperWins;
        private double _paperPnl;

        // live bookkeeping
        private DateTime _liveExitUtc = DateTime.MinValue;

        protected override void OnStart()
        {
            _dayStartEquity = _peakEquity = Account.Equity;
            _dayUtc = Server.Time.Date;
            _cts = new CancellationTokenSource();
            Task.Run(() => LeadLoop(_cts.Token));
            Timer.Start(TimeSpan.FromMilliseconds(50));
            Print("LatArbBot started on {0}. Mode: {1}. Min volume {2} units.", SymbolName, PaperMode ? "PAPER" : "LIVE", Symbol.VolumeInUnitsMin);
        }

        protected override void OnStop()
        {
            _cts?.Cancel();
            Print("Stopped. Paper trades {0}, wins {1}, paper P&L {2:F2} (at {3} units).", _paperTrades, _paperWins, _paperPnl, Volume());
        }

        private double Volume()
        {
            var v = VolumeUnits > 0 ? VolumeUnits : Symbol.VolumeInUnitsMin;
            return Symbol.NormalizeVolumeInUnits(Math.Max(v, Symbol.VolumeInUnitsMin));
        }

        // ---------- lead feed ----------
        private async Task LeadLoop(CancellationToken ct)
        {
            var sub = "{\"op\":\"subscribe\",\"args\":[{\"channel\":\"bbo-tbt\",\"instId\":\"" + LeadInstrument + "\"}]}";
            while (!ct.IsCancellationRequested)
            {
                try
                {
                    using (var ws = new ClientWebSocket())
                    {
                        ws.Options.KeepAliveInterval = TimeSpan.FromSeconds(15);
                        await ws.ConnectAsync(new Uri("wss://ws.okx.com:8443/ws/v5/public"), ct);
                        await ws.SendAsync(new ArraySegment<byte>(Encoding.UTF8.GetBytes(sub)), WebSocketMessageType.Text, true, ct);
                        var buf = new byte[16384];
                        var sb = new StringBuilder();
                        while (ws.State == WebSocketState.Open && !ct.IsCancellationRequested)
                        {
                            var r = await ws.ReceiveAsync(new ArraySegment<byte>(buf), ct);
                            if (r.MessageType == WebSocketMessageType.Close) break;
                            sb.Append(Encoding.UTF8.GetString(buf, 0, r.Count));
                            if (!r.EndOfMessage) continue;
                            var msg = sb.ToString(); sb.Clear();
                            double bid, ask;
                            if (TryFirstLevel(msg, "\"bids\":[[\"", out bid) && TryFirstLevel(msg, "\"asks\":[[\"", out ask))
                            {
                                var now = DateTime.UtcNow;
                                lock (_lock)
                                {
                                    _leadMid = (bid + ask) / 2;
                                    _leadTimeUtc = now;
                                    if ((now - _leadAnchorUtc).TotalMilliseconds >= 1000) { _leadMidOneSecAgo = _leadMid; _leadAnchorUtc = now; }
                                }
                                BeginInvokeOnMainThread(Evaluate);
                            }
                        }
                    }
                }
                catch (Exception e)
                {
                    if (!ct.IsCancellationRequested) Print("Lead feed error: {0}. Reconnecting.", e.Message);
                }
                try { await Task.Delay(1000, ct); } catch { }
            }
        }

        private static bool TryFirstLevel(string s, string key, out double v)
        {
            v = 0;
            var i = s.IndexOf(key, StringComparison.Ordinal);
            if (i < 0) return false;
            i += key.Length;
            var j = s.IndexOf('"', i);
            return j > i && double.TryParse(s.Substring(i, j - i), System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out v);
        }

        // ---------- strategy ----------
        protected override void OnTick() { Evaluate(); }

        protected override void OnTimer()
        {
            var now = Server.Time;
            if (_paperOpen && now >= _paperExitUtc) ClosePaper();
            if (!PaperMode && _liveExitUtc != DateTime.MinValue && now >= _liveExitUtc)
            {
                var p = Positions.Find(Label, SymbolName);
                if (p != null) ClosePosition(p);
                _liveExitUtc = DateTime.MinValue;
            }
        }

        private void Evaluate()
        {
            double lead, leadAgo; DateTime leadT;
            lock (_lock) { lead = _leadMid; leadAgo = _leadMidOneSecAgo; leadT = _leadTimeUtc; }
            if (lead <= 0) return;
            var nowUtc = DateTime.UtcNow;
            if ((nowUtc - leadT).TotalMilliseconds > StaleMs) return;

            var mid = (Symbol.Bid + Symbol.Ask) / 2;
            var spreadUsd = Symbol.Ask - Symbol.Bid;

            // basis learns only while the lead is still (moved < $3 in the last second)
            if (double.IsNaN(_basis)) _basis = lead - mid;
            else if (Math.Abs(lead - leadAgo) < 3) _basis += BasisAlpha * ((lead - mid) - _basis);

            var gap = (lead - _basis) - mid;
            RollDay();
            if (_killed || _paperOpen || Positions.Find(Label, SymbolName) != null) return;
            if (spreadUsd > MaxSpreadUsd) return;
            if ((Server.Time - _lastTradeUtc).TotalMilliseconds < CooldownMs) return;
            if (_tradesToday >= MaxTradesPerDay) return;
            if (Math.Abs(gap) < spreadUsd + MarginUsd) return;

            var side = gap > 0 ? TradeType.Buy : TradeType.Sell;
            _lastTradeUtc = Server.Time;
            _tradesToday++;
            if (PaperMode)
            {
                _paperOpen = true;
                _paperSide = side == TradeType.Buy ? 1 : -1;
                _paperEntry = side == TradeType.Buy ? Symbol.Ask : Symbol.Bid;
                _paperExitUtc = Server.Time.AddMilliseconds(HoldMs);
                Print("PAPER {0} at {1:F2} | lead gap {2:F2} vs spread {3:F2}", side, _paperEntry, gap, spreadUsd);
                return;
            }
            var slPips = StopUsd / Symbol.PipSize;
            double? tpPips = TakeProfitUsd > 0 ? TakeProfitUsd / Symbol.PipSize : (double?)null;
            var res = ExecuteMarketOrder(side, SymbolName, Volume(), Label, slPips, tpPips);
            if (res.IsSuccessful)
            {
                _liveExitUtc = Server.Time.AddMilliseconds(HoldMs);
                Print("LIVE {0} filled at {1:F2} | lead gap {2:F2} vs spread {3:F2}", side, res.Position.EntryPrice, gap, spreadUsd);
            }
            else Print("Order failed: {0}", res.Error);
        }

        private void ClosePaper()
        {
            var exit = _paperSide > 0 ? Symbol.Bid : Symbol.Ask;
            var pnl = _paperSide * (exit - _paperEntry) * Volume();
            _paperOpen = false;
            _paperTrades++;
            if (pnl > 0) _paperWins++;
            _paperPnl += pnl;
            Print("PAPER close at {0:F2}: {1:+0.00;-0.00} | trades {2}, win {3:F0}%, total {4:+0.00;-0.00}",
                exit, pnl, _paperTrades, 100.0 * _paperWins / _paperTrades, _paperPnl);
        }

        private void RollDay()
        {
            if (Server.Time.Date != _dayUtc)
            {
                _dayUtc = Server.Time.Date;
                _tradesToday = 0;
                _dayStartEquity = Account.Equity;
            }
            _peakEquity = Math.Max(_peakEquity, Account.Equity);
            if (!_killed && (_dayStartEquity - Account.Equity >= DailyLossLimit && DailyLossLimit > 0))
            {
                Print("Daily loss limit reached; no new trades until tomorrow (UTC).");
                _tradesToday = MaxTradesPerDay;
            }
            if (!_killed && MaxDrawdown > 0 && _peakEquity - Account.Equity >= MaxDrawdown)
            {
                _killed = true;
                Print("Max drawdown reached; bot stopped trading.");
            }
        }
    }
}
