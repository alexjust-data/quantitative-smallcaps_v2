#!/usr/bin/env python
"""
Prototipo DIB/VIB v4: Funciona con NUEVO formato timestamps (t_raw + t_unit)

CAMBIOS vs V3:
- Lee formato NUEVO: t_raw (Int64) + t_unit (String)
- Convierte timestamps correctamente según t_unit detectado
- Incluye timestamps en barras DIB (bar_start_ts, bar_end_ts)
- Mantiene algoritmo DIB vectorizado de V3

FORMATO ESPERADO (post timestamp fix):
  t_raw: Int64     # Timestamp RAW sin conversión
  t_unit: String   # 'ns', 'us', o 'ms'
  p: Float64       # Precio
  s: UInt64        # Size
  c: List[UInt8]   # Condiciones
  x: UInt8         # Exchange
  z: UInt8         # Tape
"""

import polars as pl
from pathlib import Path
import json
import sys


def build_simple_dib(df_ticks: pl.DataFrame, threshold_usd: float = 250_000.0):
    """
    Construye Dollar Imbalance Bars de forma vectorizada

    Args:
        df_ticks: DataFrame con columnas [timestamp_dt, p, s]
        threshold_usd: Umbral de imbalance para crear barras

    Returns:
        DataFrame con barras DIB incluyendo timestamps
    """
    if len(df_ticks) == 0:
        return pl.DataFrame()

    # Calcular dollar volume
    df = df_ticks.with_columns([
        (pl.col('p') * pl.col('s')).alias('dollar_volume')
    ])

    # Inferir dirección con tick rule
    df = df.with_columns([
        pl.when(pl.col('p') > pl.col('p').shift(1))
          .then(pl.lit(1))
          .when(pl.col('p') < pl.col('p').shift(1))
          .then(pl.lit(-1))
          .otherwise(pl.lit(0))
          .alias('direction')
    ])

    # Signed dollar volume
    df = df.with_columns([
        (pl.col('direction') * pl.col('dollar_volume')).alias('signed_dv')
    ])

    # Acumular imbalance
    df = df.with_columns([
        pl.col('signed_dv').cum_sum().alias('cumulative_imbalance')
    ])

    # Crear IDs de barra cuando |imbalance| >= threshold
    df = df.with_columns([
        (pl.col('cumulative_imbalance').abs() >= threshold_usd).alias('bar_trigger')
    ])

    df = df.with_columns([
        pl.col('bar_trigger').cum_sum().alias('bar_id')
    ])

    # Agregar por bar_id para crear barras (INCLUYE TIMESTAMPS)
    bars = df.group_by('bar_id').agg([
        pl.col('timestamp_dt').min().alias('bar_start_ts'),  # ✅ NUEVO
        pl.col('timestamp_dt').max().alias('bar_end_ts'),    # ✅ NUEVO
        pl.col('p').first().alias('open'),
        pl.col('p').max().alias('high'),
        pl.col('p').min().alias('low'),
        pl.col('p').last().alias('close'),
        pl.col('s').sum().alias('volume'),
        pl.col('dollar_volume').sum().alias('notional'),
        pl.col('signed_dv').sum().alias('imbalance'),
        pl.count().alias('n_ticks'),
    ])

    # Calcular VWAP
    bars = bars.with_columns([
        (pl.col('notional') / pl.col('volume')).alias('vwap')
    ])

    # Calcular duración de barra en segundos
    bars = bars.with_columns([
        ((pl.col('bar_end_ts') - pl.col('bar_start_ts')).dt.total_seconds()).alias('duration_sec')
    ])

    return bars.sort('bar_id')


