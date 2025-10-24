#!/usr/bin/env python
"""
Enriquece el universo híbrido con datos adicionales:
- Activos: market_cap, description, sic_code, etc. (desde ticker_details)
- Inactivos: delisted_utc, composite_figi (ya están en snapshot)

Autor: Claude Code
Fecha: 2025-10-24
"""

import polars as pl
from pathlib import Path
import sys
import io

# UTF-8 encoding para Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# =============================================================================
# CARGAR DATOS
# =============================================================================

print("Cargando datos...")

# Universo híbrido (8,686 tickers: 3,092 activos + 5,594 inactivos)
df_hybrid = pl.read_parquet(
    "processed/universe/cs_xnas_xnys_hybrid_2025-10-24.parquet"
)
print(f"✅ Universo híbrido: {len(df_hybrid):,} tickers")

# Snapshot original (tiene info de inactivos: delisted_utc, cik, figi)
df_snapshot = pl.read_parquet(
    "raw/polygon/reference/tickers_snapshot/snapshot_date=2025-10-24/tickers_all.parquet"
)
print(f"✅ Snapshot original: {len(df_snapshot):,} tickers")

# Ticker details (tiene market_cap solo para activos)
df_details = pl.read_parquet(
    "raw/polygon/reference/ticker_details/ticker_details_2025-10-24.parquet"
)
# Filtrar solo los que NO tienen error (los que tienen data válida)
df_details = df_details.filter(pl.col("error").is_null())
print(f"✅ Ticker details (sin errores): {len(df_details):,} tickers")

# =============================================================================
# ENRIQUECER ACTIVOS: join con ticker_details
# =============================================================================

print("\nEnriqueciendo activos con ticker_details...")

df_activos = df_hybrid.filter(pl.col("active") == True).join(
    df_details.select([
        "ticker",
        "market_cap",
        "description",
        "sic_code",
        "sic_description",
        "total_employees",
        "homepage_url",
        "list_date",
        "share_class_shares_outstanding",
        "weighted_shares_outstanding"
    ]),
    on="ticker",
    how="left"
)

print(f"✅ Activos enriquecidos: {len(df_activos):,}")
print(f"   - Con market_cap: {len(df_activos.filter(pl.col('market_cap').is_not_null())):,}")

# =============================================================================
# ENRIQUECER INACTIVOS: join con snapshot (tiene delisted_utc, figi, etc.)
# =============================================================================

print("\nEnriqueciendo inactivos con snapshot...")

# Los inactivos YA tienen todas las columnas del snapshot en df_hybrid
# Solo necesitamos asegurar que tengan las columnas adicionales que vienen de ticker_details
df_inactivos = df_hybrid.filter(pl.col("active") == False)

# Agregar columnas que solo tienen los activos (de ticker_details) como None
df_inactivos = df_inactivos.with_columns([
    pl.lit(None).cast(pl.Float64).alias("market_cap"),
    pl.lit(None).cast(pl.Utf8).alias("description"),
    pl.lit(None).cast(pl.Utf8).alias("sic_code"),
    pl.lit(None).cast(pl.Utf8).alias("sic_description"),
    pl.lit(None).cast(pl.Int64).alias("total_employees"),
    pl.lit(None).cast(pl.Utf8).alias("homepage_url"),
    pl.lit(None).cast(pl.Utf8).alias("list_date"),
    pl.lit(None).cast(pl.Int64).alias("share_class_shares_outstanding"),
    pl.lit(None).cast(pl.Int64).alias("weighted_shares_outstanding")
])

print(f"✅ Inactivos enriquecidos: {len(df_inactivos):,}")
print(f"   - Con delisted_utc: {len(df_inactivos.filter(pl.col('delisted_utc').is_not_null())):,}")

# =============================================================================
# AGREGAR delisted_utc COMO None PARA ACTIVOS
# =============================================================================

# Los activos no tienen delisted_utc, agregarlo como None
if "delisted_utc" not in df_activos.columns:
    df_activos = df_activos.with_columns(
        pl.lit(None).cast(pl.Utf8).alias("delisted_utc")
    )

# =============================================================================
# UNIR AMBOS SEGMENTOS
# =============================================================================

print("\nUniendo activos + inactivos...")

# Obtener columnas comunes (intersección)
cols_activos = set(df_activos.columns)
cols_inactivos = set(df_inactivos.columns)
cols_comunes = sorted(cols_activos & cols_inactivos)

print(f"   Columnas comunes: {len(cols_comunes)}")

# Unir con columnas comunes
df_hybrid_enriched = pl.concat([
    df_activos.select(cols_comunes),
    df_inactivos.select(cols_comunes)
], how="vertical")

print(f"\n✅ Universo híbrido enriquecido: {len(df_hybrid_enriched):,}")
print(f"   - Activos:   {len(df_hybrid_enriched.filter(pl.col('active') == True)):,}")
print(f"   - Inactivos: {len(df_hybrid_enriched.filter(pl.col('active') == False)):,}")
print(f"   - Columnas totales: {len(df_hybrid_enriched.columns)}")

# =============================================================================
# ESTADÍSTICAS DE COMPLETITUD
# =============================================================================

print("\n" + "="*80)
print("ESTADÍSTICAS DE COMPLETITUD")
print("="*80)

key_fields = ["market_cap", "delisted_utc", "sic_description", "total_employees", "composite_figi"]
for field in key_fields:
    if field in df_hybrid_enriched.columns:
        count = len(df_hybrid_enriched.filter(pl.col(field).is_not_null()))
        pct = (count / len(df_hybrid_enriched)) * 100
        print(f"{field:30s}: {count:5,} / {len(df_hybrid_enriched):,} ({pct:5.1f}%)")

# =============================================================================
# GUARDAR RESULTADO
# =============================================================================

output_path = Path("processed/universe/cs_xnas_xnys_hybrid_enriched_2025-10-24.parquet")
output_path.parent.mkdir(parents=True, exist_ok=True)

df_hybrid_enriched.write_parquet(
    output_path,
    compression="zstd",
    compression_level=3
)

print(f"\n✅ Guardado: {output_path}")
print(f"   Tamaño: {output_path.stat().st_size / 1024 / 1024:.2f} MB")
