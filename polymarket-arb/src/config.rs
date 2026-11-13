//! Configuration (TOML file, every field optional).

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct Config {
    /// Starting bankroll in USDC (paper mode) / assumed bankroll (live mode).
    pub bankroll: f64,
    /// Minimum edge per share after fees, in dollars of a $1 payout, to enter.
    pub min_edge: f64,
    /// Exit once the bid (net of fees) is within this of fair value.
    pub exit_edge: f64,
    /// Max fraction of equity put at risk on one trade (premium paid = max loss).
    pub risk_per_trade: f64,
    /// Max fraction of start-of-day equity at risk per UTC day
    /// (realised losses + premium of open positions).
    pub daily_risk: f64,
    /// Only enter when the ask is inside [min_price, max_price].
    pub min_price: f64,
    pub max_price: f64,
    /// Do not open positions with fewer seconds than this left in the window.
    pub min_secs_left: f64,
    /// Do not open positions in the first seconds of a window.
    pub min_secs_elapsed: f64,
    /// Ticks of slippage allowed on the limit price of the taker order.
    pub slippage_ticks: f64,
    /// Minimum time between order attempts in one market.
    pub cooldown_ms: i64,
    /// Ignore order books older than this (0 disables the check).
    pub max_book_age_ms: i64,
    /// Ignore the spot composite when older than this.
    pub max_spot_age_ms: i64,
    /// Taker-fee curve: fee/share = fee_rate * p * (p(1-p))^fee_exponent.
    pub fee_rate: f64,
    pub fee_exponent: f64,
    /// Polymarket minimums.
    pub min_order_usd: f64,
    /// Volatility estimator.
    pub vol_init_annual: f64,
    pub vol_floor_annual: f64,
    pub vol_halflife_s: f64,
    /// Multiplier on estimated volatility (>1 = more conservative fair values).
    pub vol_mult: f64,
    /// Simulated feed->fill latency for paper trading.
    pub paper_latency_ms: i64,
    /// Window lengths to trade, in minutes (Polymarket lists 5 and 15).
    pub intervals_min: Vec<u32>,
    /// Spot feeds to use: binance, coinbase, kraken, okx.
    pub feeds: Vec<String>,
    /// Dashboard listen address.
    pub dashboard_addr: String,
    pub live: Live,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct Live {
    pub clob_host: String,
    /// 0 = EOA, 1 = Polymarket proxy (email login), 2 = Gnosis Safe (browser wallet).
    pub signature_type: u8,
    /// Address holding the funds when signature_type != 0.
    pub funder: Option<String>,
}

impl Default for Config {
    fn default() -> Self {
        Self {
            bankroll: 1000.0,
            min_edge: 0.03,
            exit_edge: 0.005,
            risk_per_trade: 0.005,
            daily_risk: 0.02,
            min_price: 0.05,
            max_price: 0.95,
            min_secs_left: 10.0,
            min_secs_elapsed: 5.0,
            slippage_ticks: 1.0,
            cooldown_ms: 1500,
            max_book_age_ms: 0,
            max_spot_age_ms: 3000,
            fee_rate: 0.25,
            fee_exponent: 2.0,
            min_order_usd: 1.0,
            vol_init_annual: 0.5,
            vol_floor_annual: 0.15,
            vol_halflife_s: 300.0,
            vol_mult: 1.0,
            paper_latency_ms: 80,
            intervals_min: vec![5, 15],
            feeds: ["binance", "coinbase", "kraken", "okx"].map(String::from).to_vec(),
            dashboard_addr: "127.0.0.1:8787".into(),
            live: Live::default(),
        }
    }
}

impl Default for Live {
    fn default() -> Self {
        Self { clob_host: "https://clob.polymarket.com".into(), signature_type: 0, funder: None }
    }
}

impl Config {
    pub fn load(path: Option<&str>) -> anyhow::Result<Self> {
        let cfg: Config = match path {
            Some(p) => toml::from_str(&std::fs::read_to_string(p)?)?,
            None => match std::fs::read_to_string("config.toml") {
                Ok(s) => toml::from_str(&s)?,
                Err(_) => Config::default(),
            },
        };
        cfg.validate()?;
        Ok(cfg)
    }

    pub fn validate(&self) -> anyhow::Result<()> {
        anyhow::ensure!(self.bankroll > 0.0, "bankroll must be positive");
        anyhow::ensure!(self.min_edge > 0.0, "min_edge must be positive");
        anyhow::ensure!(
            self.risk_per_trade > 0.0 && self.risk_per_trade <= self.daily_risk,
            "need 0 < risk_per_trade <= daily_risk"
        );
        anyhow::ensure!(self.daily_risk <= 1.0, "daily_risk is a fraction (0.02 = 2%)");
        anyhow::ensure!(self.min_price < self.max_price, "min_price must be < max_price");
        Ok(())
    }
}
