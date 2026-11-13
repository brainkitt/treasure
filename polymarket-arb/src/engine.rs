//! Strategy core: a synchronous, clock-injected state machine.
//!
//! Inputs are spot ticks, order-book updates and timer ticks; outputs are
//! order intents. In paper mode the engine fills its own intents against the
//! book as it looks `paper_latency_ms` later; in live mode the caller sends
//! them to the exchange and reports back with `on_fill`.

use std::collections::{HashMap, VecDeque};

use serde::Serialize;

use crate::book::{Book, BookSide};
use crate::config::Config;
use crate::model::{VolEstimator, fair_up, fee_per_share};

#[derive(Debug, Clone)]
pub struct MarketDef {
    pub slug: String,
    pub label: String,
    pub up_token: String,
    pub down_token: String,
    pub start_ms: i64,
    pub end_ms: i64,
    pub tick: f64,
    pub min_size: f64,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
pub enum Outcome {
    Up,
    Down,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Action {
    Buy,
    Sell,
}

#[derive(Debug, Clone)]
pub struct OrderIntent {
    pub slug: String,
    pub token: String,
    pub outcome: Outcome,
    pub action: Action,
    pub shares: f64,
    pub limit: f64,
    /// Engine clock when the signal fired.
    pub signal_ms: i64,
}

#[derive(Debug, Clone)]
pub struct FillReport {
    pub intent: OrderIntent,
    pub shares: f64,
    pub avg_px: f64,
    pub latency_ms: f64,
    pub error: Option<String>,
}

#[derive(Debug, Clone)]
struct Position {
    outcome: Outcome,
    shares: f64,
    /// Total paid including fees.
    cost: f64,
}

struct MarketState {
    def: MarketDef,
    strike: Option<f64>,
    up: Book,
    down: Book,
    pos: Option<Position>,
    in_flight: bool,
    /// Worst-case cost of a buy order that has not been confirmed yet.
    in_flight_cost: f64,
    last_order_ms: i64,
    final_spot: Option<f64>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Mode {
    Paper,
    Live,
}

#[derive(Debug, Clone, Serialize)]
pub struct LogLine {
    pub ts_ms: i64,
    pub kind: &'static str,
    pub text: String,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct Snapshot {
    pub mode: String,
    pub now_ms: i64,
    pub started_ms: i64,
    pub seed: f64,
    pub equity: f64,
    pub cash: f64,
    pub total_pnl: f64,
    pub daily_pnl: f64,
    pub risk_used: f64,
    pub wins: u32,
    pub losses: u32,
    pub trades: u32,
    pub missed: u32,
    pub fees_paid: f64,
    pub latency_ms: f64,
    pub spot: f64,
    pub vol_annual: f64,
    pub market: String,
    pub secs_left: f64,
    pub strike: f64,
    pub clob_mid: f64,
    pub fair: f64,
    pub edge: f64,
    pub open_positions: u32,
    pub feeds: Vec<(String, f64)>,
    pub equity_curve: Vec<(i64, f64)>,
    pub log: Vec<LogLine>,
}

pub struct Engine {
    pub cfg: Config,
    mode: Mode,
    markets: HashMap<String, MarketState>,
    token_index: HashMap<String, (String, Outcome)>,
    spot: f64,
    spot_ms: i64,
    vol: VolEstimator,
    cash: f64,
    seed: f64,
    day: i64,
    day_start_equity: f64,
    day_realised: f64,
    wins: u32,
    losses: u32,
    missed: u32,
    fees_paid: f64,
    latency_ewma: f64,
    paper_queue: Vec<(i64, OrderIntent)>,
    outbox: Vec<OrderIntent>,
    log: VecDeque<LogLine>,
    curve: Vec<(i64, f64)>,
    last_curve_ms: i64,
    started_ms: i64,
    now_ms: i64,
    halted_logged: bool,
    pub feeds: Vec<(String, f64)>,
}

const LOG_CAP: usize = 200;
const CURVE_CAP: usize = 2000;

impl Engine {
    pub fn new(cfg: Config, mode: Mode, now_ms: i64) -> Self {
        let vol = VolEstimator::new(cfg.vol_init_annual, cfg.vol_halflife_s, cfg.vol_floor_annual);
        let seed = cfg.bankroll;
        Self {
            cfg,
            mode,
            markets: HashMap::new(),
            token_index: HashMap::new(),
            spot: 0.0,
            spot_ms: 0,
            vol,
            cash: seed,
            seed,
            day: now_ms.div_euclid(86_400_000),
            day_start_equity: seed,
            day_realised: 0.0,
            wins: 0,
            losses: 0,
            missed: 0,
            fees_paid: 0.0,
            latency_ewma: 0.0,
            paper_queue: Vec::new(),
            outbox: Vec::new(),
            log: VecDeque::new(),
            curve: vec![(now_ms, seed)],
            last_curve_ms: now_ms,
            started_ms: now_ms,
            now_ms,
            halted_logged: false,
            feeds: Vec::new(),
        }
    }

