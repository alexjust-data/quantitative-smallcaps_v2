#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Validar datos del universo descargado"""

import sys
import polars as pl
from pathlib import Path

parquet_file = "raw/polygon/reference/tickers_snapshot/snapshot_date=2025-01-15/tickers.parquet"

if not Path(parquet_file).exists():
    print(f"ERROR: No existe {parquet_file}")
    sys.exit(1)

df = pl.read_parquet(parquet_file)

print(f"Total tickers: {len(df):,}")
print("\n=== Distribucion por 'active' ===")
print(df.group_by("active").len().sort("active"))

print("\n=== Distribucion por 'type' (top 10) ===")
print(df.group_by("type").len().sort("len", descending=True).head(10))

print("\n=== Distribucion por 'market' ===")
print(df.group_by("market").len().sort("len", descending=True))

print("\n=== CS en NASDAQ/NYSE/ARCA ===")
cs_df = df.filter(
    (pl.col("type") == "CS") &
    (pl.col("primary_exchange").is_in(["XNAS", "XNYS", "ARCX"]))
)
print(f"Total CS filtrados: {len(cs_df):,}")
print(cs_df.group_by("active").len().sort("active"))

print("\n=== Ejemplos de tickers conocidos ===")
ejemplos = ["HMNY", "DRYS", "LFIN", "TOPS", "AAPL", "TSLA"]
for ticker in ejemplos:
    row = df.filter(pl.col("ticker") == ticker)
    if len(row) > 0:
        active = row["active"][0]
        delisted = row.get("delisted_utc", [None])[0] if "delisted_utc" in row.columns else None
        print(f"  {ticker}: active={active}, delisted_utc={delisted}")
    else:
        print(f"  {ticker}: NO ENCONTRADO")

print("\n[DONE]")
