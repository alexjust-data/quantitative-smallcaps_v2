#!/usr/bin/env python3
"""
Preprocess vendor data files to normalized format

Normalizes vendor data to consistent UTC timezone and optionally filters to Regular Trading Hours (RTH).

Usage:
    python preprocess_vendor_data.py --in data.json --vendor twelvedata --assume-tz US/Eastern --rth-only --out normalized/WOLF_2025-05-13_twelvedata_minute.parquet
"""

import argparse
import pathlib
import pandas as pd
import json
from datetime import time

def parse_vendor_json(data: dict, vendor: str) -> pd.DataFrame:
    """
    Parse vendor-specific JSON structures into standard DataFrame

    Args:
        data: Raw JSON data from vendor API
        vendor: Vendor name (alphavantage, twelvedata, polygon, fmp)

    Returns:
        DataFrame with columns: timestamp, open, high, low, close, volume
    """
    vendor_lower = vendor.strip().lower()

    if vendor_lower == "alphavantage":
        # Alpha Vantage: timestamps as dictionary keys
        time_series_key = "Time Series (1min)"
        if time_series_key not in data:
            raise ValueError(f"Missing '{time_series_key}' in Alpha Vantage response")

        records = []
        for timestamp_str, values in data[time_series_key].items():
            records.append({
                "timestamp": timestamp_str,
                "open": values.get("1. open"),
                "high": values.get("2. high"),
                "low": values.get("3. low"),
                "close": values.get("4. close"),
                "volume": values.get("5. volume")
            })
        return pd.DataFrame(records)

    elif vendor_lower == "twelvedata":
        # Twelve Data: 'values' array with 'datetime' column
        if "values" not in data:
            raise ValueError("Missing 'values' in Twelve Data response")

        df = pd.DataFrame(data["values"])

        # Rename 'datetime' to 'timestamp' for consistency
        if "datetime" in df.columns:
            df = df.rename(columns={"datetime": "timestamp"})
        elif "date" in df.columns:
            df = df.rename(columns={"date": "timestamp"})

        return df

    elif vendor_lower == "polygon":
        # Polygon: 'results' array with 't' as unix nanoseconds
        if "results" not in data:
            raise ValueError("Missing 'results' in Polygon response")

        df = pd.DataFrame(data["results"])

        # Rename columns to standard names
        column_map = {
            "t": "timestamp_ns",  # Unix nanoseconds
            "o": "open",
            "h": "high",
            "l": "low",
            "c": "close",
            "v": "volume"
        }

        df = df.rename(columns=column_map)

        # Convert unix nanoseconds to datetime
        if "timestamp_ns" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp_ns"], unit="ns", utc=True)
            df = df.drop(columns=["timestamp_ns"])

        return df

    elif vendor_lower == "fmp":
        # FMP: array with 'date' column
        if isinstance(data, list):
            df = pd.DataFrame(data)
        else:
            raise ValueError("FMP response should be a list")

        # Rename 'date' to 'timestamp'
        if "date" in df.columns:
            df = df.rename(columns={"date": "timestamp"})

        return df

    else:
        # Generic: assume it's already a DataFrame-compatible structure
        if isinstance(data, list):
            return pd.DataFrame(data)
        elif isinstance(data, dict) and "data" in data:
            return pd.DataFrame(data["data"])
        else:
            raise ValueError(f"Unknown JSON structure for vendor: {vendor}")