    // ---- inputs -----------------------------------------------------------

    pub fn add_market(&mut self, def: MarketDef, strike: Option<f64>) {
        if self.markets.contains_key(&def.slug) {
            return;
        }
        self.token_index.insert(def.up_token.clone(), (def.slug.clone(), Outcome::Up));
        self.token_index.insert(def.down_token.clone(), (def.slug.clone(), Outcome::Down));
        self.push_log("info", format!("tracking \"{}\"", def.label));
        self.markets.insert(
            def.slug.clone(),
            MarketState {
                def,
                strike,
                up: Book::default(),
                down: Book::default(),
                pos: None,
                in_flight: false,
                in_flight_cost: 0.0,
                last_order_ms: 0,
                final_spot: None,
            },
        );
    }

    pub fn has_market(&self, slug: &str) -> bool {
        self.markets.contains_key(slug)
    }

    pub fn set_strike(&mut self, slug: &str, strike: f64) {
        if let Some(m) = self.markets.get_mut(slug)
            && m.strike.is_none() {
                m.strike = Some(strike);
                let label = m.def.label.clone();
                self.push_log("info", format!("strike ${strike:.2} for \"{label}\""));
            }
    }

    /// Markets that have started but whose strike is still unknown: (slug, start_ms).
    pub fn markets_needing_strike(&self) -> Vec<(String, i64)> {
        self.markets
            .values()
            .filter(|m| m.strike.is_none())
            .map(|m| (m.def.slug.clone(), m.def.start_ms))
            .collect()
    }

    pub fn on_spot(&mut self, ts_ms: i64, px: f64) {
        self.advance(ts_ms);
        self.spot = px;
        self.spot_ms = ts_ms;
        self.vol.update(ts_ms, px);
        let slugs: Vec<String> = self.markets.keys().cloned().collect();
        for s in slugs {
            self.evaluate(&s);
        }
    }

    pub fn on_book_snapshot(&mut self, ts_ms: i64, token: &str, bids: &[(f64, f64)], asks: &[(f64, f64)]) {
        self.advance(ts_ms);
        if let Some((slug, book)) = self.book_mut(token) {
            book.set_snapshot(bids, asks, ts_ms);
            self.evaluate(&slug);
        }
    }

    pub fn on_book_level(&mut self, ts_ms: i64, token: &str, side: BookSide, price: f64, size: f64) {
        self.advance(ts_ms);
        if let Some((slug, book)) = self.book_mut(token) {
            book.set_level(side, price, size, ts_ms);
            self.evaluate(&slug);
        }
    }

    pub fn on_timer(&mut self, ts_ms: i64) {
        self.advance(ts_ms);
    }

    /// Order intents for the caller to execute (live mode only).
    pub fn drain_intents(&mut self) -> Vec<OrderIntent> {
        std::mem::take(&mut self.outbox)
    }

    pub fn on_fill(&mut self, r: FillReport) {
        let Some(m) = self.markets.get_mut(&r.intent.slug) else { return };
        m.in_flight = false;
        m.in_flight_cost = 0.0;
        let label = m.def.label.clone();
        if r.latency_ms > 0.0 {
            self.latency_ewma =
                if self.latency_ewma == 0.0 { r.latency_ms } else { 0.8 * self.latency_ewma + 0.2 * r.latency_ms };
        }
        if let Some(e) = &r.error {
            self.missed += 1;
            self.push_log("warn", format!("REJECTED \"{label}\" // {e}"));
            return;
        }
        if r.shares <= 0.0 {
            self.missed += 1;
            self.push_log("warn", format!("MISSED \"{label}\" // book moved before fill ({:.0}ms)", r.latency_ms));
            return;
        }
        let fee = fee_per_share(r.avg_px, self.cfg.fee_rate, self.cfg.fee_exponent) * r.shares;
        self.fees_paid += fee;
        match r.intent.action {
            Action::Buy => {
                let cost = r.shares * r.avg_px + fee;
                self.cash -= cost;
                let m = self.markets.get_mut(&r.intent.slug).unwrap();
                m.pos = Some(Position { outcome: r.intent.outcome, shares: r.shares, cost });
                self.push_log(
                    "exec",
                    format!(
                        "EXEC ${cost:.2} -> \"{label}\" {:?} {:.2} @ {:.3} // {:.0}ms",
                        r.intent.outcome, r.shares, r.avg_px, r.latency_ms
                    ),
                );
            }
            Action::Sell => {
                let m = self.markets.get_mut(&r.intent.slug).unwrap();
                let Some(pos) = m.pos.as_mut() else { return };
                let frac = (r.shares / pos.shares).min(1.0);
                let cost_part = pos.cost * frac;
                let proceeds = r.shares * r.avg_px - fee;
                pos.shares -= r.shares;
                pos.cost -= cost_part;
                if pos.shares < 0.01 {
                    m.pos = None;
                }
                self.cash += proceeds;
                self.close_trade(proceeds - cost_part, &label, "market converged", "adverse move");
            }
        }
    }

