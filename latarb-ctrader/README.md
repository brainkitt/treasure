# LatArbBot — the Polymarket "stale price" idea on cTrader BTCUSD

`LatArbBot.cs` is a cTrader Automate cBot. It watches OKX's BTC price over a WebSocket and trades
the broker's BTCUSD CFD when the broker's quote is behind by more than the spread.

**Start in paper mode (the default).** Testing on the Deriv demo account (16 Nov 2026) found Deriv's
BTCUSD trails the exchanges by only 0–0.5 s and costs ~$18.42 to cross, so any edge exists only if
your orders reach Deriv faster than its own feed lag. Paper mode measures exactly that on your machine
using Deriv's real quotes. See the published test report for the data.

## Install
1. cTrader desktop → Algo → cBots → New → paste `LatArbBot.cs` → Build.
2. Add an instance on **BTCUSD**. Approve **Full Access** (needed for the OKX WebSocket).
3. Leave `Paper mode = Yes`. Run it for several days, including busy US hours.
4. Read the log: every `PAPER close` line shows the hypothetical P&L with Deriv's real bid/ask.
   Only consider live mode on a demo account if the running total is clearly positive after 100+ trades.

## Parameters (small-account defaults)
| Parameter | Default | Meaning |
| - | - | - |
| Paper mode | Yes | Log signals and hypothetical P&L; send no orders |
| Extra edge over spread (USD) | 5 | Trade only when the gap exceeds spread + this |
| Hold time (ms) | 3000 | Close after this long |
| Protective stop (USD of price) | 60 | Hard stop per trade ($0.60 at 0.01 BTC) |
| Take profit (USD of price) | 0 | Optional |
| Volume in units | 0 | 0 = broker minimum (0.01 BTC on Deriv) |
| Max spread (USD) | 25 | Skip when the broker widens its spread |
| Cooldown (ms) | 2000 | Minimum gap between trades |
| Max trades per day | 30 | |
| Daily loss limit | 1.5 | Account currency; stops new trades until 00:00 UTC |
| Max drawdown kill switch | 4.5 | Account currency; stops the bot |
| Lead feed stale after (ms) | 1500 | Ignore OKX if silent this long |
| Basis EWMA weight | 0.01 | How fast the OKX-vs-Deriv price offset is learned |
| OKX instrument | BTC-USDT | Leading price |

## Warning
Most CFD brokers prohibit latency arbitrage in their terms and can cancel trades or close accounts
that use it. Check your broker's terms before running live mode on real money.
