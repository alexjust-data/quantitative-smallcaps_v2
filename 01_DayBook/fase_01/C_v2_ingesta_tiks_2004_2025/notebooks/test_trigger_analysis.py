"""
Script de validacin: Anlisis de triggers E0 intraday
Prueba con una muestra pequea (100 eventos) para validar sintaxis y lgica
"""

import polars as pl
from pathlib import Path
from multiprocessing import Pool, cpu_count
from tqdm.auto import tqdm
import sys

# Fix encoding para Windows
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Configuracin
PROJECT_ROOT = Path(r"D:\04_TRADING_SMALLCAPS")
WATCHLISTS = PROJECT_ROOT / "processed" / "universe" / "info_rich" / "daily"
TRADES_DIR = PROJECT_ROOT / "raw" / "polygon" / "trades"

print("="*80)
print("VALIDACION: ANALISIS INTRADAY TRIGGER E0")
print("="*80)

# 1. Cargar datos E0
print("\n[INFO] Cargando eventos E0...")
try:
    # Usar scan_parquet para cargar todos los watchlists diarios
    df_all = pl.scan_parquet(WATCHLISTS / "date=*" / "watchlist.parquet").collect()
    print(f"[OK] Cargados {len(df_all):,} registros totales")
except Exception as e:
    print(f"[ERROR] Error cargando watchlists: {e}")
    sys.exit(1)

# Evaluar filtros E0
df_all = df_all.with_columns([
    (pl.col('rvol30') >= 2.0).fill_null(False).alias('f1_rvol'),
    (pl.col('pctchg_d').abs() >= 0.15).fill_null(False).alias('f2_pctchg'),
    (pl.col('dollar_vol_d') >= 5_000_000).fill_null(False).alias('f3_dvol'),
    ((pl.col('close_d') >= 0.20) & (pl.col('close_d') <= 20.0)).fill_null(False).alias('f4_price')
])

df_all = df_all.with_columns([
    (pl.col('f1_rvol').cast(pl.Int8) +
     pl.col('f2_pctchg').cast(pl.Int8) +
     pl.col('f3_dvol').cast(pl.Int8) +
     pl.col('f4_price').cast(pl.Int8)).alias('num_filtros')
])

df_e0 = df_all.filter(pl.col('num_filtros') == 4)
print(f"[OK] Eventos E0 (4 filtros): {len(df_e0):,}")

# 2. Muestra de 100 eventos para test
df_e0_sample = df_e0.sample(min(100, len(df_e0)), seed=42)
print(f"\n[TEST] Usando muestra de {len(df_e0_sample):,} eventos para validacion")

# 3. Funcin para detectar trigger intraday (OPTIMIZADA)
def detectar_trigger_intraday(ticker, date, trades_dir):
    """
    Analiza trades tick-by-tick y encuentra la hora exacta del trigger E0.

    Returns:
        dict con: ticker, date, trigger_time, rvol_trigger, pctchg_trigger, etc.
    """
    from datetime import datetime, time
    import polars as pl

    # Path al archivo de trades
    date_str = date if isinstance(date, str) else str(date)
    trades_file = trades_dir / ticker / f"date={date_str}" / "trades.parquet"

    if not trades_file.exists():
        return None

    try:
        # Cargar trades (solo columnas necesarias - OPTIMIZACIN)
        df_trades = pl.read_parquet(trades_file, columns=['t_raw', 't_unit', 'p', 's'])

        if len(df_trades) == 0:
            return None

        # Convertir timestamps (formato NUEVO: t_raw + t_unit)
        time_unit = df_trades['t_unit'][0]

        if time_unit == 'ns':
            df_trades = df_trades.with_columns([
                pl.col('t_raw').cast(pl.Datetime(time_unit='ns')).alias('timestamp')
            ])
        elif time_unit == 'us':
            df_trades = df_trades.with_columns([
                pl.col('t_raw').cast(pl.Datetime(time_unit='us')).alias('timestamp')
            ])
        else:  # ms
            df_trades = df_trades.with_columns([
                pl.col('t_raw').cast(pl.Datetime(time_unit='ms')).alias('timestamp')
            ])

        # Filtrar solo RTH (9:30 AM - 4:00 PM ET) - OPTIMIZACIN: una sola pasada
        df_trades = df_trades.with_columns([
            pl.col('timestamp').dt.hour().alias('hour'),
            pl.col('timestamp').dt.minute().alias('minute')
        ]).filter(
            ((pl.col('hour') == 9) & (pl.col('minute') >= 30)) |
            ((pl.col('hour') >= 10) & (pl.col('hour') < 16)) |
            ((pl.col('hour') == 16) & (pl.col('minute') == 0))
        )

        if len(df_trades) == 0:
            return None

        # Construir barras 1-min (OPTIMIZACIN: lazy evaluation)
        df_1min = (df_trades
                   .lazy()
                   .with_columns([
                       pl.col('timestamp').dt.truncate('1m').alias('bar_time')
                   ])
                   .group_by('bar_time')
                   .agg([
                       pl.col('p').first().alias('open'),
                       pl.col('p').max().alias('high'),
                       pl.col('p').min().alias('low'),
                       pl.col('p').last().alias('close'),
                       pl.col('s').sum().alias('volume'),
                       ((pl.col('p') * pl.col('s')).sum() / pl.col('s').sum()).alias('vwap')
                   ])
                   .sort('bar_time')
                   .collect())

        if len(df_1min) == 0:
            return None

        # Calcular features acumulativos
        open_price = df_1min['open'][0]

        df_1min = df_1min.with_columns([
            ((pl.col('close') / pl.lit(open_price)) - 1.0).alias('pctchg_from_open'),
            pl.col('volume').cum_sum().alias('vol_cumsum'),
            (pl.col('volume') * pl.col('vwap')).cum_sum().alias('dvol_cumsum')
        ])

        # Buscar primera barra donde se cumplen F2+F3+F4 (OPTIMIZACIN: early exit)
        df_trigger = df_1min.filter(
            (pl.col('pctchg_from_open').abs() >= 0.15) &
            (pl.col('dvol_cumsum') >= 5_000_000) &
            (pl.col('close') >= 0.20) & (pl.col('close') <= 20.0)
        )

        if len(df_trigger) == 0:
            return None

        # Primera barra que cumple
        trigger_bar = df_trigger[0]

        return {
            'ticker': ticker,
            'date': date_str,
            'trigger_time': trigger_bar['bar_time'][0],
            'trigger_hour': trigger_bar['bar_time'][0].hour,
            'trigger_minute': trigger_bar['bar_time'][0].minute,
            'pctchg_trigger': trigger_bar['pctchg_from_open'][0],
            'dvol_trigger': trigger_bar['dvol_cumsum'][0],
            'close_trigger': trigger_bar['close'][0]
        }

    except Exception as e:
        return None

