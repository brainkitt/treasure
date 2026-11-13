# polyarb — Polymarket BTC latency-arbitrage bot (Rust)

Trades Polymarket's "Bitcoin Up or Down" 5- and 15-minute markets when the
order book lags the BTC spot price. Runs locally as a single binary with a
web dashboard. Paper trading is the default; live trading is opt-in.

## How it works

1. **Spot** — WebSocket top-of-book from Binance, Coinbase, Kraken and OKX.
   Each venue is basis-adjusted to Polymarket's Chainlink BTC/USD stream (the
   price these markets resolve on) and the median is used, so the composite
   leads Chainlink on fast moves.
2. **Fair value** — a market resolves Up if the end price is >= the price at
   window start (the strike). Fair probability is
   `Phi(ln(S/K) / (sigma * sqrt(seconds_left)))` with `sigma` from an EWMA of
   realised volatility.
3. **Signal** — buy Up or Down when `fair - ask - taker_fee >= min_edge`.
4. **Exit** — sell when the bid has caught up with fair value, otherwise hold
   to resolution.
5. **Risk** — premium paid on a trade is at most 0.5% of equity; realised
   losses plus open premium are at most 2% of start-of-day equity per UTC day.

## Usage

```sh
cargo build --release

# Offline simulation: synthetic BTC path, market maker quoting 500 ms late
./target/release/polyarb sim --hours 24 --lag-ms 500 --serve

# Paper-trade real market data (no keys needed)
./target/release/polyarb run

# Live trading
export POLYMARKET_PRIVATE_KEY=0x...
./target/release/polyarb run --live
```

Dashboard: <http://127.0.0.1:8787>. Settings: copy `config.example.toml` to
`config.toml`. Tests: `cargo test`.

Live mode needs USDC and token allowances already set on the wallet (trading
once through the Polymarket UI does this), and `[live]` `signature_type` /
`funder` set if you log in by email or browser wallet. The bot's balance is
its own bookkeeping from `bankroll`, not a read of the wallet, and winning
positions held to resolution still have to be redeemed on Polymarket.

## Status — read before using real money

- **Not yet run against live Polymarket or exchange endpoints.** It was built
  in a sandbox without access to them. The engine, risk limits, paper fills
  and dashboard are tested (`cargo test`, simulator); the network layer is
  written against the official `polymarket-client-sdk` types and compiles,
  but market slugs (`btc-updown-5m-<epoch>`), feed message formats and order
  placement are unverified. Run `polyarb run` in paper mode first and check
  that feeds connect, markets appear and a strike is set.
- **Simulator profits are not a forecast.** The simulated market maker never
  widens, pulls quotes or adapts. `--lag-ms 0` shows the strategy does
  nothing when the book is not stale; real edge depends entirely on how stale
  real quotes are after fees.
- **Fees.** The default fee curve (up to ~1.56% of notional at 50c) is my
  understanding of Polymarket's taker fee on these markets; confirm it.
  Whether buy fees are taken in shares (which would make the tracked position
  slightly too large for a later sell) is also unconfirmed.
- **Minimum order size.** Polymarket requires 5 shares / $1 per order. With a
  0.5% per-trade cap that needs roughly $500+ of bankroll; at $50 the bot
  will never place an order unless you raise `risk_per_trade`.
- **Differences from the tweet.** TradingView and CryptoQuant have no public
  real-time feed, so exchange WebSockets are used instead. "1,000 orders per
  second" is not something Polymarket's API allows; the bot sends one
  fill-and-kill order per signal. The 0.3% threshold is `min_edge`, default
  3c because anything smaller is inside the model's own error.
- Polymarket restricts access from some jurisdictions, including the US.
