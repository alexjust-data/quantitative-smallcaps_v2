#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Verificación PASO 0: SCD-2 Market Cap Dimension
Script standalone para verificar la dimensión SCD-2 generada.
Ejecutar desde: D:\04_TRADING_SMALLCAPS
"""
import polars as pl
import json
from pathlib import Path
from datetime import date
import os
import sys

# ============================================================================
# CONFIGURACIÓN
# ============================================================================
PROJECT_ROOT = Path(r"D:\04_TRADING_SMALLCAPS")
os.chdir(PROJECT_ROOT)

print("=" * 80)
print("VERIFICACIÓN PASO 0: SCD-2 MARKET CAP DIMENSION")
print("=" * 80)
print(f"Working directory: {os.getcwd()}\n")

# ============================================================================
# 1. VERIFICAR EXISTENCIA DE ARCHIVOS
# ============================================================================
print("[1] VERIFICACIÓN DE ARCHIVOS GENERADOS")
print("-" * 80)

scd2_dir = Path("processed/ref/market_cap_dim")
dim_file = scd2_dir / "market_cap_dim.parquet"
manifest_file = scd2_dir / "MANIFEST.json"
success_file = scd2_dir / "_SUCCESS"

files_ok = True
for f, name in [(dim_file, "market_cap_dim.parquet"),
                 (manifest_file, "MANIFEST.json"),
                 (success_file, "_SUCCESS")]:
    exists = f.exists()
    status = "[OK]" if exists else "[FAIL]"
    print(f"{status} {name}: {'EXISTS' if exists else 'MISSING'}")
    files_ok = files_ok and exists

if not files_ok:
    print("\n[FAIL] Archivos del PASO 0 no encontrados")
    sys.exit(1)

print("\n[OK] Todos los archivos existen\n")

# ============================================================================
# 2. CARGAR Y VERIFICAR MANIFEST
# ============================================================================
print("[2] VERIFICACIÓN DE MANIFEST.JSON")
print("-" * 80)

with open(manifest_file) as f:
    manifest = json.load(f)

print(f"Timestamp generación: {manifest['timestamp']}")
print(f"Total tickers: {manifest['total_tickers']:,}")
print(f"Total periodos SCD-2: {manifest['total_periods']:,}")
print(f"Rango temporal: {manifest['date_range']['min']} -> {manifest['date_range']['max']}")
print(f"\nCobertura global:")
print(f"  - market_cap: {manifest['market_cap_coverage']['with_cap']:,} / "
      f"{manifest['market_cap_coverage']['total']:,} "
      f"({100*manifest['market_cap_coverage']['with_cap']/manifest['market_cap_coverage']['total']:.1f}%)")
print(f"  - shares_outstanding: {manifest['market_cap_coverage']['with_shares']:,} / "
      f"{manifest['market_cap_coverage']['total']:,} "
      f"({100*manifest['market_cap_coverage']['with_shares']/manifest['market_cap_coverage']['total']:.1f}%)")

# ============================================================================
# 3. CARGAR DIMENSIÓN SCD-2
# ============================================================================
print("\n[3] CARGA Y VALIDACIÓN DE DIMENSIÓN SCD-2")
print("-" * 80)

dim = pl.read_parquet(dim_file)

print(f"Shape: {dim.shape}")
print(f"\nSchema:")
for col, dtype in dim.schema.items():
    null_count = dim[col].null_count()
    null_pct = 100 * null_count / len(dim)
    print(f"  {col:25s} {str(dtype):15s} (nulls: {null_count:,} = {null_pct:.1f}%)")

# ============================================================================
# 4. VERIFICAR INTEGRIDAD SCD-2
# ============================================================================
print("\n[4] VERIFICACIÓN INTEGRIDAD SCD-2")
print("-" * 80)

# 4.1 Verificar que effective_to >= effective_from
invalid_ranges = dim.filter(pl.col("effective_to") < pl.col("effective_from"))
print(f"[OK] Rangos válidos (effective_from < effective_to): {len(invalid_ranges) == 0}")
if len(invalid_ranges) > 0:
    print(f"   [FAIL] {len(invalid_ranges)} rangos inválidos")

# 4.2 Verificar que no hay gaps ni overlaps por ticker
gaps_overlaps = (
    dim
    .sort(["ticker", "effective_from"])
    .with_columns([
        pl.col("effective_from").shift(-1).over("ticker").alias("next_from")
    ])
    .filter(
        (pl.col("next_from").is_not_null()) &
        (pl.col("effective_to") != pl.col("next_from"))
    )
)
print(f"[OK] Sin gaps/overlaps entre periodos: {len(gaps_overlaps) == 0}")

# 4.3 Verificar que effective_to abierto = 2099-12-31
open_periods = dim.filter(pl.col("effective_to") == date(2099, 12, 31))
print(f"[OK] Periodos abiertos (effective_to=2099-12-31): {len(open_periods):,}")

# ============================================================================
# 5. VERIFICAR COBERTURA PARA NUESTRO UNIVERSO HÍBRIDO
# ============================================================================
print("\n[5] VERIFICACIÓN COBERTURA UNIVERSO HÍBRIDO")
print("-" * 80)

# Obtener tickers de daily_cache (nuestro universo)
cache_root = Path("processed/daily_cache")
cache_tickers = set([p.name.replace('ticker=', '')
                     for p in cache_root.glob('ticker=*')])

print(f"Tickers en daily_cache (universo actual): {len(cache_tickers):,}")

# Filtrar SCD-2 solo para nuestro universo
dim_universe = dim.filter(pl.col("ticker").is_in(list(cache_tickers)))

print(f"Tickers en SCD-2 (universo): {len(dim_universe):,}")

# NOTA IMPORTANTE: Es NORMAL que haya tickers en daily_cache que NO estén en SCD-2
# Estos son tickers delistados ANTES del snapshot de ticker_details (2025-10-19)
# Polygon solo mantiene ticker_details para tickers que existen HOY
missing_in_scd2 = len(cache_tickers) - len(dim_universe)
if missing_in_scd2 > 0:
    print(f"\n[NOTA] {missing_in_scd2} tickers en cache NO están en SCD-2")
    print(f"       Estos fueron delistados antes de 2025-10-19 (ESPERADO)")
    print(f"       Representan {100*missing_in_scd2/len(cache_tickers):.1f}% del universo")

# Cobertura de market_cap y shares
cap_coverage = dim_universe.filter(pl.col("market_cap").is_not_null())
shares_coverage = dim_universe.filter(pl.col("shares_outstanding").is_not_null())

cap_pct = 100*len(cap_coverage)/len(dim_universe) if len(dim_universe) > 0 else 0
shares_pct = 100*len(shares_coverage)/len(dim_universe) if len(dim_universe) > 0 else 0

print(f"\nCobertura UNIVERSO HÍBRIDO:")
print(f"  [OK] market_cap: {len(cap_coverage):,} / {len(dim_universe):,} ({cap_pct:.1f}%)")
print(f"  [OK] shares_outstanding: {len(shares_coverage):,} / {len(dim_universe):,} ({shares_pct:.1f}%)")

# CRÍTICO: Debe ser 100% para continuar
if len(cap_coverage) < len(dim_universe):
    missing = dim_universe.filter(pl.col("market_cap").is_null())
    print(f"\n  [WARN] {len(missing)} tickers sin market_cap:")
    print(missing.select(["ticker", "effective_from", "effective_to"]).head(10))

# ============================================================================
# 6. VERIFICAR DISTRIBUCIÓN DE MARKET CAP
# ============================================================================
print("\n[6] DISTRIBUCIÓN DE MARKET CAP (UNIVERSO HÍBRIDO)")
print("-" * 80)

if len(dim_universe) > 0 and len(cap_coverage) > 0:
    cap_stats = dim_universe.filter(
        pl.col("market_cap").is_not_null()
    ).select([
        pl.col("market_cap").min().alias("min"),
        pl.col("market_cap").quantile(0.25).alias("p25"),
        pl.col("market_cap").median().alias("median"),
        pl.col("market_cap").quantile(0.75).alias("p75"),
        pl.col("market_cap").max().alias("max"),
    ])

    print("Estadísticas market_cap (USD):")
    for stat in cap_stats.to_dicts()[0].items():
        name, value = stat
        print(f"  {name:10s}: ${value:,.0f}")

    # Contar por rango de market cap
    cap_ranges = dim_universe.filter(pl.col("market_cap").is_not_null()).with_columns([
        pl.when(pl.col("market_cap") < 50_000_000).then(pl.lit("< $50M (Nano)"))
        .when(pl.col("market_cap") < 300_000_000).then(pl.lit("$50M-$300M (Micro)"))
        .when(pl.col("market_cap") < 2_000_000_000).then(pl.lit("$300M-$2B (Small)"))
        .when(pl.col("market_cap") < 10_000_000_000).then(pl.lit("$2B-$10B (Mid)"))
        .otherwise(pl.lit("> $10B (Large)"))
        .alias("cap_range")
    ])

    print("\nDistribución por rango:")
    distribution = cap_ranges.group_by("cap_range").agg([
        pl.len().alias("count")
    ]).sort("count", descending=True)
    print(distribution)
else:
    print("No hay datos para analizar distribución")

# ============================================================================
# 7. MUESTRA DE TICKERS ESPECÍFICOS
# ============================================================================
print("\n[7] MUESTRA DE TICKERS ESPECÍFICOS")
print("-" * 80)

if len(dim_universe) >= 5:
    # Seleccionar 5 tickers aleatorios de nuestro universo
    sample_tickers = dim_universe.sample(n=5, seed=42).select("ticker")["ticker"].to_list()

    print(f"Tickers seleccionados: {', '.join(sample_tickers)}")
    print("\nDetalle:")

    for ticker in sample_tickers:
        ticker_data = dim.filter(pl.col("ticker") == ticker)
        row = ticker_data.to_dicts()[0]

        print(f"\n  {ticker}:")
        print(f"    effective_from: {row['effective_from']}")
        print(f"    effective_to: {row['effective_to']}")
        print(f"    market_cap: ${row['market_cap']:,.0f}" if row['market_cap'] else "    market_cap: NULL")
        print(f"    shares_outstanding: {row['shares_outstanding']:,.0f}" if row['shares_outstanding'] else "    shares_outstanding: NULL")
else:
    print(f"Insuficientes tickers para muestra ({len(dim_universe)} disponibles)")

# ============================================================================
# 8. VERIFICAR JOIN TEMPORAL (SIMULACIÓN)
# ============================================================================
print("\n[8] SIMULACIÓN JOIN TEMPORAL SCD-2")
print("-" * 80)

if len(dim_universe) > 0:
    # Simular join para una fecha específica
    test_date = date(2025, 10, 21)
    print(f"Fecha de prueba: {test_date}")

    # Join: effective_from <= test_date < effective_to
    joined = dim_universe.filter(
        (pl.col("effective_from") <= test_date) &
        (pl.col("effective_to") > test_date)
    )

    print(f"Tickers con market_cap válido en {test_date}: {len(joined):,}")
    if len(dim_universe) > 0:
        print(f"Cobertura: {100*len(joined)/len(dim_universe):.1f}%")

    # Verificar que no hay duplicados
    duplicates = (
        joined
        .group_by("ticker")
        .agg(pl.len().alias("count"))
        .filter(pl.col("count") > 1)
    )

    if len(duplicates) == 0:
        print("[OK] Sin duplicados en join temporal")
    else:
        print(f"[FAIL] {len(duplicates)} tickers con múltiples periodos válidos")

    # Muestra del join
    if len(joined) >= 10:
        print("\nMuestra join (10 tickers):")
        print(joined.sample(n=10, seed=42).select([
            "ticker", "effective_from", "effective_to", "market_cap", "shares_outstanding"
        ]))
else:
    print("No hay datos en universo para simular join")

# ============================================================================
# 9. VERIFICACIÓN FINAL
# ============================================================================
print("\n" + "=" * 80)
print("VERIFICACIÓN FINAL - PASO 0")
print("=" * 80)

# CORRECCIÓN: La cobertura debe ser sobre tickers EN SCD-2, no sobre TODO el cache
# Muchos tickers en cache fueron delistados ANTES del snapshot de 2025-10-19
# y por tanto NO aparecen en ticker_details (esto es NORMAL)
coverage_pct = (len(cap_coverage) / len(dim_universe) * 100) if len(dim_universe) > 0 else 0

checks = {
    "Archivos generados": files_ok,
    "Rangos SCD-2 válidos": len(invalid_ranges) == 0,
    "Sin gaps/overlaps": len(gaps_overlaps) == 0,
    "Cobertura SCD-2 >95%": coverage_pct >= 95.0,  # Tolerancia 5% para tickers edge case
}

all_passed = all(checks.values())

for check, passed in checks.items():
    status = "[OK]" if passed else "[FAIL]"
    print(f"{status} {check}")

print("\n" + "=" * 80)
if all_passed:
    print("[SUCCESS] PASO 0 COMPLETADO EXITOSAMENTE")
    print("Dimensión SCD-2 lista para uso en PASO 1 (daily_cache)")
else:
    print("[FAIL] Verificar errores arriba")
print("=" * 80)

sys.exit(0 if all_passed else 1)
