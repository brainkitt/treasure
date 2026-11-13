//! Polymarket I/O via the official Rust SDK: market discovery (Gamma),
//! order books (CLOB WebSocket), the Chainlink reference price (RTDS) and
//! live order placement (CLOB REST).

use std::collections::HashSet;
use std::str::FromStr as _;
use std::time::{Duration, Instant};

use anyhow::Context as _;
use futures::StreamExt as _;
use polymarket_client_sdk::auth::{LocalSigner, Signer as _};
use polymarket_client_sdk::clob::types::{OrderType, Side, SignatureType};
use polymarket_client_sdk::gamma::types::request::MarketBySlugRequest;
use polymarket_client_sdk::types::{Address, Decimal, U256};
use polymarket_client_sdk::{POLYGON, PRIVATE_KEY_VAR, clob, gamma, rtds};
use tokio::sync::mpsc::{Receiver, Sender};

use crate::book::BookSide;
use crate::config::Config;
use crate::engine::{Action, FillReport, MarketDef, OrderIntent};
use crate::run::{Event, now_ms};

fn f(d: Decimal) -> f64 {
    f64::try_from(d).unwrap_or(0.0)
}

/// Slug of the BTC up/down market for a window, e.g. `btc-updown-15m-1763068500`.
pub fn updown_slug(minutes: u32, start_s: i64) -> String {
    format!("btc-updown-{minutes}m-{start_s}")
}

/// Poll Gamma for the current and next window of every configured interval.
pub async fn discover(cfg: Config, tx: Sender<Event>) {
    let client = gamma::Client::default();
    let mut seen: HashSet<String> = HashSet::new();
    loop {
        let now_s = now_ms() / 1000;
        for &mins in &cfg.intervals_min {
            let step = i64::from(mins) * 60;
            let cur = now_s.div_euclid(step) * step;
            for start in [cur, cur + step] {
                let slug = updown_slug(mins, start);
                if seen.contains(&slug) {
                    continue;
                }
                let req = MarketBySlugRequest::builder().slug(slug.clone()).build();
                match client.market_by_slug(&req).await {
                    Ok(m) => match market_def(&slug, mins, start, &m) {
                        Ok(def) => {
                            seen.insert(slug);
                            if tx.send(Event::Market(def)).await.is_err() {
                                return;
                            }
                        }
                        Err(e) => tracing::warn!(%slug, "unusable market: {e:#}"),
                    },
                    Err(e) => tracing::debug!(%slug, "not listed yet: {e}"),
                }
            }
        }
        seen.retain(|s| s.rsplit('-').next().and_then(|t| t.parse::<i64>().ok()).is_some_and(|t| t > now_s - 7200));
        tokio::time::sleep(Duration::from_secs(15)).await;
    }
}

fn market_def(slug: &str, mins: u32, start_s: i64, m: &gamma::types::response::Market) -> anyhow::Result<MarketDef> {
    let outcomes = m.outcomes.as_ref().context("no outcomes")?;
    let tokens = m.clob_token_ids.as_ref().context("no clob token ids")?;
    let idx = |name: &str| outcomes.iter().position(|o| o.eq_ignore_ascii_case(name)).with_context(|| format!("no {name} outcome"));
    let (up, down) = (idx("Up")?, idx("Down")?);
    anyhow::ensure!(tokens.len() > up.max(down), "token/outcome mismatch");
    let hhmm = chrono::DateTime::from_timestamp(start_s, 0).map(|d| d.format("%H:%M").to_string()).unwrap_or_default();
    Ok(MarketDef {
        slug: slug.to_owned(),
        label: format!("BTC Up/Down {mins}m {hhmm} UTC"),
        up_token: tokens[up].to_string(),
        down_token: tokens[down].to_string(),
        start_ms: start_s * 1000,
        end_ms: (start_s + i64::from(mins) * 60) * 1000,
        tick: m.order_price_min_tick_size.map(f).filter(|t| *t > 0.0).unwrap_or(0.01),
        min_size: m.order_min_size.map(f).filter(|s| *s > 0.0).unwrap_or(5.0),
    })
}

