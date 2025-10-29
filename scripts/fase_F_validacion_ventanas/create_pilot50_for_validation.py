#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
create_pilot50_for_validation.py

Crea watchlist pilot de 50 tickers para validar ventanas temporales.

Criterios de selección:
- Mix balanceado de eventos E1-E11
- Tickers con múltiples eventos (información rica)
- Cobertura temporal amplia (2004-2025)
- Variedad de frecuencias (high/medium/low activity)

Output:
  processed/watchlist_E1_E11_pilot50_validation.parquet
"""

import polars as pl
from pathlib import Path

def select_pilot50_tickers():
    """
    Selecciona 50 tickers representativos para validación de ventanas.
    """

    # Cargar watchlist E1-E11 completa
    watchlist_file = Path('processed/watchlist_E1_E11.parquet')
    df = pl.read_parquet(watchlist_file)

    print('=' * 80)
    print('CREANDO PILOT 50 TICKERS PARA VALIDACIÓN DE VENTANAS')
    print('=' * 80)
    print()
    print(f'Watchlist completa: {len(df):,} ticker-dates')
    print(f'Tickers únicos: {df["ticker"].n_unique():,}')
    print()

    # Calcular estadísticas por ticker
    df_ticker_stats = (
        df
        .group_by('ticker')
        .agg([
            pl.len().alias('n_days'),
            pl.col('event_count').sum().alias('total_events'),
            pl.col('date').min().alias('first_date'),
            pl.col('date').max().alias('last_date'),
        ])
        .with_columns([
            (pl.col('last_date') - pl.col('first_date')).dt.total_days().alias('span_days')
        ])
    )

    # Explotar eventos para análisis de cobertura
    df_events_exploded = df.explode('events')

    # Contar eventos por ticker
    df_event_coverage = (
        df_events_exploded
        .group_by('ticker')
        .agg([
            pl.col('events').n_unique().alias('n_unique_events')
        ])
    )

    # Join con stats
    df_ticker_stats = df_ticker_stats.join(df_event_coverage, on='ticker', how='left')

    # Criterios de selección
    # 1. Tickers con múltiples eventos únicos (información rica)
    # 2. Balance entre high/medium/low activity
    # 3. Cobertura temporal amplia

    # Segmentar por actividad
    q33 = df_ticker_stats['n_days'].quantile(0.33)
    q67 = df_ticker_stats['n_days'].quantile(0.67)

    df_high = df_ticker_stats.filter(pl.col('n_days') > q67)
    df_medium = df_ticker_stats.filter(
        (pl.col('n_days') > q33) & (pl.col('n_days') <= q67)
    )
    df_low = df_ticker_stats.filter(pl.col('n_days') <= q33)

    print('Distribución de actividad:')
    print(f'  High activity (>{int(q67)} días):   {len(df_high):,} tickers')
    print(f'  Medium activity ({int(q33)}-{int(q67)} días): {len(df_medium):,} tickers')
    print(f'  Low activity (<{int(q33)} días):    {len(df_low):,} tickers')
    print()

    # Seleccionar top tickers por diversidad de eventos + actividad
    # Score = n_unique_events * log(n_days)

    # Agregar diversity_score a cada segmento
    df_high = df_high.with_columns([
        (pl.col('n_unique_events') * pl.col('n_days').log()).alias('diversity_score')
    ])

    df_medium = df_medium.with_columns([
        (pl.col('n_unique_events') * pl.col('n_days').log()).alias('diversity_score')
    ])

    df_low = df_low.with_columns([
        (pl.col('n_unique_events') * pl.col('n_days').log()).alias('diversity_score')
    ])

    # Seleccionar 50 tickers
    # - 20 high activity
    # - 20 medium activity
    # - 10 low activity

    pilot_high = (
        df_high
        .sort('diversity_score', descending=True)
        .head(20)['ticker']
        .to_list()
    )

    pilot_medium = (
        df_medium
        .sort('diversity_score', descending=True)
        .head(20)['ticker']
        .to_list()
    )

    pilot_low = (
        df_low
        .sort('diversity_score', descending=True)
        .head(10)['ticker']
        .to_list()
    )

    pilot50_tickers = pilot_high + pilot_medium + pilot_low

    # Filtrar watchlist a pilot50
    df_pilot50 = df.filter(pl.col('ticker').is_in(pilot50_tickers))

    # Estadísticas del pilot
    print('PILOT 50 SELECCIONADO:')
    print()
    print(f'Tickers: {len(pilot50_tickers)}')
    print(f'Ticker-dates: {len(df_pilot50):,}')
    print(f'Rango temporal: {df_pilot50["date"].min()} -> {df_pilot50["date"].max()}')
    print()

    # Distribución de eventos en pilot
    df_pilot_events = df_pilot50.explode('events')
    event_dist = (
        df_pilot_events
        .group_by('events')
        .agg([pl.len().alias('count')])
        .sort('count', descending=True)
    )

    print('Distribución de eventos en pilot:')
    for row in event_dist.iter_rows(named=True):
        print(f"  {row['events']}: {row['count']:,}")
    print()

    # Lista de tickers
    print('Tickers seleccionados:')
    print(f"  High (20): {', '.join(pilot_high[:10])}...")
    print(f"  Medium (20): {', '.join(pilot_medium[:10])}...")
    print(f"  Low (10): {', '.join(pilot_low)}")
    print()

    return df_pilot50, pilot50_tickers

def save_pilot50(df_pilot50, tickers):
    """Guarda pilot50 watchlist"""
    output_file = Path('processed/watchlist_E1_E11_pilot50_validation.parquet')
    df_pilot50.write_parquet(output_file)

    print(f'[OK] Pilot50 guardado: {output_file}')
    print()

    # También guardar lista de tickers
    ticker_list_file = Path('processed/pilot50_tickers_validation.txt')
    with open(ticker_list_file, 'w') as f:
        for t in tickers:
            f.write(f"{t}\n")

    print(f'[OK] Lista de tickers guardada: {ticker_list_file}')
    print()

if __name__ == '__main__':
    df_pilot50, tickers = select_pilot50_tickers()
    save_pilot50(df_pilot50, tickers)

    print('=' * 80)
    print('RESUMEN')
    print('=' * 80)
    print()
    print(f'Pilot50 listo para descarga con --event-window 3')
    print(f'Próximo paso: Descargar trades con ventana conservadora ±3')
    print()
    print('Comando:')
    print('  python scripts/fase_C_ingesta_tiks/download_trades_optimized.py \\')
    print('    --outdir raw/polygon/trades_pilot50_validation \\')
    print('    --from 2004-01-01 \\')
    print('    --to 2025-10-24 \\')
    print('    --mode watchlists \\')
    print('    --watchlist-root processed/universe/multi_event/daily \\')
    print('    --tickers-csv processed/pilot50_tickers_validation.txt \\')
    print('    --event-window 3 \\')
    print('    --page-limit 50000 \\')
    print('    --rate-limit 0.12 \\')
    print('    --workers 6 \\')
    print('    --resume')
