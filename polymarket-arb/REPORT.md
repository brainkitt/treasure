# polyarb — Test Report and Live-Trading Guide

Polymarket BTC "Up or Down" latency-arbitrage bot, written in Rust.
Testing ran 13–16 November 2026. All P&L below is **paper trading**: real
live market data, simulated fills, no real orders.

---

## 1. Short answers

**Can it go live right now?** Not today, and not from this cloud server.
Four things stand in the way (details in §7):

1. **Location.** Polymarket blocks this cloud server (`{"blocked":true,"country":"US"}`
   from `polymarket.com/api/geoblock`). The bot has to run on your own
   computer, in a country where Polymarket allows trading.
2. **Wallet type.** Every Polymarket account created on or after 4 May 2026
   uses a "Deposit Wallet". The Rust SDK this bot signs orders with (latest
   version, 0.4.4) only supports the three older types: plain wallet (EOA),
   Proxy and Safe. A new polymarket.com account **cannot** be traded by this
   bot. Use a separate plain wallet instead (§8).
3. **Real orders are untested.** The order code compiles against the official
   SDK, but no real order has ever been sent. The first live session must be
   supervised.
4. **No automatic redemption.** Winning shares held to expiry have to be
   redeemed before the money is usable again. The bot does not do this yet.
   It rarely holds to expiry (5 of 216 paper trades), but those shares stay
   locked until redeemed.

**Is $15 enough?**
- **Under the tweet's rules (0.5% per trade, 2% per day): no.** Polymarket's
  smallest order is 5 shares, which costs about $2.54 at a typical entry
  price. 0.5% of $15 is 7 cents. The bot placed **zero** trades with $15 on
  those rules (§5).
- **It can trade if each trade risks about 20% of the account.** That works
  mechanically, but a single bad trade loses about a fifth of your money.
  That is gambling-sized risk, not the controlled risk the tweet describes.
  Treat $15 as a test of the setup that you can afford to lose.
- **Realistic minimums:**

  | Goal | Minimum capital |
  | - | - |
  | Tweet rules (0.5%/trade) on about half of signals | **~$500** |
  | Tweet rules on every signal | **~$1,000** |
  | Moderate rules (5%/trade, 15%/day), every signal | **~$100** |
  | Trades at all (20%/trade, 50%/day) | $15 (high risk) |

---

## 2. What was built

A single Rust program (`polyarb`) with a local web dashboard.

| Part | What it does |
| - | - |
| Spot feeds | Live BTC top-of-book from Coinbase, Kraken, OKX and Binance. Each venue is adjusted to Polymarket's Chainlink price, and the median is used. |
| Reference feed | Chainlink BTC/USD spot and **60-second TWAP** streams from Polymarket (`ws-live-data.polymarket.com`). |
| Market discovery | Finds the current and next 5- and 15-minute markets (`btc-updown-5m-<epoch>`, `btc-updown-15m-<epoch>`). |
| Order books | Polymarket CLOB WebSocket. A local book is kept per outcome and checked against the exchange's own best bid/ask. |
| Fair value | Probability that the end-of-window TWAP is at or above the start-of-window TWAP. Uses spot, realised volatility, time left, and the part of the final average that has already printed. |
| Signal | Buy Up or Down when `fair − ask − fee ≥ min_edge` (default 3¢ per $1 share). |
| Exit | Sell as soon as the bid has caught up with fair value; otherwise hold to expiry. |
| Risk | Per-trade cap (premium paid = maximum loss) and a daily cap that counts realised losses plus premium still open. |
| Execution | Paper: fills against the real book after a configurable delay. Live: one fill-and-kill limit order per signal through the official Rust SDK. |
| Dashboard | `http://127.0.0.1:8787`: balance, P&L, latency, win rate, equity curve, execution log. |

Commands:

```
polyarb sim [--hours 24 --lag-ms 500 --serve]   offline simulation
polyarb run                                     paper trading on live data
polyarb run --live                              real orders
polyarb approve [--check]                       one-time wallet setup (EOA)
```

Code: `polymarket-arb/` on branch `claude/polymarket-btc-arbitrage-0avqt1`.
16 automated tests, all passing.

---

## 3. How the markets actually work (verified live)

**Contract.** Every 5 (or 15) minutes Polymarket lists "Bitcoin Up or Down".
"Up" pays $1 per share if BTC finishes the window at or above where it
started; otherwise "Down" pays $1. Share prices are between $0.01 and $0.99.

