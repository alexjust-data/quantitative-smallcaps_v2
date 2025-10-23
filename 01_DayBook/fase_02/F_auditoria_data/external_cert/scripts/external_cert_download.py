#!/usr/bin/env python3
"""
External Certification - Download Script
Downloads raw data from Alpha Vantage, Yahoo Finance, and Twelve Data.

Usage:
    python external_cert_download.py --config ../config/samples.yaml
"""

import argparse
import json
import pathlib
import sys
import time
from datetime import datetime
from typing import Dict, List
import yaml
import os
from dotenv import load_dotenv

# Load environment variables
project_root = pathlib.Path(__file__).parent.parent.parent.parent.parent.parent
env_file = project_root / ".env"
if env_file.exists():
    load_dotenv(env_file)

# Add vendors to path
vendors_path = pathlib.Path(__file__).parent.parent.parent / "independent_audit_multi_wrds" / "independent_audit_multi"
sys.path.insert(0, str(vendors_path))

try:
    from vendors.alphavantage_client import fetch_alphavantage_1min
    from vendors.twelvedata_client import fetch_twelvedata_1min
except ImportError as e:
    print(f"[ERROR] Could not import vendor clients: {e}")
    print(f"[ERROR] Make sure vendors are in: {vendors_path}")
    sys.exit(1)

# Yahoo Finance
try:
    import yfinance as yf
except ImportError:
    print("[WARN] yfinance not installed. Yahoo Finance downloads will be skipped.")
    yf = None


def load_config(config_path: pathlib.Path) -> Dict:
    """Load configuration from YAML file."""
    with open(config_path) as f:
        return yaml.safe_load(f)


def download_alphavantage_month(symbol: str, year_month: str, output_dir: pathlib.Path, api_key: str) -> bool:
    """
    Download full month from Alpha Vantage (1 call = ~20 trading days).

    Args:
        symbol: Ticker symbol
        year_month: Format "YYYY-MM"
        output_dir: Directory to save raw JSON
        api_key: Alpha Vantage API key

    Returns:
        True if successful, False otherwise
    """
    output_file = output_dir / f"{symbol}_{year_month}_alphavantage_raw.json"

    # Skip if already exists
    if output_file.exists():
        print(f"[SKIP] {symbol} {year_month} - Alpha Vantage data already exists")
        return True

    print(f"[DOWNLOADING] {symbol} {year_month} from Alpha Vantage...")

    try:
        import requests

        url = "https://www.alphavantage.co/query"
        params = {
            "function": "TIME_SERIES_INTRADAY",
            "symbol": symbol,
            "interval": "1min",
            "month": year_month,
            "outputsize": "full",
            "apikey": api_key
        }

        response = requests.get(url, params=params, timeout=60)
        response.raise_for_status()
        data = response.json()

        # Check for API errors
        if "Error Message" in data:
            print(f"[ERROR] Alpha Vantage API error: {data['Error Message']}")
            return False

        if "Note" in data:
            print(f"[ERROR] Alpha Vantage rate limit: {data['Note']}")
            return False

        # Save raw JSON
        output_file.write_text(json.dumps(data, indent=2))

        # Count data points
        time_series_key = "Time Series (1min)"
        if time_series_key in data:
            count = len(data[time_series_key])
            print(f"[OK] {symbol} {year_month} - {count} minute bars downloaded")
            return True
        else:
            print(f"[WARN] {symbol} {year_month} - No time series data in response")
            return False

    except Exception as e:
        print(f"[ERROR] {symbol} {year_month} - {e}")
        return False