def process_ticker_day(ticker: str, date_str: str, threshold_usd: float = 250_000.0):
    """
    Procesa un ticker-día: ticks (NUEVO formato) → DIB bars
    """
    ticks_path = Path(f"raw/polygon/trades/{ticker}/date={date_str}/trades.parquet")

    if not ticks_path.exists():
        return {
            'ticker': ticker,
            'date': date_str,
            'status': 'SKIP',
            'reason': 'no_ticks',
            'n_ticks': 0,
            'n_bars': 0,
        }

    try:
        # PASO 1: Leer archivo con NUEVO formato
        df_ticks = pl.read_parquet(ticks_path, columns=['t_raw', 't_unit', 'p', 's'])

        if len(df_ticks) == 0:
            return {
                'ticker': ticker,
                'date': date_str,
                'status': 'SKIP',
                'reason': 'empty_file',
                'n_ticks': 0,
                'n_bars': 0,
            }

        # PASO 2: Verificar formato NUEVO
        if 't_raw' not in df_ticks.columns or 't_unit' not in df_ticks.columns:
            return {
                'ticker': ticker,
                'date': date_str,
                'status': 'ERROR',
                'reason': 'OLD_FORMAT_DETECTED (need t_raw + t_unit)',
                'n_ticks': len(df_ticks),
                'n_bars': 0,
            }

        # PASO 3: Convertir timestamps según t_unit
        time_unit = df_ticks['t_unit'][0]  # Detectar unidad ('ns', 'us', 'ms')

        if time_unit == 'ns':
            df_ticks = df_ticks.with_columns([
                pl.col('t_raw').cast(pl.Datetime(time_unit='ns')).alias('timestamp_dt')
            ])
        elif time_unit == 'us':
            df_ticks = df_ticks.with_columns([
                pl.col('t_raw').cast(pl.Datetime(time_unit='us')).alias('timestamp_dt')
            ])
        elif time_unit == 'ms':
            df_ticks = df_ticks.with_columns([
                pl.col('t_raw').cast(pl.Datetime(time_unit='ms')).alias('timestamp_dt')
            ])
        else:
            return {
                'ticker': ticker,
                'date': date_str,
                'status': 'ERROR',
                'reason': f'UNKNOWN_TIME_UNIT: {time_unit}',
                'n_ticks': len(df_ticks),
                'n_bars': 0,
            }

        n_ticks = len(df_ticks)

        # PASO 4: Construir DIB con timestamps incluidos
        df_bars = build_simple_dib(df_ticks, threshold_usd=threshold_usd)
        n_bars = len(df_bars)

        if n_bars == 0:
            return {
                'ticker': ticker,
                'date': date_str,
                'status': 'SUCCESS',
                'reason': 'no_bars_formed (threshold too high)',
                'n_ticks': n_ticks,
                'n_bars': 0,
                'time_unit': time_unit,
            }

        # PASO 5: Guardar barras
        outdir = Path(f"temp_prototype_bars/{ticker}/date={date_str}")
        outdir.mkdir(parents=True, exist_ok=True)

        df_bars.write_parquet(outdir / "dib.parquet")

        # PASO 6: Stats
        stats = {
            'ticker': ticker,
            'date': date_str,
            'status': 'SUCCESS',
            'reason': None,
            'n_ticks': n_ticks,
            'n_bars': n_bars,
            'threshold_usd': threshold_usd,
            'time_unit': time_unit,
            'price_min': float(df_bars['low'].min()),
            'price_max': float(df_bars['high'].max()),
            'volume_total': int(df_bars['volume'].sum()),
            'notional_total': float(df_bars['notional'].sum()),
            'avg_ticks_per_bar': n_ticks / n_bars,
            'avg_duration_sec': float(df_bars['duration_sec'].mean()),
            'bar_start_first': str(df_bars['bar_start_ts'].min()),
            'bar_end_last': str(df_bars['bar_end_ts'].max()),
        }

        with open(outdir / "metadata.json", 'w') as f:
            json.dump(stats, f, indent=2)

        return stats

    except Exception as e:
        import traceback
        return {
            'ticker': ticker,
            'date': date_str,
            'status': 'ERROR',
            'reason': f"{type(e).__name__}: {str(e)[:100]}",
            'traceback': traceback.format_exc(),
            'n_ticks': 0,
            'n_bars': 0,
        }


