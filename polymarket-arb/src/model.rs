//! Fair-value model for "BTC Up or Down" binary markets.
//!
//! A market resolves Up when the reference price at window end is >= the
//! reference price at window start (the strike). Treating log-returns as
//! driftless Gaussian over the remaining seconds, the fair probability is
//! Phi(ln(S/K) / (sigma * sqrt(tau))).

/// Standard normal CDF (Abramowitz & Stegun 7.1.26, |err| < 1.5e-7).
pub fn norm_cdf(x: f64) -> f64 {
    let z = x.abs() / std::f64::consts::SQRT_2;
    let t = 1.0 / (1.0 + 0.327_591_1 * z);
    let poly = t
        * (0.254_829_592
            + t * (-0.284_496_736 + t * (1.421_413_741 + t * (-1.453_152_027 + t * 1.061_405_429))));
    let erf = 1.0 - poly * (-z * z).exp();
    if x >= 0.0 { 0.5 * (1.0 + erf) } else { 0.5 * (1.0 - erf) }
}

/// Probability that the market resolves Up. `sigma` is volatility per sqrt(second).
pub fn fair_up(spot: f64, strike: f64, sigma: f64, secs_left: f64) -> f64 {
    if spot <= 0.0 || strike <= 0.0 {
        return 0.5;
    }
    let tau = secs_left.max(0.0);
    let denom = sigma * tau.sqrt();
    if denom < 1e-12 {
        return if spot >= strike { 1.0 } else { 0.0 };
    }
    norm_cdf((spot / strike).ln() / denom)
}

/// Polymarket taker fee per share, in USDC, for a fill at price `p`:
/// `fee_rate * p * (p * (1 - p))^exponent`. With the crypto-market
/// parameters (0.25, 2) this peaks at 1.56% of notional at p = 0.50.
pub fn fee_per_share(p: f64, fee_rate: f64, exponent: f64) -> f64 {
    if fee_rate <= 0.0 {
        return 0.0;
    }
    fee_rate * p * (p * (1.0 - p)).max(0.0).powf(exponent)
}

/// EWMA realized-volatility estimator on ~1s samples.
#[derive(Debug, Clone)]
pub struct VolEstimator {
    last_px: f64,
    last_ts_ms: i64,
    var_per_s: f64,
    lambda: f64,
    floor: f64,
}

impl VolEstimator {
    /// `init_annual` seeds the estimate (e.g. 0.5 = 50% annualised);
    /// `halflife_s` is the EWMA half-life; `floor_annual` bounds it below.
    pub fn new(init_annual: f64, halflife_s: f64, floor_annual: f64) -> Self {
        let per_s = |a: f64| a / (365.25f64 * 86_400.0).sqrt();
        Self {
            last_px: 0.0,
            last_ts_ms: 0,
            var_per_s: per_s(init_annual).powi(2),
            lambda: 0.5f64.powf(1.0 / halflife_s.max(1.0)),
            floor: per_s(floor_annual),
        }
    }

    pub fn update(&mut self, ts_ms: i64, px: f64) {
        if self.last_px <= 0.0 {
            self.last_px = px;
            self.last_ts_ms = ts_ms;
            return;
        }
        let dt_ms = ts_ms - self.last_ts_ms;
        if dt_ms < 1000 {
            return;
        }
        let dt = dt_ms as f64 / 1000.0;
        let r = (px / self.last_px).ln();
        // Skip samples across long gaps (reconnects) so they don't pollute the estimate.
        if dt < 30.0 {
            let w = self.lambda.powf(dt);
            self.var_per_s = w * self.var_per_s + (1.0 - w) * r * r / dt;
        }
        self.last_px = px;
        self.last_ts_ms = ts_ms;
    }

    /// Volatility per sqrt(second).
    pub fn sigma(&self) -> f64 {
        self.var_per_s.sqrt().max(self.floor)
    }

    pub fn annualised(&self) -> f64 {
        self.sigma() * (365.25f64 * 86_400.0).sqrt()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn cdf_known_values() {
        assert!((norm_cdf(0.0) - 0.5).abs() < 1e-7);
        assert!((norm_cdf(1.0) - 0.841_344_7).abs() < 1e-6);
        assert!((norm_cdf(-1.96) - 0.024_997_9).abs() < 1e-6);
    }

    #[test]
    fn fair_behaves() {
        assert!((fair_up(100.0, 100.0, 1e-4, 300.0) - 0.5).abs() < 1e-9);
        assert!(fair_up(100.3, 100.0, 1e-4, 300.0) > 0.95);
        assert!(fair_up(99.7, 100.0, 1e-4, 300.0) < 0.05);
        assert_eq!(fair_up(100.1, 100.0, 1e-4, 0.0), 1.0);
        assert_eq!(fair_up(99.9, 100.0, 1e-4, 0.0), 0.0);
        // Less time left => same move is more decisive.
        assert!(fair_up(100.1, 100.0, 1e-4, 30.0) > fair_up(100.1, 100.0, 1e-4, 600.0));
    }

    #[test]
    fn fee_peaks_at_half() {
        let f = fee_per_share(0.5, 0.25, 2.0);
        assert!((f - 0.007_812_5).abs() < 1e-12); // 1.5625% of 0.50
        assert!(fee_per_share(0.9, 0.25, 2.0) < f);
        assert_eq!(fee_per_share(0.5, 0.0, 2.0), 0.0);
    }

    #[test]
    fn vol_tracks_realised() {
        let mut v = VolEstimator::new(0.5, 60.0, 0.05);
        let mut px = 100_000.0;
        // +-1bp every second => sigma = 1e-4 per sqrt(s)
        for i in 0..2000 {
            px *= if i % 2 == 0 { 1.0001 } else { 1.0 / 1.0001 };
            v.update(i * 1000, px);
        }
        assert!((v.sigma() - 1e-4).abs() < 5e-6, "{}", v.sigma());
    }
}
