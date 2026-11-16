//! WebSocket connect helper that honours HTTPS_PROXY (HTTP CONNECT tunnel).

use tokio::io::{AsyncReadExt as _, AsyncWriteExt as _};
use tokio::net::TcpStream;
use tokio_tungstenite::tungstenite::client::IntoClientRequest as _;
use tokio_tungstenite::{MaybeTlsStream, WebSocketStream};

pub type Ws = WebSocketStream<MaybeTlsStream<TcpStream>>;

pub async fn connect(url: &str) -> anyhow::Result<Ws> {
    let req = url.into_client_request()?;
    let host = req.uri().host().ok_or_else(|| anyhow::anyhow!("no host in {url}"))?.to_owned();
    let port = req.uri().port_u16().unwrap_or(if url.starts_with("wss") { 443 } else { 80 });
    let proxy = ["HTTPS_PROXY", "https_proxy"].iter().find_map(|k| std::env::var(k).ok()).filter(|p| !p.is_empty());
    let tcp = match proxy {
        Some(p) => tunnel(&p, &host, port).await?,
        None => TcpStream::connect((host.as_str(), port)).await?,
    };
    tcp.set_nodelay(true)?;
    let (ws, _) = tokio_tungstenite::client_async_tls(req, tcp).await?;
    Ok(ws)
}

async fn tunnel(proxy: &str, host: &str, port: u16) -> anyhow::Result<TcpStream> {
    let rest = proxy.split_once("://").map_or(proxy, |x| x.1).trim_end_matches('/');
    let (auth, addr) = match rest.rsplit_once('@') {
        Some((a, h)) => (Some(a), h),
        None => (None, rest),
    };
    let mut s = TcpStream::connect(addr).await.map_err(|e| anyhow::anyhow!("proxy {addr}: {e}"))?;
    let mut req = format!("CONNECT {host}:{port} HTTP/1.1\r\nHost: {host}:{port}\r\n");
    if let Some(a) = auth {
        req += &format!("Proxy-Authorization: Basic {}\r\n", base64(a.as_bytes()));
    }
    req += "\r\n";
    s.write_all(req.as_bytes()).await?;
    let mut buf = Vec::with_capacity(256);
    while !buf.ends_with(b"\r\n\r\n") {
        anyhow::ensure!(buf.len() < 8192, "oversized proxy response");
        buf.push(s.read_u8().await?);
    }
    let status = String::from_utf8_lossy(&buf).lines().next().unwrap_or_default().to_owned();
    anyhow::ensure!(status.split_whitespace().nth(1) == Some("200"), "proxy refused {host}:{port}: {status}");
    Ok(s)
}

fn base64(input: &[u8]) -> String {
    const T: &[u8; 64] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    let mut out = String::new();
    for c in input.chunks(3) {
        let n = (u32::from(c[0]) << 16) | (u32::from(*c.get(1).unwrap_or(&0)) << 8) | u32::from(*c.get(2).unwrap_or(&0));
        for i in 0..4 {
            if i <= c.len() {
                out.push(T[(n >> (18 - 6 * i) & 63) as usize] as char);
            } else {
                out.push('=');
            }
        }
    }
    out
}

#[cfg(test)]
mod tests {
    #[test]
    fn base64_matches_rfc4648() {
        assert_eq!(super::base64(b"user:pass"), "dXNlcjpwYXNz");
        assert_eq!(super::base64(b"ab"), "YWI=");
        assert_eq!(super::base64(b"a"), "YQ==");
    }
}