**Resolution rule — what the bot settles on.** The market text says it
resolves on Chainlink's **BTC/USD TWAP** (time-weighted average price), not
on a single spot print. I recorded both Chainlink streams for 70 minutes and
compared five candidate rules against Polymarket's official result on 20
windows:

| Rule | Correct |
| - | - |
| TWAP at end ≥ TWAP at start | **20 / 20** |
| TWAP at end ≥ spot at start | 20 / 20 |
| Average of window ≥ spot at start | 19 / 20 |
| Average of window ≥ TWAP at start | 17 / 20 |
| Spot at end ≥ spot at start (the "price to beat" on the website) | 17 / 20 |

The website's "price to beat" and close price are spot prints, and comparing
them gave the wrong winner in 3 of 20 windows. The bot uses the first rule.
Its own settlement matched Polymarket's official outcome on every window it
traded through.

**Fees.** Polymarket publishes the crypto taker fee as
`fee = shares × 0.07 × p × (1 − p)`. That is 1.75¢ per share at p = 0.50
(3.5% of the money spent), falling toward the extremes. The market's own data
(`feeSchedule: rate 0.07, exponent 1, takerOnly`) confirms it. Makers pay no
fee. Every bot trade is a taker trade, and the fee is in every number below.

**Order limits.** Minimum 5 shares per order, 1¢ price steps (`orderMinSize
= 5`, `orderPriceMinTickSize = 0.01`). The bot also enforces a $1 minimum
order value.

---

## 4. Test log

### 4.1 Offline simulation (13 Nov)
A synthetic BTC path with a simulated market maker whose quotes trail spot by
a set delay.
- With the quotes trailing by 100 ms or more, the strategy made money in
  simulation, and more as the lag grew.
- With no lag, it placed at most 3 trades. This was the control: the bot only
  trades when the book is stale.
- With a deliberately wrong volatility input, losses stopped at the 2% daily
  cap. This confirms the risk limit works.

Simulation proves the mechanics, not profitability: the simulated market
maker never adapts.

### 4.2 First contact with live data (16 Nov) — what broke and was fixed

| Finding | Fix |
| - | - |
| Markets resolve on Chainlink's 60s TWAP, not spot | Fair value, strike and settlement rewritten around the TWAP stream (§3) |
| Real taker fee is `0.07·p·(1−p)` (3.5% at 50¢), more than double my first assumption | Fee model replaced and checked against Polymarket's published table |
| The SDK's WebSocket clients don't go through an HTTPS proxy | Own WebSocket clients for the order book and price streams |
| The reference stream once stayed connected but **stopped sending prices for ~3 minutes**; the bot kept trading on a stale strike | Reconnect after 8 s without a price; no trading while the reference is over 10 s old |
| Local order book drifted from the exchange on rare updates | Each update is checked against the exchange's reported best bid/ask: agreement on 99.96% of 1.18 million checks, corrected on the rest |
| Binance's main endpoint refuses some locations | Uses Binance's market-data-only host |
| A "delayed" order (accepted, matched later) would have been counted as missed, leaving an untracked position | Delayed orders are followed to their final state and cancelled after ~10 s |

### 4.3 Live paper trading — $1,000, about $5 per trade (16 Nov, 08:18–09:18 UTC)

| Run | Fill delay | Length | Buys filled | Orders missed | P&L |
| - | - | - | - | - | - |
| A | 80 ms | 45 min | 70 | 12 | +$31.96 |
| B | 80 ms | 30 min | 74 | 11 | +$42.25 |
| C | 500 ms | 30 min | 42 | 55 | +$31.56 |
| D | 1500 ms | 30 min | 32 | 100 | +$16.36 |

B, C and D ran at the same time on the same data, so the delay is the only
difference between them. Slower fills miss many more orders and earn less,
but the edge had not vanished at 1.5 s in this sample.

### 4.4 Trade statistics (all 216 closed paper trades above)

| Measure | Value |
| - | - |
| Win rate | 68.5% |
| Average win / average loss | +$1.27 / −$0.97 |
| Return on premium per trade | mean +12.5%, median +8.1%, worst 10% below −23.2%, best 10% above +54.1% |
| Holding time when sold | median 8 s, 90% under 53 s |
| Held to expiry | 5 trades, −$17.41 (almost all losses) |
| Entry price | median 0.48 (10% below 0.17, 10% above 0.74) |
| Edge at entry | median 3.3¢, 90th percentile 4.9¢ |
| 5-minute markets | 185 trades, +$104.94, 68% wins |
| 15-minute markets | 31 trades, +$16.75, 74% wins |
| Signals vs fills | 309 signals, 178 orders missed (book moved before the fill) |

