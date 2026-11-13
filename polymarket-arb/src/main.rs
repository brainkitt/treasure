mod book;
mod config;
mod dashboard;
mod engine;
mod model;
mod polymarket;
mod run;
mod sim;
mod spot;

use clap::{Parser, Subcommand};

#[derive(Parser)]
#[command(name = "polyarb", about = "Polymarket BTC up/down latency-arbitrage bot")]
struct Cli {
    /// Path to a TOML config (defaults to ./config.toml if present).
    #[arg(long, global = true)]
    config: Option<String>,
    #[command(subcommand)]
    cmd: Cmd,
}

#[derive(Subcommand)]
enum Cmd {
    /// Trade live market data. Paper-trades unless --live is given.
    Run {
        /// Send real orders. Needs POLYMARKET_PRIVATE_KEY in the environment.
        #[arg(long)]
        live: bool,
    },
    /// Offline simulation against a synthetic market whose quotes lag spot.
    Sim {
        #[arg(long, default_value_t = 24.0)]
        hours: f64,
        /// Milliseconds the simulated market maker trails spot.
        #[arg(long, default_value_t = 500)]
        lag_ms: i64,
        #[arg(long, default_value_t = 7)]
        seed: u64,
        /// Keep running and show the result on the dashboard.
        #[arg(long)]
        serve: bool,
    },
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(tracing_subscriber::EnvFilter::try_from_default_env().unwrap_or_else(|_| "info".into()))
        .init();
    let cli = Cli::parse();
    let cfg = config::Config::load(cli.config.as_deref())?;
    match cli.cmd {
        Cmd::Run { live } => run::run(cfg, live).await?,
        Cmd::Sim { hours, lag_ms, seed, serve } => {
            let p = sim::SimParams { hours, lag_ms, seed, ..Default::default() };
            let addr = cfg.dashboard_addr.clone();
            let mut s = sim::run(cfg, &p).snapshot();
            s.mode = "SIM".into();
            let rate = if s.trades > 0 { 100.0 * f64::from(s.wins) / f64::from(s.trades) } else { 0.0 };
            println!("simulated {hours}h, market lag {lag_ms}ms, seed {seed}");
            println!("  equity   ${:.2} (start ${:.2}, pnl {:+.2})", s.equity, s.seed, s.total_pnl);
            println!("  trades   {} closed, {:.1}% win ({}W / {}L), {} orders missed", s.trades, rate, s.wins, s.losses, s.missed);
            println!("  fees     ${:.2}", s.fees_paid);
            if serve {
                let listener = tokio::net::TcpListener::bind(&addr).await?;
                println!("dashboard: http://{}  (ctrl-c to quit)", listener.local_addr()?);
                dashboard::serve(listener, std::sync::Arc::new(std::sync::RwLock::new(s))).await;
            }
        }
    }
    Ok(())
}
