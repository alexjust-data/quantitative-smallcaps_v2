#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
download_polygon_ticker_events.py
Descarga ticker events de Polygon para detectar offerings, delistings, ticker changes, etc.

Endpoint: /v3/reference/tickers/{ticker}/events

Event types:
  - offering: Ofertas publicas/privadas (ATM, S-3, PIPE)
  - delisting: Suspension del ticker
  - name_change: Cambio de nombre corporativo
  - ticker_change: Cambio de simbolo (CEI->VKIN)
  - merger_acquisition: M&A, SPAC combinations
  - stock_split: Ya descargado via /reference/splits
  - dividend: Ya descargado via /reference/dividends

Uso:
  python download_polygon_ticker_events.py \
    --tickers-csv processed/universe/info_rich/info_rich_tickers_20200101_20251021.csv \
    --outdir raw/polygon/ticker_events \
    --workers 4 \
    --rate-limit 0.3 \
    --resume
"""

import os, sys, time, argparse
from pathlib import Path
from datetime import datetime
from typing import List, Optional
from multiprocessing import Pool

import polars as pl
import requests
import certifi

API_BASE = "https://api.polygon.io"
TIMEOUT = (10, 60)  # connect, read

def log(msg: str):
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)

def ensure_ssl_env():
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())

def build_session() -> requests.Session:
    s = requests.Session()
    adapter = requests.adapters.HTTPAdapter(pool_connections=2, pool_maxsize=3, max_retries=0)
    s.mount("https://", adapter)
    return s

def load_tickers(csv_path: Path) -> List[str]:
    df = pl.read_csv(csv_path)
    col = "ticker" if "ticker" in df.columns else df.columns[0]
    return df[col].unique().to_list()

def success_marker(path: Path):
    (path / "_SUCCESS").touch(exist_ok=True)

def exists_success(path: Path) -> bool:
    return (path / "_SUCCESS").exists()

def http_get_ticker_events(session: requests.Session, ticker: str, api_key: str) -> dict:
    """
    Get all events for ticker.
    types: offering,delisting,name_change,ticker_change,merger_acquisition
    """
    url = f"{API_BASE}/v3/reference/tickers/{ticker}/events"
    params = {
        "types": "offering,delisting,name_change,ticker_change,merger_acquisition",
        "apiKey": api_key,
    }
    r = session.get(url, params=params, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()

def to_parquet_events(out_parquet: Path, records: List[dict]):
    if not records:
        # Create empty parquet with minimal schema
        schema = {
            "ticker": pl.Utf8,
            "event_type": pl.Utf8,
            "date": pl.Utf8,
        }
        pl.DataFrame(schema=schema).write_parquet(
            out_parquet, compression="zstd", compression_level=2, statistics=False
        )
        return

    # Flatten events structure
    flat_records = []
    for item in records:
        ticker = item.get("ticker", "")
        events_list = item.get("events", {}).get("results", [])

        for event in events_list:
            flat = {
                "ticker": ticker,
                "event_id": event.get("id"),
                "event_type": event.get("type"),
                "date": event.get("date"),
                "ticker_change_from": event.get("ticker_change", {}).get("ticker") if event.get("ticker_change") else None,
                "name": event.get("name"),
                "cash_amount": event.get("cash_amount"),
                "declaration_date": event.get("declaration_date"),
                "execution_date": event.get("execution_date"),
                "expiration_date": event.get("expiration_date"),
                "pay_date": event.get("pay_date"),
                "record_date": event.get("record_date"),
                "security_type": event.get("security_type"),
            }
            flat_records.append(flat)

    if not flat_records:
        # No events, create empty
        schema = {
            "ticker": pl.Utf8,
            "event_type": pl.Utf8,
            "date": pl.Utf8,
        }
        pl.DataFrame(schema=schema).write_parquet(
            out_parquet, compression="zstd", compression_level=2, statistics=False
        )
        return

    df = pl.DataFrame(flat_records)
    out_parquet.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(out_parquet, compression="zstd", compression_level=2, statistics=False)

def download_ticker_events(session: requests.Session, ticker: str, outdir: Path,
                           api_key: str, rate_limit: float, resume: bool):
    """Download events for single ticker."""
    ticker_path = outdir / ticker
    if resume and exists_success(ticker_path):
        log(f"{ticker}: resume skip (_SUCCESS)")
        return

    try:
        data = http_get_ticker_events(session, ticker, api_key)

        # Wrap ticker and events in list for to_parquet_events
        records = [{
            "ticker": ticker,
            "events": data
        }]

        out_parquet = ticker_path / "events.parquet"
        to_parquet_events(out_parquet, records)

        # Count events
        events_count = len(data.get("results", []))
        log(f"{ticker}: OK ({events_count} events)")

        success_marker(ticker_path)
        time.sleep(rate_limit)

    except requests.HTTPError as e:
        log(f"{ticker}: ERROR {e}")
        time.sleep(rate_limit)
    except Exception as e:
        log(f"{ticker}: ERROR {e}")
        time.sleep(rate_limit)

# ============================================================================
# Worker function for multiprocessing (must be module-level for Windows)
# ============================================================================
def worker_download_events(args):
    """Module-level worker for multiprocessing."""
    ticker, outdir, api_key, rate_limit, resume = args
    ensure_ssl_env()
    session = build_session()
    download_ticker_events(session, ticker, outdir, api_key, rate_limit, resume)

def main():
    parser = argparse.ArgumentParser(description="Download Polygon ticker events")
    parser.add_argument("--tickers-csv", type=Path, required=True)
    parser.add_argument("--outdir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--rate-limit", type=float, default=0.3)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    ensure_ssl_env()

    api_key = os.getenv("POLYGON_API_KEY")
    if not api_key:
        log("ERROR: falta POLYGON_API_KEY en el entorno")
        sys.exit(1)

    tickers = load_tickers(args.tickers_csv)
    log(f"Tickers: {len(tickers):,}")

    # Prepare tasks
    tasks = [
        (ticker, args.outdir, api_key, args.rate_limit, args.resume)
        for ticker in tickers
    ]

    # Process with multiprocessing
    batch_size = 20
    total_batches = (len(tasks) + batch_size - 1) // batch_size

    for batch_idx in range(total_batches):
        start_idx = batch_idx * batch_size
        end_idx = min(start_idx + batch_size, len(tasks))
        batch_tasks = tasks[start_idx:end_idx]

        with Pool(processes=args.workers) as pool:
            pool.map(worker_download_events, batch_tasks)

        # Progress
        completed = end_idx
        pct = completed / len(tasks) * 100
        log(f"Progreso: {batch_idx+1}/{total_batches} batches ({pct:.1f}%) | OK: {completed}")

    log("COMPLETADO")

if __name__ == "__main__":
    main()