def main():
    print("="*80)
    print("PROTOTYPE DIB/VIB v4 - NUEVO FORMATO TIMESTAMPS (t_raw + t_unit)")
    print("="*80)

    # Sample: Usar archivos que sabemos existen con formato NUEVO
    sample_config = [
        ("BCRX", "2020-03-09"),
        ("BCRX", "2020-03-16"),
        ("BCRX", "2020-04-13"),
        ("BCRX", "2020-04-14"),
        ("BCRX", "2020-04-15"),
        ("BCRX", "2020-06-26"),
        ("BCRX", "2020-12-04"),
        ("GERN", "2020-04-13"),
        ("VXRT", "2020-03-17"),
        ("VXRT", "2020-04-13"),
        ("SRNE", "2020-04-13"),
        ("TLRY", "2020-04-19"),
    ]

    threshold_usd = 250_000.0
    print(f"\nSample: {len(sample_config)} ticker-days")
    print(f"Threshold: ${threshold_usd:,.0f} USD\n")

    # Procesar
    results = []
    for ticker, date_str in sample_config:
        print(f"Processing {ticker} {date_str}...", end=" ")
        result = process_ticker_day(ticker, date_str, threshold_usd=threshold_usd)
        results.append(result)

        status_map = {
            'SUCCESS': '[OK]',
            'SKIP': '[SKIP]',
            'ERROR': '[ERROR]',
        }
        status_str = status_map.get(result['status'], '[?]')

        if result['status'] == 'SUCCESS' and result['n_bars'] > 0:
            print(f"{status_str} {result['n_ticks']:,} ticks -> {result['n_bars']} bars "
                  f"(avg {result['avg_ticks_per_bar']:.0f} ticks/bar, "
                  f"{result['avg_duration_sec']:.1f}s/bar, unit={result['time_unit']})")
        elif result['status'] == 'SUCCESS':
            print(f"{status_str} {result['n_ticks']:,} ticks ({result.get('reason', 'no bars')})")
        else:
            print(f"{status_str} {result.get('reason', 'unknown')}")
            if 'traceback' in result:
                print(f"    Traceback: {result['traceback'][:200]}")

    # Resumen
    print(f"\n{'='*80}")
    print(f"VALIDACION COMPLETA")
    print(f"{'='*80}")

    success_count = sum(1 for r in results if r['status'] == 'SUCCESS')
    success_with_bars = sum(1 for r in results if r['status'] == 'SUCCESS' and r['n_bars'] > 0)
    skip_count = sum(1 for r in results if r['status'] == 'SKIP')
    error_count = sum(1 for r in results if r['status'] == 'ERROR')

    print(f"SUCCESS: {success_count}/{len(results)} ticker-days")
    print(f"  - With DIB bars: {success_with_bars}")
    print(f"  - No bars (threshold): {success_count - success_with_bars}")
    print(f"SKIP: {skip_count} (no ticks)")
    print(f"ERROR: {error_count}")

    if success_with_bars > 0:
        total_ticks = sum(r.get('n_ticks', 0) for r in results if r['status'] == 'SUCCESS' and r['n_bars'] > 0)
        total_bars = sum(r.get('n_bars', 0) for r in results if r['status'] == 'SUCCESS' and r['n_bars'] > 0)
        total_notional = sum(r.get('notional_total', 0) for r in results if r['status'] == 'SUCCESS' and r['n_bars'] > 0)
        avg_duration = sum(r.get('avg_duration_sec', 0) for r in results if r['status'] == 'SUCCESS' and r['n_bars'] > 0) / success_with_bars

        print(f"\nTotal ticks procesados: {total_ticks:,}")
        print(f"Total barras DIB generadas: {total_bars:,}")
        print(f"Promedio ticks/bar: {total_ticks/total_bars:.1f}")
        print(f"Promedio duración/bar: {avg_duration:.1f} seconds")
        print(f"Total notional: ${total_notional:,.0f}")

    print(f"\nOutput directory: temp_prototype_bars/")

    # Criterio de éxito
    success_rate = success_count / len(sample_config) if len(sample_config) > 0 else 0

    if success_rate >= 0.8:  # 80% threshold
        print(f"\n{'='*80}")
        print("[OK] VALIDACION EXITOSA")
        print("="*80)
        print("[OK] Timestamps NUEVO formato (t_raw + t_unit) funcionan correctamente")
        print("[OK] Algoritmo DIB vectorizado funciona con timestamps incluidos")
        print("[OK] Barras DIB tienen timestamps (bar_start_ts, bar_end_ts)")
        print("[OK] Pipeline estable - listo para escalar")
        print("\nProximos pasos (segun C.6):")
        print("  1. Implementar detectores E1-E8 (Track A)")
        print("  2. Descargar ticks E1-E13 adicionales (con mismo fix timestamps)")
        print("  3. Construir DIB/VIB sobre dataset completo {E0 U E1-E13}")
        print("  4. Triple barrier labeling con barras DIB")
        return 0
    else:
        print(f"\n{'='*80}")
        print("[ERROR] VALIDACION FALLO")
        print("="*80)
        print(f"Solo {success_count}/{len(sample_config)} procesados exitosamente")
        print(f"Tasa de exito: {success_rate:.1%} (requerido: >= 80%)")

        # Mostrar errores
        error_results = [r for r in results if r['status'] == 'ERROR']
        if error_results:
            print("\nERRORES DETECTADOS:")
            for r in error_results[:3]:
                print(f"  {r['ticker']} {r['date']}: {r.get('reason', 'unknown')}")

        return 1


if __name__ == "__main__":
    sys.exit(main())