Almost all of the profit came from selling within seconds once Polymarket's
book caught up. Holding to expiry lost money.

### 4.5 Small-account runs ($15 and $500, 250 ms fill delay)

Three runs side by side, 09:35–10:14 UTC, same live data, 250 ms fill delay
(closer to a home connection than the 80 ms runs).

| Run | Balance | Risk per trade / day | Buys filled | Missed | Wins / losses | Max drawdown | End balance |
| - | - | - | - | - | - | - | - |
| $15, tweet rules | $15 | 0.5% / 2% | **0** | 0 | — | — | $15.00 |
| $15, minimum to trade | $15 | 20% / 50% | 76 | 36 | 51 / 23 | **27.9%** | $55.33 (+269%) |
| $500, tweet rules | $500 | 0.5% / 2% | 42 | 16 | 25 / 17 | 0.8% | $505.67 (+1.1%) |

What these show:
- **$15 on the tweet's rules cannot trade at all.** Every signal was skipped
  because 5 shares cost more than the 7¢ budget.
- **$15 at 20% per trade traded constantly and, on paper, nearly quadrupled
  in 38 minutes.** That came from compounding: each win raised the next trade
  size, from ~$3 to ~$7. It also fell 27.9% from its high at one point, had a
  run of 5 losses in a row, and hit its daily risk cap once. If the real edge
  is smaller than paper (§6), the same compounding works in reverse just as
  fast. **Do not read +269% as a forecast.**
- **$500 on the tweet's rules made +1.1%** with a 0.8% maximum drawdown. That
  is what the tweet's risk control looks like: small, steady and slow. Most
  orders were the 5-share minimum (~$1.70–$2.50), so it still only took the
  cheaper signals.
- About a third of signals at 250 ms were missed because the book moved
  first, compared with about a fifth at 80 ms.

---

## 5. Capital analysis — why $15 is a problem

The binding limit is Polymarket's **5-share minimum order**. From the
entry prices of the 216 real paper trades, the cost of the smallest allowed
order (5 shares, one tick of slippage, plus fee) was:

- median **$2.54**, 90th percentile $3.82, maximum $4.81.

The bot only trades if that cost fits inside `risk_per_trade × equity`.
Share of real signals each account could have taken:

| Equity | Risk per trade | Budget | Signals affordable |
| - | - | - | - |
| $15 | 0.5% (tweet) | $0.07 | **0%** |
| $15 | 5% | $0.75 | 7% |
| $15 | 10% | $1.50 | 23% |
| $15 | 20% | $3.00 | 65% |
| $50 | 5% | $2.50 | 49% |
| $50 | 10% | $5.00 | 100% |
| $100 | 5% | $5.00 | 100% |
| $200 | 0.5% | $1.00 | 11% |
| $300 | 0.5% | $1.50 | 23% |
| $500 | 0.5% | $2.50 | 49% |
| $1,000 | 0.5% | $5.00 | 100% |

What $15 at 20% per trade means in practice:
- Each trade puts about $2.50–$3.00 at risk, roughly 17–20% of the account.
- The average paper loss was 18% of the premium, but a trade held to expiry
  can lose 100% of it.
- Three losers in a row would take the account to about $9–10. At that size
  most signals become unaffordable and the bot effectively stops.
- Expected profit is tiny even if the paper edge held: about $0.30–$0.40 per
  winning trade.

**The tweet's numbers.** "$400–$700 a day" at 0.5% risk per trade would need
an account in the tens of thousands of dollars, with every trade taking
liquidity at a size the book often doesn't have. The "$50 → $435,000" claim
and "1,000 orders per second" are not compatible with Polymarket's order
minimums, fees or API, and the dashboard in the video looks like a scripted
animation (its own numbers contradict each other).

---

## 6. Why live results will be worse than paper

Treat the paper numbers as evidence that the pipeline works, **not** as an
expected return. A mean of +12.5% per trade over an 8-second hold is far
better than a real market should allow. Reasons live will be worse:

1. **Competition.** Paper assumes nobody else takes the stale quote. Other
   bots run the same idea, and when they get there first you are filled at a
   worse price or not at all.
2. **Our view of the book is also late.** The WebSocket delivers book updates
   after the fact. Some "stale" quotes the bot sees may already be gone.
3. **Matching delay.** Polymarket can delay marketable orders (the `delayed`
   status). A delay is exactly what kills a latency strategy.
4. **Exit depth.** Paper sells into the full displayed bid. Real bids can be
   thinner or pulled the moment BTC moves.
