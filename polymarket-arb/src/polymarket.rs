//! Polymarket I/O: market discovery (Gamma) and live order placement (CLOB
//! REST) through the official Rust SDK; order books (CLOB WebSocket) and the
//! Chainlink reference prices (RTDS WebSocket) through our own sockets.

use std::collections::HashSet;
use std::str::FromStr as _;
use std::time::{Duration, Instant};

use anyhow::Context as _;
use futures::{SinkExt as _, StreamExt as _};
use polymarket_client_sdk::auth::{LocalSigner, Signer as _};
use polymarket_client_sdk::clob::types::request::BalanceAllowanceRequest;
use polymarket_client_sdk::clob::types::{OrderStatusType, OrderType, Side, SignatureType};
use polymarket_client_sdk::gamma::types::request::MarketBySlugRequest;
use polymarket_client_sdk::types::{Address, Decimal, U256};
use polymarket_client_sdk::{POLYGON, PRIVATE_KEY_VAR, clob, gamma};
use serde_json::Value;
use tokio_tungstenite::tungstenite::Message;
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

const CLOB_WS: &str = "wss://ws-subscriptions-clob.polymarket.com/ws/market";
const RTDS_WS: &str = "wss://ws-live-data.polymarket.com";

fn num(v: &Value) -> Option<f64> {
    match v {
        Value::String(s) => s.parse().ok(),
        Value::Number(n) => n.as_f64(),
        _ => None,
    }
}

fn levels(v: Option<&Value>) -> Vec<(f64, f64)> {
    v.and_then(Value::as_array)
        .map(|a| a.iter().filter_map(|l| Some((num(l.get("price")?)?, num(l.get("size")?)?))).collect())
        .unwrap_or_default()
}

/// Translate one CLOB market-channel message into engine events.
pub fn parse_clob(v: &Value, out: &mut Vec<Event>) {
    if let Some(arr) = v.as_array() {
        arr.iter().for_each(|x| parse_clob(x, out));
    } else if let Some(changes) = v.get("price_changes").and_then(Value::as_array) {
        for c in changes {
            let side = match c.get("side").and_then(Value::as_str) {
                Some("BUY") => BookSide::Bid,
                Some("SELL") => BookSide::Ask,
                _ => continue,
            };
            if let (Some(token), Some(price), Some(size)) =
                (c.get("asset_id").and_then(Value::as_str), c.get("price").and_then(num), c.get("size").and_then(num))
            {
                out.push(Event::BookLevel { token: token.to_owned(), side, price, size });
            }
        }
        // After all levels are applied, check each token against the reported top of book.
        let mut seen: Vec<&str> = Vec::new();
        for c in changes.iter().rev() {
            if let (Some(token), Some(best_bid), Some(best_ask)) =
                (c.get("asset_id").and_then(Value::as_str), c.get("best_bid").and_then(num), c.get("best_ask").and_then(num))
                && !seen.contains(&token)
            {
                seen.push(token);
                out.push(Event::BookTop { token: token.to_owned(), best_bid, best_ask });
            }
        }
    } else if (v.get("bids").is_some() || v.get("asks").is_some())
        && let Some(token) = v.get("asset_id").and_then(Value::as_str) {
            out.push(Event::BookSnap { token: token.to_owned(), bids: levels(v.get("bids")), asks: levels(v.get("asks")) });
        }
}

/// Stream both outcome books of one market until its window has ended.
pub async fn stream_books(def: MarketDef, tx: Sender<Event>) {
    let stop_ms = def.end_ms + 5000;
    while now_ms() < stop_ms && !tx.is_closed() {
        if let Err(e) = books_session(&def, &tx, stop_ms).await {
            tracing::warn!(slug = %def.slug, "book stream: {e:#}");
            tokio::time::sleep(Duration::from_secs(1)).await;
        }
    }
}

async fn books_session(def: &MarketDef, tx: &Sender<Event>, stop_ms: i64) -> anyhow::Result<()> {
    let mut ws = crate::ws::connect(CLOB_WS).await?;
    let sub = serde_json::json!({ "assets_ids": [def.up_token, def.down_token], "type": "market" });
    ws.send(Message::text(sub.to_string())).await?;
    let mut ping = tokio::time::interval(Duration::from_secs(10));
    let mut out = Vec::new();
    while now_ms() < stop_ms {
        tokio::select! {
            _ = ping.tick() => ws.send(Message::text("PING")).await?,
            msg = tokio::time::timeout(Duration::from_secs(30), ws.next()) => {
                match msg.map_err(|_| anyhow::anyhow!("no data for 30s"))?.ok_or_else(|| anyhow::anyhow!("closed"))?? {
                    Message::Text(t) => {
                        if let Ok(v) = serde_json::from_str::<Value>(&t) {
                            parse_clob(&v, &mut out);
                            for e in out.drain(..) {
                                if tx.send(e).await.is_err() {
                                    return Ok(());
                                }
                            }
                        }
                    }
                    Message::Ping(p) => ws.send(Message::Pong(p)).await?,
                    Message::Close(_) => anyhow::bail!("closed by server"),
                    _ => {}
                }
            }
        }
    }
    Ok(())
}

