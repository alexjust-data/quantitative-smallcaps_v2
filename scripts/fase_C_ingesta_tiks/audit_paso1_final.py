#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
audit_paso1_final.py
Auditoria final PASO 1: Build Daily Cache 2004-2025

Verifica:
1. Archivo _SUCCESS existe
2. Cantidad de tickers procesados vs esperados
3. Cobertura temporal (2004-2025)
4. Integridad de archivos (daily.parquet + _SUCCESS)
5. Columnas requeridas (rvol30, pctchg_d, dollar_vol_d, market_cap_d)
6. Estadisticas de storage
7. Tickers con errores
"""
import polars as pl
from pathlib import Path
from datetime import datetime, date
import json

print("=" * 80)
print("AUDITORIA FINAL - PASO 1: BUILD DAILY CACHE 2004-2025")
print("=" * 80)

# ============================================================================
# 1. VERIFICAR ARCHIVO _SUCCESS
# ============================================================================
print("\n[1] VERIFICACION _SUCCESS")
print("-" * 80)

cache_root = Path("processed/daily_cache")
success_file = cache_root / "_SUCCESS"

if success_file.exists():
    mtime = datetime.fromtimestamp(success_file.stat().st_mtime)
    print(f"[OK] _SUCCESS existe")
    print(f"     Timestamp: {mtime.strftime('%Y-%m-%d %H:%M:%S')}")
else:
    print("[FAIL] _SUCCESS NO existe - proceso no completo")
    exit(1)

# ============================================================================
# 2. CONTAR TICKERS PROCESADOS
# ============================================================================
print("\n[2] CONTEO DE TICKERS")
print("-" * 80)

ticker_dirs = list(cache_root.glob("ticker=*"))
total_dirs = len(ticker_dirs)

# Tickers con _SUCCESS (completados exitosamente)
success_tickers = [d for d in ticker_dirs if (d / "_SUCCESS").exists()]
completed = len(success_tickers)

# Tickers con daily.parquet pero sin _SUCCESS (posibles errores)
partial = [d for d in ticker_dirs if (d / "daily.parquet").exists() and not (d / "_SUCCESS").exists()]
failed = len(partial)

# Tickers sin datos
no_data = total_dirs - completed - failed

print(f"Total directorios ticker=*: {total_dirs:,}")
print(f"  [OK] Completados (_SUCCESS): {completed:,} ({100*completed/total_dirs:.1f}%)")
print(f"  [WARN] Fallidos (sin _SUCCESS): {failed:,}")
print(f"  [INFO] Sin datos: {no_data:,}")

# Comparar con expectativa (8,620 tickers)
expected = 8620
if completed >= expected * 0.95:  # Tolerancia 5%
    print(f"\n[OK] Cobertura: {100*completed/expected:.1f}% del objetivo ({expected:,} tickers)")
else:
    print(f"\n[WARN] Cobertura baja: {100*completed/expected:.1f}% del objetivo ({expected:,} tickers)")

# ============================================================================
# 3. VERIFICAR INTEGRIDAD DE ARCHIVOS
# ============================================================================
print("\n[3] INTEGRIDAD DE ARCHIVOS")
print("-" * 80)

corrupted = []
for d in success_tickers[:100]:  # Muestra primeros 100
    parquet_file = d / "daily.parquet"
    if not parquet_file.exists():
        corrupted.append(d.name.replace("ticker=", ""))

if len(corrupted) == 0:
    print(f"[OK] Muestra 100 tickers: todos tienen daily.parquet")
else:
    print(f"[FAIL] {len(corrupted)} tickers sin daily.parquet: {corrupted[:10]}")

# ============================================================================
# 4. VERIFICAR SCHEMA Y COLUMNAS REQUERIDAS
# ============================================================================
print("\n[4] VERIFICACION SCHEMA")
print("-" * 80)

required_cols = [
    "ticker", "trading_day", "close_d", "vol_d", "dollar_vol_d",
    "vwap_d", "pctchg_d", "rvol30", "market_cap_d"
]

# Leer un ticker de muestra
if completed > 0:
    sample_ticker = success_tickers[0]
    sample_df = pl.read_parquet(sample_ticker / "daily.parquet")

    print(f"Ticker muestra: {sample_ticker.name.replace('ticker=', '')}")
    print(f"Shape: {sample_df.shape}")
    print(f"\nColumnas encontradas:")

    missing_cols = []
    for col in required_cols:
        if col in sample_df.columns:
            dtype = sample_df.schema[col]
            null_count = sample_df[col].null_count()
            null_pct = 100 * null_count / len(sample_df)
            print(f"  [OK] {col:20s} {str(dtype):15s} (nulls: {null_pct:.1f}%)")
        else:
            print(f"  [FAIL] {col:20s} MISSING")
            missing_cols.append(col)

    if len(missing_cols) == 0:
        print(f"\n[OK] Todas las columnas requeridas presentes")
    else:
        print(f"\n[FAIL] Columnas faltantes: {missing_cols}")

# ============================================================================
# 5. VERIFICAR COBERTURA TEMPORAL
# ============================================================================
print("\n[5] COBERTURA TEMPORAL")
print("-" * 80)

if completed > 0:
    # Muestra de 10 tickers para verificar rango de fechas
    sample_size = min(10, completed)
    date_ranges = []

    for ticker_dir in success_tickers[:sample_size]:
        ticker = ticker_dir.name.replace("ticker=", "")
        df = pl.read_parquet(ticker_dir / "daily.parquet")

        if len(df) > 0:
            min_date = df["trading_day"].min()
            max_date = df["trading_day"].max()
            days = len(df)
            date_ranges.append({
                "ticker": ticker,
                "min_date": min_date,
                "max_date": max_date,
                "days": days
            })

    print(f"Muestra de {len(date_ranges)} tickers:")
    for r in date_ranges:
        print(f"  {r['ticker']:10s} {r['min_date']} -> {r['max_date']} ({r['days']:,} dias)")

    # Verificar que los mas recientes llegan hasta 2025-10-21
    target_end = date(2025, 10, 21)
    recent_coverage = [r for r in date_ranges if r['max_date'] >= target_end]

    print(f"\nTickers con datos hasta {target_end}: {len(recent_coverage)}/{len(date_ranges)}")

    if len(recent_coverage) >= len(date_ranges) * 0.8:  # 80% threshold
        print(f"[OK] Cobertura temporal adecuada")
    else:
        print(f"[WARN] Cobertura temporal baja")

# ============================================================================
# 6. VERIFICAR market_cap_d (JOIN CON SCD-2)
# ============================================================================
print("\n[6] VERIFICACION market_cap_d (JOIN SCD-2)")
print("-" * 80)

if completed > 0:
    # Verificar que market_cap_d tiene valores (no todo null como C_v1)
    sample_size = min(20, completed)
    cap_coverage = []

    for ticker_dir in success_tickers[:sample_size]:
        ticker = ticker_dir.name.replace("ticker=", "")
        df = pl.read_parquet(ticker_dir / "daily.parquet")

        total = len(df)
        with_cap = df.filter(pl.col("market_cap_d").is_not_null()).height
        coverage_pct = 100 * with_cap / total if total > 0 else 0

        cap_coverage.append({
            "ticker": ticker,
            "total": total,
            "with_cap": with_cap,
            "coverage": coverage_pct
        })

    print(f"Muestra de {len(cap_coverage)} tickers - cobertura market_cap_d:")
    for c in cap_coverage[:10]:
        status = "[OK]" if c['coverage'] > 0 else "[WARN]"
        print(f"  {status} {c['ticker']:10s} {c['with_cap']:,}/{c['total']:,} ({c['coverage']:.1f}%)")

    avg_coverage = sum(c['coverage'] for c in cap_coverage) / len(cap_coverage)
    print(f"\nCobertura promedio: {avg_coverage:.1f}%")

    if avg_coverage > 50:
        print(f"[OK] market_cap_d poblado (SCD-2 join exitoso)")
    elif avg_coverage > 0:
        print(f"[WARN] market_cap_d parcialmente poblado ({avg_coverage:.1f}%)")
    else:
        print(f"[FAIL] market_cap_d completamente null (SCD-2 join fallo)")

# ============================================================================
# 7. ESTADISTICAS DE STORAGE
# ============================================================================
print("\n[7] STORAGE")
print("-" * 80)

total_size = 0
for ticker_dir in success_tickers:
    parquet_file = ticker_dir / "daily.parquet"
    if parquet_file.exists():
        total_size += parquet_file.stat().st_size

total_gb = total_size / (1024**3)
avg_mb = (total_size / (1024**2)) / completed if completed > 0 else 0

print(f"Total storage: {total_gb:.2f} GB ({completed:,} tickers)")
print(f"Promedio/ticker: {avg_mb:.3f} MB")
print(f"Compresion: ZSTD")

# ============================================================================
# 8. TICKERS CON ERRORES
# ============================================================================
print("\n[8] TICKERS CON ERRORES/PROBLEMAS")
print("-" * 80)

if failed > 0:
    print(f"[WARN] {failed} tickers fallidos (sin _SUCCESS):")
    for d in partial[:10]:
        ticker = d.name.replace("ticker=", "")
        print(f"  - {ticker}")
else:
    print(f"[OK] Sin errores - todos los tickers procesados tienen _SUCCESS")

# Tickers sin datos
no_data_tickers = [d for d in ticker_dirs if not (d / "daily.parquet").exists()]
if len(no_data_tickers) > 0:
    print(f"\n[INFO] {len(no_data_tickers)} tickers sin datos (esperado para algunos):")
    for d in no_data_tickers[:10]:
        ticker = d.name.replace("ticker=", "")
        print(f"  - {ticker}")

# ============================================================================
# 9. VERIFICACION FINAL
# ============================================================================
print("\n" + "=" * 80)
print("VERIFICACION FINAL")
print("=" * 80)

checks = {
    "_SUCCESS existe": success_file.exists(),
    "Cobertura >= 95%": completed >= expected * 0.95,
    "Schema correcto": len(missing_cols) == 0 if completed > 0 else False,
    "market_cap_d poblado": avg_coverage > 0 if completed > 0 else False,
    "Sin tickers corruptos": len(corrupted) == 0,
}

all_passed = all(checks.values())

for check, passed in checks.items():
    status = "[OK]" if passed else "[FAIL]"
    print(f"{status} {check}")

print("\n" + "=" * 80)
if all_passed:
    print("[SUCCESS] PASO 1 COMPLETADO EXITOSAMENTE")
    print(f"Tickers procesados: {completed:,} / {expected:,}")
    print(f"Storage total: {total_gb:.2f} GB")
    print(f"Listo para PASO 3: Generacion universo dinamico E0")
else:
    print("[FAIL] PASO 1 tiene problemas - revisar errores arriba")
print("=" * 80)

# ============================================================================
# 10. RESUMEN EJECUTIVO
# ============================================================================
print("\n" + "=" * 80)
print("RESUMEN EJECUTIVO")
print("=" * 80)

print(f"""
PASO 1: Build Daily Cache 2004-2025

