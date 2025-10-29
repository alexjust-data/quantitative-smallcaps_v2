#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
fix_pilot50_add_info_rich_column.py

Agrega columna 'info_rich' = True a todos los watchlists particionados.
El downloader requiere esta columna para identificar dias info-rich.
"""

import polars as pl
from pathlib import Path

def fix_pilot50_watchlists():
    """Agrega columna info_rich=True a todos los watchlists"""

    watchlist_root = Path('processed/universe/pilot50_validation/daily')

    # Buscar todos los watchlist.parquet
    watchlist_files = list(watchlist_root.rglob('watchlist.parquet'))

    print('=' * 80)
    print('FIX: AGREGANDO COLUMNA info_rich')
    print('=' * 80)
    print()
    print(f'Archivos encontrados: {len(watchlist_files):,}')
    print()

    for i, watchlist_file in enumerate(watchlist_files):
        # Leer
        df = pl.read_parquet(watchlist_file)

        # Agregar columna si no existe
        if 'info_rich' not in df.columns:
            df = df.with_columns([
                pl.lit(True).alias('info_rich')
            ])

            # Reescribir
            df.write_parquet(watchlist_file)

        if (i + 1) % 500 == 0:
            print(f'  Progreso: {i+1:,}/{len(watchlist_files):,} ({(i+1)/len(watchlist_files)*100:.1f}%)')

    print()
    print('[OK] Fix completo!')
    print(f'     Archivos actualizados: {len(watchlist_files):,}')
    print()

if __name__ == '__main__':
    fix_pilot50_watchlists()
