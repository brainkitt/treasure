//! BTC spot feeds: one WebSocket per exchange, each pushing top-of-book mids.

use std::time::Duration;

use futures::{SinkExt as _, StreamExt as _};
use serde_json::Value;
use tokio::sync::mpsc::Sender;
use tokio_tungstenite::tungstenite::Message;

use crate::run::Event;

pub struct Feed {
    pub name: &'static str,
    url: &'static str,
    subscribe: Option<&'static str>,
    /// Some venues want an application-level text ping.
    text_ping: Option<&'static str>,
    parse: fn(&Value) -> Option<f64>,
}

pub fn feed(name: &str) -> Option<Feed> {
    Some(match name {
        "binance" => Feed {
            name: "binance",
            url: "wss://stream.binance.com:9443/ws/btcusdt@bookTicker",
            subscribe: None,
            text_ping: None,
            parse: parse_binance,
        },
        "coinbase" => Feed {
            name: "coinbase",
            url: "wss://ws-feed.exchange.coinbase.com",
            subscribe: Some(r#"{"type":"subscribe","product_ids":["BTC-USD"],"channels":["ticker"]}"#),
            text_ping: None,
            parse: parse_coinbase,
        },
        "kraken" => Feed {
            name: "kraken",
            url: "wss://ws.kraken.com/v2",
            subscribe: Some(r#"{"method":"subscribe","params":{"channel":"ticker","symbol":["BTC/USD"]}}"#),
            text_ping: None,
            parse: parse_kraken,
        },
        "okx" => Feed {
            name: "okx",
            url: "wss://ws.okx.com:8443/ws/v5/public",
            subscribe: Some(r#"{"op":"subscribe","args":[{"channel":"bbo-tbt","instId":"BTC-USDT"}]}"#),
            text_ping: Some("ping"),
            parse: parse_okx,
        },
        _ => return None,
    })
}

fn num(v: &Value) -> Option<f64> {
    match v {
        Value::String(s) => s.parse().ok(),
        Value::Number(n) => n.as_f64(),
        _ => None,
    }
}

fn mid(bid: &Value, ask: &Value) -> Option<f64> {
    let (b, a) = (num(bid)?, num(ask)?);
    (b > 0.0 && a >= b).then_some((a + b) / 2.0)
}

fn parse_binance(v: &Value) -> Option<f64> {
    mid(v.get("b")?, v.get("a")?)
}

fn parse_coinbase(v: &Value) -> Option<f64> {
    if v.get("type")?.as_str()? != "ticker" {
        return None;
    }
    mid(v.get("best_bid")?, v.get("best_ask")?)
}

fn parse_kraken(v: &Value) -> Option<f64> {
    if v.get("channel")?.as_str()? != "ticker" {
        return None;
    }
    let d = v.get("data")?.get(0)?;
    mid(d.get("bid")?, d.get("ask")?)
}

fn parse_okx(v: &Value) -> Option<f64> {
    let d = v.get("data")?.get(0)?;
    mid(d.get("bids")?.get(0)?.get(0)?, d.get("asks")?.get(0)?.get(0)?)
}

/// Run one feed forever, reconnecting with backoff.
pub async fn run_feed(idx: usize, f: Feed, tx: Sender<Event>) {
    let mut backoff = 1u64;
    loop {
        match session(idx, &f, &tx).await {
            Ok(()) => backoff = 1,
            Err(e) => tracing::warn!(feed = f.name, "feed error: {e:#}"),
        }
        if tx.is_closed() {
            return;
        }
        tokio::time::sleep(Duration::from_secs(backoff)).await;
        backoff = (backoff * 2).min(30);
    }
}

async fn session(idx: usize, f: &Feed, tx: &Sender<Event>) -> anyhow::Result<()> {
    let (mut ws, _) = tokio_tungstenite::connect_async(f.url).await?;
    if let Some(sub) = f.subscribe {
        ws.send(Message::text(sub)).await?;
    }
    tracing::info!(feed = f.name, "connected");
    let mut ping = tokio::time::interval(Duration::from_secs(20));
    loop {
        tokio::select! {
            _ = ping.tick() => match f.text_ping {
                Some(p) => ws.send(Message::text(p)).await?,
                None => ws.send(Message::Ping(Default::default())).await?,
            },
            msg = tokio::time::timeout(Duration::from_secs(45), ws.next()) => {
                let msg = msg.map_err(|_| anyhow::anyhow!("no data for 45s"))?
                    .ok_or_else(|| anyhow::anyhow!("stream closed"))??;
                match msg {
                    Message::Text(t) => {
                        if let Some(px) = serde_json::from_str::<Value>(&t).ok().and_then(|v| (f.parse)(&v))
                            && tx.send(Event::Spot { src: idx, px }).await.is_err() {
                                return Ok(());
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

#[cfg(test)]
mod tests {
    use super::*;

    fn p(f: fn(&Value) -> Option<f64>, s: &str) -> Option<f64> {
        f(&serde_json::from_str(s).unwrap())
    }

    #[test]
    fn parsers() {
        assert_eq!(
            p(parse_binance, r#"{"u":1,"s":"BTCUSDT","b":"100000.00","B":"1.2","a":"100000.10","A":"0.5"}"#),
            Some(100_000.05)
        );
        assert_eq!(
            p(parse_coinbase, r#"{"type":"ticker","product_id":"BTC-USD","price":"100001","best_bid":"100000","best_ask":"100002"}"#),
            Some(100_001.0)
        );
        assert_eq!(p(parse_coinbase, r#"{"type":"subscriptions","channels":[]}"#), None);
        assert_eq!(
            p(parse_kraken, r#"{"channel":"ticker","type":"update","data":[{"symbol":"BTC/USD","bid":100000.0,"ask":100001.0,"last":100000.5}]}"#),
            Some(100_000.5)
        );
        assert_eq!(p(parse_kraken, r#"{"channel":"heartbeat"}"#), None);
        assert_eq!(
            p(parse_okx, r#"{"arg":{"channel":"bbo-tbt","instId":"BTC-USDT"},"data":[{"asks":[["100002","1","0","1"]],"bids":[["100000","2","0","1"]],"ts":"1"}]}"#),
            Some(100_001.0)
        );
        assert_eq!(p(parse_okx, r#"{"event":"subscribe","arg":{"channel":"bbo-tbt"}}"#), None);
    }
}