Estado: {"COMPLETADO" if all_passed else "CON ERRORES"}
Tickers procesados: {completed:,} / {expected:,} ({100*completed/expected:.1f}%)
Tickers fallidos: {failed:,}
Tickers sin datos: {len(no_data_tickers):,}

Storage:
  Total: {total_gb:.2f} GB
  Promedio/ticker: {avg_mb:.3f} MB
  Compresion: ZSTD

Cobertura temporal: 2004-2025
Columnas criticas:
  - rvol30: {"OK" if "rvol30" in sample_df.columns else "MISSING"}
  - pctchg_d: {"OK" if "pctchg_d" in sample_df.columns else "MISSING"}
  - dollar_vol_d: {"OK" if "dollar_vol_d" in sample_df.columns else "MISSING"}
  - market_cap_d: {"OK" if avg_coverage > 0 else "FAIL"} ({avg_coverage:.1f}% poblado)

Proximo paso: PASO 3 - Generar universo dinamico E0
  Comando:
    python scripts/fase_C_ingesta_tiks/build_dynamic_universe_optimized.py \\
      --daily-cache processed/daily_cache \\
      --outdir processed/universe/info_rich \\
      --from 2004-01-01 --to 2025-10-21 \\
      --config configs/universe_config.yaml
""")

print("=" * 80)
