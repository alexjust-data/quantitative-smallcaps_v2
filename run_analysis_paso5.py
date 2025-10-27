#!/usr/bin/env python3
"""
Analisis visual completo PASO 5 (version simplificada del notebook)
"""
import polars as pl
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import random

def format_size(bytes_size):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} PB"

def get_file_size(path):
    try:
        return path.stat().st_size
    except:
        return 0

print("="*80)
print("ANALISIS PASO 5: DESCARGA TICKS E0 (2004-2025)")
print("="*80)
print()

# Paths
trades_dir = Path('raw/polygon/trades')
watchlists_dir = Path('processed/universe/info_rich/daily')

# ============================================================================
# 1. ANALISIS EVENTOS E0
# ============================================================================
print("1. CARGANDO EVENTOS E0...")
print("-" * 80)

watchlist_files = sorted(watchlists_dir.glob('date=*/watchlist.parquet'))
print(f"Watchlists encontrados: {len(watchlist_files):,}")

e0_events = []
for wf in watchlist_files:
    try:
        df = pl.read_parquet(wf)
        e0_df = df.filter(pl.col('info_rich') == True)
        if len(e0_df) > 0:
            date_str = wf.parent.name.split('=')[1]
            for row in e0_df.iter_rows(named=True):
                e0_events.append({
                    'ticker': row['ticker'],
                    'trading_day': date_str,
                    'rvol30': row['rvol30'],
                    'pctchg_d': row['pctchg_d'],
                    'dollar_vol_d': row['dollar_vol_d'],
                    'close_d': row['close_d']
                })
    except Exception as e:
        print(f"Error leyendo {wf}: {e}")

e0_df = pl.DataFrame(e0_events)
print(f"\nEventos E0 totales: {len(e0_df):,}")
print(f"Tickers unicos con E0: {e0_df['ticker'].n_unique():,}")
print(f"Dias unicos con E0: {e0_df['trading_day'].n_unique():,}")
print()

# Eventos por año
e0_df_pd = e0_df.to_pandas()
e0_df_pd['year'] = e0_df_pd['trading_day'].str[:4]
events_by_year = e0_df_pd.groupby('year').size().sort_index()

print("Eventos E0 por año:")
for year, count in events_by_year.items():
    print(f"  {year}: {count:,}")
print()

# TOP 20 tickers
top_tickers = e0_df.group_by('ticker').agg(
    pl.count().alias('eventos_e0')
).sort('eventos_e0', descending=True).head(20)

print("TOP 20 Tickers con mas Eventos E0:")
for i, row in enumerate(top_tickers.iter_rows(named=True), 1):
    print(f"  {i:2d}. {row['ticker']:6s}: {row['eventos_e0']:3d} eventos")
print()

# ============================================================================
# 2. ANALISIS DESCARGAS
# ============================================================================
print("2. ANALIZANDO ARCHIVOS DESCARGADOS...")
print("-" * 80)

success_files = list(trades_dir.rglob('_SUCCESS'))
trades_files = list(trades_dir.rglob('trades.parquet'))
ticker_dirs = [d for d in trades_dir.iterdir() if d.is_dir()]

target_days = 82_012
coverage_pct = (len(success_files) / target_days) * 100

print(f"\nDias completados (_SUCCESS): {len(success_files):,}")
print(f"Archivos trades.parquet: {len(trades_files):,}")
print(f"Tickers con descargas: {len(ticker_dirs):,}")
print(f"Cobertura: {coverage_pct:.1f}% ({len(success_files):,} / {target_days:,} dias)")
print()

# ============================================================================
# 3. ANALISIS TAMANO
# ============================================================================
print("3. CALCULANDO TAMANO DE DESCARGA...")
print("-" * 80)

total_size = 0
size_by_ticker = {}

for ticker_dir in ticker_dirs:
    ticker_size = 0
    for tf in ticker_dir.rglob('trades.parquet'):
        size = get_file_size(tf)
        ticker_size += size
        total_size += size

    if ticker_size > 0:
        size_by_ticker[ticker_dir.name] = ticker_size

total_gb = total_size / (1024**3)
avg_size_per_day = total_size / len(success_files) if len(success_files) > 0 else 0
projected_total = avg_size_per_day * target_days
projected_gb = projected_total / (1024**3)

