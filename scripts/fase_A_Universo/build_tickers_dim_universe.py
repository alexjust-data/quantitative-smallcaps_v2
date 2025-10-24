#!/usr/bin/env python
"""
Construye dimensión SCD-2 (Slowly Changing Dimension Type 2) para nuestro
universo híbrido de 8,686 tickers.

Esta dimensión mantiene historial de cambios en atributos de tickers
(nombre, exchange, estado activo, market_cap, etc.) usando ventanas temporales
(effective_from / effective_to).

Basado en: universo enriquecido 2025-10-24 (8,686 tickers)

Autor: Claude Code
Fecha: 2025-10-24
"""

import polars as pl
from pathlib import Path
import sys
import io
import datetime as dt

# UTF-8 encoding para Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# =============================================================================
# CONFIGURACIÓN
# =============================================================================

UNIVERSO_PATH = "processed/universe/cs_xnas_xnys_hybrid_enriched_2025-10-24.parquet"
OUTPUT_DIR = Path("processed/ref/tickers_dim_universe")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SNAPSHOT_DATE = "2025-10-24"

# Columnas a trackear en la dimensión (Slowly Changing Attributes)
TRACK_COLS = [
    # Identificación básica
    "name",
    "primary_exchange",
    "active",
    "type",

    # Información de mercado
    "market",
    "locale",
    "currency_name",

    # Identificadores
    "cik",
    "composite_figi",
    "share_class_figi",

    # Datos corporativos (solo activos)
    "market_cap",
    "description",
    "sic_code",
    "sic_description",
    "total_employees",
    "homepage_url",
    "list_date",
    "share_class_shares_outstanding",
    "weighted_shares_outstanding",

    # Datos de inactivos
    "delisted_utc",

    # Metadata
    "snapshot_date",
    "last_updated_utc"
]

# =============================================================================
# CARGAR DATOS
# =============================================================================

print("="*80)
print("CONSTRUCCIÓN DE DIMENSIÓN SCD-2 PARA UNIVERSO HÍBRIDO")
print("="*80)
print(f"\nFecha: {dt.datetime.now():%Y-%m-%d %H:%M:%S}")

print("\n[1/3] Cargando universo enriquecido...")
df_universo = pl.read_parquet(UNIVERSO_PATH)
print(f"✅ Universo cargado: {len(df_universo):,} tickers")
print(f"   Columnas: {len(df_universo.columns)}")

# =============================================================================
# CONSTRUCCIÓN DE LA DIMENSIÓN SCD-2
# =============================================================================

print("\n[2/3] Construyendo dimensión SCD-2...")

# Seleccionar columnas para la dimensión
# Asegurar que todas las columnas existen, si no, crear como null
for col in TRACK_COLS:
    if col not in df_universo.columns:
        print(f"   ⚠️  Columna '{col}' no existe, agregando como null")
        df_universo = df_universo.with_columns(pl.lit(None).alias(col))

