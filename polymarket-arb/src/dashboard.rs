//! Local web dashboard: one static page polling a JSON snapshot.

use std::sync::{Arc, RwLock};

use axum::extract::State;
use axum::response::Html;
use axum::routing::get;
use axum::{Json, Router};

use crate::engine::Snapshot;

pub async fn serve(listener: tokio::net::TcpListener, state: Arc<RwLock<Snapshot>>) {
    let app = Router::new()
        .route("/", get(|| async { Html(include_str!("dashboard.html")) }))
        .route("/api/state", get(|State(s): State<Arc<RwLock<Snapshot>>>| async move { Json(s.read().unwrap().clone()) }))
        .with_state(state);
    if let Err(e) = axum::serve(listener, app).await {
        tracing::error!("dashboard stopped: {e}");
    }
}