print(f"\nTamano total descargado: {format_size(total_size)} ({total_gb:.2f} GB)")
print(f"Tamano promedio/dia: {format_size(avg_size_per_day)}")
print(f"\nPROYECCION FINAL (100% completado): ~{projected_gb:.2f} GB")
print(f"  Estimacion original C.5: 2,600 GB")
print(f"  Diferencia: {projected_gb - 2600:+,.0f} GB ({((projected_gb - 2600) / 2600) * 100:+.1f}%)")
print()

# TOP 10 tickers por tamaño
sorted_sizes = sorted(size_by_ticker.items(), key=lambda x: x[1], reverse=True)[:10]
print("TOP 10 Tickers por Tamano de Descarga:")
for i, (ticker, size) in enumerate(sorted_sizes, 1):
    print(f"  {i:2d}. {ticker:6s}: {format_size(size)}")
print()

# ============================================================================
# 4. ANALISIS TICKS (SAMPLE)
# ============================================================================
print("4. ANALIZANDO ESTADISTICAS DE TICKS (SAMPLE 100 archivos)...")
print("-" * 80)

sample_size = min(100, len(trades_files))
sample_files = random.sample(trades_files, sample_size)

tick_stats = []
for tf in sample_files:
    try:
        df = pl.read_parquet(tf)
        ticker = tf.parent.parent.name
        date = tf.parent.name.split('=')[1]

        tick_stats.append({
            'ticker': ticker,
            'date': date,
            'ticks': len(df),
            'file_size': get_file_size(tf)
        })
    except:
        continue

ticks_df = pl.DataFrame(tick_stats)
ticks_pd = ticks_df.to_pandas()

print(f"\nArchivos analizados: {len(ticks_df)}")
print(f"Total ticks (sample): {ticks_df['ticks'].sum():,}")
print(f"\nEstadisticas de ticks por dia:")
print(f"  Minimo: {ticks_pd['ticks'].min():,}")
print(f"  Maximo: {ticks_pd['ticks'].max():,}")
print(f"  Media: {ticks_pd['ticks'].mean():,.0f}")
print(f"  Mediana: {ticks_pd['ticks'].median():,.0f}")

# Proyectar total de ticks
if len(success_files) > 0:
    avg_ticks_per_day = ticks_pd['ticks'].mean()
    projected_total_ticks = int(avg_ticks_per_day * len(success_files))
    print(f"\nPROYECCION TOTAL TICKS: ~{projected_total_ticks:,} ({projected_total_ticks/1e6:.0f}M ticks)")
print()

# ============================================================================
# 5. VERIFICACION EVENT WINDOWS (5 TICKERS RANDOM)
# ============================================================================
print("5. VERIFICACION DETALLADA DE EVENT WINDOWS (5 TICKERS RANDOM)")
print("=" * 80)

tickers_with_e0 = e0_df['ticker'].unique().to_list()
random_tickers = random.sample(tickers_with_e0, min(5, len(tickers_with_e0)))

