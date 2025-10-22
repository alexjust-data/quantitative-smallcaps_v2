#!/usr/bin/env python3
"""
Data Quality validation for Bloque A (Universo y Referencia)
"""
import polars as pl
from pathlib import Path

def log(msg): print(f"[+] {msg}")

def validate_reference_snapshot(snapdir: Path):
    log("="*70)
    log("REFERENCE SNAPSHOT VALIDATION")
    log("="*70)

    df = pl.read_parquet(snapdir / "tickers.parquet")

    print(f"\nTotal tickers: {len(df):,}")
    print(f"\nDistribution by type:")
    types = df.group_by("type").len().sort("len", descending=True)
    for row in types.head(10).iter_rows():
        print(f"  {row[0]:20s}: {row[1]:,}")

    print(f"\nDistribution by exchange:")
    exchanges = df.group_by("primary_exchange").len().sort("len", descending=True)
    for row in exchanges.head(10).iter_rows():
        exch = row[0] if row[0] else "NULL"
        print(f"  {exch:20s}: {row[1]:,}")

    print(f"\nActive status:")
    active = df.group_by("active").len()
    for row in active.iter_rows():
        print(f"  {row[0]}: {row[1]:,}")

def validate_ticker_details(detaildir: Path):
    log("\n" + "="*70)
    log("TICKER DETAILS VALIDATION")
    log("="*70)

    df = pl.read_parquet(detaildir / "details.parquet")

    print(f"\nTotal tickers with details: {len(df):,}")

    # Check for null/missing critical fields
    critical_fields = ["market_cap", "weighted_shares_outstanding", "share_class_shares_outstanding"]

    print(f"\nData completeness:")
    for field in critical_fields:
        if field in df.columns:
            non_null = df.filter(pl.col(field).is_not_null()).height
            pct = (non_null / len(df)) * 100
            print(f"  {field:40s}: {non_null:>7,} / {len(df):>7,} ({pct:>5.1f}%)")
        else:
            print(f"  {field:40s}: MISSING COLUMN")

    # Market cap distribution (for non-null values)
    if "market_cap" in df.columns:
        mcap_df = df.filter(pl.col("market_cap").is_not_null())
        if mcap_df.height > 0:
            print(f"\nMarket Cap Distribution (non-null only):")
            print(f"  Count: {mcap_df.height:,}")
            print(f"  Mean:  ${mcap_df['market_cap'].mean():,.0f}")
            print(f"  P50:   ${mcap_df['market_cap'].median():,.0f}")
            print(f"  P90:   ${mcap_df['market_cap'].quantile(0.90):,.0f}")
            print(f"  P95:   ${mcap_df['market_cap'].quantile(0.95):,.0f}")
            print(f"  Max:   ${mcap_df['market_cap'].max():,.0f}")

            # Small-cap count (< $2B)
            smallcap = mcap_df.filter(pl.col("market_cap") < 2_000_000_000)
            print(f"\n  Small-caps (< $2B): {smallcap.height:,} ({smallcap.height/mcap_df.height*100:.1f}%)")

def validate_splits_dividends(basedir: Path):
    log("\n" + "="*70)
    log("SPLITS & DIVIDENDS VALIDATION")
    log("="*70)

    # Splits
    splits_dir = basedir / "splits"
    if splits_dir.exists():
        splits_files = list(splits_dir.glob("year=*/splits.parquet"))
        if splits_files:
            splits_df = pl.concat([pl.read_parquet(f) for f in splits_files])
            print(f"\nSplits:")
            print(f"  Total records: {len(splits_df):,}")
            print(f"  Years covered: {len(splits_files)}")

            if "ratio" in splits_df.columns:
                print(f"  Ratio stats:")
                print(f"    Mean: {splits_df['ratio'].mean():.4f}")
                print(f"    Min:  {splits_df['ratio'].min():.4f}")
                print(f"    Max:  {splits_df['ratio'].max():.4f}")

                # Check for outliers
                outliers = splits_df.filter((pl.col("ratio") < 0.1) | (pl.col("ratio") > 10))
                if outliers.height > 0:
                    print(f"    WARNING: {outliers.height} outlier ratios detected")

    # Dividends
    dividends_dir = basedir / "dividends"
    if dividends_dir.exists():
        div_files = list(dividends_dir.glob("year=*/dividends.parquet"))
        if div_files:
            div_df = pl.concat([pl.read_parquet(f) for f in div_files])
            print(f"\nDividends:")
            print(f"  Total records: {len(div_df):,}")
            print(f"  Years covered: {len(div_files)}")

            if "cash_amount" in div_df.columns:
                print(f"  Cash amount stats:")
                print(f"    Mean: ${div_df['cash_amount'].mean():.4f}")
                print(f"    P50:  ${div_df['cash_amount'].median():.4f}")
                print(f"    Max:  ${div_df['cash_amount'].max():.4f}")

def main():
    base = Path("raw/polygon/reference")

    # 1. Reference snapshot
    snapdir = base / "tickers_snapshot" / "snapshot_date=2025-10-19"
    if snapdir.exists():
        validate_reference_snapshot(snapdir)
    else:
        print(f"WARNING: Snapshot not found at {snapdir}")

    # 2. Ticker details
    detaildir = base / "ticker_details" / "as_of_date=2025-10-19"
    if detaildir.exists():
        validate_ticker_details(detaildir)
    else:
        print(f"WARNING: Details not found at {detaildir}")

    # 3. Splits & Dividends
    if base.exists():
        validate_splits_dividends(base)

    log("\n" + "="*70)
    log("VALIDATION COMPLETE")
    log("="*70)

if __name__ == "__main__":
    main()
