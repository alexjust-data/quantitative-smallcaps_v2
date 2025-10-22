#!/usr/bin/env python3
"""
Retry failed ticker-days with timestamp range splitting.

Strategy: Instead of downloading full day at once, split into 4 sub-ranges (6h each)
to avoid Polygon API cursor bugs on high-volume tickers.

Usage:
    python retry_failed_trades.py \
        --missing-file missing_ticker_days_info_rich.txt \
        --outdir raw/polygon/trades \
        --workers 4 \
        --rate-limit 0.15
"""

import argparse
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import List, Tuple, Dict
import polars as pl
import requests

def log(msg: str):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)

def build_session() -> requests.Session:
    s = requests.Session()
    adapter = requests.adapters.HTTPAdapter(
        pool_connections=2,
        pool_maxsize=3,
        max_retries=0
    )
    s.mount("https://", adapter)
    return s

def success_marker(path: Path):
    (path / "_SUCCESS").touch(exist_ok=True)

def exists_success(path: Path) -> bool:
    return (path / "_SUCCESS").exists()

def http_get_trades(session: requests.Session, ticker: str, ts_gte: str, ts_lt: str,
                    limit: int, api_key: str, cursor: str = None) -> dict:
    """Get trades for ticker in timestamp range [ts_gte, ts_lt)"""
    url = f"https://api.polygon.io/v3/trades/{ticker}"
    params = {
        "limit": limit,
        "sort": "asc",
        "timestamp.gte": ts_gte,
        "timestamp.lt": ts_lt,
        "apiKey": api_key
    }
    if cursor:
        params["cursor"] = cursor

    r = session.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json()

def to_parquet_trades(out_path: Path, records: List[dict]):
    """Write trades to parquet with ZSTD compression"""
    if not records:
        return

    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Convert to polars with explicit schema
    df = pl.DataFrame(records)

    # Rename columns to match expected schema
    rename_map = {}
    if "participant_timestamp" in df.columns:
        rename_map["participant_timestamp"] = "t"
    if "price" in df.columns:
        rename_map["price"] = "p"
    if "size" in df.columns:
        rename_map["size"] = "s"
    if "conditions" in df.columns:
        rename_map["conditions"] = "c"

    if rename_map:
        df = df.rename(rename_map)

    # Write with ZSTD compression
    df.write_parquet(
        out_path,
        compression="zstd",
        compression_level=2,
        statistics=False
    )

def download_ticker_day_split(ticker: str, day: date, outdir: Path,
                               page_limit: int, api_key: str,
                               rate_limit: float) -> Tuple[str, str, str]:
    """
    Download ticker-day with 6-hour range splitting to avoid cursor bugs.

    Strategy: Split day into 4 ranges:
        - 00:00-06:00
        - 06:00-12:00
        - 12:00-18:00
        - 18:00-24:00

    Returns: (ticker, date_str, status)
    """
    day_path = outdir / ticker / f"date={day.isoformat()}"
    if exists_success(day_path):
        return (ticker, day.isoformat(), "skip_exists")

    session = build_session()
    all_records: List[dict] = []

    # Define 6-hour sub-ranges
    ranges = [
        (0, 6),   # 00:00-06:00
        (6, 12),  # 06:00-12:00
        (12, 18), # 12:00-18:00
        (18, 24)  # 18:00-24:00
    ]

    try:
        for start_hour, end_hour in ranges:
            ts_gte = f"{day.isoformat()}T{start_hour:02d}:00:00Z"
            ts_lt = f"{day.isoformat()}T{end_hour:02d}:00:00Z" if end_hour < 24 else f"{(day + timedelta(days=1)).isoformat()}T00:00:00Z"

            cursor = None
            range_records = []

            # Paginate within this 6-hour range
            while True:
                try:
                    data = http_get_trades(session, ticker, ts_gte, ts_lt,
                                          page_limit, api_key, cursor)

                    results = data.get("results", [])
                    if results:
                        range_records.extend(results)

                    # Get next cursor
                    cursor = data.get("next_url") or data.get("nextUrl")
                    if cursor and "cursor=" in cursor:
                        cursor = cursor.split("cursor=")[-1]
                    else:
                        cursor = data.get("next_page_token")

                    time.sleep(rate_limit)

                    if not cursor:
                        break

                except requests.HTTPError as e:
                    if e.response.status_code == 429:
                        log(f"{ticker} {day}: 429 in range {start_hour:02d}-{end_hour:02d}, sleep 30s")
                        time.sleep(30)
                        continue
                    elif e.response.status_code == 400:
                        # Cursor bug - log and skip this range
                        log(f"{ticker} {day}: ERROR 400 in range {start_hour:02d}-{end_hour:02d} (cursor bug)")
                        break  # Skip to next range
                    else:
                        raise
                except Exception as e:
                    log(f"{ticker} {day}: ERROR in range {start_hour:02d}-{end_hour:02d}: {e}")
                    break  # Skip to next range

            # Add this range's records to total
            if range_records:
                all_records.extend(range_records)
                log(f"{ticker} {day}: range {start_hour:02d}-{end_hour:02d} -> {len(range_records):,} trades")

        # Write combined records from all ranges
        if all_records:
            out_parquet = day_path / "trades.parquet"
            to_parquet_trades(out_parquet, all_records)
            success_marker(day_path)
            return (ticker, day.isoformat(), f"ok_{len(all_records)}_trades")
        else:
            log(f"{ticker} {day}: WARNING - no trades found in any range")
            return (ticker, day.isoformat(), "no_data")

    except Exception as e:
        log(f"{ticker} {day}: FATAL ERROR {e}")
        return (ticker, day.isoformat(), f"error_{e}")

