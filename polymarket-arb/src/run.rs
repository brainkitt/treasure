//! Live runtime: wires feeds, Polymarket streams, the engine, the executor
//! and the dashboard together.

use std::collections::VecDeque;
use std::sync::{Arc, RwLock};
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

use polymarket_client_sdk::clob;
use tokio::sync::mpsc;

use crate::book::BookSide;
use crate::config::Config;
use crate::engine::{Engine, FillReport, MarketDef, Mode, Snapshot};
use crate::polymarket::{self, ExecMsg};
use crate::{dashboard, spot};

pub enum Event {
    Spot { src: usize, px: f64 },
    Chainlink { ts_ms: i64, px: f64 },
    Market(MarketDef),
    BookSnap { token: String, bids: Vec<(f64, f64)>, asks: Vec<(f64, f64)> },
    BookLevel { token: String, side: BookSide, price: f64, size: f64 },
    Fill(FillReport),
}

pub fn now_ms() -> i64 {
    SystemTime::now().duration_since(UNIX_EPOCH).map_or(0, |d| d.as_millis() as i64)
}

/// Blends exchange mids into one estimate of where the Chainlink reference
/// price is heading. Each source carries a slow-moving basis to Chainlink so
/// USD/USDT and venue premia cancel while fast moves pass straight through.
pub struct Composite {
    srcs: Vec<Src>,
    max_age_ms: i64,
}

#[derive(Clone, Default)]
struct Src {
    px: f64,
    ts_ms: i64,
    basis: Option<f64>,
}

impl Composite {
    const ALPHA: f64 = 0.02;

    pub fn new(n: usize, max_age_ms: i64) -> Self {
        Self { srcs: vec![Src::default(); n], max_age_ms }
    }

    pub fn on_spot(&mut self, src: usize, px: f64, now: i64) {
        self.srcs[src].px = px;
        self.srcs[src].ts_ms = now;
    }

    pub fn on_chainlink(&mut self, px: f64, now: i64) {
        for s in self.srcs.iter_mut().filter(|s| s.px > 0.0 && now - s.ts_ms <= self.max_age_ms) {
            let d = px - s.px;
            s.basis = Some(s.basis.map_or(d, |b| b + Self::ALPHA * (d - b)));
        }
    }

    /// Median of basis-adjusted fresh sources.
    pub fn value(&self, now: i64) -> Option<f64> {
        let mut v: Vec<f64> = self
            .srcs
            .iter()
            .filter(|s| s.px > 0.0 && now - s.ts_ms <= self.max_age_ms)
            .filter_map(|s| Some(s.px + s.basis?))
            .collect();
        if v.is_empty() {
            return None;
        }
        v.sort_by(f64::total_cmp);
        let n = v.len();
        Some(if n % 2 == 1 { v[n / 2] } else { (v[n / 2 - 1] + v[n / 2]) / 2.0 })
    }

    pub fn ages(&self, now: i64) -> Vec<f64> {
        self.srcs.iter().map(|s| if s.ts_ms == 0 { -1.0 } else { (now - s.ts_ms) as f64 }).collect()
    }
}

/// Strike = first Chainlink print at or after the window start, accepted
/// only if we were already receiving prints before the start (so a bot that
/// boots mid-window never guesses).
pub fn strike_from(ticks: &VecDeque<(i64, f64)>, start_ms: i64) -> Option<f64> {
    let i = ticks.iter().position(|t| t.0 >= start_ms)?;
    (i > 0 && ticks[i].0 - start_ms <= 5000).then_some(ticks[i].1)
}