/// Stream both outcome books of one market until its window has ended.
pub async fn stream_books(ws: clob::ws::Client, def: MarketDef, tx: Sender<Event>) {
    let (Ok(up), Ok(down)) = (U256::from_str(&def.up_token), U256::from_str(&def.down_token)) else {
        tracing::warn!(slug = %def.slug, "bad token id");
        return;
    };
    let ids = vec![up, down];
    let (snaps, changes) = match (ws.subscribe_orderbook(ids.clone()), ws.subscribe_prices(ids.clone())) {
        (Ok(a), Ok(b)) => (a, b),
        (Err(e), _) | (_, Err(e)) => {
            tracing::warn!(slug = %def.slug, "book subscription failed: {e}");
            return;
        }
    };
    let (mut snaps, mut changes) = (Box::pin(snaps), Box::pin(changes));
    let deadline = tokio::time::sleep(Duration::from_millis((def.end_ms - now_ms() + 5000).max(0) as u64));
    tokio::pin!(deadline);
    loop {
        let ev = tokio::select! {
            () = &mut deadline => break,
            Some(s) = snaps.next() => match s {
                Ok(b) => vec![Event::BookSnap {
                    token: b.asset_id.to_string(),
                    bids: b.bids.iter().map(|l| (f(l.price), f(l.size))).collect(),
                    asks: b.asks.iter().map(|l| (f(l.price), f(l.size))).collect(),
                }],
                Err(e) => { tracing::debug!("book stream: {e}"); continue }
            },
            Some(c) = changes.next() => match c {
                Ok(c) => c.price_changes.iter().filter_map(|e| Some(Event::BookLevel {
                    token: e.asset_id.to_string(),
                    side: match e.side { Side::Buy => BookSide::Bid, Side::Sell => BookSide::Ask, _ => return None },
                    price: f(e.price),
                    size: f(e.size?),
                })).collect(),
                Err(e) => { tracing::debug!("price stream: {e}"); continue }
            },
            else => break,
        };
        for e in ev {
            if tx.send(e).await.is_err() {
                return;
            }
        }
    }
    let _ = ws.unsubscribe_orderbook(&ids);
    let _ = ws.unsubscribe_prices(&ids);
}

/// Chainlink BTC/USD stream - the price these markets resolve against.
pub async fn chainlink(tx: Sender<Event>) {
    let client = rtds::Client::default();
    loop {
        match client.subscribe_chainlink_prices(Some("btc/usd".to_owned())) {
            Ok(stream) => {
                let mut stream = Box::pin(stream);
                while let Ok(Some(item)) = tokio::time::timeout(Duration::from_secs(30), stream.next()).await {
                    match item {
                        Ok(p) => {
                            if tx.send(Event::Chainlink { ts_ms: p.timestamp, px: f(p.value) }).await.is_err() {
                                return;
                            }
                        }
                        Err(e) => tracing::debug!("chainlink stream: {e}"),
                    }
                }
                tracing::warn!("chainlink stream stalled; resubscribing");
                let _ = client.unsubscribe_chainlink_prices();
            }
            Err(e) => tracing::warn!("chainlink subscribe failed: {e}"),
        }
        tokio::time::sleep(Duration::from_secs(2)).await;
    }
}

pub enum ExecMsg {
    /// Pre-fetch tick size / neg-risk / fee rate so the first order is fast.
    Warm(Vec<String>),
    Order(OrderIntent, Instant),
}

fn dec(x: f64, dp: usize) -> anyhow::Result<Decimal> {
    Ok(format!("{x:.dp$}").parse::<Decimal>()?.normalize())
}

fn decimals(tick: f64) -> usize {
    (-tick.log10()).round().clamp(1.0, 4.0) as usize
}