def retry_worker(args_tuple):
    """Worker function for multiprocessing"""
    tasks, outdir, page_limit, api_key, rate_limit = args_tuple
    results = []

    for ticker, date_str in tasks:
        day = date.fromisoformat(date_str)
        result = download_ticker_day_split(ticker, day, outdir,
                                          page_limit, api_key, rate_limit)
        results.append(result)

    return results

def main():
    parser = argparse.ArgumentParser(description="Retry failed ticker-days with range splitting")
    parser.add_argument("--missing-file", required=True, help="File with missing ticker-days (ticker,date per line)")
    parser.add_argument("--outdir", required=True, help="Output directory for trades")
    parser.add_argument("--workers", type=int, default=4, help="Number of parallel workers")
    parser.add_argument("--rate-limit", type=float, default=0.15, help="Rate limit between requests (seconds)")
    parser.add_argument("--page-limit", type=int, default=50000, help="Trades per page")
    parser.add_argument("--batch-size", type=int, default=10, help="Tasks per batch per worker")

    args = parser.parse_args()

    api_key = os.getenv("POLYGON_API_KEY")
    if not api_key:
        raise ValueError("POLYGON_API_KEY environment variable not set")

    # Load missing ticker-days
    missing_tasks = []
    with open(args.missing_file, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            ticker, date_str = line.split(',')
            missing_tasks.append((ticker, date_str))

    log(f"Loaded {len(missing_tasks):,} missing ticker-days from {args.missing_file}")
    log(f"Config: workers={args.workers}, rate_limit={args.rate_limit}s, page_limit={args.page_limit:,}")
    log(f"Strategy: 6-hour range splitting per day (4 ranges: 00-06, 06-12, 12-18, 18-24)")

    # Split into batches
    BATCH = args.batch_size
    batches = [missing_tasks[i:i+BATCH] for i in range(0, len(missing_tasks), BATCH)]
    log(f"Split into {len(batches)} batches of ~{BATCH} tasks each")

    outdir = Path(args.outdir)
    started = time.time()

    # Prepare worker arguments
    worker_args = [(batch, outdir, args.page_limit, api_key, args.rate_limit)
                   for batch in batches]

    # Execute with multiprocessing
    total_ok = 0
    total_err = 0
    total_skip = 0

    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futs = [ex.submit(retry_worker, wa) for wa in worker_args]
        done = 0

        for f in as_completed(futs):
            done += 1
            try:
                results = f.result()
                ok_count = sum(1 for _, _, status in results if status.startswith("ok"))
                skip_count = sum(1 for _, _, status in results if status == "skip_exists")
                err_count = len(results) - ok_count - skip_count

                total_ok += ok_count
                total_err += err_count
                total_skip += skip_count

                elapsed = (time.time() - started) / 60
                log(f"Progress: {done}/{len(batches)} batches ({done/len(batches)*100:.1f}%) | "
                    f"OK: {total_ok:,}, SKIP: {total_skip:,}, ERR: {total_err} | {elapsed:.1f} min")
            except Exception as e:
                total_err += BATCH
                log(f"Progress: {done}/{len(batches)} batches - BATCH ERROR: {e}")

    elapsed = (time.time() - started) / 60
    recovered = total_ok
    recovery_rate = recovered / len(missing_tasks) * 100 if missing_tasks else 0

    log(f"\n{'='*60}")
    log(f"RETRY COMPLETADO")
    log(f"{'='*60}")
    log(f"Tiempo: {elapsed:.1f} min")
    log(f"Total intentados: {len(missing_tasks):,}")
    log(f"Recuperados (OK): {total_ok:,} ({recovery_rate:.1f}%)")
    log(f"Ya existían (SKIP): {total_skip:,}")
    log(f"Fallidos (ERR): {total_err}")
    log(f"{'='*60}")

if __name__ == "__main__":
    main()
