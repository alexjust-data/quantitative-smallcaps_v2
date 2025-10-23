#!/usr/bin/env python3
"""
Comparación estratégica de minute bars: nuestra data vs vendors externos.

Este script:
1. Selecciona samples estratégicos (high/low volume, recent dates)
2. Carga nuestros minute bars de Polygon (raw/polygon/ohlcv_intraday_1m)
3. Descarga minute bars de vendors externos (Alpha Vantage, Twelve Data)
4. Compara OHLCV bar por bar
5. Genera reporte de match rate y discrepancias

Usage:
    python strategic_comparison_minute.py \\
        --our-minute-root ../../../../../../raw/polygon/ohlcv_intraday_1m \\
        --samples WOLF,2025-05-13 NVDA,2025-05-13 AAPL,2025-05-13
"""

import argparse
import json
import pathlib
import sys
from datetime import datetime
from typing import List, Tuple, Dict
import pandas as pd
import polars as pl
import os
from dotenv import load_dotenv

# Load .env from project root
project_root = pathlib.Path(__file__).parent.parent.parent.parent.parent.parent
env_file = project_root / ".env"
if env_file.exists():
    load_dotenv(env_file)
    print(f"[INFO] Loaded .env from {env_file}")

# Add current directory to path
sys.path.insert(0, str(pathlib.Path(__file__).parent))

from vendors.alphavantage_client import fetch_alphavantage_1min
from vendors.twelvedata_client import fetch_twelvedata_1min
from utils.compare_minute import compare_ohlcv


def load_our_minute_bars(root: pathlib.Path, symbol: str, date: str) -> pd.DataFrame:
    """
    Carga nuestros minute bars desde raw/polygon/ohlcv_intraday_1m.

    Estructura: symbol/year=YYYY/month=MM/minute.parquet

    Returns:
        DataFrame con columnas: t, open, high, low, close, volume
    """
    year, month, day = date.split("-")

    # Buscar archivo parquet
    parquet_file = root / symbol / f"year={year}" / f"month={month}" / "minute.parquet"

    if not parquet_file.exists():
        print(f"[WARN] No minute data found for {symbol} {date}")
        print(f"       Expected: {parquet_file}")
        return pd.DataFrame(columns=["t", "open", "high", "low", "close", "volume"])

    # Leer con polars (más rápido)
    df = pl.read_parquet(parquet_file)

    # Filtrar por fecha específica (usar columna 'date' que es String)
    df = df.filter(pl.col("date") == date)

    # Convertir a pandas
    df = df.to_pandas()

    # Usar columna 'minute' como timestamp (formato: "2025-05-13 HH:MM")
    if "minute" in df.columns:
        df["t"] = pd.to_datetime(df["minute"], utc=True)
    else:
        # Fallback: usar columna 't' como Unix milliseconds
        df["t"] = pd.to_datetime(df["t"], unit="ms", utc=True)

    # Renombrar columnas OHLCV si necesario
    if "o" in df.columns:
        df = df.rename(columns={"o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"})

    # Ordenar por timestamp
    df = df.sort_values("t").reset_index(drop=True)

    print(f"[LOADED] {symbol} {date} - {len(df)} bars from our data")

    return df[["t", "open", "high", "low", "close", "volume"]]


def compare_with_vendor(
    our_data: pd.DataFrame,
    vendor: str,
    symbol: str,
    date: str,
    api_key: str = None
) -> Dict:
    """
    Compara nuestros minute bars vs un vendor externo.

    Returns:
        Dict con resultados de comparación
    """
    print(f"\n[COMPARING] {symbol} {date} vs {vendor}")

    # Descargar data del vendor
    try:
        if vendor.lower() == "alphavantage":
            vendor_data = fetch_alphavantage_1min(symbol, date, api_key)
        elif vendor.lower() == "twelvedata":
            vendor_data = fetch_twelvedata_1min(symbol, date, api_key)
        else:
            raise ValueError(f"Unknown vendor: {vendor}")

        if vendor_data is None or vendor_data.empty:
            print(f"[ERROR] No data returned from {vendor}")
            return {
                "vendor": vendor,
                "status": "no_data",
                "error": "Vendor returned no data"
            }

        print(f"[DOWNLOADED] {vendor} - {len(vendor_data)} bars")

    except Exception as e:
        print(f"[ERROR] Failed to download from {vendor}: {e}")
        return {
            "vendor": vendor,
            "status": "error",
            "error": str(e)
        }

    # Comparar usando compare_ohlcv
    try:
        result = compare_ohlcv(
            df_ref=vendor_data,
            df_ours=our_data,
            price_tol=0.01,  # 1% tolerance for price differences
            vol_tol=0.05     # 5% tolerance for volume differences
        )

        # Agregar vendor info
        result["vendor"] = vendor
        result["status"] = "success"

        # Print summary
        print(f"\n[RESULT] {vendor} Comparison:")
        print(f"  Rows compared: {result.get('rows_compared', 0)}")
        print(f"  Match rate: {result.get('match_rate', 0)*100:.2f}%")
        print(f"  Breaks: {len(result.get('breaks', []))}")
        print(f"  Avg price diff: {result.get('stats', {}).get('mean_d_price', 0)*100:.3f}%")
        print(f"  Avg volume diff: {result.get('stats', {}).get('mean_d_vol', 0)*100:.3f}%")

        return result

    except Exception as e:
        print(f"[ERROR] Comparison failed: {e}")
        return {
            "vendor": vendor,
            "status": "comparison_error",
            "error": str(e)
        }


