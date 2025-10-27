#!/usr/bin/env python
"""
Spot Check - Verifica muestra aleatoria de archivos descargados

Ejecutar después de la descarga (o durante):
    python scripts/spot_check_timestamps.py

Revisa 20 archivos aleatorios y verifica timestamps
"""

import polars as pl
from pathlib import Path
import random
import sys

def main():
    print("="*80)
    print("SPOT CHECK - VALIDACION TIMESTAMPS")
    print("="*80)

    trades_dir = Path("raw/polygon/trades")

    # Encontrar todos los parquet files
    all_parquets = list(trades_dir.rglob("trades.parquet"))
    print(f"\nTotal files found: {len(all_parquets):,}")

    if len(all_parquets) == 0:
        print("[ERROR] No trades.parquet files found!")
        return 1

    # Tomar muestra aleatoria
    sample_size = min(20, len(all_parquets))
    sample_files = random.sample(all_parquets, sample_size)

    print(f"Checking random sample of {sample_size} files...\n")

    results = {'ok': 0, 'error': 0, 'missing_t_raw': 0}

    for i, parquet_file in enumerate(sample_files, 1):
        rel_path = str(parquet_file).replace(str(trades_dir) + '/', '')

        try:
            df = pl.read_parquet(parquet_file)

            # Check 1: tiene t_raw?
            if 't_raw' not in df.columns:
                print(f"[{i:2d}] [ERROR] {rel_path}")
                print(f"       Missing t_raw column. Columns: {df.columns[:5]}")
                results['missing_t_raw'] += 1
                results['error'] += 1
                continue

            # Check 2: t_raw es Int64?
            if df['t_raw'].dtype != pl.Int64:
                print(f"[{i:2d}] [ERROR] {rel_path}")
                print(f"       t_raw is {df['t_raw'].dtype}, expected Int64")
                results['error'] += 1
                continue

            # Check 3: valores en rango válido?
            max_ts = int(df['t_raw'].max())
            min_ts = int(df['t_raw'].min())

            # Rangos válidos (microsegundos o nanosegundos)
            valid_us = (900_000_000_000_000, 2_000_000_000_000_000)
            valid_ns = (900_000_000_000_000_000, 2_000_000_000_000_000_000)

            is_valid = (
                (valid_us[0] <= min_ts <= valid_us[1]) or
                (valid_ns[0] <= min_ts <= valid_ns[1])
            )

            if not is_valid:
                print(f"[{i:2d}] [ERROR] {rel_path}")
                print(f"       Timestamp out of range: {min_ts} to {max_ts}")
                results['error'] += 1
                continue

            # TODO OK!
            time_unit = "ns" if max_ts > 1e17 else "us"
            print(f"[{i:2d}] [OK] {rel_path} ({len(df):,} ticks, {time_unit})")
            results['ok'] += 1

        except Exception as e:
            print(f"[{i:2d}] [ERROR] {rel_path}")
            print(f"       Exception: {e}")
            results['error'] += 1

    # Resumen
    print("\n" + "="*80)
    print("SPOT CHECK RESULTS")
    print("="*80)
    print(f"OK: {results['ok']}/{sample_size} ({results['ok']/sample_size*100:.1f}%)")
    print(f"Errors: {results['error']}/{sample_size}")
    if results['missing_t_raw'] > 0:
        print(f"  - Missing t_raw: {results['missing_t_raw']}")

    if results['error'] == 0:
        print("\n[OK] All sampled files have correct timestamps!")
        print("[OK] Descarga parece estar funcionando correctamente.")
        return 0
    else:
        print(f"\n[WARNING] {results['error']} files have timestamp issues")
        print("[ACTION] Revisar download_trades_optimized.py - puede que el fix no se aplicó bien")
        return 1


if __name__ == "__main__":
    sys.exit(main())