def download_yahoo_daily(symbol: str, start_date: str, end_date: str, output_dir: pathlib.Path) -> bool:
    """
    Download daily bars from Yahoo Finance (unlimited, free).

    Args:
        symbol: Ticker symbol
        start_date: Start date "YYYY-MM-DD"
        end_date: End date "YYYY-MM-DD"
        output_dir: Directory to save CSV

    Returns:
        True if successful, False otherwise
    """
    if yf is None:
        print("[SKIP] Yahoo Finance - yfinance not installed")
        return False

    output_file_unadj = output_dir / f"{symbol}_{start_date}_{end_date}_yahoo_unadj.csv"
    output_file_adj = output_dir / f"{symbol}_{start_date}_{end_date}_yahoo_adj.csv"

    # Skip if both exist
    if output_file_unadj.exists() and output_file_adj.exists():
        print(f"[SKIP] {symbol} {start_date} to {end_date} - Yahoo data already exists")
        return True

    print(f"[DOWNLOADING] {symbol} {start_date} to {end_date} from Yahoo Finance...")

    try:
        ticker = yf.Ticker(symbol)

        # Download unadjusted
        df_unadj = yf.download(symbol, start=start_date, end=end_date, auto_adjust=False, progress=False)
        if not df_unadj.empty:
            df_unadj.to_csv(output_file_unadj)
            print(f"[OK] {symbol} - {len(df_unadj)} days (unadjusted)")

        # Download adjusted
        df_adj = yf.download(symbol, start=start_date, end=end_date, auto_adjust=True, progress=False)
        if not df_adj.empty:
            df_adj.to_csv(output_file_adj)
            print(f"[OK] {symbol} - {len(df_adj)} days (adjusted)")

        # Download splits and dividends
        splits = ticker.splits
        if not splits.empty:
            splits_file = output_dir / f"{symbol}_yahoo_splits.csv"
            splits.to_csv(splits_file)
            print(f"[OK] {symbol} - {len(splits)} splits")

        dividends = ticker.dividends
        if not dividends.empty:
            divs_file = output_dir / f"{symbol}_yahoo_dividends.csv"
            dividends.to_csv(divs_file)
            print(f"[OK] {symbol} - {len(dividends)} dividends")

        return True

    except Exception as e:
        print(f"[ERROR] {symbol} Yahoo Finance - {e}")
        return False


