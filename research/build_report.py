"""Build the final arena v2 report (single self-contained HTML with inline SVG charts).

    cd /home/user/treasure/ctrader-arena && python ../research/build_report.py OUT.html
Reads submissions/<AGENT>/metrics.json + trades.csv, agents/<AGENT>/report_data.json, the cBot sources,
and re-runs each strategy's signal function to recover SL/TP levels for the annotated trade charts.
"""
import html, json, os, sys
import numpy as np, pandas as pd

ROOT = "/home/user/treasure/ctrader-arena"
sys.path.insert(0, ROOT)
from arena import evaluate2, ingest  # noqa: E402

AGENTS = [("IDX", "AGENT_01 · US Indices Specialist", "US indices", "IdxBot.cs", "var(--c1)"),
          ("CFX", "AGENT_02 · Crypto & Forex Specialist", "Crypto / Forex", "CfxBot.cs", "var(--c2)"),
          ("VOL", "AGENT_03 · Volatility Indices Specialist", "Deriv synthetics", "VolBot.cs", "var(--c3)")]
E = html.escape


def fmt(x, d=2, pre=""):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "–"
    return f"{pre}{x:,.{d}f}"


def money(x, d=2):
    if x is None:
        return "–"
    return ("−$" if x < 0 else "$") + f"{abs(x):,.{d}f}"


# ---------------------------------------------------------------- SVG helpers
def scale(v0, v1, p0, p1):
    if v1 == v0:
        v1 = v0 + 1
    return lambda v: p0 + (v - v0) / (v1 - v0) * (p1 - p0)


def nice_ticks(lo, hi, n=5):
    span = hi - lo if hi > lo else 1
    raw = span / n
    mag = 10 ** np.floor(np.log10(raw))
    step = min([1, 2, 2.5, 5, 10], key=lambda m: abs(m * mag - raw)) * mag
    start = np.ceil(lo / step) * step
    return [round(t, 10) for t in np.arange(start, hi + step * 0.001, step)]


def line_chart(series, w=860, h=300, ylab="", pct=False, zero=True, area=False, title=""):
    """series: list of (label, color, xs(datetime64), ys)."""
    allx = np.concatenate([np.asarray(s[2], "datetime64[ns]").astype("int64") for s in series])
    ally = np.concatenate([np.asarray(s[3], float) for s in series] + ([np.array([0.0])] if zero else []))
    L, R, T, B = 58, 16, 14, 34
    x0, x1 = allx.min(), allx.max()
    y0, y1 = ally.min(), ally.max()
    pad = (y1 - y0) * 0.06 or 1
    y0, y1 = y0 - pad, y1 + pad
    X = scale(x0, x1, L, w - R); Y = scale(y0, y1, h - B, T)
    out = [f'<svg viewBox="0 0 {w} {h}" class="chart" role="img" aria-label="{E(title)}">']
    for t in nice_ticks(y0, y1, 5):
        yy = Y(t)
        out.append(f'<line x1="{L}" x2="{w-R}" y1="{yy:.1f}" y2="{yy:.1f}" class="grid"/>')
        out.append(f'<text x="{L-6}" y="{yy+4:.1f}" class="tick" text-anchor="end">{t:,.0f}{"%" if pct else ""}</text>')
    if zero and y0 < 0 < y1:
        out.append(f'<line x1="{L}" x2="{w-R}" y1="{Y(0):.1f}" y2="{Y(0):.1f}" class="zero"/>')
    yrs = pd.date_range(pd.Timestamp(x0).normalize(), pd.Timestamp(x1), freq="QS")
    for d in yrs:
        xx = X(d.value)
        if xx < L + 20 or xx > w - R - 20:
            continue
        out.append(f'<line x1="{xx:.1f}" x2="{xx:.1f}" y1="{T}" y2="{h-B}" class="grid v"/>')
        out.append(f'<text x="{xx:.1f}" y="{h-B+16}" class="tick" text-anchor="middle">{d.strftime("%b %y")}</text>')
    for lab, col, xs, ys in series:
        xs = np.asarray(xs, "datetime64[ns]").astype("int64"); ys = np.asarray(ys, float)
        pts = " ".join(f"{X(a):.1f},{Y(b):.1f}" for a, b in zip(xs, ys))
        if area:
            base = Y(0 if y0 <= 0 <= y1 else y0)
            out.append(f'<polygon points="{X(xs[0]):.1f},{base:.1f} {pts} {X(xs[-1]):.1f},{base:.1f}" style="fill:{col};opacity:.18"/>')
        out.append(f'<polyline points="{pts}" fill="none" style="stroke:{col}" stroke-width="1.8" stroke-linejoin="round"/>')
        out.append(f'<circle cx="{X(xs[-1]):.1f}" cy="{Y(ys[-1]):.1f}" r="3.2" style="fill:{col}"/>')
    if ylab:
        out.append(f'<text x="12" y="{T+4}" class="tick">{E(ylab)}</text>')
    out.append("</svg>")
    return "".join(out)