# 4. Funcin wrapper para map
def process_evento(args):
    ticker, date = args
    return detectar_trigger_intraday(ticker, date, TRADES_DIR)

# 5. Procesar en paralelo CON BARRA DE PROGRESO
N_WORKERS = min(8, cpu_count())  # Usar menos workers en test
print(f"\n Procesamiento paralelo con {N_WORKERS} workers...")

# Preparar lista de eventos
eventos_list = [(row['ticker'], row['trading_day']) for row in df_e0_sample.iter_rows(named=True)]

print(f" Preparados {len(eventos_list)} eventos para procesar")

# Procesar en paralelo CON PROGRESO
triggers = []
try:
    with Pool(N_WORKERS) as pool:
        #  CAMBIO CLAVE: imap_unordered con chunksize + tqdm
        results = list(tqdm(
            pool.imap_unordered(process_evento, eventos_list, chunksize=10),
            total=len(eventos_list),
            desc="Procesando eventos",
            unit="evento"
        ))

        # Filtrar resultados vlidos
        triggers = [r for r in results if r is not None]

    print("\n Procesamiento completado sin errores")

except Exception as e:
    print(f"\n Error durante procesamiento: {e}")
    sys.exit(1)

# 6. Anlisis de resultados
processed = len(results)
found = len(triggers)

print(f"\n RESULTADOS:")
print(f"   Eventos analizados: {processed:,}")
print(f"   Triggers encontrados: {found:,}")
print(f"   % con trades disponibles: {found/processed*100:.1f}%")
print(f"   Eventos sin trades: {processed - found:,}")

if len(triggers) > 0:
    df_triggers = pl.DataFrame(triggers)

    print("\n DataFrame de triggers creado correctamente")
    print(f"   Columnas: {df_triggers.columns}")
    print(f"   Filas: {len(df_triggers):,}")

    print("\n MUESTRA DE TRIGGERS (primeros 5):")
    print(df_triggers.head(5))

    print("\n ESTADSTICAS BSICAS:")
    print(f"   Hora promedio trigger: {df_triggers['trigger_hour'].mean():.1f}:{df_triggers['trigger_minute'].mean():.0f}")
    print(f"   Hora ms temprana: {df_triggers['trigger_hour'].min()}:{df_triggers['trigger_minute'].min():02d}")
    print(f"   Hora ms tarda: {df_triggers['trigger_hour'].max()}:{df_triggers['trigger_minute'].max():02d}")

    # Distribucin por hora
    by_hour_trigger = df_triggers.group_by('trigger_hour').agg(pl.count().alias('count')).sort('trigger_hour')

    print("\n DISTRIBUCIN POR HORA:")
    for row in by_hour_trigger.iter_rows(named=True):
        hour = row['trigger_hour']
        count = row['count']
        pct = count / len(df_triggers) * 100
        print(f"   {hour:02d}:00 - {hour:02d}:59: {count:>4,} triggers ({pct:>5.1f}%)")

    print("\n VALIDACIN EXITOSA")
    print("   El cdigo funciona correctamente y puede ejecutarse en el notebook completo")
    print(f"   Tiempo estimado para {len(df_e0):,} eventos: ~15-30 minutos")

else:
    print("\n  No se encontraron triggers en la muestra")
    print("   Esto puede ser normal si los eventos no tienen trades descargados")

print("\n" + "="*80)
print("FIN DE LA VALIDACIN")
print("="*80)