def download_twelvedata(symbol: str, date: str, output_dir: pathlib.Path, api_key: str) -> bool:
    """
    Download minute bars from Twelve Data (spot check only).

    Args:
        symbol: Ticker symbol
        date: Date "YYYY-MM-DD"
        output_dir: Directory to save data
        api_key: Twelve Data API key

    Returns:
        True if successful, False otherwise
    """
    output_file = output_dir / f"{symbol}_{date}_twelvedata_raw.json"

    # Skip if exists
    if output_file.exists():
        print(f"[SKIP] {symbol} {date} - Twelve Data already exists")
        return True

    print(f"[DOWNLOADING] {symbol} {date} from Twelve Data...")

    try:
        df = fetch_twelvedata_1min(symbol, date, api_key)

        if df is None or df.empty:
            print(f"[WARN] {symbol} {date} - No data from Twelve Data")
            return False

        # Save as JSON (convert DataFrame to records)
        data = {
            "symbol": symbol,
            "date": date,
            "bars": df.to_dict(orient="records")
        }

        output_file.write_text(json.dumps(data, indent=2, default=str))
        print(f"[OK] {symbol} {date} - {len(df)} bars from Twelve Data")
        return True

    except Exception as e:
        print(f"[ERROR] {symbol} {date} Twelve Data - {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Download external vendor data")
    parser.add_argument("--config", required=True, help="Path to samples.yaml config file")
    parser.add_argument("--vendors", nargs="+", default=["alphavantage", "yahoo", "twelvedata"],
                        help="Vendors to download from")

    args = parser.parse_args()

    # Load configuration
    config_path = pathlib.Path(args.config)
    if not config_path.exists():
        print(f"[ERROR] Config file not found: {config_path}")
        sys.exit(1)

    config = load_config(config_path)

    # Get API keys
    av_key = os.getenv("ALPHAVANTAGE_API_KEY")
    td_key = os.getenv("TWELVEDATA_API_KEY")

    if not av_key and "alphavantage" in args.vendors:
        print("[WARN] ALPHAVANTAGE_API_KEY not set")
    if not td_key and "twelvedata" in args.vendors:
        print("[WARN] TWELVEDATA_API_KEY not set")

    # Setup output directories
    base_dir = pathlib.Path(__file__).parent.parent
    av_dir = base_dir / "raw_data" / "alphavantage"
    yahoo_dir = base_dir / "raw_data" / "yahoo"
    td_dir = base_dir / "raw_data" / "twelvedata"

    av_dir.mkdir(parents=True, exist_ok=True)
    yahoo_dir.mkdir(parents=True, exist_ok=True)
    td_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("EXTERNAL CERTIFICATION - DATA DOWNLOAD")
    print("=" * 70)
    print(f"Config: {config_path}")
    print(f"Vendors: {', '.join(args.vendors)}")
    print(f"Output: {base_dir / 'raw_data'}")
    print()

    # Get priority tickers
    priority_tickers = config.get("priority_tickers", [])

    if not priority_tickers:
        print("[ERROR] No priority tickers in config")
        sys.exit(1)

    print(f"[INFO] {len(priority_tickers)} priority tickers to download")
    print()

    # Track statistics
    stats = {
        "alphavantage": {"success": 0, "skip": 0, "error": 0},
        "yahoo": {"success": 0, "skip": 0, "error": 0},
        "twelvedata": {"success": 0, "skip": 0, "error": 0}
    }

    # Download from each vendor
    for ticker_info in priority_tickers:
        symbol = ticker_info["symbol"]
        dates = ticker_info.get("dates", [])

        print(f"\n{'='*70}")
        print(f"SYMBOL: {symbol}")
        print(f"{'='*70}")

        # Alpha Vantage: Download by month (1 call = full month)
        if "alphavantage" in args.vendors and av_key:
            # Extract unique year-months from dates
            year_months = set()
            for date in dates:
                year_month = date[:7]  # "YYYY-MM"
                year_months.add(year_month)

            for year_month in sorted(year_months):
                result = download_alphavantage_month(symbol, year_month, av_dir, av_key)
                if result:
                    stats["alphavantage"]["success"] += 1
                else:
                    stats["alphavantage"]["error"] += 1

                # Rate limiting (5 calls/min)
                time.sleep(12)  # 12 seconds = 5 calls/min

        # Yahoo Finance: Download daily data for date range
        if "yahoo" in args.vendors and dates:
            start_date = min(dates)
            end_date = max(dates)
            result = download_yahoo_daily(symbol, start_date, end_date, yahoo_dir)
            if result:
                stats["yahoo"]["success"] += 1
            else:
                stats["yahoo"]["error"] += 1

        # Twelve Data: Download specific dates (spot checks only)
        if "twelvedata" in args.vendors and td_key:
            # Only download first date as spot check
            if dates:
                date = dates[0]
                result = download_twelvedata(symbol, date, td_dir, td_key)
                if result:
                    stats["twelvedata"]["success"] += 1
                else:
                    stats["twelvedata"]["error"] += 1

                # Rate limiting (8 calls/min)
                time.sleep(8)

    # Print summary
    print(f"\n{'='*70}")
    print("DOWNLOAD SUMMARY")
    print(f"{'='*70}")

    for vendor, counts in stats.items():
        if counts["success"] + counts["error"] > 0:
            print(f"\n{vendor.upper()}:")
            print(f"  Success: {counts['success']}")
            print(f"  Errors:  {counts['error']}")
            total = counts["success"] + counts["error"]
            success_rate = (counts["success"] / total * 100) if total > 0 else 0
            print(f"  Success Rate: {success_rate:.1f}%")

    print(f"\n{'='*70}")
    print("✅ Download phase complete")
    print(f"Raw data saved to: {base_dir / 'raw_data'}")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
