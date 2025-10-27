#!/usr/bin/env python
"""
Monitor de salud de descarga - Verifica timestamps sobre la marcha

Ejecutar en paralelo mientras corre download_trades_optimized.py:
    python scripts/monitor_download_health.py

Verifica cada 30 segundos:
- Archivos recién descargados
- Timestamps están como Int64 (no Datetime corrupto)
- Valores de t_raw están en rango válido
"""

import polars as pl
from pathlib import Path
import time
import sys
from datetime import datetime

def check_recent_files(trades_dir: Path, minutes_ago: int = 5):
    """
    Verifica archivos descargados en los últimos N minutos
    """
    now = time.time()
    cutoff = now - (minutes_ago * 60)

    recent_files = []
    for parquet_file in trades_dir.rglob("trades.parquet"):
        mtime = parquet_file.stat().st_mtime
        if mtime >= cutoff:
            recent_files.append(parquet_file)

    return recent_files


def validate_timestamps(parquet_path: Path):
    """
    Valida que timestamps estén correctos

    Returns:
        dict con resultado de validación
    """
    try:
        df = pl.read_parquet(parquet_path)

        # Verificar que exista t_raw (Int64)
        if 't_raw' not in df.columns:
            return {
                'status': 'ERROR',
                'reason': 'missing_t_raw_column',
                'has_t_raw': False,
                'has_t_unit': False,
            }

        # Verificar tipo de t_raw
        if df['t_raw'].dtype != pl.Int64:
            return {
                'status': 'ERROR',
                'reason': f't_raw is {df["t_raw"].dtype}, expected Int64',
                'has_t_raw': True,
                'has_t_unit': 't_unit' in df.columns,
            }

        # Verificar rango de valores (no debe ser year 52XXX)
        max_ts = int(df['t_raw'].max())
        min_ts = int(df['t_raw'].min())

        # Timestamp válido debe estar entre:
        # 2000-01-01 (946684800000000 us) y 2030-01-01 (1893456000000000 us)
        # o en nanosegundos: multiplicar por 1000

        valid_range_us = (900_000_000_000_000, 2_000_000_000_000_000)
        valid_range_ns = (900_000_000_000_000_000, 2_000_000_000_000_000_000)

        in_valid_range = (
            (valid_range_us[0] <= min_ts <= valid_range_us[1]) or
            (valid_range_ns[0] <= min_ts <= valid_range_ns[1])
        )

        if not in_valid_range:
            return {
                'status': 'ERROR',
                'reason': f'timestamp out of valid range: {min_ts} to {max_ts}',
                'has_t_raw': True,
                'has_t_unit': 't_unit' in df.columns,
                'min_ts': min_ts,
                'max_ts': max_ts,
            }

        # TODO OK
        return {
            'status': 'OK',
            'reason': None,
            'has_t_raw': True,
            'has_t_unit': 't_unit' in df.columns,
            'min_ts': min_ts,
            'max_ts': max_ts,
            'n_ticks': len(df),
        }

    except Exception as e:
        return {
            'status': 'ERROR',
            'reason': str(e),
            'has_t_raw': False,
            'has_t_unit': False,
        }


def main():
    print("="*80)
    print("MONITOR DE SALUD - DESCARGA TICKS")
    print("="*80)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\nMonitoring: raw/polygon/trades/")
    print("Press Ctrl+C to stop\n")

    trades_dir = Path("raw/polygon/trades")

    total_checked = 0
    total_ok = 0
    total_errors = 0
    last_check_time = None

    try:
        while True:
            # Buscar archivos recién descargados (últimos 2 minutos)
            recent_files = check_recent_files(trades_dir, minutes_ago=2)

            if len(recent_files) == 0:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] No new files in last 2 min. Waiting...", end="\r")
                time.sleep(30)
                continue

            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Found {len(recent_files)} recent files. Checking...")

            for parquet_file in recent_files[:5]:  # Solo primeros 5 para no saturar
                result = validate_timestamps(parquet_file)
                total_checked += 1

                if result['status'] == 'OK':
                    total_ok += 1
                    status_icon = "[OK]"
                else:
                    total_errors += 1
                    status_icon = "[ERROR]"

                # Mostrar solo path relativo
                rel_path = str(parquet_file).replace('raw/polygon/trades/', '')

                if result['status'] == 'OK':
                    print(f"  {status_icon} {rel_path}: {result['n_ticks']:,} ticks")
                else:
                    print(f"  {status_icon} {rel_path}: {result['reason']}")

            # Resumen
            success_rate = (total_ok / total_checked * 100) if total_checked > 0 else 0
            print(f"\nStats: {total_ok}/{total_checked} OK ({success_rate:.1f}%), {total_errors} errors")

            # Verificar si hay errores críticos
            if total_errors > 0 and total_checked > 10:
                error_rate = total_errors / total_checked
                if error_rate > 0.3:  # Más del 30% errores
                    print("\n" + "="*80)
                    print("WARNING: ERROR RATE > 30%")
                    print("="*80)
                    print("La descarga puede estar escribiendo mal los timestamps.")
                    print("RECOMENDACION: Detener descarga y revisar download_trades_optimized.py")
                    print("="*80)

            time.sleep(30)  # Esperar 30 segundos antes de siguiente check

    except KeyboardInterrupt:
        print("\n\n" + "="*80)
        print("MONITOR STOPPED")
        print("="*80)
        print(f"\nFinal stats:")
        print(f"  Total checked: {total_checked}")
        print(f"  OK: {total_ok} ({total_ok/total_checked*100:.1f}%)")
        print(f"  Errors: {total_errors} ({total_errors/total_checked*100:.1f}%)")

        if total_errors == 0 and total_ok > 0:
            print("\n[OK] All validated files have correct timestamps!")
        elif total_errors > 0:
            print(f"\n[WARNING] {total_errors} files have timestamp issues")

        return 0 if total_errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
