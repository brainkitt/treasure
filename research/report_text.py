"""Supervisor's editorial text for the final report (imported by build_report.py)."""
import html
E = html.escape

SUMMARY = """
<div class="panel verdict" style="margin-top:16px">
<h3 style="margin-top:0">Verdict</h3>
<ul class="tight">
<li><b>Overall winner: IDX "IndexDipBuy" (US indices), score 72.4/100.</b> It has the most trades, the strongest t-statistic (3.25), the best out-of-sample profit factor (2.19), and passed every gate. The same frozen rules also worked on US Tech 100, which was never used to build it.</li>
<li><b>Runner-up: CFX "Crypto Momentum Burst" (ETHUSD H1), score 66.0/100.</b> It also passes every gate, needs the smallest account of the two ($300), and never pays swap. Its weakness is that profits come in bursts from a handful of large trades.</li>
<li><b>VOL (Deriv synthetics): no bot is recommended.</b> {vol_line}</li>
<li><b>$30 is not achievable responsibly with any edge found.</b> Every strategy that fits a $30 account (FX at 0.01 lot, synthetics at minimum volume) lost money after costs on multi-year data. The real edges need wider stops than a $30 account can absorb at the broker's minimum volume. The smallest responsible accounts are <b>$300 (CFX)</b> and <b>$700 (IDX)</b>, or <b>$250</b> for the IDX small-cap-only variant.</li>
<li>Both qualified bots run at the broker's minimum volume. Dollar drawdowns stay the same however big the account is, so a larger account only lowers the percentage risk. Running both together diversifies across markets: $1,000–$1,700 covers both comfortably.</li>
<li>Nothing here is guaranteed. Expect forward profit factors of about 1.3–1.5, below the backtests, and run each bot on the demo account for 2–6 months before using real money.</li>
</ul></div>
<div class="grid2" style="margin-top:14px">
<div class="panel"><h4 style="margin-top:0">Best timeframe per bot</h4><ul class="tight">
<li><b>IDX:</b> H1 chart, one decision per day at the H1 bar opening 14:00 New York (closes 15:00 NY). 12:00 NY was weaker (PF 1.51); M15 added nothing.</li>
<li><b>CFX:</b> H1 chart. On H2/H4 the effect is gone (PF 0.87), because the follow-through lasts about 3 hours.</li>
<li><b>VOL:</b> M5 was the only timeframe with a gross edge, and the spread erased it.</li></ul></div>
<div class="panel"><h4 style="margin-top:0">Minimum account balance</h4>
<div class="tbl" style="margin:0"><table><tr><th>Bot</th><th class="n">Technical min.</th><th class="n">Recommended min.</th><th class="n">Operating</th></tr>
{bal_rows}</table></div>
<p class="small muted" style="margin:6px 0 0">Technical minimum = 99th-percentile Monte Carlo drawdown + margin, i.e. survival only. Recommended = the largest of: Monte Carlo 95% drawdown ≤ 25% of balance, worst trade ≤ 3% of balance, margin ≤ 50%. Operating = 1.5 × recommended.</p></div>
</div>
"""

VOL_LINE = "Drift Switch indices have a real momentum effect before costs, but Deriv's spread widens exactly when they trend and absorbs it (official PF 0.65). Volatility 75 and the other synthetics behaved like fair games."