/// Live order executor. Each intent becomes one fill-and-kill limit order.
pub async fn live_executor(cfg: Config, mut rx: Receiver<ExecMsg>, tx: Sender<Event>) -> anyhow::Result<()> {
    let key = std::env::var(PRIVATE_KEY_VAR).with_context(|| format!("{PRIVATE_KEY_VAR} is not set"))?;
    let signer = LocalSigner::from_str(key.trim())
        .map_err(|_| anyhow::anyhow!("{PRIVATE_KEY_VAR} is not a valid private key"))?
        .with_chain_id(Some(POLYGON));
    let base = clob::Client::new(&cfg.live.clob_host, clob::Config::default())?;
    let mut auth = base.authentication_builder(&signer);
    if let Some(funder) = &cfg.live.funder {
        auth = auth.funder(Address::from_str(funder).context("live.funder is not an address")?);
    }
    auth = auth.signature_type(match cfg.live.signature_type {
        0 => SignatureType::Eoa,
        1 => SignatureType::Proxy,
        2 => SignatureType::GnosisSafe,
        n => anyhow::bail!("live.signature_type {n} is not 0, 1 or 2"),
    });
    let client = auth.authenticate().await.context("CLOB authentication failed")?;
    tracing::info!("live executor authenticated as {}", signer.address());

    while let Some(msg) = rx.recv().await {
        let (client, signer, tx) = (client.clone(), signer.clone(), tx.clone());
        match msg {
            ExecMsg::Warm(tokens) => {
                tokio::spawn(async move {
                    for t in tokens.iter().filter_map(|t| U256::from_str(t).ok()) {
                        let _ = client.tick_size(t).await;
                        let _ = client.neg_risk(t).await;
                        let _ = client.fee_rate_bps(t).await;
                    }
                });
            }
            ExecMsg::Order(intent, t0) => {
                tokio::spawn(async move {
                    let res = async {
                        let tick = f(client.tick_size(U256::from_str(&intent.token)?).await?.minimum_tick_size.as_decimal());
                        let order = client
                            .limit_order()
                            .token_id(U256::from_str(&intent.token)?)
                            .side(if intent.action == Action::Buy { Side::Buy } else { Side::Sell })
                            .order_type(OrderType::FAK)
                            .price(dec(intent.limit, decimals(tick))?)
                            .size(dec((intent.shares * 100.0).floor() / 100.0, 2)?)
                            .build()
                            .await?;
                        let signed = client.sign(&signer, order).await?;
                        anyhow::Ok(client.post_order(signed).await?)
                    }
                    .await;
                    let latency_ms = t0.elapsed().as_secs_f64() * 1000.0;
                    let report = match res {
                        Ok(r) => {
                            // Buy: maker gives USDC, takes shares. Sell: the reverse.
                            let (shares, usdc) = match intent.action {
                                Action::Buy => (f(r.taking_amount), f(r.making_amount)),
                                Action::Sell => (f(r.making_amount), f(r.taking_amount)),
                            };
                            let error = (!r.success).then(|| r.error_msg.clone().unwrap_or_else(|| format!("{:?}", r.status)));
                            let avg_px = if shares > 0.0 { usdc / shares } else { 0.0 };
                            FillReport { intent, shares, avg_px, latency_ms, error }
                        }
                        Err(e) => FillReport { intent, shares: 0.0, avg_px: 0.0, latency_ms, error: Some(format!("{e:#}")) },
                    };
                    let _ = tx.send(Event::Fill(report)).await;
                });
            }
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn slug_and_rounding() {
        assert_eq!(updown_slug(15, 1_763_068_500), "btc-updown-15m-1763068500");
        assert_eq!(decimals(0.01), 2);
        assert_eq!(decimals(0.001), 3);
        assert_eq!(dec(0.53, 2).unwrap().to_string(), "0.53");
        assert_eq!(dec(12.5, 2).unwrap().to_string(), "12.5");
    }
}
