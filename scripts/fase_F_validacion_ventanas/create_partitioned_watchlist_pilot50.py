#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
create_partitioned_watchlist_pilot50.py

Crea watchlists particionados por día para el pilot50.

El downloader actual espera estructura:
  processed/universe/pilot50_validation/daily/date=YYYY-MM-DD/watchlist.parquet

Este script toma el pilot50 único y lo particiona por fecha.
"""

import polars as pl
from pathlib import Path

def partition_pilot50():
    """Particiona pilot50 watchlist por fecha"""

    # Cargar pilot50
    pilot50_file = Path('processed/watchlist_E1_E11_pilot50_validation.parquet')
    df_pilot50 = pl.read_parquet(pilot50_file)

    print('=' * 80)
    print('PARTICIONANDO PILOT50 POR FECHA')
    print('=' * 80)
    print()
    print(f'Total ticker-dates: {len(df_pilot50):,}')
    print(f'Fechas únicas: {df_pilot50["date"].n_unique():,}')
    print()

    # Directorio de salida
    output_root = Path('processed/universe/pilot50_validation/daily')
    output_root.mkdir(parents=True, exist_ok=True)

    # Agrupar por fecha
    dates = df_pilot50['date'].unique().sort().to_list()

    print(f'Creando {len(dates):,} archivos particionados...')

    for i, date in enumerate(dates):
        # Filtrar por fecha
        df_date = df_pilot50.filter(pl.col('date') == date)

        # Crear directorio
        date_dir = output_root / f'date={date.isoformat()}'
        date_dir.mkdir(parents=True, exist_ok=True)

        # Guardar watchlist
        output_file = date_dir / 'watchlist.parquet'
        df_date.write_parquet(output_file)

        if (i + 1) % 100 == 0:
            print(f'  Progreso: {i+1:,}/{len(dates):,} ({(i+1)/len(dates)*100:.1f}%)')

    print()
    print('[OK] Particionado completo!')
    print(f'     Output: {output_root}')
    print()

    return output_root

if __name__ == '__main__':
    output_root = partition_pilot50()

    print('=' * 80)
    print('COMANDO DE DESCARGA')
    print('=' * 80)
    print()
    print('python scripts/fase_C_ingesta_tiks/download_trades_optimized.py \\')
    print('  --outdir raw/polygon/trades_pilot50_validation \\')
    print('  --from 2004-01-01 \\')
    print('  --to 2025-10-24 \\')
    print('  --mode watchlists \\')
    print(f'  --watchlist-root {output_root} \\')
    print('  --event-window 3 \\')
    print('  --page-limit 50000 \\')
    print('  --rate-limit 0.12 \\')
    print('  --workers 6 \\')
    print('  --resume')
