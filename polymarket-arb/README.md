# polyarb — Polymarket BTC latency-arbitrage bot (Rust)

Trades Polymarket's "Bitcoin Up or Down" 5- and 15-minute markets when the
order book lags the BTC spot price. Runs locally as a single binary with a
web dashboard. Paper trading is the default; live trading is opt-in.

## How it works

1. **Spot** — WebSocket top-of-book from Coinbase, Kraken, OKX and Binance.
   Each venue is basis-adjusted to Polymarket's Chainlink BTC/USD stream and
   the median is used, so the composite leads Chainlink on fast moves.
2. **Resolution rule** — these markets resolve on Chainlink's 60-second TWAP
   stream: Up if the stream's value at window end is >= its value at window
   start (the strike). The bot reads that stream directly for strikes and
   settlement.
3. **Fair value** — probability that the end TWAP beats the strike, from the
   current spot, an EWMA of realised volatility, the seconds left, and (in
   the final minute) the part of the average that has already printed.
4. **Signal** — buy Up or Down when `fair - ask - taker_fee >= min_edge`.
5. **Exit** — sell when the bid has caught up with fair value, otherwise hold
   to resolution.
6. **Risk** — premium paid on a trade is at most 0.5% of equity; realised
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

WebSockets honour `HTTPS_PROXY`. Live mode needs USDC and token allowances already set on the wallet (trading
once through the Polymarket UI does this), and `[live]` `signature_type` /
`funder` set if you log in by email or browser wallet. The bot's balance is
its own bookkeeping from `bankroll`, not a read of the wallet, and winning
positions held to resolution still have to be redeemed on Polymarket.

## Status — read before using real money

**Verified against live Polymarket and exchange data (paper mode):**

- Market discovery, all four spot feeds, the Chainlink spot and TWAP streams
  and the order-book stream connect and parse.
- The local order book agrees with the exchange's own best bid/ask on
  99.96% of updates and self-corrects on the rest.
- The bot's settlement matched Polymarket's official outcome on every window
  checked. (The "price to beat" shown on the website is the spot print, and
  open-vs-close on spot does **not** predict the outcome; the TWAP rule does.)
- Fee curve matches the published table: `0.07 * p * (1 - p)` per share,
  3.5% of notional at 50c.

**Live paper results** — see RESULTS below. They are short samples from one
quiet hour and say nothing reliable about expected profit.

**Not verified:**

- **Real order placement.** `run --live` is written against the official SDK
  and compiles, but no real order has ever been sent. Start with the minimum
  bankroll you are willing to lose and watch the first fills.
- **Your latency.** Paper fills are taken from the real book 80 ms after the
  signal (configurable). From a home connection the true figure may be
  several hundred ms, and Polymarket may delay taker orders on these markets.
- **Share accounting.** If Polymarket deducts buy fees in shares, the tracked
  position is slightly larger than the real one and the exit sell may be
  rejected; the position then rides to resolution.
- **The reference stream is being retired.** The public RTDS price topics
  used here are deprecated in favour of an authenticated feed (PolyBolt).
  When they are switched off the bot stops trading (it stands aside when the
  stream is stale) until the feed is migrated.

**Other things to know:**

- **Minimum order size.** Polymarket requires 5 shares / $1 per order. With a
  0.5% per-trade cap that needs roughly $500+ of bankroll; at $50 the bot
  will never place an order unless you raise `risk_per_trade`.
- **Simulator profits are not a forecast.** The simulated market maker never
  widens, pulls quotes or adapts.
- **Differences from the tweet.** TradingView and CryptoQuant have no public
  real-time feed, so exchange WebSockets are used instead. "1,000 orders per
  second" is not something Polymarket's API allows; the bot sends one
  fill-and-kill order per signal. The 0.3% threshold is `min_edge`, default
  3c because anything smaller is inside the model's own error.
- Binance's main endpoints refuse some locations; the bot uses its
  market-data-only host, and runs fine on any subset of feeds.
- Polymarket restricts access from some jurisdictions, including the US.

RESULTS_PLACEHOLDER
