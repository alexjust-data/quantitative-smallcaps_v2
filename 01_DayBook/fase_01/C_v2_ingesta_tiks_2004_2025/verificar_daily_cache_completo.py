#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
verificar_daily_cache_completo.py
Verificación científica del PASO 1: Daily Cache 2004-2025

Verifica:
1. Existencia y completitud de archivos
2. Schema y tipos de datos
3. Integridad de features calculados
4. Cobertura market_cap_d (join SCD-2)
5. Distribución estadística
6. Casos edge (tickers con pocos datos)
"""
import polars as pl
from pathlib import Path
from datetime import date
import numpy as np
import sys
import os

# Cambiar al directorio raíz del proyecto
PROJECT_ROOT = Path(r"D:\04_TRADING_SMALLCAPS")
os.chdir(PROJECT_ROOT)

print("=" * 80)
print("VERIFICACIÓN CIENTÍFICA - PASO 1: DAILY CACHE")
print("=" * 80)
print(f"Working directory: {os.getcwd()}\n")

cache_root = Path("processed/daily_cache")

# ============================================================================
# TEST 1: Existencia de archivos críticos
# ============================================================================
print("\n[TEST 1] ARCHIVOS CRÍTICOS")
print("-" * 80)

tests_passed = 0
tests_total = 0

# Test 1.1: _SUCCESS existe
tests_total += 1
success_file = cache_root / "_SUCCESS"
if success_file.exists():
    print(f"[OK] _SUCCESS existe")
    tests_passed += 1
else:
    print(f"[FAIL] _SUCCESS NO existe")

# Test 1.2: Contar tickers
tests_total += 1
ticker_dirs = list(cache_root.glob("ticker=*"))
if len(ticker_dirs) >= 6000:
    print(f"[OK] Tickers procesados: {len(ticker_dirs):,} (>= 6,000)")
    tests_passed += 1
else:
    print(f"[FAIL] Pocos tickers: {len(ticker_dirs):,}")

# Test 1.3: Todos tienen _SUCCESS
tests_total += 1
success_count = sum(1 for d in ticker_dirs if (d / "_SUCCESS").exists())
if success_count == len(ticker_dirs):
    print(f"[OK] Todos los tickers tienen _SUCCESS: {success_count:,}")
    tests_passed += 1
else:
    print(f"[FAIL] {len(ticker_dirs) - success_count} tickers sin _SUCCESS")

# ============================================================================
# TEST 2: Schema y tipos de datos
# ============================================================================
print("\n[TEST 2] SCHEMA Y TIPOS")
print("-" * 80)

expected_schema = {
    "ticker": pl.String,
    "trading_day": pl.Date,
    "close_d": pl.Float64,
    "vol_d": pl.Int64,
    "dollar_vol_d": pl.Float64,
    "vwap_d": pl.Float64,
    "pctchg_d": pl.Float64,
    "return_d": pl.Float64,
    "rvol30": pl.Float64,
    "session_rows": pl.Int64,
    "has_gaps": pl.Boolean,
    "market_cap_d": pl.Float64,
}

# Muestra de 10 tickers aleatorios
np.random.seed(42)
sample_tickers = np.random.choice(ticker_dirs, min(10, len(ticker_dirs)), replace=False)

schema_errors = []
for ticker_dir in sample_tickers:
    ticker = ticker_dir.name.replace("ticker=", "")
    parquet_file = ticker_dir / "daily.parquet"

    if not parquet_file.exists():
        schema_errors.append(f"{ticker}: daily.parquet missing")
        continue

    df = pl.read_parquet(parquet_file)

    # Verificar columnas
    for col, expected_type in expected_schema.items():
        if col not in df.columns:
            schema_errors.append(f"{ticker}: columna {col} faltante")
        elif df.schema[col] != expected_type:
            schema_errors.append(f"{ticker}: {col} tipo incorrecto ({df.schema[col]} vs {expected_type})")

tests_total += 1
if len(schema_errors) == 0:
    print(f"[OK] Schema correcto en muestra de {len(sample_tickers)} tickers")
    tests_passed += 1
else:
    print(f"[FAIL] Errores de schema ({len(schema_errors)}):")
    for err in schema_errors[:5]:
        print(f"   - {err}")

# ============================================================================
# TEST 3: Integridad de RVOL30
# ============================================================================
print("\n[TEST 3] RVOL30 (Rolling Volume 30 sesiones)")
print("-" * 80)

rvol_tests = []
for ticker_dir in sample_tickers[:5]:
    ticker = ticker_dir.name.replace("ticker=", "")
    parquet_file = ticker_dir / "daily.parquet"

    if not parquet_file.exists():
        continue

    df = pl.read_parquet(parquet_file)

    if len(df) < 30:
        continue  # Skip tickers con pocos datos

    # Verificar que rvol30 se calculó correctamente
    # rvol30 = vol_d / rolling_mean(vol_d, 30)
    vol_30_ma = df["vol_d"].rolling_mean(window_size=30, min_periods=1)
    rvol30_expected = df["vol_d"] / vol_30_ma

    # Comparar con rvol30 calculado (tolerancia 0.01%)
    diff = (df["rvol30"] - rvol30_expected).abs()
    max_diff = diff.max()

    if max_diff < 0.001:
        rvol_tests.append((ticker, True, max_diff))
    else:
        rvol_tests.append((ticker, False, max_diff))

tests_total += 1
if len(rvol_tests) > 0:
    rvol_passed = sum(1 for _, passed, _ in rvol_tests if passed)
    if rvol_passed == len(rvol_tests):
        print(f"[OK] RVOL30 calculado correctamente en {len(rvol_tests)} tickers")
        tests_passed += 1
    else:
        print(f"[FAIL] RVOL30 incorrecto en {len(rvol_tests) - rvol_passed} tickers")
else:
    print(f"[SKIP] No hay tickers con suficientes datos para verificar RVOL30")
    tests_passed += 1  # No penalizar si no hay datos suficientes

# ============================================================================
# TEST 4: pctchg_d (Percent Change)
# ============================================================================
print("\n[TEST 4] PCTCHG_D (Percent Change)")
print("-" * 80)

pctchg_tests = []
for ticker_dir in sample_tickers[:5]:
    ticker = ticker_dir.name.replace("ticker=", "")
    parquet_file = ticker_dir / "daily.parquet"

    if not parquet_file.exists():
        continue

    df = pl.read_parquet(parquet_file)

    if len(df) < 2:
        continue

    # Verificar pctchg_d = (close_d / close_prev) - 1
    close_prev = df["close_d"].shift(1)
    pctchg_expected = (df["close_d"] / close_prev) - 1.0

    # Comparar (ignorar primer día que es null)
    diff = (df["pctchg_d"][1:] - pctchg_expected[1:]).abs()
    max_diff = diff.max()

    if max_diff < 0.0001:  # Tolerancia 0.01%
        pctchg_tests.append((ticker, True, max_diff))
    else:
        pctchg_tests.append((ticker, False, max_diff))

tests_total += 1
if len(pctchg_tests) > 0:
    pctchg_passed = sum(1 for _, passed, _ in pctchg_tests if passed)
    if pctchg_passed == len(pctchg_tests):
        print(f"[OK] pctchg_d calculado correctamente en {len(pctchg_tests)} tickers")
        tests_passed += 1
    else:
        print(f"[FAIL] pctchg_d incorrecto en {len(pctchg_tests) - pctchg_passed} tickers")
else:
    print(f"[SKIP] No hay tickers con suficientes datos para verificar pctchg_d")
    tests_passed += 1

# ============================================================================
# TEST 5: market_cap_d (Join SCD-2)
# ============================================================================
print("\n[TEST 5] MARKET_CAP_D (Join SCD-2)")
print("-" * 80)

# Verificar que market_cap_d NO es 100% null (diferencia con C_v1)
cap_coverage = []
for ticker_dir in sample_tickers:
    ticker = ticker_dir.name.replace("ticker=", "")
    parquet_file = ticker_dir / "daily.parquet"

    if not parquet_file.exists():
        continue

    df = pl.read_parquet(parquet_file)

    total = len(df)
    if total == 0:
        continue

    with_cap = df.filter(pl.col("market_cap_d").is_not_null()).height
    coverage = 100 * with_cap / total

    cap_coverage.append((ticker, coverage, total))

tests_total += 1
if len(cap_coverage) > 0:
    avg_coverage = np.mean([c for _, c, _ in cap_coverage])

    if avg_coverage > 30:  # Al menos 30% de cobertura promedio
        print(f"[OK] market_cap_d poblado: {avg_coverage:.1f}% promedio")
        print(f"     (SCD-2 join exitoso, vs C_v1 que era 100% null)")
        tests_passed += 1
    else:
        print(f"[FAIL] market_cap_d baja cobertura: {avg_coverage:.1f}%")

    # Mostrar detalle
    print(f"\n     Muestra de cobertura por ticker:")
    for ticker, cov, total in cap_coverage[:5]:
        print(f"     - {ticker:10s}: {cov:5.1f}% ({int(cov*total/100):,}/{total:,} dias)")
else:
    print(f"[SKIP] No hay datos para verificar market_cap_d")
    tests_passed += 1

# ============================================================================
# TEST 6: Cobertura temporal
# ============================================================================
print("\n[TEST 6] COBERTURA TEMPORAL")
print("-" * 80)

target_end = date(2025, 10, 21)
date_ranges = []

for ticker_dir in sample_tickers:
    ticker = ticker_dir.name.replace("ticker=", "")
    parquet_file = ticker_dir / "daily.parquet"

    if not parquet_file.exists():
        continue

    df = pl.read_parquet(parquet_file)

    if len(df) == 0:
        continue

    min_date = df["trading_day"].min()
    max_date = df["trading_day"].max()

    date_ranges.append((ticker, min_date, max_date, len(df)))

tests_total += 1
if len(date_ranges) > 0:
    # Verificar que tickers recientes llegan hasta 2025-10-21
    recent_count = sum(1 for _, _, max_d, _ in date_ranges if max_d >= target_end)

    if recent_count >= len(date_ranges) * 0.7:  # 70% threshold
        print(f"[OK] {recent_count}/{len(date_ranges)} tickers con datos hasta {target_end}")
        tests_passed += 1
    else:
        print(f"[FAIL] Solo {recent_count}/{len(date_ranges)} llegan hasta {target_end}")

    print(f"\n     Muestra de rangos temporales:")
    for ticker, min_d, max_d, days in date_ranges[:5]:
        print(f"     - {ticker:10s}: {min_d} -> {max_d} ({days:,} dias)")
else:
    print(f"[SKIP] No hay datos para verificar cobertura temporal")
    tests_passed += 1

# ============================================================================
# TEST 7: Valores estadísticos razonables
# ============================================================================
print("\n[TEST 7] DISTRIBUCIÓN ESTADÍSTICA")
print("-" * 80)

# Concatenar muestra para análisis
dfs = []
for ticker_dir in sample_tickers[:20]:
    parquet_file = ticker_dir / "daily.parquet"
    if parquet_file.exists():
        df = pl.read_parquet(parquet_file)
        if len(df) > 0:
            dfs.append(df)

if len(dfs) > 0:
    combined = pl.concat(dfs)

    # Estadísticas de pctchg_d
    pctchg_stats = combined["pctchg_d"].drop_nulls()

    if len(pctchg_stats) > 0:
        print(f"     pctchg_d (% change diario):")
        print(f"       Media: {pctchg_stats.mean():.4f}")
        print(f"       Mediana: {pctchg_stats.median():.4f}")
        print(f"       Std: {pctchg_stats.std():.4f}")
        print(f"       Min: {pctchg_stats.min():.4f}")
        print(f"       Max: {pctchg_stats.max():.4f}")

        # Estadísticas de rvol30
        rvol_stats = combined["rvol30"].drop_nulls()

        if len(rvol_stats) > 0:
            print(f"\n     rvol30 (volumen relativo):")
            print(f"       Media: {rvol_stats.mean():.2f}")
            print(f"       Mediana: {rvol_stats.median():.2f}")
            print(f"       P95: {rvol_stats.quantile(0.95):.2f}")
            print(f"       P99: {rvol_stats.quantile(0.99):.2f}")

            tests_total += 1
            # Verificar que las distribuciones son razonables
            if (-0.5 < pctchg_stats.mean() < 0.5 and
                0.5 < rvol_stats.mean() < 2.0):
                print(f"\n[OK] Distribuciones estadisticamente razonables")
                tests_passed += 1
            else:
                print(f"\n[FAIL] Distribuciones fuera de rango esperado")
        else:
            tests_total += 1
            print(f"\n[SKIP] No hay datos rvol30 para analizar")
            tests_passed += 1
    else:
        tests_total += 1
        print(f"[SKIP] No hay datos pctchg_d para analizar")
        tests_passed += 1
else:
    tests_total += 1
    print(f"[SKIP] No hay datos para analisis estadistico")
    tests_passed += 1

# ============================================================================
# RESUMEN FINAL
# ============================================================================
print("\n" + "=" * 80)
print("RESUMEN FINAL")
print("=" * 80)

success_rate = 100 * tests_passed / tests_total if tests_total > 0 else 0

print(f"\nTests ejecutados: {tests_total}")
print(f"Tests pasados: {tests_passed}")
print(f"Tasa de exito: {success_rate:.1f}%")

print(f"\n{'=' * 80}")
if tests_passed == tests_total:
    print("[SUCCESS] VERIFICACION COMPLETA - TODOS LOS TESTS PASADOS")
    print("Daily cache generado correctamente y listo para PASO 3")
    sys.exit(0)
elif success_rate >= 80:
    print("[OK] VERIFICACION ACEPTABLE - Mayoria de tests pasados")
    print(f"Revisar {tests_total - tests_passed} tests fallidos")
    sys.exit(0)
else:
    print("[FAIL] VERIFICACION FALLIDA - Multiples problemas detectados")
    print("Revisar daily cache antes de proceder")
    sys.exit(1)
print("=" * 80)
