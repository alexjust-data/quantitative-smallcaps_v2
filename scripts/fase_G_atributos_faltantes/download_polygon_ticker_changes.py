#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
download_polygon_ticker_changes.py

Descarga ticker changes (symbol changes, renames, rebranding) desde Polygon.io
usando el endpoint /vX/reference/tickers/{id}/events (EXPERIMENTAL)

Endpoint: https://api.polygon.io/vX/reference/tickers/{id}/events?types=ticker_change
Docs: https://polygon.io/docs/stocks/get_vx_reference_tickers_id_events

Output particionado por ticker:
  raw/polygon/ticker_changes/
    ticker={TICKER}/
      events.parquet
      _SUCCESS
"""

import argparse
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict

import polars as pl
import requests

# Polygon API base
POLYGON_BASE = "https://api.polygon.io"
EVENTS_ENDPOINT = "/vX/reference/tickers/{ticker}/events"

# Rate limiting
DEFAULT_RATE_LIMIT = 0.3  # seconds between requests (5 req/sec for free tier)
TIMEOUT = 30
RETRIES = 4


def log(msg: str) -> None:
    """Log con timestamp"""
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


def backoff_sleep(k: int) -> None:
    """Exponential backoff con tope"""
    delay = min(20.0, 1.5 ** (k + 1))
    time.sleep(delay)


def fetch_ticker_events(api_key: str, ticker: str, rate_limit: float) -> Optional[Dict]:
    """
    Descarga eventos de un ticker desde Polygon /vX/reference/tickers/{ticker}/events
    Filtra solo ticker_change events
    """
    url = POLYGON_BASE + EVENTS_ENDPOINT.format(ticker=ticker)
    params = {
        "apiKey": api_key,
        "types": "ticker_change"  # SOLO ticker changes (no offerings, delistings, etc)
    }

    for k in range(RETRIES):
        try:
            time.sleep(rate_limit)
            resp = requests.get(url, params=params, timeout=TIMEOUT)

            # Handle rate limiting
            if resp.status_code == 429:
                log(f"  [429] Rate limited on {ticker}, backing off...")
                backoff_sleep(k)
                continue

            # Handle not found (ticker doesn't exist or no events)
            if resp.status_code == 404:
                return {"status": "NOT_FOUND", "results": {"events": []}}

            # Raise for other errors
            resp.raise_for_status()

            data = resp.json()
            return data

        except requests.exceptions.Timeout:
            log(f"  [TIMEOUT] {ticker}, retry {k+1}/{RETRIES}")
            backoff_sleep(k)
        except requests.exceptions.RequestException as e:
            log(f"  [ERROR] {ticker}: {e}, retry {k+1}/{RETRIES}")
            backoff_sleep(k)

    # Final attempt
    try:
        time.sleep(rate_limit * 2)
        resp = requests.get(url, params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        log(f"  [FAILED] {ticker} after {RETRIES} retries: {e}")
        return None


def save_ticker_events(ticker: str, events: List[Dict], outdir: Path) -> None:
    """
    Guarda eventos de ticker changes en formato parquet particionado por ticker
    """
    ticker_dir = outdir / f"ticker={ticker}"
    ticker_dir.mkdir(parents=True, exist_ok=True)

    out_file = ticker_dir / "events.parquet"

    if not events:
        # No events - create empty marker
        (ticker_dir / "_SUCCESS").write_text("")
        return

    # Convert to Polars DataFrame
    df = pl.from_dicts(events)

    # Save as parquet
    df.write_parquet(out_file, compression="zstd", compression_level=3)

    # Success marker
    (ticker_dir / "_SUCCESS").write_text("")


def has_success_marker(ticker: str, outdir: Path) -> bool:
    """Check if ticker already processed"""
    return (outdir / f"ticker={ticker}" / "_SUCCESS").exists()


def main():
    ap = argparse.ArgumentParser(description="Download Polygon Ticker Changes (symbol renames/rebranding)")
    ap.add_argument("--tickers-csv", required=True, help="CSV with 'ticker' column")
    ap.add_argument("--tickers-col", default="ticker", help="Ticker column name (default: ticker)")
    ap.add_argument("--outdir", required=True, help="Output directory (will be partitioned by ticker)")
    ap.add_argument("--api-key", help="Polygon API key (or set POLYGON_API_KEY env var)")
    ap.add_argument("--rate-limit", type=float, default=DEFAULT_RATE_LIMIT,
                    help=f"Seconds between requests (default: {DEFAULT_RATE_LIMIT})")
    ap.add_argument("--resume", action="store_true", help="Skip tickers with _SUCCESS marker")
    args = ap.parse_args()

    # Get API key
    api_key = args.api_key or os.getenv("POLYGON_API_KEY", "")
    if not api_key:
        log("ERROR: No Polygon API key provided. Use --api-key or set POLYGON_API_KEY env var")
        sys.exit(1)

    # Load tickers
    df_tickers = pl.read_csv(args.tickers_csv, infer_schema_length=10000)
    if args.tickers_col not in df_tickers.columns:
        log(f"ERROR: Column '{args.tickers_col}' not found in {args.tickers_csv}")
        sys.exit(1)

    tickers = sorted([t for t in df_tickers[args.tickers_col].unique().to_list()
                     if isinstance(t, str) and t.strip()])

    log(f"Total tickers: {len(tickers)}")
    log(f"Output: {args.outdir}")
    log(f"Rate limit: {args.rate_limit}s between requests")
    log(f"Resume mode: {args.resume}")

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    # Process tickers
    ok_count = 0
    skip_count = 0
    fail_count = 0
    no_events_count = 0

    for i, ticker in enumerate(tickers, 1):
        # Resume check
        if args.resume and has_success_marker(ticker, outdir):
            skip_count += 1
            if skip_count % 100 == 0:
                log(f"[SKIP] {i}/{len(tickers)} skipped so far...")
            continue

        # Fetch events
        data = fetch_ticker_events(api_key, ticker, args.rate_limit)

        if data is None:
            fail_count += 1
            log(f"{i}/{len(tickers)} {ticker} - FAILED")
            continue

        # Extract events
        status = data.get("status", "")
        results = data.get("results", {})
        events = results.get("events", []) if results else []

        # Save
        save_ticker_events(ticker, events, outdir)

        if len(events) == 0:
            no_events_count += 1
            log(f"{i}/{len(tickers)} {ticker} - No ticker_change events")
        else:
            ok_count += 1
            log(f"{i}/{len(tickers)} {ticker} - OK {len(events)} events")

    # Summary
    log("")
    log(f"===== SUMMARY =====")
    log(f"Total tickers: {len(tickers)}")
    log(f"Skipped (resume): {skip_count}")
    log(f"Success (with events): {ok_count}")
    log(f"No events: {no_events_count}")
    log(f"Failed: {fail_count}")
    log(f"Output: {outdir}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("\nInterrupted by user")
        sys.exit(130)
