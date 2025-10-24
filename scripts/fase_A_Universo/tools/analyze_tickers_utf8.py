"""
Analiza el snapshot de tickers descargado desde Polygon
Muestra head(10), tail(10) y resumen de atributos
"""
import polars as pl
from pathlib import Path
import sys

# Force UTF-8 encoding for output
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Leer snapshot más reciente
snapshot_path = Path("raw/polygon/reference/tickers_snapshot/snapshot_date=2025-10-19/tickers.parquet")

print("=" * 100)
print("ANALISIS UNIVERSO INICIAL - TICKERS SNAPSHOT POLYGON (2025-10-19)")
print("=" * 100)
print()

# Cargar datos
df = pl.read_parquet(snapshot_path)

# Información general
print(f"TOTAL TICKERS: {len(df):,}")
print(f"TOTAL COLUMNAS: {len(df.columns)}")
print()

# Listar columnas y tipos
print("=" * 100)
print("COLUMNAS Y TIPOS DE DATOS")
print("=" * 100)
for col in df.columns:
    dtype = df[col].dtype
    null_count = df[col].null_count()
    null_pct = (null_count / len(df)) * 100
    print(f"{col:30s} | {str(dtype):20s} | Nulls: {null_count:6,} ({null_pct:5.1f}%)")
print()

# HEAD 10 - Solo columnas seleccionadas para evitar problemas con nombres Unicode
print("=" * 100)
print("HEAD(10) - PRIMERAS 10 ACCIONES (columnas seleccionadas)")
print("=" * 100)
cols_to_show = ["ticker", "market", "locale", "primary_exchange", "type", "active", "currency_name"]
print(df.select(cols_to_show).head(10))
print()

# TAIL 10
print("=" * 100)
print("TAIL(10) - ULTIMAS 10 ACCIONES (columnas seleccionadas)")
print("=" * 100)
print(df.select(cols_to_show).tail(10))
print()

# Distribución por atributos categóricos importantes
print("=" * 100)
print("DISTRIBUCIONES CATEGORICAS")
print("=" * 100)

# Market (exchange)
if "market" in df.columns:
    print("\nDISTRIBUCION POR EXCHANGE (market):")
    market_dist = df.group_by("market").agg(pl.count().alias("count")).sort("count", descending=True)
    print(market_dist)

# Type (tipo de activo)
if "type" in df.columns:
    print("\nDISTRIBUCION POR TIPO DE ACTIVO (type):")
    type_dist = df.group_by("type").agg(pl.count().alias("count")).sort("count", descending=True)
    print(type_dist)

# Active status
if "active" in df.columns:
    print("\nDISTRIBUCION POR ESTADO (active):")
    active_dist = df.group_by("active").agg(pl.count().alias("count")).sort("count", descending=True)
    print(active_dist)

# Currency code
if "currency_name" in df.columns:
    print("\nDISTRIBUCION POR MONEDA (currency_name):")
    currency_dist = df.group_by("currency_name").agg(pl.count().alias("count")).sort("count", descending=True).head(10)
    print(currency_dist)

# Locale
if "locale" in df.columns:
    print("\nDISTRIBUCION POR LOCALE:")
    locale_dist = df.group_by("locale").agg(pl.count().alias("count")).sort("count", descending=True)
    print(locale_dist)

# Primary exchange
if "primary_exchange" in df.columns:
    print("\nDISTRIBUCION POR PRIMARY EXCHANGE:")
    exchange_dist = df.group_by("primary_exchange").agg(pl.count().alias("count")).sort("count", descending=True).head(15)
    print(exchange_dist)

# CIK status
if "cik" in df.columns:
    print("\nESTADISTICAS DE CIK:")
    cik_not_null = df.filter(pl.col("cik").is_not_null())
    print(f"  - Tickers con CIK: {len(cik_not_null):,} ({len(cik_not_null)/len(df)*100:.1f}%)")
    print(f"  - Tickers sin CIK: {df['cik'].null_count():,} ({df['cik'].null_count()/len(df)*100:.1f}%)")

print()
print("=" * 100)
print("ANALISIS COMPLETADO")
print("=" * 100)