    // ---- internals --------------------------------------------------------

    fn book_mut(&mut self, token: &str) -> Option<(String, &mut Book)> {
        let (slug, outcome) = self.token_index.get(token)?.clone();
        let m = self.markets.get_mut(&slug)?;
        Some((slug, if outcome == Outcome::Up { &mut m.up } else { &mut m.down }))
    }

    fn close_trade(&mut self, pnl: f64, label: &str, win_note: &str, loss_note: &str) {
        self.day_realised += pnl;
        if pnl >= 0.0 {
            self.wins += 1;
            self.push_log("win", format!("FILLED +${pnl:.2} // {win_note} \"{label}\""));
        } else {
            self.losses += 1;
            self.push_log("loss", format!("LOSS -${:.2} // {loss_note} \"{label}\"", -pnl));
        }
    }

    fn push_log(&mut self, kind: &'static str, text: String) {
        if self.log.len() >= LOG_CAP {
            self.log.pop_front();
        }
        self.log.push_back(LogLine { ts_ms: self.now_ms, kind, text });
    }

    /// Cash plus open positions marked at the bid.
    pub fn equity(&self) -> f64 {
        self.cash
            + self
                .markets
                .values()
                .filter_map(|m| {
                    let p = m.pos.as_ref()?;
                    let book = if p.outcome == Outcome::Up { &m.up } else { &m.down };
                    Some(p.shares * book.best_bid().map_or(0.0, |b| b.0))
                })
                .sum::<f64>()
    }

    /// Premium currently at risk: open positions plus buy orders in flight.
    fn open_risk(&self) -> f64 {
        self.markets.values().map(|m| m.pos.as_ref().map_or(0.0, |p| p.cost) + m.in_flight_cost).sum()
    }

    /// Dollars of new premium the daily cap still allows.
    fn daily_budget_left(&self) -> f64 {
        let cap = self.cfg.daily_risk * self.day_start_equity;
        cap - (-self.day_realised).max(0.0) - self.open_risk()
    }

    fn advance(&mut self, ts_ms: i64) {
        if ts_ms > self.now_ms {
            self.now_ms = ts_ms;
        }
        let now = self.now_ms;

        // UTC day roll resets the daily risk budget.
        let day = now.div_euclid(86_400_000);
        if day != self.day {
            self.day = day;
            self.day_start_equity = self.equity();
            self.day_realised = 0.0;
            self.halted_logged = false;
        }

        // Paper fills whose simulated latency has elapsed.
        if !self.paper_queue.is_empty() {
            let (due, rest): (Vec<_>, Vec<_>) = std::mem::take(&mut self.paper_queue).into_iter().partition(|(t, _)| *t <= now);
            self.paper_queue = rest;
            for (_, intent) in due {
                let report = self.paper_fill(intent);
                self.on_fill(report);
            }
        }

        // Latch the reference price at window end, then settle.
        let mut settle = Vec::new();
        for m in self.markets.values_mut() {
            if now >= m.def.end_ms {
                if m.final_spot.is_none() && self.spot > 0.0 {
                    m.final_spot = Some(self.spot);
                }
                if !m.in_flight {
                    settle.push(m.def.slug.clone());
                }
            }
        }
        for slug in settle {
            self.settle(&slug);
        }

        if now - self.last_curve_ms >= 1000 {
            self.last_curve_ms = now;
            let eq = self.equity();
            if self.curve.len() >= CURVE_CAP {
                // Halve resolution instead of dropping history.
                let mut i = 0;
                self.curve.retain(|_| {
                    i += 1;
                    i % 2 == 0
                });
            }
            self.curve.push((now, eq));
        }
    }