for ticker in random_tickers:
    print(f"\n{'='*80}")
    print(f"TICKER: {ticker}")
    print(f"{'='*80}")

    # Obtener eventos E0
    ticker_e0 = e0_df.filter(pl.col('ticker') == ticker).sort('trading_day')
    print(f"\nEventos E0: {len(ticker_e0)}")

    # Verificar archivos descargados
    ticker_dir = trades_dir / ticker
    if not ticker_dir.exists():
        print(f"WARNING: Directorio {ticker} no existe!")
        continue

    downloaded_dates = []
    for date_dir in sorted(ticker_dir.glob('date=*')):
        if (date_dir / '_SUCCESS').exists():
            downloaded_dates.append(date_dir.name.split('=')[1])

    print(f"Dias descargados: {len(downloaded_dates)}")

    # Verificar primeros 3 eventos E0
    for i, row in enumerate(ticker_e0.head(3).iter_rows(named=True)):
        event_date = row['trading_day']
        print(f"\n  Evento E0 #{i+1}: {event_date}")
        print(f"    RVOL={row['rvol30']:.2f}, %chg={row['pctchg_d']:.2%}")

        # Calcular ventana esperada (+-1 dia)
        event_dt = datetime.strptime(event_date, '%Y-%m-%d')
        expected_dates = [
            (event_dt - timedelta(days=1)).strftime('%Y-%m-%d'),
            event_date,
            (event_dt + timedelta(days=1)).strftime('%Y-%m-%d')
        ]

        print(f"    Ventana esperada (+-1 dia): {expected_dates}")

        # Verificar cada dia
        for exp_date in expected_dates:
            if exp_date in downloaded_dates:
                trades_file = ticker_dir / f"date={exp_date}" / "trades.parquet"
                if trades_file.exists():
                    try:
                        df_ticks = pl.read_parquet(trades_file)
                        tick_count = len(df_ticks)

                        if tick_count > 0:
                            min_ts = df_ticks['t'].min()
                            max_ts = df_ticks['t'].max()
                            min_date = min_ts.strftime('%Y-%m-%d')
                            max_date = max_ts.strftime('%Y-%m-%d')

                            if min_date == exp_date and max_date == exp_date:
                                status = "OK"
                            else:
                                status = f"RANGE ISSUE: {min_date} -> {max_date}"

                            print(f"      {exp_date}: {status} - {tick_count:,} ticks")
                            print(f"                Rango: {min_ts:%H:%M:%S} -> {max_ts:%H:%M:%S}")
                        else:
                            print(f"      {exp_date}: EMPTY FILE (0 ticks)")
                    except Exception as e:
                        print(f"      {exp_date}: ERROR leyendo: {e}")
            else:
                print(f"      {exp_date}: NO DESCARGADO")

print(f"\n{'='*80}")

# ============================================================================
# 6. INTEGRIDAD
# ============================================================================
print("\n6. VERIFICANDO INTEGRIDAD...")
print("-" * 80)

success_set = set()
for sf in success_files:
    ticker = sf.parent.parent.name
    date = sf.parent.name.split('=')[1]
    success_set.add((ticker, date))

trades_set = set()
for tf in trades_files:
    ticker = tf.parent.parent.name
    date = tf.parent.name.split('=')[1]
    trades_set.add((ticker, date))

missing_trades = success_set - trades_set
missing_success = trades_set - success_set

print(f"\nTotal _SUCCESS: {len(success_set):,}")
print(f"Total trades.parquet: {len(trades_set):,}")
print(f"Archivos con _SUCCESS pero sin trades.parquet: {len(missing_trades)}")
print(f"Archivos con trades.parquet pero sin _SUCCESS: {len(missing_success)}")

if len(missing_trades) == 0 and len(missing_success) == 0:
    print("\nINTEGRIDAD: Perfecta correspondencia entre _SUCCESS y trades.parquet")
print()

# ============================================================================
# RESUMEN FINAL
# ============================================================================
print("="*80)
print("RESUMEN FINAL - PASO 5: DESCARGA TICKS E0")
print("="*80)
print()
print("EVENTOS E0:")
print(f"  Total eventos: {len(e0_df):,}")
print(f"  Tickers unicos: {e0_df['ticker'].n_unique():,}")
print(f"  Dias con E0: {e0_df['trading_day'].n_unique():,}")
print()
print("DESCARGA:")
print(f"  Dias objetivo: {target_days:,}")
print(f"  Dias completados: {len(success_files):,}")
print(f"  Cobertura: {coverage_pct:.1f}%")
print()
print("TAMANO:")
print(f"  Total descargado: {total_gb:.2f} GB")
print(f"  Proyeccion 100%: ~{projected_gb:.2f} GB")
print(f"  vs. Estimacion: 2,600 GB ({((projected_gb - 2600) / 2600) * 100:+.1f}%)")
print()
print("TICKS:")
if len(ticks_pd) > 0:
    print(f"  Media ticks/dia: {ticks_pd['ticks'].mean():,.0f}")
    print(f"  Mediana ticks/dia: {ticks_pd['ticks'].median():,.0f}")
    print(f"  Total proyectado: ~{projected_total_ticks/1e6:.0f}M ticks")
print()
print("INTEGRIDAD:")
if len(missing_trades) == 0 and len(missing_success) == 0:
    print("  PERFECTO: 100% correspondencia")
else:
    print(f"  Issues: {len(missing_trades) + len(missing_success)}")
print()
print("="*80)
print(f"Analisis completado: {datetime.now():%Y-%m-%d %H:%M:%S}")
print("="*80)