METHOD = """
<h2 id="method">How the competition was run</h2>
<div class="grid2">
<div class="panel"><h4 style="margin-top:0">Setup</h4><ul class="tight">
<li>Three independent agents each owned one market. They could read but not change each other's work, and could not change the scoring code.</li>
<li>Data came from your Deriv cTrader demo account through MCP: H1 history back to 2023–2024, plus M15/M5/M1 where needed. Your own closed-trade history (Oct–Nov 2026) was analysed as well.</li>
<li>One scoring engine was used for everyone. It runs on BID bars and is deliberately pessimistic: if the stop and target fall in the same bar, it counts the stop; stops slip; spike instruments fill at the bar extreme.</li>
<li>Costs charged: the widest live spread sampled, commission (0 on this account, verified from 150+ deals), swap per night held (a conservative bound where Deriv does not publish rates), and slippage.</li>
<li>Broker minimum volumes were confirmed with limit-order probes far from market. Each probe was rejected or cancelled immediately, and no position was ever opened. Your live XAUUSD "G2" position was not touched.</li>
</ul></div>
<div class="panel"><h4 style="margin-top:0">Validation (15 gates, all must pass)</h4><ul class="tight">
<li>Profit factor ≥ 1.30 on the full sample, and ≥ 1.20 on both the first 70% (fitting) and the last 30% (unseen).</li>
<li>Profit factor ≥ 1.10 with spread × 1.5 plus extra slippage.</li>
<li>≥ 100 trades, ≥ 30 of them out-of-sample. At least 4 of 5 equal time folds profitable.</li>
<li>Expectancy t-statistic ≥ 2.0.</li>
<li>Max drawdown ≤ 25% of the start balance; 95th-percentile Monte Carlo drawdown (5,000 reshuffles) ≤ 35%.</li>
<li>Worst trade ≤ 5% of the start balance.</li>
<li>No look-ahead: signals recomputed on truncated history must match.</li>
<li>Minimum lot respected; swap known for overnight holds; margin ≤ 50% of balance.</li>
<li>On top of the gates, each agent ran an anchored walk-forward that re-fitted parameters fold by fold, reported neighbouring-parameter results, counted every parameter set tried, and tried to disprove its own best idea.</li>
</ul></div></div>
<div class="panel" style="margin-top:14px"><h4 style="margin-top:0">How each bot decides (logic flow)</h4>
<pre class="mermaid">
flowchart LR
  subgraph IDX["IDX · US SP 500 / US Small Cap 2000 · H1"]
    A1["H1 bar opening 14:00 NY closes"] --> A2{"Close is lowest of last 7 session closes?"}
    A2 -- no --> A0["wait for next session"]
    A2 -- yes --> A3{"Spread ≤ max, no open position, risk caps OK?"}
    A3 -- yes --> A4["BUY 0.1 unit · SL 3×ATR · TP 0.75×ATR"]
    A4 --> A5["Exit at TP / SL / next day 15:00 NY"]
  end
  subgraph CFX["CFX · ETHUSD · H1"]
    B1["H1 bar closes"] --> B2{"Body larger than 2.5 × ATR24?"}
    B2 -- no --> B0["wait"]
    B2 -- yes --> B3{"Next 3 hours avoid 20:00–22:59 UTC?"}
    B3 -- yes --> B4["Enter in candle direction · 0.1 ETH · SL 2×ATR"]
    B4 --> B5["Exit at SL or after 3 hours"]
  end
</pre></div>
<div class="panel" style="margin-top:14px"><h4 style="margin-top:0">Risk and reward of a single trade</h4>
<div class="grid2">
<div><svg viewBox="0 0 420 200" class="chart" role="img" aria-label="IDX risk reward">
<rect x="60" y="20" width="300" height="38" style="fill:var(--good);opacity:.18"/><rect x="60" y="58" width="300" height="122" style="fill:var(--bad);opacity:.14"/>
<line x1="60" x2="360" y1="20" y2="20" class="lvl" style="stroke:var(--good);stroke-dasharray:5 3"/>
<line x1="60" x2="360" y1="58" y2="58" style="stroke:var(--ink)"/><line x1="60" x2="360" y1="180" y2="180" style="stroke:var(--bad);stroke-dasharray:5 3"/>
<text x="366" y="24" class="tick" style="fill:var(--good)">TP +0.75 ATR</text><text x="366" y="62" class="tick">entry</text><text x="366" y="184" class="tick" style="fill:var(--bad)">SL −3 ATR</text>
<text x="70" y="44" class="val">reached by 63% of trades</text><text x="70" y="124" class="val">full stop is rare: most losers exit on time</text>
<text x="10" y="196" class="tick">IDX: small target, wide stop, high win rate, time exit</text></svg></div>
<div><svg viewBox="0 0 420 200" class="chart" role="img" aria-label="CFX risk reward">
<rect x="60" y="20" width="300" height="80" style="fill:var(--good);opacity:.18"/><rect x="60" y="100" width="300" height="80" style="fill:var(--bad);opacity:.14"/>
<line x1="60" x2="360" y1="100" y2="100" style="stroke:var(--ink)"/><line x1="60" x2="360" y1="180" y2="180" style="stroke:var(--bad);stroke-dasharray:5 3"/>
<text x="366" y="104" class="tick">entry</text><text x="366" y="184" class="tick" style="fill:var(--bad)">SL −2 ATR</text><text x="366" y="24" class="tick" style="fill:var(--good)">no TP</text>
<text x="70" y="50" class="val">winners run for 3 h (no cap)</text><text x="70" y="140" class="val">losers mostly cut by the 3 h time exit</text>
<text x="10" y="196" class="tick">CFX: ~49% win rate, average win larger than average loss</text></svg></div>
</div></div>
"""