    fn settle(&mut self, slug: &str) {
        let Some(m) = self.markets.remove(slug) else { return };
        self.token_index.remove(&m.def.up_token);
        self.token_index.remove(&m.def.down_token);
        let (Some(pos), Some(strike), Some(fin)) = (m.pos, m.strike, m.final_spot) else { return };
        let up_won = fin >= strike;
        let won = (pos.outcome == Outcome::Up) == up_won;
        let payout = if won { pos.shares } else { 0.0 };
        self.cash += payout;
        let note = format!("resolved {} (${fin:.2} vs ${strike:.2})", if up_won { "Up" } else { "Down" });
        self.close_trade(payout - pos.cost, &m.def.label, &note, &note);
    }

    fn paper_fill(&self, intent: OrderIntent) -> FillReport {
        let lat = (self.now_ms - intent.signal_ms) as f64;
        let (shares, avg_px) = match self.markets.get(&intent.slug) {
            Some(m) => {
                let book = if intent.outcome == Outcome::Up { &m.up } else { &m.down };
                match intent.action {
                    Action::Buy => book.take_asks(intent.limit, intent.shares),
                    Action::Sell => book.take_bids(intent.limit, intent.shares),
                }
            }
            None => (0.0, 0.0),
        };
        FillReport { intent, shares, avg_px, latency_ms: lat, error: None }
    }

    fn submit(&mut self, intent: OrderIntent) {
        match self.mode {
            Mode::Paper => self.paper_queue.push((self.now_ms + self.cfg.paper_latency_ms, intent)),
            Mode::Live => self.outbox.push(intent),
        }
    }

    /// Fair probability of Up for a market right now, if computable.
    fn fair_for(&self, m: &MarketState) -> Option<(f64, f64)> {
        let strike = m.strike?;
        if self.spot <= 0.0 || self.now_ms - self.spot_ms > self.cfg.max_spot_age_ms {
            return None;
        }
        let secs_left = (m.def.end_ms - self.now_ms) as f64 / 1000.0;
        if secs_left <= 0.0 || self.now_ms < m.def.start_ms {
            return None;
        }
        Some((fair_up(self.spot, strike, self.vol.sigma() * self.cfg.vol_mult, secs_left), secs_left))
    }

    fn evaluate(&mut self, slug: &str) {
        let now = self.now_ms;
        let cfg = &self.cfg;
        let Some(m) = self.markets.get(slug) else { return };
        if m.in_flight || now - m.last_order_ms < cfg.cooldown_ms {
            return;
        }
        let Some((fair_u, secs_left)) = self.fair_for(m) else { return };
        let fee = |p: f64| fee_per_share(p, cfg.fee_rate, cfg.fee_exponent);
        let fresh = |b: &Book| cfg.max_book_age_ms == 0 || now - b.updated_ms <= cfg.max_book_age_ms;

        let intent = if let Some(pos) = &m.pos {
            // Exit once the market has caught up with (or overshot) fair value.
            let (book, fair, token) = match pos.outcome {
                Outcome::Up => (&m.up, fair_u, &m.def.up_token),
                Outcome::Down => (&m.down, 1.0 - fair_u, &m.def.down_token),
            };
            let Some((bid, _)) = book.best_bid() else { return };
            if !fresh(book) || bid - fee(bid) < fair - cfg.exit_edge || pos.shares < m.def.min_size {
                return;
            }
            OrderIntent {
                slug: slug.to_owned(),
                token: token.clone(),
                outcome: pos.outcome,
                action: Action::Sell,
                shares: pos.shares,
                limit: (bid - cfg.slippage_ticks * m.def.tick).max(m.def.tick),
                signal_ms: now,
            }
        } else {
            let elapsed = (now - m.def.start_ms) as f64 / 1000.0;
            if secs_left < cfg.min_secs_left || elapsed < cfg.min_secs_elapsed {
                return;
            }
            // Best side by net edge.
            let mut best: Option<(f64, Outcome, f64, f64)> = None;
            for (outcome, book, fair) in [(Outcome::Up, &m.up, fair_u), (Outcome::Down, &m.down, 1.0 - fair_u)] {
                let Some((ask, size)) = book.best_ask() else { continue };
                if !fresh(book) || ask < cfg.min_price || ask > cfg.max_price {
                    continue;
                }
                let edge = fair - ask - fee(ask);
                if edge >= cfg.min_edge && best.as_ref().is_none_or(|b| edge > b.0) {
                    best = Some((edge, outcome, ask, size));
                }
            }
            let Some((edge, outcome, ask, avail)) = best else { return };

            // Risk: premium paid is the max loss.
            let equity = self.equity();
            let budget = (cfg.risk_per_trade * equity).min(self.daily_budget_left()).min(self.cash);
            let limit = (ask + cfg.slippage_ticks * m.def.tick).min(0.99);
            let per_share = limit + fee(limit);
            let shares = ((budget / per_share).min(avail) * 100.0).floor() / 100.0;
            if shares < m.def.min_size || shares * ask < cfg.min_order_usd {
                if self.daily_budget_left() < m.def.min_size * per_share && !self.halted_logged {
                    self.halted_logged = true;
                    let used = cfg.daily_risk * 100.0;
                    self.push_log("warn", format!("daily risk cap ({used:.1}%) reached - no new entries until 00:00 UTC"));
                }
                return;
            }
            let fair = if outcome == Outcome::Up { fair_u } else { 1.0 - fair_u };
            let label = m.def.label.clone();
            let token = if outcome == Outcome::Up { m.def.up_token.clone() } else { m.def.down_token.clone() };
            self.push_log(
                "signal",
                format!("+{:.1}c edge -> \"{label}\" {outcome:?} CLOB @ {ask:.2} | fair {fair:.3} | {secs_left:.0}s left", edge * 100.0),
            );
            OrderIntent { slug: slug.to_owned(), token, outcome, action: Action::Buy, shares, limit, signal_ms: now }
        };

        let fee_rate = (self.cfg.fee_rate, self.cfg.fee_exponent);
        let m = self.markets.get_mut(slug).unwrap();
        m.in_flight = true;
        m.last_order_ms = now;
        if intent.action == Action::Buy {
            m.in_flight_cost = intent.shares * (intent.limit + fee_per_share(intent.limit, fee_rate.0, fee_rate.1));
        }
        self.submit(intent);
    }

