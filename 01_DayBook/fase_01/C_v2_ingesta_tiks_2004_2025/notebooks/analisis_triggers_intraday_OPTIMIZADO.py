"""
Análisis de Triggers E0 Intraday - OPTIMIZADO
Ejecuta análisis completo de ~29K eventos con hora exacta del trigger
"""

import polars as pl
import matplotlib.pyplot as plt
from pathlib import Path
from multiprocessing import Pool, cpu_count
from tqdm import tqdm
import warnings
warnings.filterwarnings('ignore')

print("="*80)
print("ANÁLISIS INTRADAY: HORA EXACTA DEL TRIGGER E0")
print("="*80)

# Configuración
PROJECT_ROOT = Path(r"D:\04_TRADING_SMALLCAPS")
WATCHLISTS = PROJECT_ROOT / "processed" / "universe" / "info_rich" / "daily"
TRADES_DIR = PROJECT_ROOT / "raw" / "polygon" / "trades"
OUTPUT_DIR = PROJECT_ROOT / "01_DayBook" / "fase_01" / "C_v2_ingesta_tiks_2004_2025" / "notebooks"

print("\n[PASO 1/4] Cargando eventos E0...")
df_all = pl.scan_parquet(WATCHLISTS / "date=*" / "watchlist.parquet").collect()
print(f"   Cargados {len(df_all):,} registros totales")

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
print(f"   Eventos E0 (4 filtros): {len(df_e0):,}")

# Función optimizada para detectar trigger
def detectar_trigger_intraday(ticker, date, trades_dir):
    """Analiza trades tick-by-tick y encuentra la hora exacta del trigger E0."""
    import polars as pl
    from pathlib import Path

    date_str = date if isinstance(date, str) else str(date)
    trades_file = Path(trades_dir) / ticker / f"date={date_str}" / "trades.parquet"

    if not trades_file.exists():
        return None

    try:
        # Cargar solo columnas necesarias
        df_trades = pl.read_parquet(trades_file, columns=['t_raw', 't_unit', 'p', 's'])

        if len(df_trades) == 0:
            return None

        # Convertir timestamps
        time_unit = df_trades['t_unit'][0]

        if time_unit == 'ns':
            df_trades = df_trades.with_columns([
                pl.col('t_raw').cast(pl.Datetime(time_unit='ns')).alias('timestamp')
            ])
        elif time_unit == 'us':
            df_trades = df_trades.with_columns([
                pl.col('t_raw').cast(pl.Datetime(time_unit='us')).alias('timestamp')
            ])
        else:
            df_trades = df_trades.with_columns([
                pl.col('t_raw').cast(pl.Datetime(time_unit='ms')).alias('timestamp')
            ])

        # Filtrar RTH (9:30-16:00 ET)
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

        # Construir barras 1-min con lazy evaluation
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

        # Buscar primera barra con F2+F3+F4
        df_trigger = df_1min.filter(
            (pl.col('pctchg_from_open').abs() >= 0.15) &
            (pl.col('dvol_cumsum') >= 5_000_000) &
            (pl.col('close') >= 0.20) & (pl.col('close') <= 20.0)
        )

        if len(df_trigger) == 0:
            return None

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

# Procesamiento paralelo
print("\n[PASO 2/4] Procesando eventos en paralelo...")
N_WORKERS = min(16, cpu_count())
print(f"   Workers: {N_WORKERS}")

eventos_list = [(row['ticker'], row['trading_day'], TRADES_DIR) for row in df_e0.iter_rows(named=True)]

def process_evento(args):
    return detectar_trigger_intraday(*args)

if __name__ == '__main__':
    triggers = []
    with Pool(N_WORKERS) as pool:
        results = list(tqdm(
            pool.imap_unordered(process_evento, eventos_list, chunksize=100),
            total=len(eventos_list),
            desc="Analizando triggers",
            unit="evento"
        ))

        triggers = [r for r in results if r is not None]

    processed = len(results)
    found = len(triggers)

    print(f"\n[PASO 3/4] Análisis completado:")
    print(f"   Eventos analizados: {processed:,}")
    print(f"   Triggers encontrados: {found:,}")
    print(f"   % con trades disponibles: {found/processed*100:.1f}%")

    if len(triggers) > 0:
        df_triggers = pl.DataFrame(triggers)

        print("\n[ESTADÍSTICAS]")
        print(f"   Hora promedio trigger: {df_triggers['trigger_hour'].mean():.1f}:{df_triggers['trigger_minute'].mean():.0f}")

        # Distribución por hora
        by_hour_trigger = df_triggers.group_by('trigger_hour').agg(pl.count().alias('count')).sort('trigger_hour')

        print("\n[DISTRIBUCIÓN POR HORA]")
        for row in by_hour_trigger.iter_rows(named=True):
            hour = row['trigger_hour']
            count = row['count']
            pct = count / len(df_triggers) * 100
            print(f"   {hour:02d}:00-{hour:02d}:59: {count:>6,} triggers ({pct:>5.1f}%)")

        # Gráfico
        print("\n[PASO 4/4] Generando gráfico y CSV...")
        fig, ax = plt.subplots(figsize=(14, 6))
        by_hour_pd = by_hour_trigger.to_pandas()

        ax.bar(by_hour_pd['trigger_hour'], by_hour_pd['count'], color='orange', alpha=0.7, edgecolor='black')
        ax.set_xlabel('Hora del Día (ET)', fontsize=12)
        ax.set_ylabel('Número de Triggers E0', fontsize=12)
        ax.set_title(f'Distribución de Triggers E0 por Hora del Día ({len(df_triggers):,} eventos)',
                     fontsize=14, fontweight='bold')
        ax.set_xticks(range(9, 17))
        ax.set_xticklabels([f'{h:02d}:00' for h in range(9, 17)])
        ax.grid(axis='y', alpha=0.3)

        for i, (hour, count) in enumerate(zip(by_hour_pd['trigger_hour'], by_hour_pd['count'])):
            ax.text(hour, count + max(by_hour_pd['count'])*0.01, f'{count:,}',
                    ha='center', va='bottom', fontweight='bold', fontsize=9)

        plt.tight_layout()
        plt.savefig(OUTPUT_DIR / 'e0_triggers_por_hora_COMPLETO.png', dpi=150, bbox_inches='tight')
        print(f"   Gráfico guardado: e0_triggers_por_hora_COMPLETO.png")

        # Exportar CSV
        df_export_triggers = df_triggers.select([
            'ticker',
            'date',
            'trigger_time',
            'trigger_hour',
            'trigger_minute',
            'pctchg_trigger',
            'dvol_trigger',
            'close_trigger'
        ]).sort(['date', 'trigger_time'])

        csv_triggers = OUTPUT_DIR / 'eventos_E0_CON_HORA_EXACTA_COMPLETO_TRADINGVIEW.csv'
        df_export_triggers.write_csv(csv_triggers)

        print(f"   CSV exportado: {csv_triggers.name}")
        print(f"   Total triggers: {len(df_export_triggers):,}")

        best_hour = by_hour_pd.loc[by_hour_pd['count'].idxmax()]
        print(f"\n[RESULTADO CLAVE]")
        print(f"   MEJOR HORA: {best_hour['trigger_hour']:02d}:00 con {best_hour['count']:,} triggers ({best_hour['count']/len(df_triggers)*100:.1f}%)")

        print("\n" + "="*80)
        print("ANÁLISIS COMPLETADO CON ÉXITO")
        print("="*80)
    else:
        print("\n[ERROR] No se encontraron triggers")
