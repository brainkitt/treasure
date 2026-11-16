//! One-time on-chain setup for a plain (EOA) wallet: let Polymarket's CTF
//! exchange move the wallet's USDC.e and outcome tokens. Polymarket website
//! accounts do this through the site instead and do not need it.

use std::str::FromStr as _;

use alloy::primitives::{Address, U256};
use alloy::providers::{Provider, ProviderBuilder};
use alloy::signers::Signer as _;
use alloy::signers::local::PrivateKeySigner;
use alloy::sol;
use anyhow::Context as _;
use polymarket_client_sdk::{POLYGON, PRIVATE_KEY_VAR, contract_config};

sol! {
    #[sol(rpc)]
    interface IERC20 {
        function approve(address spender, uint256 value) external returns (bool);
        function allowance(address owner, address spender) external view returns (uint256);
        function balanceOf(address owner) external view returns (uint256);
    }
    #[sol(rpc)]
    interface IERC1155 {
        function setApprovalForAll(address operator, bool approved) external;
        function isApprovedForAll(address account, address operator) external view returns (bool);
    }
}

pub async fn run(check_only: bool) -> anyhow::Result<()> {
    let rpc = std::env::var("POLYGON_RPC_URL").unwrap_or_else(|_| "https://polygon-rpc.com".into());
    let key = std::env::var(PRIVATE_KEY_VAR).with_context(|| format!("{PRIVATE_KEY_VAR} is not set"))?;
    let signer = PrivateKeySigner::from_str(key.trim())
        .map_err(|_| anyhow::anyhow!("{PRIVATE_KEY_VAR} is not a valid private key"))?
        .with_chain_id(Some(POLYGON));
    let owner = signer.address();
    let cfg = contract_config(POLYGON, false).context("no Polygon contract config")?;
    let provider = ProviderBuilder::new().wallet(signer).connect(&rpc).await?;

    let usdc = IERC20::new(cfg.collateral, provider.clone());
    let ctf = IERC1155::new(cfg.conditional_tokens, provider.clone());
    let pol = provider.get_balance(owner).await?;
    let bal = usdc.balanceOf(owner).call().await?;
    let allowance = usdc.allowance(owner, cfg.exchange).call().await?;
    let approved = ctf.isApprovedForAll(owner, cfg.exchange).call().await?;
    println!("wallet           {owner}");
    println!("POL (gas)        {:.4}", f64::from(pol) / 1e18);
    println!("USDC.e balance   ${:.2}", f64::from(bal) / 1e6);
    println!("USDC.e allowance {}", if allowance > U256::from(1_000_000_000_000u64) { "ok".into() } else { format!("{allowance} (needs approval)") });
    println!("CTF approval     {}", if approved { "ok" } else { "needs approval" });
    if check_only || (allowance > U256::from(1_000_000_000_000u64) && approved) {
        return Ok(());
    }
    anyhow::ensure!(pol > U256::ZERO, "the wallet needs a little POL on Polygon to pay gas for the approvals");
    let exchange: Address = cfg.exchange;
    if allowance <= U256::from(1_000_000_000_000u64) {
        let tx = usdc.approve(exchange, U256::MAX).send().await?.watch().await?;
        println!("USDC.e approved  tx {tx}");
    }
    if !approved {
        let tx = ctf.setApprovalForAll(exchange, true).send().await?.watch().await?;
        println!("CTF approved     tx {tx}");
    }
    println!("done - this wallet can now trade with live.signature_type = 0");
    Ok(())
}
