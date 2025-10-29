#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
audit_pilot50_download.py

Audita el estado de la descarga Pilot50 validation.
Analiza archivos descargados, errores, progreso y estima tiempo restante.
"""

import polars as pl
from pathlib import Path
from datetime import datetime
import json

def audit_download():
    """Audita descarga Pilot50"""

    print('=' * 80)
    print('AUDITORIA DESCARGA PILOT50 VALIDATION')
    print('=' * 80)
    print()

    # 1. Cargar watchlist esperado
    print('[1/5] Cargando watchlist esperado...')
    watchlist_root = Path('processed/universe/pilot50_validation/daily')

    # Contar ticker-dates esperados
    expected_ticker_dates = []
    for watchlist_file in watchlist_root.rglob('watchlist.parquet'):
        df = pl.read_parquet(watchlist_file)
        for row in df.iter_rows(named=True):
            expected_ticker_dates.append({
                'ticker': row['ticker'],
                'date': str(row['date'])
            })

    total_expected = len(expected_ticker_dates)
    print(f'      Ticker-dates esperados: {total_expected:,}')
    print()

    # 2. Escanear archivos descargados
    print('[2/5] Escaneando archivos descargados...')
    trades_root = Path('raw/polygon/trades_pilot50_validation')

    if not trades_root.exists():
        print('      [!] Directorio de descarga no existe todavia')
        print()
        return

    downloaded_files = []
    total_size_bytes = 0

    for parquet_file in trades_root.rglob('trades.parquet'):
        parts = parquet_file.parts
        ticker = parts[-3]
        date = parts[-2].split('=')[1]
        size = parquet_file.stat().st_size

        downloaded_files.append({
            'ticker': ticker,
            'date': date,
            'size_bytes': size
        })
        total_size_bytes += size

    total_downloaded = len(downloaded_files)
    total_size_mb = total_size_bytes / (1024 * 1024)
    total_size_gb = total_size_mb / 1024

    print(f'      Archivos descargados: {total_downloaded:,}')
    print(f'      Tamano total: {total_size_mb:,.1f} MB ({total_size_gb:.2f} GB)')
    print()

    # 3. Calcular progreso
    print('[3/5] Calculando progreso...')
    progress_pct = (total_downloaded / total_expected * 100) if total_expected > 0 else 0
    remaining = total_expected - total_downloaded

    print(f'      Progreso: {progress_pct:.1f}% ({total_downloaded:,} / {total_expected:,})')
    print(f'      Restantes: {remaining:,} ticker-dates')
    print()

    # 4. Analizar tickers
    print('[4/5] Analizando por ticker...')
    df_downloaded = pl.DataFrame(downloaded_files)

    if len(downloaded_files) > 0:
        ticker_stats = (
            df_downloaded
            .group_by('ticker')
            .agg([
                pl.len().alias('n_dates'),
                pl.col('size_bytes').sum().alias('total_bytes')
            ])
            .sort('n_dates', descending=True)
        )

        print(f'      Tickers con datos: {len(ticker_stats):,}')
        print()
        print('      Top 10 tickers por volumen:')
        for row in ticker_stats.head(10).iter_rows(named=True):
            mb = row['total_bytes'] / (1024 * 1024)
            print(f'        {row["ticker"]:6s}: {row["n_dates"]:4d} dates, {mb:6.1f} MB')
    else:
        print('      [!] No hay archivos descargados todavia')

    print()

    # 5. Estimar tiempo restante
    print('[5/5] Estimando tiempo restante...')

    if total_downloaded > 0 and remaining > 0:
        # Estimar rate actual
        avg_size_per_file = total_size_bytes / total_downloaded
        estimated_remaining_bytes = avg_size_per_file * remaining
        estimated_remaining_mb = estimated_remaining_bytes / (1024 * 1024)
        estimated_remaining_gb = estimated_remaining_mb / 1024

        # Con 6 workers y rate-limit 0.12s -> ~8 req/s -> ~50 archivos/min
        # Pero depende de tamano de archivos y paginacion
        # Estimacion conservadora: 10-15 archivos/min
        files_per_min = 12  # Conservador
        estimated_min_remaining = remaining / files_per_min
        estimated_hours_remaining = estimated_min_remaining / 60

        print(f'      Tamano estimado restante: {estimated_remaining_mb:,.1f} MB ({estimated_remaining_gb:.2f} GB)')
        print(f'      Tiempo estimado restante: {estimated_hours_remaining:.1f} horas')
        print(f'      (Asumiendo {files_per_min} archivos/min)')
    else:
        print('      [!] Insuficientes datos para estimar')

    print()
    print('=' * 80)
    print('RESUMEN')
    print('=' * 80)
    print(f'Esperado:    {total_expected:,} ticker-dates')
    print(f'Descargado:  {total_downloaded:,} archivos ({progress_pct:.1f}%)')
    print(f'Restante:    {remaining:,} archivos')
    print(f'Tamano:      {total_size_gb:.2f} GB')
    print('=' * 80)
    print()

    # Guardar audit result
    audit_data = {
        'timestamp': datetime.now().isoformat(),
        'expected': total_expected,
        'downloaded': total_downloaded,
        'remaining': remaining,
        'progress_pct': progress_pct,
        'total_size_bytes': total_size_bytes,
        'total_size_gb': total_size_gb
    }

    audit_file = Path('processed/audit_pilot50_download.json')
    with open(audit_file, 'w') as f:
        json.dump(audit_data, f, indent=2)

    print(f'Audit guardado en: {audit_file}')
    print()

if __name__ == '__main__':
    audit_download()
