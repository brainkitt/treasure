# Arena v2 — Round 3: Deriv synthetics deep search (AGENT_03 "VOL", split into two teams)

The account owner reviewed the final report. IDX (US indices dip-buy, score 72.4) and CFX (ETH momentum burst,
score 66.0) qualified. VOL (synthetics) did not: the owner wants AGENT_03 to keep searching the WHOLE Deriv
synthetic universe — volatility indices, Crash/Boom, Jump, Step, DEX, Range Break, everything — with a
preference for **M5-ish timeframes and a small account ($30 preferred)**, until a real, validated edge is found.

Read first: `BRIEF2.md` (rules, data access, deliverables — all still apply), `arena/evaluate2.py`, `arena/engine.py`,
`agents/VOL/NOTES.md` (rounds 1-2) and `agents/CHARLIE/NOTES.md` (round-0 spike families). Do NOT repeat a test those
notes already killed unless you change something material (longer history, different timeframe, different mechanism).

## Teams (work in parallel, do not edit each other's folders; you may read them)
| team | folder | instrument families |
|---|---|---|
| VOLA | `agents/VOLA/`, `submissions/VOLA/` | spike / jump families: Crash & Boom (all), Jump (all), DEX, Range Break, Snap, Volatility Crash/Boom, Crash Boom Flip, Skew Step, Trek, Exponential Growth, Ladder |
| VOLB | `agents/VOLB/`, `submissions/VOLB/` | continuous families: Volatility 10..250 (+ all (1s) versions), Step (all), Multi Step, VolSwitch, Drift Switch (DSI already tested — only revisit with a new mechanism) |

## THE SEALED HOLDOUT (most important new rule)
Earlier rounds searched thousands of parameter sets; the more you search, the more the visible out-of-sample is
contaminated. So synthetic data from **2026-09-15 onward is sealed**: `arena.ingest.load()` silently drops those bars
for every synthetic symbol (rule file `data/.holdout`). You research, fit, validate and run evaluate2 on data before
2026-09-15 only. **Never set ARENA_HOLDOUT_UNLOCK, never read the raw csv files around the loader, never edit
data/.holdout.** The supervisor will run your finalist ONCE on the sealed 2 months. Downloading new bars is fine
(they get sealed automatically). Your candidate must therefore be fully specified before the holdout test; you will
be told the holdout result and may then iterate, but every look at the holdout is counted.

## Qualification for this round
1. All 15 evaluate2 gates on pre-holdout data (`python -m arena.evaluate2 agents/<TEAM>/strategy.py --out submissions/<TEAM>`).
2. Supervisor's sealed-holdout check: PF >= 1.20 and net > 0 on the 2 holdout months with >= 30 holdout trades, worst
   trade and drawdown inside the same balance limits.
3. Economic/structural rationale: Deriv synthetics are RNG-driven. An edge must come from a documented structural
   feature (asymmetric jump/drift compensation, regime persistence, step quantisation vs spread, spread schedule,
   spike hazard non-memorylessness, boundary rules...) or a measured statistical anomaly with a correction for the
   number of tests (report the number of symbols x tests scanned and a Bonferroni/BH-adjusted p-value).

## Suggested plan (you may deviate with reasons)
1. **Universe screen (cheap):** list every synthetic in your families from the symbols file (descriptions!). Sample
   live spreads for all of them with `get_spot_prices` (8 ids per call), several times. Compute cost/volatility
   (spread / median M5 range) — instruments where spread > ~15-20% of the M5 range are nearly hopeless at M5.
2. **Statistics screen:** for the cheapest ~10-15 symbols pull M5 history (1000 bars = 3.5 days/call; target
   >= 3 months each for the shortlist, before 2026-09-15 matters most) and H1 (30 days/call) for longer context. Test
   drift, autocorrelation and variance ratios at several horizons, jump/spike hazard vs time since last spike, spike
   size distribution, time-of-day / day-of-week effects (Deriv's spread may follow a schedule), volatility clustering,
   regime persistence. Record every test in a table (count them).
3. **Strategy families to try** (>= 4 genuinely different, only where the screen shows structure): spike-hazard
   timing on Crash/Boom (ride the drift between spikes with a stop beyond the spike size; check drift vs spike
   compensation net of spread), post-spike mean reversion/continuation, Jump-index volatility-breakout or fade,
   Step-index quantised mean reversion, volatility-regime filters, session/time-of-day spread windows, multi-symbol
   portfolios of weak independent edges (independent RNGs -> diversification), and anything new you can justify.
4. Small account first: design for $30 at the broker minimum volume (probe it). If the edge needs more, state the
   smallest responsible balance. M5 is the owner's preferred timeframe; M1-M15 are fine, others with reasons.
5. Keep the safety rules: hard stop on every trade, no martingale / grid / averaging down, daily loss limit,
   kill-switch, max consecutive-loss pause.
6. If a family fails, say why in one line and move to the next. Iterate internally: hypotheses -> test -> diagnose ->
   new hypothesis. Do not stop after one failure; stop when you have a candidate ready for the holdout or when you
   have honestly exhausted your families (then report the evidence).

## Deliverables (as BRIEF2, in your team folder)
`strategy.py`, `specs.json` (measured spreads, min_units probed, swap bound, margin), `<Team>Bot.cs` compiled with
`bash arena/check_cbot.sh`, `NOTES.md` (all tests incl. failures + counts), `report_data.json` (BRIEF2 schema plus
`"screen": [{"symbol","spread","m5_range","cost_ratio","key_stats","verdict"}]`), official evaluate2 output.

Final message (<= 50 lines): evaluate2 printout, strategy in 5 lines, the screen summary (how many symbols/tests),
total parameter sets tried, walk-forward summary, and your honest verdict. Be context-efficient: write scripts to
files and print compact summaries; never dump large tables into the conversation.
