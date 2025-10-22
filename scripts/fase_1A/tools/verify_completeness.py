#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
verify_completeness.py

Verifica que TODAS las descargas sean completas validando:
1. Reference Universe: distribución alfabética, exchanges esperados
2. Ticker Details: cobertura por exchange
3. Splits/Dividends: distribución temporal esperada
"""

import sys
from pathlib import Path
import polars as pl

def verify_tickers():
    print("=" * 80)
    print("1. REFERENCE UNIVERSE VALIDATION")
    print("=" * 80)

    df = pl.read_parquet("raw/polygon/reference/tickers_snapshot/snapshot_date=2025-10-19/tickers.parquet")

    print(f"\nTotal tickers: {df.height:,}")

    # Distribución alfabética (debe tener tickers en todo el alfabeto)
    df = df.with_columns(pl.col("ticker").str.slice(0, 1).alias("first_letter"))
    by_letter = df.group_by("first_letter").len().sort("first_letter")
    print(f"\nDistribucion alfabetica (primeras letras):")
    print(by_letter.head(26))

    # Verificar que tenemos todas las letras A-Z
    letters = set(by_letter["first_letter"].to_list())
    alphabet = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    missing = alphabet - letters
    if missing:
        print(f"\nWARNING: Faltan tickers que empiecen con: {sorted(missing)}")
    else:
        print(f"\n✓ OK: Tenemos tickers de todas las letras A-Z")

    # Exchanges
    by_exchange = df.group_by("primary_exchange").len().sort("len", descending=True)
    print(f"\nTop exchanges:")
    print(by_exchange.head(10))

    # Tipos de activos
    by_type = df.group_by("type").len().sort("len", descending=True)
    print(f"\nTop tipos de activos:")
    print(by_type.head(15))

    return df.height

def verify_details():
    print("\n" + "=" * 80)
    print("2. TICKER DETAILS VALIDATION")
    print("=" * 80)

    df = pl.read_parquet("raw/polygon/reference/ticker_details/as_of_date=2025-10-19/details.parquet")

    print(f"\nTotal details descargados: {df.height:,}")

    # Verificar tickers únicos
    unique_tickers = df["ticker"].n_unique()
    print(f"Tickers unicos: {unique_tickers:,}")

    if df.height != unique_tickers:
        print(f"WARNING: Hay duplicados ({df.height - unique_tickers} extras)")
    else:
        print("✓ OK: Sin duplicados")

    # Distribución alfabética
    df = df.with_columns(pl.col("ticker").str.slice(0, 1).alias("first_letter"))
    by_letter = df.group_by("first_letter").len().sort("first_letter")
    print(f"\nDistribucion alfabetica:")
    print(by_letter.head(26))

    letters = set(by_letter["first_letter"].to_list())
    alphabet = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    missing = alphabet - letters
    if missing:
        print(f"\nWARNING: Faltan tickers que empiecen con: {sorted(missing)}")
    else:
        print(f"\n✓ OK: Tenemos tickers de todas las letras A-Z")

    return df.height

def verify_splits_dividends():
    print("\n" + "=" * 80)
    print("3. SPLITS & DIVIDENDS VALIDATION")
    print("=" * 80)

    # Splits
    df_s = pl.read_parquet("raw/polygon/reference/splits")
    print(f"\nSplits totales: {df_s.height:,}")

    # Distribución por año
    df_s = df_s.with_columns(pl.col("execution_date").str.slice(0, 4).alias("year"))
    by_year = df_s.group_by("year").len().sort("year")
    print(f"\nSplits por ano:")
    print(by_year)

    # Distribución por ticker (top 10)
    by_ticker = df_s.group_by("ticker").len().sort("len", descending=True)
    print(f"\nTop tickers con mas splits:")
    print(by_ticker.head(10))

    # Dividends
    df_d = pl.read_parquet("raw/polygon/reference/dividends")
    print(f"\n\nDividends totales: {df_d.height:,}")

    df_d = df_d.with_columns(pl.col("ex_dividend_date").str.slice(0, 4).alias("year"))
    by_year = df_d.group_by("year").len().sort("year")
    print(f"\nDividends por ano:")
    print(by_year)

    by_ticker = df_d.group_by("ticker").len().sort("len", descending=True)
    print(f"\nTop tickers con mas dividends:")
    print(by_ticker.head(10))

    return df_s.height, df_d.height

def main():
    n_tickers = verify_tickers()
    n_details = verify_details()
    n_splits, n_divs = verify_splits_dividends()

    print("\n" + "=" * 80)
    print("RESUMEN FINAL")
    print("=" * 80)
    print(f"Reference Universe: {n_tickers:,} tickers")
    print(f"Ticker Details:     {n_details:,} tickers")
    print(f"Splits:             {n_splits:,} registros")
    print(f"Dividends:          {n_divs:,} registros")

    if n_splits == 1000:
        print("\n⚠ WARNING: Splits = exactamente 1,000 (probable descarga incompleta)")
    else:
        print(f"\n✓ Splits: cantidad no redonda ({n_splits:,}), probable descarga completa")

    if n_divs == 1000:
        print("⚠ WARNING: Dividends = exactamente 1,000 (probable descarga incompleta)")
    else:
        print(f"✓ Dividends: cantidad no redonda ({n_divs:,}), probable descarga completa")

if __name__ == "__main__":
    main()
