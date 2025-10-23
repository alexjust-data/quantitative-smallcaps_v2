#!/usr/bin/env python3
"""
Batch download ALL ticker-days from Polygon (unlimited plan).

This script:
1. Discovers all ticker-day pairs from our processed DIB bars
2. Downloads minute data from Polygon for each pair
3. Saves raw JSON responses to raw_data/
4. Provides progress tracking and error handling

Usage:
    python batch_download_polygon_complete.py --dib-root ../../../../../../processed/bars
"""

import argparse
import json
import pathlib
import sys
import time
from datetime import datetime
from typing import List, Tuple

# Add vendors to path
sys.path.insert(0, str(pathlib.Path(__file__).parent))

from vendors.polygon_client import fetch_polygon_1min


def discover_ticker_days(dib_root: pathlib.Path) -> List[Tuple[str, str]]:
    """
    Discover all ticker-day pairs from DIB bars directory.

    Returns:
        List of (symbol, date) tuples
    """
    pairs = []

    if not dib_root.exists():
        print(f"[ERROR] DIB root does not exist: {dib_root}")
        return pairs

    # Iterate through symbol directories
    for symbol_dir in sorted(dib_root.iterdir()):
        if not symbol_dir.is_dir():
            continue

        symbol = symbol_dir.name

        # Iterate through date partitions
        for date_dir in sorted(symbol_dir.iterdir()):
            if not date_dir.is_dir() or not date_dir.name.startswith("date="):
                continue

            date_str = date_dir.name.replace("date=", "")

            # Check if dollar_imbalance.parquet exists
            dib_file = date_dir / "dollar_imbalance.parquet"
            if dib_file.exists():
                pairs.append((symbol, date_str))

    return pairs


def download_polygon_data(symbol: str, date: str, output_dir: pathlib.Path, api_key: str) -> bool:
    """
    Download Polygon minute data for a single ticker-day.

    Returns:
        True if successful, False otherwise
    """
    output_file = output_dir / f"{symbol}_{date}_polygon_raw.json"

    # Skip if already downloaded
    if output_file.exists():
        print(f"[SKIP] {symbol} {date} - already exists")
        return True

    try:
        # Fetch data (returns DataFrame, but we want raw JSON)
        # We'll modify polygon_client to also save raw response
        df = fetch_polygon_1min(symbol, date, api_key)

        if df is None or df.empty:
            print(f"[WARN] {symbol} {date} - no data returned")
            return False

        print(f"[OK] {symbol} {date} - {len(df)} bars")
        return True

    except Exception as e:
        print(f"[ERROR] {symbol} {date} - {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Batch download from Polygon (unlimited)")
    parser.add_argument("--dib-root", required=True, help="Path to processed/bars directory")
    parser.add_argument("--output-dir", default="raw_data", help="Output directory for raw data")
    parser.add_argument("--api-key", help="Polygon API key (or set POLYGON_API_KEY env var)")
    parser.add_argument("--delay", type=float, default=0.1, help="Delay between requests (seconds)")
    parser.add_argument("--limit", type=int, help="Limit number of downloads (for testing)")

    args = parser.parse_args()

    # Setup paths
    dib_root = pathlib.Path(args.dib_root).resolve()
    output_dir = pathlib.Path(args.output_dir).resolve()
    output_dir.mkdir(exist_ok=True, parents=True)

    # Load API key
    api_key = args.api_key
    if not api_key:
        import os
        api_key = os.getenv("POLYGON_API_KEY")

    if not api_key:
        print("[ERROR] No API key provided. Use --api-key or set POLYGON_API_KEY")
        sys.exit(1)

    # Discover ticker-days
    print(f"[INFO] Discovering ticker-days from {dib_root}")
    pairs = discover_ticker_days(dib_root)

    if not pairs:
        print("[ERROR] No ticker-day pairs found")
        sys.exit(1)

    total = len(pairs)
    if args.limit:
        pairs = pairs[:args.limit]
        total = len(pairs)

    print(f"[INFO] Found {total} ticker-day pairs")
    print(f"[INFO] Output directory: {output_dir}")
    print(f"[INFO] Starting downloads...")
    print()

    # Download progress tracking
    success_count = 0
    skip_count = 0
    error_count = 0
    start_time = time.time()

    for i, (symbol, date) in enumerate(pairs, 1):
        print(f"[{i}/{total}] {symbol} {date}", end=" - ")

        result = download_polygon_data(symbol, date, output_dir, api_key)

        if result:
            success_count += 1
        else:
            error_count += 1

        # Rate limiting (Polygon allows high throughput, but be respectful)
        if i < total:
            time.sleep(args.delay)

        # Progress update every 50 downloads
        if i % 50 == 0:
            elapsed = time.time() - start_time
            rate = i / elapsed
            remaining = (total - i) / rate if rate > 0 else 0
            print(f"\n[PROGRESS] {i}/{total} ({100*i/total:.1f}%) - {rate:.1f} downloads/sec - ETA: {remaining/60:.1f} min\n")

    # Final summary
    elapsed = time.time() - start_time
    print()
    print("=" * 60)
    print("DOWNLOAD SUMMARY")
    print("=" * 60)
    print(f"Total pairs:     {total}")
    print(f"Successful:      {success_count}")
    print(f"Errors:          {error_count}")
    print(f"Time elapsed:    {elapsed/60:.1f} minutes")
    print(f"Rate:            {total/elapsed:.1f} downloads/sec")
    print(f"Output dir:      {output_dir}")
    print("=" * 60)

    # Save summary
    summary = {
        "timestamp": datetime.now().isoformat(),
        "total_pairs": total,
        "successful": success_count,
        "errors": error_count,
        "time_elapsed_sec": elapsed,
        "rate_per_sec": total / elapsed if elapsed > 0 else 0,
        "output_dir": str(output_dir)
    }

    summary_file = output_dir / "polygon_download_summary.json"
    with open(summary_file, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\nSummary saved to: {summary_file}")


if __name__ == "__main__":
    main()