5. **Sample.** One hour of one quiet morning (BTC moved only a few hundred
   dollars). Fast markets bring bigger moves, wider books and more losses held
   to expiry.
6. **Home latency.** These runs had 80–1,500 ms simulated delay on a
   data-centre connection. A home connection adds more.

A reasonable expectation is that live results land somewhere between "a
fraction of paper" and "losing money". Only real fills will tell.

---

## 7. What is required to run live

| Requirement | Status |
| - | - |
| Run from a location Polymarket allows | **You**: check `https://polymarket.com/api/geoblock` shows `"blocked":false` on your own connection. Polymarket blocks the US and other places; do not try to get around it. |
| A computer that stays on while trading | **You**: Windows, macOS or Linux with Rust installed (`rustup.rs`). This cloud session is ephemeral and geo-blocked. |
| A wallet type the bot can sign for | **You**: a plain wallet (EOA) set up for this, or an older (pre-May 2026) Polymarket Proxy/Safe account. **Not** a new polymarket.com account. |
| USDC.e on Polygon in that wallet | **You**: see §8. Note that exchanges usually withdraw *native* USDC, not USDC.e. |
| A little POL for gas (EOA only) | **You**: enough for two approval transactions (a dollar's worth is plenty). |
| One-time token approvals (EOA only) | `polyarb approve` — written, **not yet run against Polygon**. |
| Private key | Set as the `POLYMARKET_PRIVATE_KEY` environment variable on your machine. Never paste it into chat or commit it. Use a wallet that holds only trading money. |
| Supervised first session | **You**: watch the first fills and compare them with your Polymarket positions. |
| Redeeming expired winning shares | **Missing** in the bot; must be done by hand for now. |

---

## 8. Step-by-step: going live

**Step 1 — Location check.** On the computer you will trade from, open
`https://polymarket.com/api/geoblock`. If it says `"blocked":true`, stop.

**Step 2 — Build and paper-trade first (at least a day).**
```
git clone <repo> && cd treasure/polymarket-arb
cargo build --release
cp config.example.toml config.toml        # then edit (step 6)
./target/release/polyarb run              # paper mode, open http://127.0.0.1:8787
```
Confirm that all feeds show fresh times on the dashboard, markets appear, a
strike is set within seconds of each window opening, and the equity curve
looks like it did here.

**Step 3 — Choose the wallet.**

| You have | Use | Config |
| - | - | - |
| Nothing yet, or a polymarket.com account made after 4 May 2026 | A **new plain wallet** (EOA), used only for this | `signature_type = 0`, no `funder` |
| A polymarket.com account made **before** 4 May 2026 with email/Google login | That account's exported signing key | `signature_type = 1`, `funder = "<your Polymarket wallet address>"` |
| A polymarket.com account made **before** 4 May 2026 with MetaMask/Rabby | That browser wallet's key | `signature_type = 2`, `funder = "<your Polymarket wallet address>"` |

**Step 4 — Fund it (EOA route).** Send USDC.e (Polygon contract
`0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174`) and a small amount of POL to
the wallet on the **Polygon** network. If your exchange only withdraws native
USDC on Polygon, swap it to USDC.e first. On $15, swap and withdrawal fees
can take a noticeable bite.

**Step 5 — Approvals (EOA route).**
```
export POLYMARKET_PRIVATE_KEY=0x...        # in your own terminal only
./target/release/polyarb approve --check   # shows POL, USDC.e and approval state
./target/release/polyarb approve           # sends the two approval transactions
```
Optional: set `POLYGON_RPC_URL` to another Polygon endpoint if the default is
slow.

**Step 6 — Config.** Set `bankroll` to **exactly** your wallet balance and
pick a risk profile from §9.

**Step 7 — First live session, supervised.**
```
./target/release/polyarb run --live
```
In the first lines, check:
- `live executor authenticated as 0x...` — the right wallet.
- `wallet collateral balance $X` — matches what you deposited. If it shows $0
  while the wallet holds USDC.e, stop: the account or collateral setup is
  wrong.
- No `no exchange allowance` warning.

Then watch the first few `EXEC` and `FILLED`/`LOSS` lines and compare them with
the positions shown for your wallet on Polymarket. Stop with Ctrl-C at any
time. Positions still open stay open and resolve on their own.

**Step 8 — Redeem.** After a window ends, any winning shares still held need
redeeming before the money can be used again.

---

## 9. Parameter reference

Put these in `config.toml`. Any key you leave out uses the default.

| Key | Default | Meaning |
| - | - | - |
| `bankroll` | 1000 | Your starting balance in USDC. **Set to your real balance.** All risk limits are fractions of it. |
| `risk_per_trade` | 0.005 | Maximum premium on one trade, as a fraction of equity. Premium paid is the maximum loss. |
| `daily_risk` | 0.02 | Maximum of (today's realised losses + premium still open), as a fraction of start-of-day equity. Resets 00:00 UTC. |
| `min_edge` | 0.03 | Required edge after fees, in dollars per $1 share (0.03 = 3¢). Higher = fewer, safer trades. |
| `exit_edge` | 0.005 | Sell once the bid (after fees) is within this of fair value. |
| `min_price` / `max_price` | 0.05 / 0.95 | Only buy shares priced in this range. |
| `min_secs_left` | 10 | No new trades in the last N seconds of a window. |
| `min_secs_elapsed` | 5 | No new trades in the first N seconds of a window. |
| `slippage_ticks` | 1 | Pay up to this many 1¢ ticks above the ask. |
| `cooldown_ms` | 1500 | Minimum gap between orders in one market. |
| `max_book_age_ms` | 5000 | Ignore an order book with no update for this long. |
| `max_spot_age_ms` | 3000 | Ignore exchange prices older than this. |
| `max_ref_age_ms` | 10000 | Stand aside if the Chainlink stream is older than this. |
| `fee_rate` / `fee_exponent` | 0.07 / 1 | Polymarket's crypto taker fee curve. Do not change. |
| `twap_window_s` | 60 | Markets resolve on a 60-second TWAP. Do not change. |
| `vol_mult` | 1.0 | Multiplier on estimated volatility. Above 1 = more cautious fair values. |
| `paper_latency_ms` | 80 | Paper mode only: simulated delay before a fill. Use 250+ to mimic home. |
| `intervals_min` | [5, 15] | Which markets to trade. |
| `feeds` | coinbase, kraken, okx, binance | Spot feeds. Any subset works; remove any your country blocks. |
| `dashboard_addr` | 127.0.0.1:8787 | Dashboard address. |
| `[live] signature_type` | 0 | 0 = plain wallet, 1 = Polymarket Proxy, 2 = Polymarket Safe. |
| `[live] funder` | — | Your Polymarket wallet address (types 1 and 2 only). |

### Suggested profiles

**$15 — setup test only (high risk; this exact profile ran in §4.5: +269% on paper with a 27.9% drawdown in 38 minutes)**
```toml
bankroll       = 15.0
risk_per_trade = 0.20    # ~$3 per trade: the smallest that fits a 5-share order
daily_risk     = 0.50    # stops for the day after ~$7.50 of losses or open premium
min_edge       = 0.03
# the bot skips any signal where 5 shares cost more than the $3 budget
```

**$100 — moderate**
```toml
bankroll       = 100.0
risk_per_trade = 0.05    # $5 per trade
daily_risk     = 0.15    # $15 per day
min_edge       = 0.03
```

**$500–$1,000 — the tweet's rules**
```toml
bankroll       = 1000.0
risk_per_trade = 0.005   # $5 per trade
daily_risk     = 0.02    # $20 per day
min_edge       = 0.03
```

---

## 10. Risks and safeguards

| Risk | What the bot does | What you should do |
| - | - | - |
| Feed goes silent | Stops trading when the Chainlink stream is over 10 s old or spot is over 3 s old | Watch the feed ages on the dashboard |
| Bad day | Daily cap stops new entries until 00:00 UTC | Choose `daily_risk` as the most you accept losing in a day |
| Book out of sync | Corrects against the exchange's best bid/ask on every update | — |
| Delayed or partial fills | Follows delayed orders to completion; partial fills are tracked | Compare with your Polymarket positions in the first session |
| Bankroll in config differs from wallet | Warns at startup | Set `bankroll` to the real balance |
| Polymarket retires the public price stream | Stops trading (stale reference) | The bot then needs migrating to the authenticated feed ("PolyBolt") |
| Polymarket moves BTC markets to "V2" | Untested; orders would likely be rejected | Check that markets still show `version: v1` |
| Key theft | — | Dedicated wallet, only trading money in it, key only in an environment variable |

---

## 11. Open items before trusting it with real money

1. **First real orders.** Never sent. Expect at least one small fix after
   seeing real responses.
2. **Deposit Wallet support.** Needs the executor ported to Polymarket's
   official TypeScript or Python client, or a Rust SDK update.
3. **Automatic redemption** of winning shares held to expiry.
4. **Migration to the authenticated price feed** before the public one is
   switched off.
5. **Longer paper record.** Several days covering quiet and volatile
   markets, at your real latency.