def deploy_section(ranked, data):
    return """
<h2 id="deploy">Deployment, settings and monitoring</h2>
<div class="grid2">
<div class="panel"><h4 style="margin-top:0">Step by step</h4><ol class="tight">
<li>cTrader → Automate → New cBot. Paste the source from the cBot code section below and click Build (it should report 0 errors).</li>
<li><b>IDX:</b> attach one instance to a <b>US SP 500 H1</b> chart and one to a <b>US Small Cap 2000 H1</b> chart, with the same parameters.</li>
<li><b>CFX:</b> attach one instance to an <b>ETHUSD H1</b> chart.</li>
<li>Keep the default parameters: they are the tested ones. Leave volume at the broker minimum and risk-% sizing off until the forward test confirms the edge.</li>
<li>Run on the <b>demo</b> account first: at least 8–12 weeks for IDX (about 1.7 trades a week) and at least 6 months for CFX (about 0.7 a week).</li>
<li>Before going live, check in cTrader's symbol info: the real swap rates for US SP 500 / US Small Cap 2000, the spread at 15:00 New York, and ETHUSD spreads at night and at weekends.</li>
<li>Go live at minimum volume only after the demo results are in line (see the stop rules). Scale up slowly, and only with live evidence.</li>
</ol></div>
<div class="panel"><h4 style="margin-top:0">When to stop a bot (pre-committed)</h4><ul class="tight">
<li>Built-in: an equity kill-switch at 25% below peak; a daily loss limit (IDX 8%, CFX 5%); a pause after a losing streak (IDX 7 losses, CFX 6 losses, then 48 h); a planned-risk cap per trade; a spread filter.</li>
<li><b>IDX:</b> review if drawdown passes $77 (the 95% Monte Carlo level) or if the US market enters a sustained bear trend (for example SP 500 below its 200-day average for a month). A long-only dip buyer is most exposed then.</li>
<li><b>CFX:</b> review if drawdown passes $46, or if PF over the last 40 trades drops below 1.0. Long flat stretches are normal for this bot.</li>
<li>Compare live fills with the backtest every month: spread paid, swap charged, slippage on stops.</li>
<li>Never add martingale, grid or averaging-down logic. None of the tested edges needs it.</li>
</ul></div></div>
<div class="note" style="margin-top:14px"><b>Known weaknesses.</b> IDX was tested only in a rising equity market (2024–2026), and its worst loss came on a crash day (3 Apr 2025, −$33.84). Its swap charge is an estimate: Deriv's index swap rates were not visible, so it uses a 7.5%/year bound. CFX depends on a few large trades (PF 1.40 without its best 5, 1.11 without its best 10). It lost money in the second half of 2023 and was flat from June to November 2026. Its night and weekend spreads were never measured. Both bots were researched with thousands of parameter trials (IDX about 6,300, CFX about 830). The walk-forward tests, neighbouring-parameter tests and out-of-sample replication reduce the chance of a curve-fit but cannot rule it out.</div>
"""
