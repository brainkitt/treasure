"""Merge raw cTrader MCP get_trendbars tool-result files into data/<symbolId>_<period>.csv.gz.

Usage: python -m arena.ingest            (safe to run concurrently; idempotent)
"""
import fcntl, glob, json, os, sys
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
RAW_GLOBS = ["/root/.claude/projects/**/*get_trendbars*.txt", "/root/.claude/projects/**/*get_trendbars*.json"]
SCALE = 1e5  # trendbar prices are price * 1e5 for every symbol


def main():
    os.makedirs(DATA, exist_ok=True)
    lock = open(os.path.join(DATA, ".lock"), "w")
    fcntl.flock(lock, fcntl.LOCK_EX)
    seen_path = os.path.join(DATA, ".ingested")
    seen = set(open(seen_path).read().split("\n")) if os.path.exists(seen_path) else set()
    files = sorted({f for g in RAW_GLOBS for f in glob.glob(g, recursive=True)} - seen)
    new = {}
    for f in files:
        try:
            d = json.load(open(f))
            bars = d["trendbars"]
            key = (int(d["symbolId"]), d["period"])
        except Exception as e:
            print("skip", f, e)
            continue
        new.setdefault(key, []).extend(bars)
        seen.add(f)
    for (sid, period), bars in new.items():
        df = pd.DataFrame(bars)[["timestamp", "open", "high", "low", "close", "volume"]]
        path = os.path.join(DATA, f"{sid}_{period}.csv.gz")
        if os.path.exists(path):
            df = pd.concat([pd.read_csv(path), df])
        df = df.drop_duplicates("timestamp", keep="last").sort_values("timestamp")
        df.to_csv(path + ".tmp", index=False, compression="gzip")
        os.replace(path + ".tmp", path)
        t = pd.to_datetime(df.timestamp, unit="ms")
        print(f"{sid}_{period}: {len(df)} bars  {t.iloc[0]} -> {t.iloc[-1]}")
    open(seen_path, "w").write("\n".join(sorted(seen)))
    print(f"ingested {len(files)} new raw files")


def load(symbol_id, period="M_1"):
    """Return DataFrame indexed 0..n-1 with columns ts(ms), time(UTC), open, high, low, close (BID, real price), volume."""
    df = pd.read_csv(os.path.join(DATA, f"{symbol_id}_{period}.csv.gz"))
    for c in ("open", "high", "low", "close"):
        df[c] = df[c] / SCALE
    df = df.rename(columns={"timestamp": "ts"})
    df["time"] = pd.to_datetime(df.ts, unit="ms")
    return df.reset_index(drop=True)


def plan(days, period="M_1", end_ms=None):
    """Print toTimestamp values (ISO) for paging back `days` of history, 1000 bars per call."""
    import time
    mins = {"M_1": 1, "M_5": 5, "M_15": 15, "M_30": 30, "H_1": 60}[period]
    end = end_ms or int(time.time() * 1000)
    step = 1000 * mins * 60_000
    n = int(days * 1440 / (1000 * mins)) + 1
    return [pd.Timestamp(end - i * step, unit="ms").strftime("%Y-%m-%dT%H:%M:%SZ") for i in range(n)]


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "plan":
        print("\n".join(plan(float(sys.argv[2]), sys.argv[3] if len(sys.argv) > 3 else "M_1")))
    else:
        main()
