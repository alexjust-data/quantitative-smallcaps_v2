#!/usr/bin/env python3
import polars as pl
from pathlib import Path

# Read the parquet file
df = pl.read_parquet("raw/polygon/reference/tickers_snapshot/snapshot_date=2025-10-19/tickers.parquet")

print("="*70)
print("REFERENCE UNIVERSE VALIDATION")
print("="*70)
print()

print(f"Total tickers downloaded: {len(df):,}")
print()

print("Distribution by type:")
types = df.group_by("type").len().sort("len", descending=True)
for row in types.iter_rows():
    print(f"  {row[0]:20s}: {row[1]:,}")
print()

print("Distribution by exchange:")
exchanges = df.group_by("primary_exchange").len().sort("len", descending=True).head(10)
for row in exchanges.iter_rows():
    exch = row[0] if row[0] else "NULL"
    print(f"  {exch:20s}: {row[1]:,}")
print()

print("Distribution by active status:")
active = df.group_by("active").len().sort("len", descending=True)
for row in active.iter_rows():
    print(f"  {row[0]}: {row[1]:,}")
print()

# Filter for common stocks on major exchanges
common_stocks = df.filter(
    (pl.col("type") == "CS") &
    (pl.col("primary_exchange").is_in(["NASDAQ", "NYSE", "ARCA"]))
)

print(f"Common Stocks (CS) on NASDAQ/NYSE/ARCA: {len(common_stocks):,}")
print()

print("="*70)
print("DOWNLOAD SUCCESSFUL!")
print("="*70)
