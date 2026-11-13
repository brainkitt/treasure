//! Local limit order book for one outcome token.

use std::collections::BTreeMap;

const SCALE: f64 = 10_000.0;

fn key(p: f64) -> i64 {
    (p * SCALE).round() as i64
}

#[derive(Debug, Clone, Default)]
pub struct Book {
    bids: BTreeMap<i64, f64>,
    asks: BTreeMap<i64, f64>,
    pub updated_ms: i64,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum BookSide {
    Bid,
    Ask,
}

impl Book {
    pub fn set_snapshot(&mut self, bids: &[(f64, f64)], asks: &[(f64, f64)], ts_ms: i64) {
        self.bids = bids.iter().filter(|l| l.1 > 0.0).map(|l| (key(l.0), l.1)).collect();
        self.asks = asks.iter().filter(|l| l.1 > 0.0).map(|l| (key(l.0), l.1)).collect();
        self.updated_ms = ts_ms;
    }

    /// Set the resting size at one price level (0 removes it).
    pub fn set_level(&mut self, side: BookSide, price: f64, size: f64, ts_ms: i64) {
        let m = match side {
            BookSide::Bid => &mut self.bids,
            BookSide::Ask => &mut self.asks,
        };
        if size > 0.0 {
            m.insert(key(price), size);
        } else {
            m.remove(&key(price));
        }
        self.updated_ms = ts_ms;
    }

    pub fn best_bid(&self) -> Option<(f64, f64)> {
        self.bids.iter().next_back().map(|(k, s)| (*k as f64 / SCALE, *s))
    }

    pub fn best_ask(&self) -> Option<(f64, f64)> {
        self.asks.iter().next().map(|(k, s)| (*k as f64 / SCALE, *s))
    }

    pub fn mid(&self) -> Option<f64> {
        Some((self.best_bid()?.0 + self.best_ask()?.0) / 2.0)
    }

    /// Simulate an immediate-or-cancel buy: take asks priced <= `limit` for up
    /// to `shares`. Returns (filled shares, average price). Does not mutate.
    pub fn take_asks(&self, limit: f64, shares: f64) -> (f64, f64) {
        walk(self.asks.iter().take_while(|(k, _)| **k <= key(limit)), shares)
    }

    /// Simulate an immediate-or-cancel sell into bids priced >= `limit`.
    pub fn take_bids(&self, limit: f64, shares: f64) -> (f64, f64) {
        walk(self.bids.iter().rev().take_while(|(k, _)| **k >= key(limit)), shares)
    }
}

fn walk<'a>(levels: impl Iterator<Item = (&'a i64, &'a f64)>, shares: f64) -> (f64, f64) {
    let (mut filled, mut notional) = (0.0, 0.0);
    for (k, size) in levels {
        let take = size.min(shares - filled);
        if take <= 0.0 {
            break;
        }
        filled += take;
        notional += take * (*k as f64 / SCALE);
    }
    if filled > 0.0 { (filled, notional / filled) } else { (0.0, 0.0) }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn best_levels_and_walk() {
        let mut b = Book::default();
        b.set_snapshot(&[(0.48, 100.0), (0.47, 50.0)], &[(0.50, 30.0), (0.51, 100.0)], 1);
        assert_eq!(b.best_bid(), Some((0.48, 100.0)));
        assert_eq!(b.best_ask(), Some((0.50, 30.0)));
        let (f, px) = b.take_asks(0.51, 50.0);
        assert_eq!(f, 50.0);
        assert!((px - (30.0 * 0.50 + 20.0 * 0.51) / 50.0).abs() < 1e-12);
        // Limit excludes the second level.
        assert_eq!(b.take_asks(0.50, 50.0).0, 30.0);
        assert_eq!(b.take_bids(0.48, 500.0).0, 100.0);
        b.set_level(BookSide::Ask, 0.50, 0.0, 2);
        assert_eq!(b.best_ask(), Some((0.51, 100.0)));
    }
}