pub async fn run(cfg: Config, live: bool) -> anyhow::Result<()> {
    let (tx, mut rx) = mpsc::channel::<Event>(16_384);
    let state = Arc::new(RwLock::new(Snapshot::default()));

    let feeds: Vec<spot::Feed> = cfg
        .feeds
        .iter()
        .map(|n| spot::feed(n).ok_or_else(|| anyhow::anyhow!("unknown feed \"{n}\"")))
        .collect::<anyhow::Result<_>>()?;
    anyhow::ensure!(!feeds.is_empty(), "configure at least one spot feed");
    let mut names: Vec<String> = feeds.iter().map(|f| f.name.to_owned()).collect();
    names.push("chainlink".into());
    for (i, f) in feeds.into_iter().enumerate() {
        tokio::spawn(spot::run_feed(i, f, tx.clone()));
    }
    tokio::spawn(polymarket::chainlink(tx.clone()));
    tokio::spawn(polymarket::discover(cfg.clone(), tx.clone()));

    let listener = tokio::net::TcpListener::bind(&cfg.dashboard_addr).await?;
    tracing::info!("dashboard: http://{}", listener.local_addr()?);
    tokio::spawn(dashboard::serve(listener, state.clone()));

    let (exec_tx, exec_rx) = mpsc::channel::<ExecMsg>(1024);
    let mut exec_task = if live {
        tokio::spawn(polymarket::live_executor(cfg.clone(), exec_rx, tx.clone()))
    } else {
        drop(exec_rx);
        tokio::spawn(std::future::pending())
    };

    let ws = clob::ws::Client::default();
    let mut engine = Engine::new(cfg.clone(), if live { Mode::Live } else { Mode::Paper }, now_ms());
    let mut comp = Composite::new(names.len() - 1, cfg.max_spot_age_ms);
    let mut ticks: VecDeque<(i64, f64)> = VecDeque::new();
    let mut last_cl_ms = 0i64;
    let mut timer = tokio::time::interval(Duration::from_millis(100));
    let mut n = 0u64;
    tracing::info!("running in {} mode with ${:.2} bankroll", if live { "LIVE" } else { "PAPER" }, cfg.bankroll);

    loop {
        tokio::select! {
            ev = rx.recv() => {
                let Some(ev) = ev else { break };
                let now = now_ms();
                match ev {
                    Event::Spot { src, px } => {
                        comp.on_spot(src, px, now);
                        if let Some(v) = comp.value(now) {
                            engine.on_spot(now, v);
                        }
                    }
                    Event::Chainlink { ts_ms, px } => {
                        last_cl_ms = now;
                        comp.on_chainlink(px, now);
                        ticks.push_back((ts_ms, px));
                        while ticks.front().is_some_and(|t| t.0 < ts_ms - 1_200_000) {
                            ticks.pop_front();
                        }
                        for (slug, start) in engine.markets_needing_strike() {
                            if let Some(k) = strike_from(&ticks, start) {
                                engine.set_strike(&slug, k);
                            }
                        }
                    }
                    Event::Market(def) => {
                        if !engine.has_market(&def.slug) {
                            if live {
                                let _ = exec_tx.try_send(ExecMsg::Warm(vec![def.up_token.clone(), def.down_token.clone()]));
                            }
                            tokio::spawn(polymarket::stream_books(ws.clone(), def.clone(), tx.clone()));
                            engine.add_market(def, None);
                        }
                    }
                    Event::BookSnap { token, bids, asks } => engine.on_book_snapshot(now, &token, &bids, &asks),
                    Event::BookLevel { token, side, price, size } => engine.on_book_level(now, &token, side, price, size),
                    Event::Fill(r) => engine.on_fill(r),
                }
            }
            _ = timer.tick() => {
                let now = now_ms();
                engine.on_timer(now);
                n += 1;
                if n.is_multiple_of(3) {
                    let mut ages = comp.ages(now);
                    ages.push(if last_cl_ms == 0 { -1.0 } else { (now - last_cl_ms) as f64 });
                    engine.feeds = names.iter().cloned().zip(ages).collect();
                    *state.write().unwrap() = engine.snapshot();
                }
            }
            r = &mut exec_task => {
                anyhow::bail!("live executor stopped: {:?}", r.map_err(anyhow::Error::from).and_then(|x| x));
            }
            _ = tokio::signal::ctrl_c() => break,
        }
        for intent in engine.drain_intents() {
            if exec_tx.try_send(ExecMsg::Order(intent.clone(), Instant::now())).is_err() {
                engine.on_fill(FillReport { intent, shares: 0.0, avg_px: 0.0, latency_ms: 0.0, error: Some("executor unavailable".into()) });
            }
        }
    }
    let s = engine.snapshot();
    println!("stopped. equity ${:.2} | pnl {:+.2} | trades {} (W{} / L{}) | open positions {}", s.equity, s.total_pnl, s.trades, s.wins, s.losses, s.open_positions);
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn composite_removes_basis_but_keeps_fast_moves() {
        let mut c = Composite::new(2, 3000);
        c.on_spot(0, 100_050.0, 0); // USDT venue trading $50 rich
        c.on_spot(1, 100_000.0, 0);
        assert_eq!(c.value(0), None); // no chainlink yet => no basis => no value
        c.on_chainlink(100_000.0, 0);
        assert_eq!(c.value(0), Some(100_000.0));
        // Both venues jump $100 before Chainlink prints: composite leads.
        c.on_spot(0, 100_150.0, 100);
        c.on_spot(1, 100_100.0, 100);
        assert_eq!(c.value(100), Some(100_100.0));
        // Stale sources drop out.
        assert_eq!(c.value(10_000), None);
    }

    #[test]
    fn strike_needs_a_print_before_the_window() {
        let t: VecDeque<(i64, f64)> = [(900, 1.0), (1900, 2.0), (2900, 3.0)].into();
        assert_eq!(strike_from(&t, 1000), Some(2.0));
        assert_eq!(strike_from(&t, 500), None); // booted after the window opened
        assert_eq!(strike_from(&t, 5000), None); // not reached yet
    }
}