def main():
    parser = argparse.ArgumentParser(description="Strategic minute bar comparison")
    parser.add_argument("--our-minute-root", required=True, help="Path to raw/polygon/ohlcv_intraday_1m")
    parser.add_argument("--samples", nargs="+", required=True, help="List of SYMBOL,DATE pairs")
    parser.add_argument("--vendors", nargs="+", default=["alphavantage", "twelvedata"], help="Vendors to compare")
    parser.add_argument("--output-dir", default="comparison_results", help="Output directory")
    parser.add_argument("--alphavantage-key", help="Alpha Vantage API key")
    parser.add_argument("--twelvedata-key", help="Twelve Data API key")

    args = parser.parse_args()

    # Setup paths
    our_root = pathlib.Path(args.our_minute_root).resolve()
    output_dir = pathlib.Path(args.output_dir).resolve()
    output_dir.mkdir(exist_ok=True, parents=True)

    # Load API keys
    import os
    av_key = args.alphavantage_key or os.getenv("ALPHAVANTAGE_API_KEY")
    td_key = args.twelvedata_key or os.getenv("TWELVEDATA_API_KEY")

    # Parse samples
    samples = []
    for sample in args.samples:
        parts = sample.split(",")
        if len(parts) != 2:
            print(f"[WARN] Invalid sample format: {sample} (expected SYMBOL,DATE)")
            continue
        samples.append((parts[0].strip(), parts[1].strip()))

    if not samples:
        print("[ERROR] No valid samples provided")
        sys.exit(1)

    print("=" * 70)
    print("STRATEGIC MINUTE BAR COMPARISON")
    print("=" * 70)
    print(f"Our data root: {our_root}")
    print(f"Samples: {len(samples)}")
    print(f"Vendors: {', '.join(args.vendors)}")
    print(f"Output: {output_dir}")
    print()

    # Run comparisons
    all_results = []

    for symbol, date in samples:
        print("\n" + "=" * 70)
        print(f"SAMPLE: {symbol} @ {date}")
        print("=" * 70)

        # Load our data
        our_data = load_our_minute_bars(our_root, symbol, date)

        if our_data.empty:
            print(f"[SKIP] No data available for {symbol} {date}")
            all_results.append({
                "symbol": symbol,
                "date": date,
                "status": "no_our_data",
                "vendors": []
            })
            continue

        # Compare with each vendor
        vendor_results = []

        for vendor in args.vendors:
            api_key = av_key if vendor.lower() == "alphavantage" else td_key

            if not api_key:
                print(f"[SKIP] No API key for {vendor}")
                vendor_results.append({
                    "vendor": vendor,
                    "status": "no_api_key"
                })
                continue

            result = compare_with_vendor(our_data, vendor, symbol, date, api_key)
            vendor_results.append(result)

        # Save sample results
        sample_result = {
            "symbol": symbol,
            "date": date,
            "status": "completed",
            "our_bar_count": len(our_data),
            "vendors": vendor_results,
            "timestamp": datetime.now().isoformat()
        }

        all_results.append(sample_result)

        # Save individual sample report
        sample_file = output_dir / f"{symbol}_{date}_comparison.json"
        with open(sample_file, "w") as f:
            json.dump(sample_result, f, indent=2)

        print(f"\n[SAVED] {sample_file}")

    # Generate summary report
    summary = {
        "timestamp": datetime.now().isoformat(),
        "our_data_root": str(our_root),
        "total_samples": len(samples),
        "vendors": args.vendors,
        "results": all_results
    }

    # Calculate aggregate statistics
    successful_comparisons = []
    for result in all_results:
        if result["status"] == "completed":
            for vendor_result in result["vendors"]:
                if vendor_result.get("status") == "success":
                    successful_comparisons.append(vendor_result)

    if successful_comparisons:
        avg_match_rate = sum(c.get("match_rate", 0) for c in successful_comparisons) / len(successful_comparisons)
        summary["aggregate_stats"] = {
            "successful_comparisons": len(successful_comparisons),
            "average_match_rate": avg_match_rate,
            "average_match_rate_percent": f"{avg_match_rate*100:.2f}%"
        }

    summary_file = output_dir / "comparison_summary.json"
    with open(summary_file, "w") as f:
        json.dump(summary, f, indent=2)

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total samples: {len(samples)}")
    print(f"Successful comparisons: {len(successful_comparisons)}")
    if successful_comparisons:
        print(f"Average match rate: {avg_match_rate*100:.2f}%")
    print(f"\nResults saved to: {output_dir}")
    print("=" * 70)


if __name__ == "__main__":
    main()
