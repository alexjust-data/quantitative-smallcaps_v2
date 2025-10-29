#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
create_ticker_cik_mapping.py
Crea mapping ticker->CIK desde ticker_details de Polygon para SEC EDGAR.
SOLO para los tickers del universo info_rich (1,906 tickers).
"""
import polars as pl
from pathlib import Path

def main():
    # Input: ticker details from Polygon
    details_path = Path("raw/polygon/reference/ticker_details/as_of_date=2025-10-19/details.parquet")

    # Input: CS XNAS/XNYS under 2B universe (3,107 tickers)
    universe_path = Path("processed/universe/cs_xnas_xnys_under2b_2025-10-21.csv")

    # Output: ticker->CIK mapping for 3,107 tickers
    output_path = Path("processed/ref/ticker_cik_mapping/ticker_cik_mapping_3107.parquet")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Load universe tickers
    universe = pl.read_csv(universe_path).select(["ticker"]).unique()
    print(f"Universe tickers (CS XNAS/XNYS <2B): {universe.height:,}")

    # Load ticker details
    df = pl.read_parquet(details_path)

    print(f"Total tickers in details: {df.height:,}")
    print(f"Columns: {df.columns}")

    # Select and filter relevant columns
    if "cik" not in df.columns:
        print("ERROR: No 'cik' column found in ticker_details!")
        return

    # Create clean mapping - JOIN with universe tickers
    mapping = df.select(["ticker", "cik"]).filter(
        pl.col("ticker").is_not_null() &
        pl.col("cik").is_not_null() &
        (pl.col("cik") != "")
    ).join(universe, on="ticker", how="inner").unique()

    print(f"3,107 tickers with valid CIK: {mapping.height:,}")

    # Save
    mapping.write_parquet(output_path, compression="zstd", compression_level=2)
    print(f"Saved: {output_path}")

    # Also save CSV for convenience
    mapping.write_csv(output_path.with_suffix(".csv"))
    print(f"Saved: {output_path.with_suffix('.csv')}")

if __name__ == "__main__":
    main()