def normalize_vendor_data(
    input_path: str,
    vendor: str,
    assume_tz: str = "UTC",
    rth_only: bool = False,
    output_path: str = None
):
    """
    Normalize vendor data to UTC and optionally filter to RTH

    Args:
        input_path: Path to input file (parquet, csv, json)
        vendor: Vendor name (for custom parsing logic)
        assume_tz: Timezone to assume if timestamps are naive
        rth_only: If True, filter to Regular Trading Hours (09:30-16:00 ET)
        output_path: Path to output file (parquet, csv, json)

    Returns:
        DataFrame with columns: t, open, high, low, close, volume (all in UTC)
    """
    # Read input file
    input_path = pathlib.Path(input_path)
    if input_path.suffix.lower() in (".parquet", ".pq"):
        df = pd.read_parquet(input_path)
    elif input_path.suffix.lower() in (".csv", ".txt"):
        df = pd.read_csv(input_path)
    elif input_path.suffix.lower() == ".json":
        # Use vendor-specific parser for JSON files
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        df = parse_vendor_json(data, vendor)
    else:
        raise ValueError(f"Unsupported file type: {input_path.suffix}")

    # Detect timestamp column
    time_col = None
    for col in ["t", "timestamp", "datetime", "date", "time"]:
        if col in df.columns:
            time_col = col
            break

    if time_col is None:
        raise ValueError(f"No timestamp column found in {input_path}")

    # Parse timestamps
    dt = pd.to_datetime(df[time_col], errors="coerce")

    # Handle timezone
    if dt.dt.tz is None:
        # Naive timestamps - localize to assumed timezone
        import pytz
        tz = pytz.timezone(assume_tz)
        dt = dt.dt.tz_localize(tz, nonexistent='NaT', ambiguous='NaT')

    # Convert to UTC
    dt = dt.dt.tz_convert("UTC")

    # Assign normalized timestamp
    df["t"] = dt

    # Ensure OHLCV columns exist
    required_cols = ["open", "high", "low", "close", "volume"]
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    # Select and order columns
    df = df[["t", "open", "high", "low", "close", "volume"]].copy()

    # Convert types
    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype(float)
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0).astype("Int64")

    # Drop invalid rows
    df = df.dropna(subset=["t"]).sort_values("t")

    # Filter to Regular Trading Hours if requested
    if rth_only:
        # RTH: 09:30-16:00 US/Eastern
        import pytz
        eastern = pytz.timezone("US/Eastern")

        # Convert to Eastern for filtering
        df_et = df.copy()
        df_et["t_et"] = df_et["t"].dt.tz_convert(eastern)
        df_et["time_only"] = df_et["t_et"].dt.time

        # Define RTH bounds
        rth_start = time(9, 30)   # 09:30
        rth_end = time(16, 0)     # 16:00

        # Filter
        mask = (df_et["time_only"] >= rth_start) & (df_et["time_only"] < rth_end)
        df = df[mask].copy()

        print(f"Filtered to RTH (09:30-16:00 ET): {len(df)} rows remaining")

    # Write output if specified
    if output_path:
        output_path = pathlib.Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if output_path.suffix.lower() in (".parquet", ".pq"):
            df.to_parquet(output_path, index=False)
        elif output_path.suffix.lower() in (".csv", ".txt"):
            df.to_csv(output_path, index=False)
        elif output_path.suffix.lower() == ".json":
            df.to_json(output_path, orient="records", date_format="iso")
        else:
            raise ValueError(f"Unsupported output type: {output_path.suffix}")

        print(f"Wrote {len(df)} rows to {output_path}")

    return df

def main():
    parser = argparse.ArgumentParser(description="Normalize vendor data to UTC and optionally filter to RTH")
    parser.add_argument("--in", dest="input", required=True, help="Input file (parquet, csv, json)")
    parser.add_argument("--vendor", required=True, help="Vendor name (for logging/identification)")
    parser.add_argument("--assume-tz", default="UTC", help="Timezone to assume for naive timestamps (default: UTC)")
    parser.add_argument("--rth-only", action="store_true", help="Filter to Regular Trading Hours (09:30-16:00 ET)")
    parser.add_argument("--out", required=True, help="Output file path (format: <SYMBOL>_<DATE>_<VENDOR>_minute.(parquet|csv|json))")

    args = parser.parse_args()

    print(f"Normalizing {args.vendor} data from {args.input}")
    print(f"Assume timezone: {args.assume_tz}")
    print(f"RTH only: {args.rth_only}")

    df = normalize_vendor_data(
        input_path=args.input,
        vendor=args.vendor,
        assume_tz=args.assume_tz,
        rth_only=args.rth_only,
        output_path=args.out
    )

    print(f"\nSummary:")
    print(f"  Rows: {len(df)}")
    print(f"  Time range: {df['t'].min()} to {df['t'].max()}")
    print(f"  Volume range: {df['volume'].min():,} to {df['volume'].max():,}")

if __name__ == "__main__":
    main()