# Construir dimensión inicial
df_dim = df_universo.select(
    ['ticker'] + TRACK_COLS
).with_columns([
    # Agregar columnas de ventana temporal
    pl.lit(SNAPSHOT_DATE).alias("effective_from"),
    pl.lit(None).cast(pl.Utf8).alias("effective_to"),

    # Agregar metadata
    pl.lit(dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")).alias("created_at"),
    pl.lit(1).alias("version")
])

print(f"✅ Dimensión SCD-2 creada:")
print(f"   Total registros: {len(df_dim):,}")
print(f"   Tickers únicos: {df_dim['ticker'].n_unique():,}")
print(f"   Columnas: {len(df_dim.columns)}")

# =============================================================================
# ESTADÍSTICAS
# =============================================================================

print("\n[ESTADÍSTICAS] Distribución de registros:")

activos = len(df_dim.filter(pl.col('active') == True))
inactivos = len(df_dim.filter(pl.col('active') == False))
print(f"   Activos:   {activos:,} ({activos/len(df_dim)*100:.1f}%)")
print(f"   Inactivos: {inactivos:,} ({inactivos/len(df_dim)*100:.1f}%)")

# Registros abiertos vs cerrados
abiertos = len(df_dim.filter(pl.col('effective_to').is_null()))
cerrados = len(df_dim.filter(pl.col('effective_to').is_not_null()))
print(f"\n   Registros abiertos (effective_to = null): {abiertos:,}")
print(f"   Registros cerrados (effective_to != null): {cerrados:,}")

# Completitud de campos clave
print("\n   Completitud de campos clave:")
key_fields = ["market_cap", "delisted_utc", "sic_code", "cik", "composite_figi"]
for field in key_fields:
    if field in df_dim.columns:
        count = len(df_dim.filter(pl.col(field).is_not_null()))
        pct = (count / len(df_dim)) * 100
        print(f"      {field:30s}: {count:5,} / {len(df_dim):,} ({pct:5.1f}%)")

# =============================================================================
# GUARDAR DIMENSIÓN
# =============================================================================

print("\n[3/3] Guardando dimensión SCD-2...")

output_path = OUTPUT_DIR / f"tickers_dim_{SNAPSHOT_DATE}.parquet"
df_dim.write_parquet(
    output_path,
    compression="zstd",
    compression_level=3
)

print(f"✅ Dimensión guardada: {output_path}")
print(f"   Tamaño: {output_path.stat().st_size / 1024:.2f} KB")

# =============================================================================
# CREAR VISTA ACTUAL (solo registros abiertos)
# =============================================================================

print("\n[BONUS] Creando vista de registros actuales...")

df_current = df_dim.filter(pl.col('effective_to').is_null())
current_path = OUTPUT_DIR / f"tickers_dim_current.parquet"
df_current.write_parquet(current_path)

print(f"✅ Vista actual guardada: {current_path}")
print(f"   Registros: {len(df_current):,}")
print(f"   Tamaño: {current_path.stat().st_size / 1024:.2f} KB")

# =============================================================================
# DOCUMENTACIÓN DEL SCHEMA
# =============================================================================

print("\n[SCHEMA] Columnas de la dimensión:")
print("\nBusiness Key:")
print("  - ticker: String (identificador único)")

print("\nSlowly Changing Attributes (SCD-2):")
for i, col in enumerate(TRACK_COLS, 1):
    dtype = df_dim.schema[col]
    print(f"  {i:2d}. {col:40s}: {dtype}")

print("\nTemporal Columns:")
print("  - effective_from: String (fecha inicio vigencia)")
print("  - effective_to: String (fecha fin vigencia, null = vigente)")

print("\nMetadata:")
print("  - created_at: String (timestamp de creación)")
print("  - version: Int64 (versión del registro)")

# =============================================================================
# RESUMEN FINAL
# =============================================================================

print("\n" + "="*80)
print("RESUMEN FINAL")
print("="*80)

print(f"""
Dimensión SCD-2 creada exitosamente para universo de {len(df_universo):,} tickers.

Archivos generados:
  1. tickers_dim_{SNAPSHOT_DATE}.parquet - Dimensión completa ({len(df_dim):,} registros)
  2. tickers_dim_current.parquet - Solo registros actuales ({len(df_current):,} registros)

Características:
  - Snapshot base: {SNAPSHOT_DATE}
  - Business key: ticker
  - Tracked columns: {len(TRACK_COLS)}
  - Temporal tracking: effective_from / effective_to
  - Initial state: Todos registros abiertos (effective_to = null)

Próximos pasos:
  1. Para actualizar con nuevo snapshot: usar script update_tickers_dim_scd2.py
  2. Para consultar historial: filtrar por effective_from <= fecha <= effective_to
  3. Para consultar estado actual: filtrar effective_to IS NULL

Ubicación: {OUTPUT_DIR}

✅ Proceso completado exitosamente!
""")

print("="*80)
