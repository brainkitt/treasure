//! Offline simulation: synthetic BTC path plus a market maker whose quotes
//! lag spot by a configurable delay. Runs the real engine with a virtual
//! clock. This tests the mechanics; it is not a forecast of live results.

use std::collections::VecDeque;

use crate::config::Config;
use crate::engine::{Engine, MarketDef, Mode};
use crate::model::fair_up;

#[derive(Debug, Clone)]
pub struct SimParams {
    pub hours: f64,
    /// How far the simulated market maker's quotes trail spot.
    pub lag_ms: i64,
    pub seed: u64,
    pub vol_annual: f64,
    pub half_spread: f64,
    pub depth: f64,
    pub jumps_per_hour: f64,
    pub jump_bps: f64,
    pub window_min: i64,
}

impl Default for SimParams {
    fn default() -> Self {
        Self {
            hours: 24.0,
            lag_ms: 500,
            seed: 7,
            vol_annual: 0.55,
            half_spread: 0.01,
            depth: 300.0,
            jumps_per_hour: 6.0,
            jump_bps: 8.0,
            window_min: 5,
        }
    }
}

struct Rng(u64);

impl Rng {
    fn unit(&mut self) -> f64 {
        // xorshift64*
        self.0 ^= self.0 >> 12;
        self.0 ^= self.0 << 25;
        self.0 ^= self.0 >> 27;
        (self.0.wrapping_mul(0x2545_F491_4F6C_DD1D) >> 11) as f64 / (1u64 << 53) as f64
    }

    fn normal(&mut self) -> f64 {
        let (u1, u2) = (self.unit().max(1e-300), self.unit());
        (-2.0 * u1.ln()).sqrt() * (std::f64::consts::TAU * u2).cos()
    }
}

pub fn run(cfg: Config, p: &SimParams) -> Engine {
    const DT_MS: i64 = 10;
    let t0: i64 = 1_800_000_000_000; // arbitrary epoch, aligned to window boundaries
    let window_ms = p.window_min * 60_000;
    let end = t0 + (p.hours * 3_600_000.0) as i64;
    let sigma = p.vol_annual / (365.25f64 * 86_400.0).sqrt();
    let step_sd = sigma * (DT_MS as f64 / 1000.0).sqrt();
    let jump_prob = p.jumps_per_hour * DT_MS as f64 / 3_600_000.0;

    let mut rng = Rng(p.seed.max(1).wrapping_mul(0x9E37_79B9_7F4A_7C15));
    let mut engine = Engine::new(cfg, Mode::Paper, t0);
    let mut spot = 100_000.0;
    let mut hist: VecDeque<(i64, f64)> = VecDeque::new();
    let mut cur: Option<(MarketDef, f64)> = None;

    let mut t = t0;
    while t < end {
        spot *= (step_sd * rng.normal()).exp();
        if rng.unit() < jump_prob {
            let sign = if rng.unit() < 0.5 { -1.0 } else { 1.0 };
            spot *= (sign * p.jump_bps * 1e-4 * (0.5 + rng.unit())).exp();
        }
        hist.push_back((t, spot));
        while hist.front().is_some_and(|h| h.0 < t - p.lag_ms) {
            hist.pop_front();
        }

        if (t - t0) % window_ms == 0 {
            let n = (t - t0) / window_ms;
            let def = MarketDef {
                slug: format!("sim-{n}"),
                label: format!("BTC Up/Down {}m #{n}", p.window_min),
                up_token: format!("up-{n}"),
                down_token: format!("down-{n}"),
                start_ms: t,
                end_ms: t + window_ms,
                tick: 0.01,
                min_size: 5.0,
            };
            engine.add_market(def.clone(), Some(spot));
            cur = Some((def, spot));
        }

        if (t - t0) % 50 == 0 {
            engine.on_spot(t, spot);
        }

        if (t - t0) % 100 == 0
            && let Some((def, strike)) = &cur {
                let lagged = hist.front().map_or(spot, |h| h.1);
                let secs_left = (def.end_ms - t) as f64 / 1000.0;
                let f = fair_up(lagged, *strike, sigma, secs_left);
                let bid = (((f - p.half_spread) * 100.0).floor() / 100.0).clamp(0.01, 0.98);
                let ask = (((f + p.half_spread) * 100.0).ceil() / 100.0).clamp(bid + 0.01, 0.99);
                engine.on_book_snapshot(t, &def.up_token, &[(bid, p.depth)], &[(ask, p.depth)]);
                engine.on_book_snapshot(t, &def.down_token, &[(1.0 - ask, p.depth)], &[(1.0 - bid, p.depth)]);
            }

        engine.on_timer(t);
        t += DT_MS;
    }
    engine.on_spot(end, spot);
    engine.on_timer(end + 1000);
    engine
}

#[cfg(test)]
mod tests {
    use super::*;

    fn params(lag_ms: i64) -> SimParams {
        SimParams { hours: 6.0, lag_ms, ..SimParams::default() }
    }

    #[test]
    fn lagging_market_is_profitable() {
        let s = run(Config::default(), &params(800)).snapshot();
        assert!(s.trades > 20, "trades {}", s.trades);
        assert!(s.total_pnl > 0.0, "pnl {}", s.total_pnl);
    }

    #[test]
    fn efficient_market_gives_no_edge() {
        // No lag and no jumps: the quotes already equal fair value, so
        // nothing clears the edge threshold after fees and spread.
        let p = SimParams { jumps_per_hour: 0.0, ..params(0) };
        let s = run(Config::default(), &p).snapshot();
        assert!(s.trades <= 3, "trades {}", s.trades);
        assert!(s.total_pnl.abs() <= 3.0 * 5.0, "pnl {}", s.total_pnl); // <= 3 trades x 0.5% risk
    }

    #[test]
    fn daily_risk_cap_bounds_losses() {
        // Bot believes a wildly wrong volatility => bad fair values => losses.
        let cfg = Config { vol_mult: 0.05, min_edge: 0.01, ..Config::default() };
        let s = run(cfg.clone(), &params(0)).snapshot();
        let cap = cfg.daily_risk * cfg.bankroll;
        assert!(s.total_pnl >= -cap - 1e-6, "lost {} > cap {}", -s.total_pnl, cap);
    }
}