/// Translate one RTDS message into events: Chainlink BTC/USD prints and the
/// 60s TWAP stream these markets resolve on. Handles both live updates and
/// the history batch sent on subscribe.
pub fn parse_rtds(v: &Value, out: &mut Vec<Event>) {
    let Some(payload) = v.get("payload") else { return };
    let twap = match v.get("topic").and_then(Value::as_str) {
        Some("crypto_prices_chainlink") => false,
        Some("crypto_prices_twap_sixty") => true,
        _ => return,
    };
    let mut one = |p: &Value| {
        if let (Some(ts_ms), Some(px)) = (p.get("timestamp").and_then(Value::as_i64), p.get("value").and_then(num)) {
            out.push(if twap { Event::Twap { ts_ms, px } } else { Event::Ref { ts_ms, px } });
        }
    };
    match payload.get("data").and_then(Value::as_array) {
        Some(batch) => batch.iter().for_each(&mut one),
        None => one(payload),
    }
}

/// Chainlink BTC/USD spot and 60s-TWAP streams, reconnecting forever.
pub async fn reference_prices(tx: Sender<Event>) {
    while !tx.is_closed() {
        if let Err(e) = rtds_session(&tx).await {
            tracing::warn!("reference price stream: {e:#}");
        }
        tokio::time::sleep(Duration::from_millis(500)).await;
    }
}

