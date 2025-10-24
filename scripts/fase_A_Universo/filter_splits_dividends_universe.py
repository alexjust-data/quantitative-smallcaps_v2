#!/usr/bin/env python
"""
Filtra splits y dividends globales de Polygon para nuestro universo de 8,686 tickers.

Los datos completos (26,641 splits y 1,878,357 dividends) fueron descargados
el 2025-10-19/20 para TODOS los tickers de Polygon. Este script extrae solo
los registros relevantes para nuestro universo híbrido de small caps.

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
# CONFIGURACIÓN
# =============================================================================

UNIVERSO_PATH = "processed/universe/cs_xnas_xnys_hybrid_enriched_2025-10-24.parquet"
SPLITS_GLOBAL_PATH = "raw/polygon/reference/splits/year=*/splits.parquet"
DIVIDENDS_GLOBAL_PATH = "raw/polygon/reference/dividends/year=*/dividends.parquet"

OUTPUT_DIR = Path("processed/corporate_actions")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# =============================================================================
# CARGAR DATOS
# =============================================================================

print("="*80)
print("FILTRADO DE SPLITS & DIVIDENDS PARA UNIVERSO HÍBRIDO")
print("="*80)

# Cargar universo
print("\n[1/5] Cargando universo híbrido...")
df_universo = pl.read_parquet(UNIVERSO_PATH)
tickers_universo = set(df_universo['ticker'].unique().to_list())
print(f"✅ Universo cargado: {len(tickers_universo):,} tickers")

# Cargar splits globales
print("\n[2/5] Cargando splits globales (26,641 registros)...")
df_splits_global = pl.read_parquet(SPLITS_GLOBAL_PATH)
print(f"✅ Splits globales cargados: {len(df_splits_global):,} registros")
print(f"   Tickers únicos: {df_splits_global['ticker'].n_unique():,}")

# Cargar dividends globales
print("\n[3/5] Cargando dividends globales (1,878,357 registros)...")
df_dividends_global = pl.read_parquet(DIVIDENDS_GLOBAL_PATH)
print(f"✅ Dividends globales cargados: {len(df_dividends_global):,} registros")
print(f"   Tickers únicos: {df_dividends_global['ticker'].n_unique():,}")

# =============================================================================
# FILTRAR POR UNIVERSO
# =============================================================================

print("\n[4/5] Filtrando splits para nuestro universo...")
df_splits_universo = df_splits_global.filter(
    pl.col('ticker').is_in(list(tickers_universo))
)
tickers_con_splits = df_splits_universo['ticker'].n_unique()
print(f"✅ Splits filtrados: {len(df_splits_universo):,} registros")
print(f"   Tickers con splits: {tickers_con_splits:,} ({tickers_con_splits/len(tickers_universo)*100:.1f}%)")

print("\n[5/5] Filtrando dividends para nuestro universo...")
df_dividends_universo = df_dividends_global.filter(
    pl.col('ticker').is_in(list(tickers_universo))
)
tickers_con_dividends = df_dividends_universo['ticker'].n_unique()
print(f"✅ Dividends filtrados: {len(df_dividends_universo):,} registros")
print(f"   Tickers con dividends: {tickers_con_dividends:,} ({tickers_con_dividends/len(tickers_universo)*100:.1f}%)")

# =============================================================================
# ESTADÍSTICAS DETALLADAS
# =============================================================================

print("\n" + "="*80)
print("ESTADÍSTICAS DETALLADAS")
print("="*80)

# Splits por década
print("\nSplits por década:")
if len(df_splits_universo) > 0 and 'execution_date' in df_splits_universo.columns:
    splits_por_decada = (df_splits_universo
        .with_columns(
            pl.col('execution_date').str.slice(0, 4).cast(pl.Int32).alias('year')
        )
        .with_columns(
            ((pl.col('year') // 10) * 10).alias('decade')
        )
        .group_by('decade')
        .agg(pl.count('ticker').alias('count'))
        .sort('decade')
    )
    for row in splits_por_decada.iter_rows(named=True):
        print(f"  {row['decade']}s: {row['count']:,} splits")

# Dividends por década
print("\nDividends por década:")
if len(df_dividends_universo) > 0 and 'ex_dividend_date' in df_dividends_universo.columns:
    dividends_por_decada = (df_dividends_universo
        .with_columns(
            pl.col('ex_dividend_date').str.slice(0, 4).cast(pl.Int32).alias('year')
        )
        .with_columns(
            ((pl.col('year') // 10) * 10).alias('decade')
        )
        .group_by('decade')
        .agg(pl.count('ticker').alias('count'))
        .sort('decade')
    )
    for row in dividends_por_decada.iter_rows(named=True):
        print(f"  {row['decade']}s: {row['count']:,} dividends")

# Top tickers con más splits
print("\nTop 10 tickers con más splits:")
if len(df_splits_universo) > 0:
    top_splits = (df_splits_universo
        .group_by('ticker')
        .agg(pl.count('ticker').alias('count'))
        .sort('count', descending=True)
        .head(10)
    )
    for row in top_splits.iter_rows(named=True):
        print(f"  {row['ticker']:6s}: {row['count']:3d} splits")

# Top tickers con más dividends
print("\nTop 10 tickers con más dividends:")
if len(df_dividends_universo) > 0:
    top_dividends = (df_dividends_universo
        .group_by('ticker')
        .agg(pl.count('ticker').alias('count'))
        .sort('count', descending=True)
        .head(10)
    )
    for row in top_dividends.iter_rows(named=True):
        print(f"  {row['ticker']:6s}: {row['count']:4d} dividends")

# =============================================================================
# GUARDAR RESULTADOS
# =============================================================================

print("\n" + "="*80)
print("GUARDANDO RESULTADOS")
print("="*80)

# Guardar splits filtrados
splits_output = OUTPUT_DIR / "splits_universe_2025-10-24.parquet"
df_splits_universo.write_parquet(
    splits_output,
    compression="zstd",
    compression_level=3
)
print(f"\n✅ Splits guardados: {splits_output}")
print(f"   Tamaño: {splits_output.stat().st_size / 1024:.2f} KB")

# Guardar dividends filtrados
dividends_output = OUTPUT_DIR / "dividends_universe_2025-10-24.parquet"
df_dividends_universo.write_parquet(
    dividends_output,
    compression="zstd",
    compression_level=3
)
print(f"\n✅ Dividends guardados: {dividends_output}")
print(f"   Tamaño: {dividends_output.stat().st_size / 1024 / 1024:.2f} MB")

# =============================================================================
# CREAR LOOKUP TABLE (ticker → has_splits, has_dividends)
# =============================================================================

print("\n[BONUS] Creando lookup table...")

tickers_splits = set(df_splits_universo['ticker'].unique().to_list())
tickers_dividends = set(df_dividends_universo['ticker'].unique().to_list())

df_lookup = df_universo.select(['ticker', 'name', 'active']).with_columns([
    pl.col('ticker').is_in(list(tickers_splits)).alias('has_splits'),
    pl.col('ticker').is_in(list(tickers_dividends)).alias('has_dividends')
])

# Contar splits y dividends por ticker
splits_count = (df_splits_universo
    .group_by('ticker')
    .agg(pl.count('ticker').alias('splits_count'))
)

dividends_count = (df_dividends_universo
    .group_by('ticker')
    .agg(pl.count('ticker').alias('dividends_count'))
)

df_lookup = (df_lookup
    .join(splits_count, on='ticker', how='left')
    .join(dividends_count, on='ticker', how='left')
    .with_columns([
        pl.col('splits_count').fill_null(0),
        pl.col('dividends_count').fill_null(0)
    ])
)

lookup_output = OUTPUT_DIR / "corporate_actions_lookup_2025-10-24.parquet"
df_lookup.write_parquet(lookup_output)
print(f"✅ Lookup table guardada: {lookup_output}")
print(f"   Tamaño: {lookup_output.stat().st_size / 1024:.2f} KB")

# =============================================================================
# RESUMEN FINAL
# =============================================================================

print("\n" + "="*80)
print("RESUMEN FINAL")
print("="*80)

print(f"""
Universo total:              {len(tickers_universo):,} tickers

Corporate Actions:
  Splits:                    {len(df_splits_universo):,} registros ({tickers_con_splits:,} tickers)
  Dividends:                 {len(df_dividends_universo):,} registros ({tickers_con_dividends:,} tickers)

Tickers sin corporate actions:
  Sin splits:                {len(tickers_universo) - tickers_con_splits:,} ({(len(tickers_universo) - tickers_con_splits)/len(tickers_universo)*100:.1f}%)
  Sin dividends:             {len(tickers_universo) - tickers_con_dividends:,} ({(len(tickers_universo) - tickers_con_dividends)/len(tickers_universo)*100:.1f}%)

Archivos generados:
  1. {splits_output.name}
  2. {dividends_output.name}
  3. {lookup_output.name}

✅ Proceso completado exitosamente!
""")

print("="*80)