    // ---- reporting --------------------------------------------------------

    pub fn snapshot(&self) -> Snapshot {
        let equity = self.equity();
        // Headline market: the one ending soonest that has started.
        let head = self
            .markets
            .values()
            .filter(|m| self.now_ms >= m.def.start_ms && self.now_ms < m.def.end_ms)
            .min_by_key(|m| m.def.end_ms);
        let (mut market, mut secs_left, mut strike, mut mid, mut fair, mut edge) = (String::new(), 0.0, 0.0, 0.0, 0.0, 0.0);
        if let Some(m) = head {
            market = m.def.label.clone();
            secs_left = (m.def.end_ms - self.now_ms) as f64 / 1000.0;
            strike = m.strike.unwrap_or(0.0);
            mid = m.up.mid().unwrap_or(0.0);
            if let Some((f, _)) = self.fair_for(m) {
                fair = f;
                let fee = |p: f64| fee_per_share(p, self.cfg.fee_rate, self.cfg.fee_exponent);
                let e_up = m.up.best_ask().map(|a| f - a.0 - fee(a.0));
                let e_dn = m.down.best_ask().map(|a| 1.0 - f - a.0 - fee(a.0));
                edge = e_up.into_iter().chain(e_dn).fold(f64::NEG_INFINITY, f64::max);
                if !edge.is_finite() {
                    edge = 0.0;
                }
            }
        }
        let cap = self.cfg.daily_risk * self.day_start_equity;
        Snapshot {
            mode: match self.mode {
                Mode::Paper => "PAPER".into(),
                Mode::Live => "LIVE".into(),
            },
            now_ms: self.now_ms,
            started_ms: self.started_ms,
            seed: self.seed,
            equity,
            cash: self.cash,
            total_pnl: equity - self.seed,
            daily_pnl: equity - self.day_start_equity,
            risk_used: if cap > 0.0 { ((cap - self.daily_budget_left()) / cap).clamp(0.0, 1.0) } else { 0.0 },
            wins: self.wins,
            losses: self.losses,
            trades: self.wins + self.losses,
            missed: self.missed,
            fees_paid: self.fees_paid,
            latency_ms: self.latency_ewma,
            spot: self.spot,
            vol_annual: self.vol.annualised(),
            market,
            secs_left,
            strike,
            clob_mid: mid,
            fair,
            edge,
            open_positions: self.markets.values().filter(|m| m.pos.is_some()).count() as u32,
            feeds: self.feeds.clone(),
            equity_curve: self.curve.clone(),
            log: self.log.iter().rev().take(60).cloned().collect(),
        }
    }
}