async fn rtds_session(tx: &Sender<Event>) -> anyhow::Result<()> {
    let mut ws = crate::ws::connect(RTDS_WS).await?;
    let filters = r#"{"symbol":"btc/usd"}"#;
    let sub = serde_json::json!({ "action": "subscribe", "subscriptions": [
        { "topic": "crypto_prices_chainlink", "type": "*", "filters": filters },
        { "topic": "crypto_prices_twap_sixty", "type": "*", "filters": filters },
    ]});
    ws.send(Message::text(sub.to_string())).await?;
    tracing::info!("reference price stream connected");
    let mut ping = tokio::time::interval(Duration::from_secs(5));
    let mut out = Vec::new();
    // The socket can stay open (answering pings) while prices stop flowing,
    // so staleness is judged on price messages, not on socket activity.
    let mut last_price = Instant::now();
    loop {
        tokio::select! {
            _ = ping.tick() => {
                anyhow::ensure!(last_price.elapsed() < Duration::from_secs(8), "no prices for 8s");
                ws.send(Message::text("PING")).await?;
            },
            msg = tokio::time::timeout(Duration::from_secs(20), ws.next()) => {
                match msg.map_err(|_| anyhow::anyhow!("no data for 20s"))?.ok_or_else(|| anyhow::anyhow!("closed"))?? {
                    Message::Text(t) => {
                        if let Ok(v) = serde_json::from_str::<Value>(&t) {
                            parse_rtds(&v, &mut out);
                            if !out.is_empty() {
                                last_price = Instant::now();
                            }
                            for e in out.drain(..) {
                                if tx.send(e).await.is_err() {
                                    return Ok(());
                                }
                            }
                        }
                    }
                    Message::Ping(p) => ws.send(Message::Pong(p)).await?,
                    Message::Close(_) => anyhow::bail!("closed by server"),
                    _ => {}
                }
            }
        }
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
    match client.balance_allowance(BalanceAllowanceRequest::default()).await {
        Ok(b) => {
            // The API reports collateral in base units (6 decimals).
            let usd = f(b.balance) / 1e6;
            tracing::info!("wallet collateral balance ${usd:.2} (raw {}); configured bankroll ${:.2}", b.balance, cfg.bankroll);
            if usd + 1e-9 < cfg.bankroll {
                tracing::warn!("configured bankroll is larger than the wallet balance: set bankroll = {usd:.2} in config.toml");
            }
            if b.allowances.values().all(|a| a.trim_start_matches('0').is_empty()) {
                tracing::warn!("no exchange allowance set for collateral: orders will be rejected until approvals are done");
            }
        }
        Err(e) => tracing::warn!("could not read wallet balance: {e}"),
    }

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
                        Ok(r) if r.success && matches!(r.status, OrderStatusType::Delayed | OrderStatusType::Live) => {
                            // Accepted but not matched yet (matching delay). It may still
                            // fill, so wait for its final state instead of calling it missed.
                            let (shares, avg_px) = settle_pending(&client, &r.order_id, intent.limit).await;
                            tracing::info!(order = %r.order_id, shares, "delayed order settled");
                            FillReport { intent, shares, avg_px, latency_ms: t0.elapsed().as_secs_f64() * 1000.0, error: None }
                        }
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

/// Poll an accepted-but-unmatched order until it reaches a final state.
/// Cancels it if it is still open after ~10s. Returns (shares filled, price);
/// the limit price stands in for the fill price, which is never better for us.
async fn settle_pending<K: polymarket_client_sdk::auth::Kind>(
    client: &clob::Client<polymarket_client_sdk::auth::state::Authenticated<K>>,
    order_id: &str,
    limit: f64,
) -> (f64, f64) {
    let mut matched = 0.0;
    for _ in 0..20 {
        tokio::time::sleep(Duration::from_millis(500)).await;
        match client.order(order_id).await {
            Ok(o) => {
                matched = f(o.size_matched);
                if !matches!(o.status, OrderStatusType::Delayed | OrderStatusType::Live) {
                    return (matched, if matched > 0.0 { limit } else { 0.0 });
                }
            }
            Err(e) => tracing::debug!(order = %order_id, "order status: {e}"),
        }
    }
    let _ = client.cancel_order(order_id).await;
    if let Ok(o) = client.order(order_id).await {
        matched = f(o.size_matched);
    }
    (matched, if matched > 0.0 { limit } else { 0.0 })
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

#[cfg(test)]
mod wire_tests {
    use super::*;

    #[test]
    fn clob_messages() {
        let mut out = Vec::new();
        // Shapes captured from the live market channel.
        let snap: Value = serde_json::from_str(r#"[{"market":"0x2f","asset_id":"212","timestamp":"1794813936655","hash":"80","bids":[{"price":"0.01","size":"8370.82"},{"price":"0.54","size":"10"}],"asks":[{"price":"0.57","size":"25.5"}]}]"#).unwrap();
        parse_clob(&snap, &mut out);
        let chg: Value = serde_json::from_str(r#"{"market":"0x2f","price_changes":[{"asset_id":"104","price":"0.63","size":"297.6","side":"SELL","hash":"e1","best_bid":"0.43","best_ask":"0.46"},{"asset_id":"212","price":"0.37","size":"0","side":"BUY","hash":"31","best_bid":"0.54","best_ask":"0.57"}],"timestamp":"1794813936654","event_type":"price_change"}"#).unwrap();
        parse_clob(&chg, &mut out);
        assert_eq!(out.len(), 5);
        assert!(matches!(&out[4], Event::BookTop { token, best_bid, best_ask } if token == "104" && *best_bid == 0.43 && *best_ask == 0.46));
        assert!(matches!(&out[0], Event::BookSnap { token, bids, asks } if token == "212" && bids.len() == 2 && asks[0] == (0.57, 25.5)));
        assert!(matches!(&out[1], Event::BookLevel { token, side: BookSide::Ask, price, size } if token == "104" && *price == 0.63 && *size == 297.6));
        assert!(matches!(&out[2], Event::BookLevel { side: BookSide::Bid, size, .. } if *size == 0.0));
    }

    #[test]
    fn rtds_messages() {
        let mut out = Vec::new();
        let upd: Value = serde_json::from_str(r#"{"connection_id":"x","payload":{"full_accuracy_value":"64547305067996552101888","symbol":"btc/usd","timestamp":1794813893000,"value":64547.30506799655,"window_s":60},"timestamp":1794813894023,"topic":"crypto_prices_twap_sixty","type":"update"}"#).unwrap();
        parse_rtds(&upd, &mut out);
        let batch: Value = serde_json::from_str(r#"{"payload":{"data":[{"timestamp":1794813832000,"value":64572.45},{"timestamp":1794813833000,"value":64572.62}],"symbol":"btc/usd"},"topic":"crypto_prices_chainlink","type":"subscribe"}"#).unwrap();
        parse_rtds(&batch, &mut out);
        assert!(matches!(out[0], Event::Twap { ts_ms: 1_794_813_893_000, px } if (px - 64547.305).abs() < 0.001));
        assert!(matches!(out[2], Event::Ref { ts_ms: 1_794_813_833_000, .. }));
        assert_eq!(out.len(), 3);
    }
}
