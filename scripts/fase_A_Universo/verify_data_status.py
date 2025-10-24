#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Verificar estado de todos los datos de FASE A"""

import polars as pl
from pathlib import Path

project_root = Path(r"D:\04_TRADING_SMALLCAPS")

print("="*80)
print("VERIFICACION DE DATOS - FASE A")
print("="*80)

# 1. UNIVERSO
print("\n1. UNIVERSO DE TICKERS:")
p_univ = project_root / "raw/polygon/reference/tickers_snapshot/snapshot_date=2025-10-24/tickers_all.parquet"
if p_univ.exists():
    df = pl.read_parquet(p_univ)
    print(f"   [OK] tickers_all.parquet existe")
    print(f"   Total tickers: {len(df):,}")
    print(f"   Activos: {len(df.filter(pl.col('active')==True)):,}")
    print(f"   Inactivos: {len(df.filter(pl.col('active')==False)):,}")
else:
    print(f"   [ERROR] No existe {p_univ}")

# 2. SPLITS
print("\n2. SPLITS (Corporate Actions):")
p_splits = project_root / "raw/polygon/reference/splits"
if p_splits.exists():
    files = list(p_splits.rglob("*.parquet"))
    print(f"   [OK] Directorio existe")
    print(f"   Archivos parquet: {len(files)}")
    if len(files) > 0:
        # Leer primer archivo para ver estructura
        sample = pl.read_parquet(files[0])
        print(f"   Muestra de registros: {len(sample):,}")
else:
    print(f"   [ERROR] Directorio no existe: {p_splits}")

# 3. DIVIDENDS
print("\n3. DIVIDENDS (Corporate Actions):")
p_div = project_root / "raw/polygon/reference/dividends"
if p_div.exists():
    files = list(p_div.rglob("*.parquet"))
    print(f"   [OK] Directorio existe")
    print(f"   Archivos parquet: {len(files)}")
    if len(files) > 0:
        sample = pl.read_parquet(files[0])
        print(f"   Muestra de registros: {len(sample):,}")
else:
    print(f"   [ERROR] Directorio no existe: {p_div}")

# 4. DIMENSION SCD-2
print("\n4. DIMENSION SCD-2 (tickers_dim):")
p_dim = project_root / "raw/polygon/reference/tickers_dim"
if p_dim.exists():
    files = list(p_dim.rglob("*.parquet"))
    print(f"   [OK] Directorio existe")
    print(f"   Archivos parquet: {len(files)}")
    if len(files) > 0:
        sample = pl.read_parquet(files[0])
        print(f"   Registros en dimension: {len(sample):,}")
else:
    print(f"   [ERROR] Directorio no existe: {p_dim}")

print("\n" + "="*80)
print("RESUMEN:")
print("="*80)

status = []
if p_univ.exists():
    status.append("[OK] Universo (34,380 tickers)")
else:
    status.append("[FALTA] Universo")

if p_splits.exists() and len(list(p_splits.rglob("*.parquet"))) > 0:
    status.append("[OK] Splits")
else:
    status.append("[FALTA] Splits")

if p_div.exists() and len(list(p_div.rglob("*.parquet"))) > 0:
    status.append("[OK] Dividends")
else:
    status.append("[FALTA] Dividends")

if p_dim.exists() and len(list(p_dim.rglob("*.parquet"))) > 0:
    status.append("[OK] Dimension SCD-2")
else:
    status.append("[FALTA] Dimension SCD-2")

for s in status:
    print(s)

print("\n")