def bar_chart(labels, values, colors, w=860, h=230, fmtv=lambda v: f"{v:.1f}", title=""):
    L, R, T, B = 50, 10, 16, 40
    vmin, vmax = min(0, min(values)), max(0, max(values))
    pad = (vmax - vmin) * 0.12 or 1
    Y = scale(vmin - (pad if vmin < 0 else 0), vmax + pad, h - B, T)
    n = len(values); bw = (w - L - R) / max(1, n)
    out = [f'<svg viewBox="0 0 {w} {h}" class="chart" role="img" aria-label="{E(title)}">']
    for t in nice_ticks(vmin, vmax + pad, 4):
        out.append(f'<line x1="{L}" x2="{w-R}" y1="{Y(t):.1f}" y2="{Y(t):.1f}" class="grid"/>'
                   f'<text x="{L-6}" y="{Y(t)+4:.1f}" class="tick" text-anchor="end">{t:,.0f}</text>')
    out.append(f'<line x1="{L}" x2="{w-R}" y1="{Y(0):.1f}" y2="{Y(0):.1f}" class="zero"/>')
    for i, (lab, v, c) in enumerate(zip(labels, values, colors)):
        x = L + i * bw + bw * 0.15; ww = bw * 0.7
        y = min(Y(v), Y(0)); hh = abs(Y(v) - Y(0))
        out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{ww:.1f}" height="{max(hh,0.8):.1f}" rx="2" style="fill:{c}"/>')
        if n <= 16:
            out.append(f'<text x="{x+ww/2:.1f}" y="{(y-5) if v>=0 else (y+hh+13):.1f}" class="val" text-anchor="middle">{fmtv(v)}</text>')
        if n <= 16 or i % max(1, n // 12) == 0:
            out.append(f'<text x="{x+ww/2:.1f}" y="{h-B+15}" class="tick" text-anchor="middle">{E(lab)}</text>')
    out.append("</svg>")
    return "".join(out)


def candle_chart(bars, i0, i1, tr, sl, tp, side, w=420, h=230, title=""):
    b = bars.iloc[i0:i1 + 1]
    lo = min(b.low.min(), sl if sl else b.low.min(), tr.exit_px, tr.entry_px)
    hi = max(b.high.max(), tp if tp else b.high.max(), tr.exit_px, tr.entry_px)
    pad = (hi - lo) * 0.08
    L, R, T, B = 8, 64, 10, 22
    X = scale(0, len(b), L, w - R); Y = scale(lo - pad, hi + pad, h - B, T)
    cw = max(1.5, (w - L - R) / len(b) * 0.6)
    out = [f'<svg viewBox="0 0 {w} {h}" class="chart candles" role="img" aria-label="{E(title)}">']
    ent = int(tr.entry_bar) - i0; ex = int(tr.exit_bar) - i0
    out.append(f'<rect x="{X(ent):.1f}" y="{T}" width="{max(2, X(ex+1)-X(ent)):.1f}" height="{h-B-T}" class="hold"/>')
    for k, r in enumerate(b.itertuples()):
        xc = X(k + 0.5); up = r.close >= r.open
        out.append(f'<line x1="{xc:.1f}" x2="{xc:.1f}" y1="{Y(r.high):.1f}" y2="{Y(r.low):.1f}" class="wick"/>')
        y_ = Y(max(r.open, r.close)); hh = max(0.8, abs(Y(r.open) - Y(r.close)))
        out.append(f'<rect x="{xc-cw/2:.1f}" y="{y_:.1f}" width="{cw:.1f}" height="{hh:.1f}" class="{"up" if up else "dn"}"/>')

    def hl(v, cls, lab):
        yy = Y(v)
        return (f'<line x1="{X(ent):.1f}" x2="{w-R}" y1="{yy:.1f}" y2="{yy:.1f}" class="lvl {cls}"/>'
                f'<text x="{w-R+4}" y="{yy+4:.1f}" class="lvlt {cls}">{lab}</text>')
    out.append(hl(tr.entry_px, "en", "entry"))
    if sl:
        out.append(hl(sl, "sl", "stop"))
    if tp:
        out.append(hl(tp, "tp", "target"))
    out.append(f'<circle cx="{X(ent+0.5):.1f}" cy="{Y(tr.entry_px):.1f}" r="4" class="mk en"/>')
    out.append(f'<circle cx="{X(ex+0.5):.1f}" cy="{Y(tr.exit_px):.1f}" r="4" class="mk {"tp" if tr.pnl>0 else "sl"}"/>')
    t0 = pd.Timestamp(b.time.iloc[0]); t1 = pd.Timestamp(b.time.iloc[-1])
    out.append(f'<text x="{L}" y="{h-6}" class="tick">{t0:%d %b %Y %H:%M}</text>'
               f'<text x="{w-R}" y="{h-6}" class="tick" text-anchor="end">{t1:%d %b %H:%M} UTC</text>')
    out.append("</svg>")
    return "".join(out)


# ---------------------------------------------------------------- data
def load_agent(name):
    sub = os.path.join(ROOT, "submissions", name)
    if not os.path.exists(os.path.join(sub, "metrics.json")):
        return None
    m = json.load(open(os.path.join(sub, "metrics.json")))
    tr = pd.read_csv(os.path.join(sub, "trades.csv"), parse_dates=["entry_time", "exit_time"])
    rd_path = os.path.join(ROOT, "agents", name, "report_data.json")
    rd = json.load(open(rd_path)) if os.path.exists(rd_path) else {}
    path = os.path.join(ROOT, "agents", name, "strategy.py")
    mod = evaluate2.load_strategy(path)
    specs = evaluate2.load_specs(path)
    legs = []
    for leg in mod.LEGS:
        sid = str(leg["symbol_id"]); per = leg.get("period", "M_1")
        bars = ingest.load(sid, per)
        od = mod.signals(bars, leg.get("params", {}), specs[sid]).sort_values("idx", kind="stable").reset_index(drop=True)
        legs.append((bars, od, specs[sid]))
    return dict(m=m, tr=tr, rd=rd, legs=legs, specs=specs, mod=mod)


def pick_examples(a, k_win=2, k_loss=2):
    tr = a["tr"]
    if len(tr) == 0:
        return []
    wins = tr[tr.pnl > 0].sort_values("pnl", ascending=False)
    loss = tr[tr.pnl < 0].sort_values("pnl")
    # a typical winner (median) + the best; a typical loser + the worst
    picks = []
    if len(wins):
        picks += [("Typical winner", wins.iloc[len(wins) // 2]), ("Best trade", wins.iloc[0])][:k_win]
    if len(loss):
        picks += [("Typical loser", loss.iloc[len(loss) // 2]), ("Worst trade", loss.iloc[0])][:k_loss]
    out = []
    for lab, t in picks:
        bars, od, spec = a["legs"][int(t.leg)]
        o = od.iloc[int(t.order_row)]
        sd = int(t.side)
        sl = t.entry_px - sd * o.sl if o.sl > 0 else None
        tp = t.entry_px + sd * o.tp if o.get("tp", 0) > 0 else None
        i0 = max(0, int(t.entry_bar) - 24); i1 = min(len(bars) - 1, int(t.exit_bar) + 8)
        if i1 - i0 > 90:
            i0 = max(0, int(t.entry_bar) - 12); i1 = min(len(bars) - 1, i0 + 90)
        out.append(dict(label=lab, t=t, sl=sl, tp=tp,
                        svg=candle_chart(bars, i0, i1, t, sl, tp, sd, title=f"{lab} {t.symbol}")))
    return out


# ---------------------------------------------------------------- page
CSS = """
:root{--bg:#f6f7f9;--panel:#ffffff;--ink:#14202e;--muted:#5b6878;--line:#dfe3ea;--soft:#eef1f5;
--accent:#0f6e74;--good:#1d7a46;--bad:#b4363a;--warn:#a36a00;--c1:#2f5fb3;--c2:#c47a12;--c3:#7b4bb7;
--up:#2e8b57;--dn:#c0474b;--f-d:'Sora',ui-sans-serif,system-ui,sans-serif;--f-b:'Instrument Sans',ui-sans-serif,system-ui,sans-serif;
--f-m:'JetBrains Mono',ui-monospace,Menlo,Consolas,monospace}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#0f141b;--panel:#161d26;--ink:#e6ebf1;--muted:#97a3b3;--line:#2a3441;--soft:#1c2531;
--accent:#4fb8be;--good:#4cc082;--bad:#ec7a7d;--warn:#e0a43c;--c1:#6f9be8;--c2:#e9a64a;--c3:#b48ef0;--up:#4cc082;--dn:#ec7a7d;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#0f141b;--panel:#161d26;--ink:#e6ebf1;--muted:#97a3b3;--line:#2a3441;--soft:#1c2531;
--accent:#4fb8be;--good:#4cc082;--bad:#ec7a7d;--warn:#e0a43c;--c1:#6f9be8;--c2:#e9a64a;--c3:#b48ef0;--up:#4cc082;--dn:#ec7a7d;color-scheme:dark}
body{background:var(--bg);color:var(--ink);font-family:var(--f-b);font-size:15px;line-height:1.55}
.wrap{max-width:1080px;margin:0 auto;padding-block:28px 80px;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}
h1,h2,h3,h4{font-family:var(--f-d);text-wrap:balance;line-height:1.2;margin:0}
h1{font-size:clamp(26px,4vw,38px);letter-spacing:-.01em}
h2{font-size:24px;margin-top:56px;padding-top:18px;border-top:1px solid var(--line)}
h3{font-size:18px;margin-top:28px}h4{font-size:15px;margin-top:18px}
p{max-width:72ch}.muted{color:var(--muted)}.small{font-size:13px}
.eyebrow{font-family:var(--f-m);font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--accent)}
.lede{font-size:17px;max-width:75ch}
nav.toc{display:flex;flex-wrap:wrap;gap:6px 14px;margin:18px 0 0;font-size:14px}
nav.toc a{color:var(--accent);text-decoration:none}nav.toc a:hover{text-decoration:underline}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}
.grid3{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:16px 18px;min-width:0}
.verdict{border-left:4px solid var(--accent)}
.kv{display:grid;grid-template-columns:auto 1fr;gap:4px 14px;font-size:14px}
.kv dt{color:var(--muted)}.kv dd{margin:0;font-family:var(--f-m);font-variant-numeric:tabular-nums}
.tbl{overflow-x:auto;margin:12px 0;border:1px solid var(--line);border-radius:10px;background:var(--panel)}
table{border-collapse:collapse;width:100%;font-size:13.5px}
th,td{padding:7px 10px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}
th{font-weight:600;color:var(--muted);font-size:12px;letter-spacing:.03em;background:var(--soft);white-space:nowrap}
td.n,th.n{text-align:right;font-family:var(--f-m);font-variant-numeric:tabular-nums;white-space:nowrap}
tr:last-child td{border-bottom:none}
.pill{display:inline-block;padding:1px 9px;border-radius:99px;font-size:12px;font-weight:600;font-family:var(--f-m)}
.pill.ok{background:color-mix(in srgb,var(--good) 16%,transparent);color:var(--good)}
.pill.no{background:color-mix(in srgb,var(--bad) 16%,transparent);color:var(--bad)}
.pill.mid{background:color-mix(in srgb,var(--warn) 18%,transparent);color:var(--warn)}
.dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:6px;vertical-align:baseline}
.pos{color:var(--good)}.neg{color:var(--bad)}
.chart{width:100%;height:auto;display:block;font-family:var(--f-m)}
.chart .grid{stroke:var(--line);stroke-width:1}.chart .grid.v{stroke-dasharray:2 4}
.chart .zero{stroke:var(--muted);stroke-width:1}
.chart .tick{fill:var(--muted);font-size:11px}.chart .val{fill:var(--ink);font-size:11px}
.candles .wick{stroke:var(--muted);stroke-width:1}.candles .up{fill:var(--up)}.candles .dn{fill:var(--dn)}
.candles .hold{fill:var(--accent);opacity:.08}
.candles .lvl{stroke-width:1.3;stroke-dasharray:5 3}.candles .lvl.en{stroke:var(--ink)}.candles .lvl.sl{stroke:var(--bad)}.candles .lvl.tp{stroke:var(--good)}
.candles .lvlt{font-size:11px}.candles .lvlt.en{fill:var(--ink)}.candles .lvlt.sl{fill:var(--bad)}.candles .lvlt.tp{fill:var(--good)}
.candles .mk{stroke:var(--panel);stroke-width:1.5}.candles .mk.en{fill:var(--ink)}.candles .mk.sl{fill:var(--bad)}.candles .mk.tp{fill:var(--good)}
.legend{display:flex;flex-wrap:wrap;gap:6px 18px;font-size:13px;margin:6px 0 0}
.bot{margin-top:40px;padding:22px;border-radius:14px;background:var(--panel);border:1px solid var(--line)}
.bot h2{border-top:none;margin-top:0;padding-top:0}
.tag{font-family:var(--f-m);font-size:12px;color:var(--muted)}
ul.tight{margin:6px 0;padding-left:20px}ul.tight li{margin:3px 0}
details{margin:10px 0;border:1px solid var(--line);border-radius:10px;background:var(--panel)}
summary{cursor:pointer;padding:10px 14px;font-weight:600}
pre.code{margin:0;padding:14px;overflow:auto;max-height:520px;font-family:var(--f-m);font-size:12px;line-height:1.45;background:var(--soft);border-top:1px solid var(--line)}
button.copy{font:inherit;font-size:12px;margin:0 14px 10px;padding:5px 12px;border-radius:7px;border:1px solid var(--line);background:var(--soft);color:var(--ink);cursor:pointer}
button.copy:focus-visible,summary:focus-visible,a:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.ex{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,400px),1fr));gap:14px}
.ex .panel h4{margin:0 0 6px}
.scorebar{display:flex;height:14px;border-radius:7px;overflow:hidden;background:var(--soft);margin:6px 0 2px}
.scorebar span{display:block;height:100%}
.rank{font-family:var(--f-d);font-size:30px;font-weight:700;line-height:1}
.note{background:color-mix(in srgb,var(--warn) 10%,var(--panel));border:1px solid color-mix(in srgb,var(--warn) 35%,var(--line));border-radius:10px;padding:12px 16px}
pre.mermaid{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px;overflow-x:auto}
"""


def gate_table(m):
    rows = "".join(f'<tr><td>{E(k)}</td><td>{"<span class=\'pill ok\'>PASS</span>" if v else "<span class=\'pill no\'>FAIL</span>"}</td></tr>'
                   for k, v in m.get("gates", {}).items())
    return f'<div class="tbl"><table><tr><th>Validation gate</th><th>Result</th></tr>{rows}</table></div>'


def split_table(m):
    rows = []
    for k, lab in (("full", "Full sample"), ("is", "In-sample (first 70%)"), ("oos", "Out-of-sample (last 30%)"), ("stress", "Cost stress (1.5× spread + slip)")):
        s = m.get(k)
        if not s:
            continue
        rows.append(f'<tr><td>{lab}</td><td class="n">{s["trades"]}</td><td class="n">{s["pf"]:.2f}</td><td class="n">{s["win_rate"]:.0f}%</td>'
                    f'<td class="n">{money(s["net"])}</td><td class="n">{money(s["expectancy"],3)}</td><td class="n">{s["t_stat"]:.2f}</td>'
                    f'<td class="n">{money(s["max_dd_usd"])}</td><td class="n">{s["sharpe_daily"]:.2f}</td><td class="n">{s["max_consec_losses"]}</td></tr>')
    return ('<div class="tbl"><table><tr><th>Sample</th><th class="n">Trades</th><th class="n">PF</th><th class="n">Win</th><th class="n">Net</th>'
            '<th class="n">Avg trade</th><th class="n">t-stat</th><th class="n">Max DD</th><th class="n">Sharpe</th><th class="n">Max loss run</th></tr>'
            + "".join(rows) + "</table></div>")


def generic_table(rows, cols=None, maxrows=40):
    if not rows:
        return '<p class="muted small">Not reported.</p>'
    if isinstance(rows, dict):
        lists = {k: v for k, v in rows.items() if isinstance(v, list) and v and isinstance(v[0], dict)}
        rest = {k: v for k, v in rows.items() if k not in lists}
        out = generic_table([{"item": k, "value": v} for k, v in rest.items()]) if rest else ""
        return out + "".join(f'<p class="small muted" style="margin:8px 0 0">{E(k)}</p>' + generic_table(v) for k, v in lists.items())
    if isinstance(rows, str):
        return f"<p class='small'>{E(rows)}</p>"
    if isinstance(rows[0], str):
        return '<ul class="tight">' + "".join(f"<li>{E(r)}</li>" for r in rows) + "</ul>"
    cols = cols or list(dict.fromkeys(k for r in rows for k in r.keys()))
    def cell(v):
        if isinstance(v, float):
            return f'<td class="n">{v:,.2f}</td>'
        if isinstance(v, int) and not isinstance(v, bool):
            return f'<td class="n">{v:,}</td>'
        if isinstance(v, (dict, list)):
            v = json.dumps(v)
        return f"<td>{E(str(v)) if v is not None else '–'}</td>"
    head = "".join(f"<th>{E(str(c)).replace('_',' ')}</th>" for c in cols)
    body = "".join("<tr>" + "".join(cell(r.get(c)) for c in cols) + "</tr>" for r in rows[:maxrows])
    return f'<div class="tbl"><table><tr>{head}</tr>{body}</table></div>'


def monthly(tr, B):
    mo = tr.groupby(tr.exit_time.dt.to_period("M")).pnl.sum()
    idx = pd.period_range(mo.index.min(), mo.index.max(), freq="M")
    return mo.reindex(idx, fill_value=0.0)


def build(out_path):
    data = {n: load_agent(n) for n, *_ in AGENTS}
    present = [(n, t, mk, cb, col) for n, t, mk, cb, col in AGENTS if data[n]]
    ranked = sorted(present, key=lambda a: (data[a[0]]["m"].get("qualified", False), data[a[0]]["m"].get("score", 0)), reverse=True)
    winner = ranked[0][0] if ranked and data[ranked[0][0]]["m"].get("qualified") else None
    P = []
    P.append('<title>Arena v2 Trading Bots</title><meta name="claude:viewport-fit-sides" content="cover">')
    P.append('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Sora:wght@500;700&family=Instrument+Sans:wght@400;600&family=JetBrains+Mono:wght@400;600&display=swap">')
    P.append(f"<style>{CSS}</style><div class='wrap'>")
    P.append('<div class="eyebrow">cTrader · Deriv demo account · research report · 17 Nov 2026</div>')
    P.append('<h1>Three specialist trading bots, tested and ranked</h1>')
    P.append(f'<p class="lede">Three independent agents each researched one market, built a cBot, and had to pass the same {len(next(iter(data.values()))["m"].get("gates",{})) if present else 15} validation gates '
             'on years of Deriv cTrader history with spread, swap, commission and slippage charged. This report compares them, explains each strategy with real trade examples, and gives the settings and account sizes to run them.</p>')
    P.append('<nav class="toc"><a href="#summary">Summary</a><a href="#compare">Comparison</a><a href="#curves">Equity &amp; drawdown</a>'
             + "".join(f'<a href="#{n.lower()}">{n}</a>' for n, *_ in present) +
             '<a href="#method">Method</a><a href="#deploy">Deployment</a><a href="#code">cBot code</a></nav>')

    # ---------------- executive summary
    P.append('<h2 id="summary">Executive summary</h2>')
    cards = []
    for i, (n, title, mk, cb, col) in enumerate(ranked):
        a = data[n]; m = a["m"]; rd = a["rd"]; f = m["full"]
        q = m.get("qualified", False)
        cards.append(f'''<div class="panel {'verdict' if n==winner else ''}"><div style="display:flex;justify-content:space-between;align-items:baseline;gap:10px">
<span class="rank" style="color:{col}">#{i+1}</span><span class="pill {'ok' if q else 'no'}">{'QUALIFIED' if q else 'NOT QUALIFIED'}</span></div>
<h3 style="margin-top:8px">{E(rd.get("strategy_name", n))}</h3><div class="tag">{E(n)} · {E(mk)} · score {m.get("score","–")}/100</div>
<p class="small" style="margin:8px 0">{E(rd.get("one_line",""))}</p>
<dl class="kv"><dt>Profit factor</dt><dd>{f["pf"]:.2f} (OOS {m["oos"]["pf"]:.2f})</dd><dt>Trades</dt><dd>{f["trades"]}</dd>
<dt>Max drawdown</dt><dd>{money(f["max_dd_usd"])} ({f["max_dd_pct"]:.1f}%)</dd><dt>Start balance tested</dt><dd>{money(m["start_balance"],0)}</dd>
<dt>Recommended min.</dt><dd>{money(m["balance"]["recommended_min"],0)}</dd></dl></div>''')
    P.append(f'<div class="grid3">{"".join(cards)}</div>')
    bal_rows = "".join(f'<tr><td>{n}</td><td class="n">{money(data[n]["m"]["balance"]["technical_min"],0)}</td><td class="n">{money(data[n]["m"]["balance"]["recommended_min"],0)}</td><td class="n">{money(data[n]["m"]["balance"]["recommended_operating"],0)}</td></tr>'
                       for n, *_ in ranked if data[n]["m"].get("qualified"))
    P.append(SUMMARY_TEXT.format(vol_line=VOL_LINE, bal_rows=bal_rows) if SUMMARY_TEXT else "")

    # ---------------- comparison table
    P.append('<h2 id="compare">Head-to-head comparison</h2>')
    cols = ["Bot", "Market", "Instrument", "Timeframe", "Start bal.", "Rec. min bal.", "Rec. operating", "Net profit", "Return", "PF",
            "Win rate", "Expectancy", "Max DD", "Sharpe", "Trades", "Avg trade", "Max consec. losses", "Trading costs", "Robustness", "Score"]
    rows = []
    for n, title, mk, cb, col in ranked:
        a = data[n]; m = a["m"]; f = m["full"]; rd = a["rd"]
        costs = a["tr"].spread_cost.sum() + a["tr"].swap.sum() + a["tr"].commission.sum()
        folds = sum(x["net"] > 0 for x in m["folds"])
        rob = f'{folds}/5 folds +, stress PF {m["stress"]["pf"]:.2f}'
        inst = ", ".join(sorted({l["symbol"] for l in m["legs"]}))
        tf = ", ".join(sorted({l.get("period", "M_1") for l in m["legs"]}))
        rows.append([f'<span class="dot" style="background:{col}"></span>{n}', mk, inst, tf, money(m["start_balance"], 0),
                     money(m["balance"]["recommended_min"], 0), money(m["balance"]["recommended_operating"], 0), money(f["net"]),
                     f'{f["return_pct"]:.0f}%', f'{f["pf"]:.2f}', f'{f["win_rate"]:.0f}%', money(f["expectancy"], 3), money(f["max_dd_usd"]),
                     f'{f["sharpe_daily"]:.2f}', str(f["trades"]), money(f["expectancy"], 2), str(f["max_consec_losses"]), money(costs), rob,
                     f'<b>{m.get("score","–")}</b>'])
    P.append('<div class="tbl"><table><tr>' + "".join(f"<th>{c}</th>" for c in cols) + "</tr>" +
             "".join("<tr>" + "".join(f'<td class="{"n" if j>=4 and j not in (18,) else ""}">{v}</td>' for j, v in enumerate(r)) + "</tr>" for r in rows) + "</table></div>")
    P.append('<p class="small muted">Return is on the start balance tested, over each bot\'s own history window. "Trading costs" = spread paid + swap + commission over the whole test (USD, negative = cost). Each bot trades the broker\'s minimum volume, so drawdown and profit in dollars do not change with account size; percentages do.</p>')

    # score breakdown
    P.append('<h3>How the score is built</h3><p class="small muted">Weights from your brief: risk-adjusted return 25, profit factor 15, drawdown control 15, out-of-sample 15, robustness 10, statistical edge 10, execution realism 5, capital efficiency 5.</p>')
    keys = list(next(iter(data[ranked[0][0]]["m"]["score_parts"].keys() for _ in [0]))) if present else []
    shades = ["var(--c1)", "var(--c2)", "var(--c3)", "var(--accent)", "var(--good)", "var(--warn)", "var(--muted)", "var(--bad)"]
    sb = []
    for n, title, mk, cb, col in ranked:
        sp = data[n]["m"]["score_parts"]
        segs = "".join(f'<span title="{E(k)}: {v}" style="width:{v}%;background:{shades[j]}"></span>' for j, (k, v) in enumerate(sp.items()))
        sb.append(f'<div><b>{n}</b> <span class="tag">{data[n]["m"]["score"]}/100</span><div class="scorebar">{segs}</div></div>')
    P.append("".join(sb))
    P.append('<div class="legend">' + "".join(f'<span><span class="dot" style="background:{shades[j]}"></span>{E(k)}</span>' for j, k in enumerate(keys)) + "</div>")
    rows = []
    for k in keys:
        rows.append(f"<tr><td>{E(k)}</td>" + "".join(f'<td class="n">{data[n]["m"]["score_parts"][k]:.1f}</td>' for n, *_ in ranked) + "</tr>")
    P.append('<div class="tbl"><table><tr><th>Component</th>' + "".join(f'<th class="n">{n}</th>' for n, *_ in ranked) + "</tr>" + "".join(rows) + "</table></div>")

    # ---------------- curves
    P.append('<h2 id="curves">Equity and drawdown</h2>')
    P.append('<p>Qualified bots only (the unqualified bot\'s curve is in its own section). Each curve is the bot\'s closed-trade equity as a percentage gain on the start balance it was tested with. Lines end on 17 Nov 2026. The bots started at different dates because history depth differs by instrument.</p>')
    ser, dds = [], []
    for n, title, mk, cb, col in [x for x in present if data[x[0]]["m"].get("qualified")] or present:
        tr = data[n]["tr"]; B = data[n]["m"]["start_balance"]
        eq = np.cumsum(tr.pnl.to_numpy()); xs = tr.exit_time.to_numpy()
        ser.append((n, col, np.concatenate([[tr.entry_time.iloc[0].to_datetime64()], xs]), np.concatenate([[0], eq / B * 100])))
        peak = np.maximum.accumulate(np.concatenate([[B], B + eq]))[1:]
        dds.append((n, col, xs, -(peak - (B + eq)) / peak * 100))
    P.append('<div class="panel">' + line_chart(ser, ylab="% gain on start balance", pct=True, title="Equity curves") +
             '<div class="legend">' + "".join(f'<span><span class="dot" style="background:{c}"></span>{n}</span>' for n, c, *_ in ser) + "</div></div>")
    P.append('<h3>Drawdown from peak (%)</h3><div class="panel">' + line_chart(dds, h=220, ylab="% below peak", pct=True, area=True, title="Drawdown") + "</div>")

    # ---------------- per bot
    for n, title, mk, cb, col in ranked:
        P.append(bot_section(n, title, mk, cb, col, data[n]))

    # ---------------- method + deployment + code
    P.append(METHOD_TEXT)
    P.append(deploy_section(ranked, data))
    P.append('<h2 id="code">cBot source code</h2><p>Every file below compiled with 0 errors against the official cTrader.Automate API (NuGet package, .NET 6). The same files are attached to the chat message that links to this report. To install: cTrader → Automate → New cBot → paste → Build → attach to a chart of the instrument/timeframe listed.</p>')
    for n, title, mk, cb, col in present:
        src = open(os.path.join(ROOT, "agents", n, cb)).read()
        P.append(f'<details><summary>{E(cb)} <span class="tag">· {n} · {src.count(chr(10))} lines</span></summary>'
                 f'<button class="copy" data-target="src-{n}">Copy code</button><pre class="code" id="src-{n}">{E(src)}</pre></details>')
    P.append("""<script>document.querySelectorAll('button.copy').forEach(b=>b.addEventListener('click',()=>{const el=document.getElementById(b.dataset.target);
navigator.clipboard.writeText(el.textContent).then(()=>{b.textContent='Copied'},()=>{const r=document.createRange();r.selectNodeContents(el);const s=getSelection();s.removeAllRanges();s.addRange(r);b.textContent='Selected, press Ctrl+C'})}))</script>""")
    P.append("</div>")
    open(out_path, "w").write("\n".join(P))
    print("wrote", out_path, os.path.getsize(out_path) // 1024, "KB")


def bot_section(n, title, mk, cb, col, a):
    m, rd, tr = a["m"], a["rd"], a["tr"]
    f = m["full"]; B = m["start_balance"]
    lg = rd.get("logic", {})
    S = [f'<section class="bot" id="{n.lower()}"><div class="eyebrow" style="color:{col}">{E(title)}</div>',
         f'<h2>{E(rd.get("strategy_name", n))}</h2><p class="lede">{E(rd.get("one_line",""))}</p>']
    S.append('<div class="grid2"><div class="panel"><h4 style="margin-top:0">Trading logic</h4><dl class="kv">' +
             "".join(f"<dt>{E(k.replace('_',' ').title())}</dt><dd style='font-family:var(--f-b)'>{E(str(v))}</dd>" for k, v in lg.items()) + "</dl></div>")
    sp = a["legs"][0][2]
    inst = rd.get("instrument(s)", [])
    S.append('<div class="panel"><h4 style="margin-top:0">Instrument, timeframe and money</h4><dl class="kv">'
             f'<dt>Instrument</dt><dd>{E(", ".join(inst) if isinstance(inst, list) else str(inst))}</dd>'
             f'<dt>Timeframe</dt><dd style="font-family:var(--f-b)">{E(str(rd.get("timeframe","")))}</dd>'
             f'<dt>Test window</dt><dd>{m["period"][0]} → {m["period"][1]}</dd><dt>OOS starts</dt><dd>{m["oos_start"]}</dd>'
             f'<dt>Start balance tested</dt><dd>{money(B,0)}</dd>'
             f'<dt>Technical minimum</dt><dd>{money(m["balance"]["technical_min"],0)}</dd>'
             f'<dt>Recommended minimum</dt><dd>{money(m["balance"]["recommended_min"],0)}</dd>'
             f'<dt>Recommended operating</dt><dd>{money(m["balance"]["recommended_operating"],0)}</dd>'
             f'<dt>Margin at max exposure</dt><dd>{money(m.get("margin_usd"))}</dd>'
             f'<dt>Broker min volume</dt><dd>' + ", ".join(f'{l[2]["name"]}: {l[2].get("min_units")} units' for l in a["legs"]) + '</dd>'
             f'<dt>Spread modelled</dt><dd>' + ", ".join(f'{l[2]["name"]}: {l[2]["spread"]}' for l in a["legs"]) + '</dd>'
             f'<dt>Commission</dt><dd>{money(f["commission_total"])} total</dd><dt>Swap</dt><dd>{money(f["swap_total"])} total, {f["overnight_trades"]} overnight trades</dd>'
             f'<dt>Spread paid</dt><dd>{money(tr.spread_cost.sum())} total</dd>'
             f'<dt>Exposure</dt><dd>{f["exposure_pct"]:.1f}% of time in market, avg hold {f["avg_hold_hours"]:.1f} h</dd>'
             f'<dt>Recovery</dt><dd>factor {f["recovery_factor"]:.1f}, longest under water {f["longest_dd_days"]:.0f} days</dd>'
             f'<dt>Monte Carlo DD</dt><dd>median {money(m["mc"]["dd50"])}, 95% {money(m["mc"]["dd95"])}, 99% {money(m["mc"]["dd99"])}</dd>'
             '</dl></div></div>')
    bal = rd.get("balance")
    if isinstance(bal, dict):
        S.append('<div class="note small" style="margin-top:14px"><b>Account size notes from the agent.</b> ' + " ".join(f"{E(k.replace('_',' '))}: {E(str(v))}." for k, v in bal.items()) + "</div>")
    S.append("<h3>Backtest, out-of-sample and stress results</h3>" + split_table(m))
    # equity + monthly
    eq = np.cumsum(tr.pnl.to_numpy())
    S.append('<div class="grid2"><div class="panel"><h4 style="margin-top:0">Balance growth ($)</h4>' +
             line_chart([(n, col, np.concatenate([[tr.entry_time.iloc[0].to_datetime64()], tr.exit_time.to_numpy()]), np.concatenate([[B], B + eq]))],
                        w=520, h=240, zero=False, title=f"{n} balance") + "</div>")
    mo = monthly(tr, B)
    S.append('<div class="panel"><h4 style="margin-top:0">Monthly net P&amp;L ($)</h4>' +
             bar_chart([p.strftime("%b%y") if i % max(1, len(mo)//10) == 0 else "" for i, p in enumerate(mo.index)], mo.values.tolist(),
                       ["var(--good)" if v >= 0 else "var(--bad)" for v in mo.values], w=520, h=240, fmtv=lambda v: "", title=f"{n} monthly") +
             f'<p class="small muted" style="margin:4px 0 0">{(mo>0).mean()*100:.0f}% of months profitable; {f["weeks_profitable_pct"]:.0f}% of weeks.</p></div></div>')
    # walk-forward folds (evaluator) + agent anchored WF
    S.append("<h3>Walk-forward and time stability</h3>")
    S.append('<div class="grid2"><div class="panel"><h4 style="margin-top:0">Five equal time folds (fixed parameters)</h4>' +
             bar_chart([x["start"][2:7] for x in m["folds"]], [x["net"] for x in m["folds"]], ["var(--good)" if x["net"] > 0 else "var(--bad)" for x in m["folds"]],
                       w=520, h=210, fmtv=lambda v: f"${v:,.0f}", title="folds") +
             '<p class="small muted" style="margin:4px 0 0">' + " · ".join(f'{x["trades"]} tr / PF {x["pf"]:.2f}' for x in m["folds"]) + "</p></div>")
    S.append('<div class="panel"><h4 style="margin-top:0">Anchored walk-forward (re-fitted each fold by the agent)</h4>' + generic_table(rd.get("walk_forward", [])) + "</div></div>")
    S.append("<h3>Parameter sensitivity (neighbouring settings)</h3>" + generic_table(rd.get("neighbour_table", [])))
    S.append("<h3>Timeframe comparison</h3>" + generic_table(rd.get("timeframe_comparison", [])))
    S.append("<h3>Input parameters</h3>" + generic_table(rd.get("parameters", [])))
    # trade examples
    S.append(f'<h3>Trade examples from the backtest</h3><p class="small muted">Shaded band = time in the trade. Dashed lines = entry, stop and target placed at entry. Marker at exit: green = profit, red = loss. Prices are BID.</p>')
    exs = pick_examples(a)
    S.append('<div class="ex">' + "".join(
        f'<div class="panel"><h4>{E(e["label"])} · <span class="{"pos" if e["t"].pnl>0 else "neg"}">{money(e["t"].pnl)}</span></h4>'
        f'<div class="tag">{E(e["t"].symbol)} · {"BUY" if e["t"].side>0 else "SELL"} · {pd.Timestamp(e["t"].entry_time):%Y-%m-%d %H:%M} UTC · exit {E(e["t"].reason)}</div>'
        f'{e["svg"]}<div class="small muted">entry {e["t"].entry_px:,.2f} · stop {fmt(e["sl"])} · target {fmt(e["tp"])} · exit {e["t"].exit_px:,.2f}</div></div>' for e in exs) + "</div>")
    if rd.get("trade_examples"):
        S.append("<h4>Agent's annotated examples (why each trade was taken)</h4>" + generic_table(rd["trade_examples"]))
    S.append("<h3>Validation gates</h3>" + gate_table(m))
    S.append('<div class="grid2"><div class="panel"><h4 style="margin-top:0">Rejected alternatives</h4>' + generic_table(rd.get("rejected_alternatives", []), cols=["name", "result", "why_rejected"]) + "</div>"
             '<div class="panel"><h4 style="margin-top:0">When this bot fails</h4>' + generic_table(rd.get("failure_conditions", [])) + "</div></div>")
    S.append(f'<p class="small muted">Parameter sets evaluated during research: {E(str(rd.get("params_tried","–")))}. {E(str(rd.get("params_tried_note","")))}</p>')
    S.append("</section>")
    return "".join(S)


SUMMARY_TEXT = ""
VOL_LINE = ""
METHOD_TEXT = ""


def deploy_section(ranked, data):
    return ""


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        import report_text as RT  # editorial text written by the supervisor
        SUMMARY_TEXT, METHOD_TEXT, VOL_LINE = RT.SUMMARY, RT.METHOD, RT.VOL_LINE
        deploy_section = RT.deploy_section
    except ImportError:
        pass
    build(sys.argv[1] if len(sys.argv) > 1 else "/tmp/report.html")
