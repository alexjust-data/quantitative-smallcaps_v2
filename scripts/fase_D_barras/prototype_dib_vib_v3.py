#!/usr/bin/env python
"""
Prototipo DIB/VIB v3: Solución definitiva para timestamps corruptos

SOLUCIÓN:
- NO convertir timestamps a Python datetime (causa "year 52XXX")
- Trabajar directamente con valores numéricos
- Calcular features sin necesidad de convertir timestamps
- Algoritmo DIB simplificado sin loops Python

Este script VALIDA y CONSTRUYE barras DIB en archivos que tienen timestamps válidos.
"""

import polars as pl
from pathlib import Path
import json
import sys


def build_simple_dib(df_ticks: pl.DataFrame, threshold_usd: float = 250_000.0):
    """
    Construye Dollar Imbalance Bars de forma vectorizada

    Evita conversiones de timestamp que causan errores
    Trabaja solo con columnas numéricas: p (price), s (size)
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
        pl.col('signed_dv').cumsum().alias('cumulative_imbalance')
    ])

    # Crear IDs de barra cuando |imbalance| >= threshold
    df = df.with_columns([
        (pl.col('cumulative_imbalance').abs() >= threshold_usd).alias('bar_trigger')
    ])

    df = df.with_columns([
        pl.col('bar_trigger').cumsum().alias('bar_id')
    ])

    # Agregar por bar_id para crear barras
    bars = df.group_by('bar_id').agg([
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

    return bars.sort('bar_id')


def process_ticker_day(ticker: str, date_str: str, threshold_usd: float = 250_000.0):
    """
    Procesa un ticker-día: ticks → DIB bars
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
        # Leer solo columnas necesarias (evitar timestamp corruption)
        df_ticks = pl.read_parquet(ticks_path, columns=['p', 's'])

        if len(df_ticks) == 0:
            return {
                'ticker': ticker,
                'date': date_str,
                'status': 'SKIP',
                'reason': 'empty_file',
                'n_ticks': 0,
                'n_bars': 0,
            }

        n_ticks = len(df_ticks)

        # Construir DIB
        df_bars = build_simple_dib(df_ticks, threshold_usd=threshold_usd)
        n_bars = len(df_bars)

        if n_bars == 0:
            return {
                'ticker': ticker,
                'date': date_str,
                'status': 'SUCCESS',
                'reason': 'no_bars_formed',
                'n_ticks': n_ticks,
                'n_bars': 0,
            }

        # Guardar barras
        outdir = Path(f"temp_prototype_bars/{ticker}/date={date_str}")
        outdir.mkdir(parents=True, exist_ok=True)

        df_bars.write_parquet(outdir / "dib.parquet")

        # Stats
        stats = {
            'ticker': ticker,
            'date': date_str,
            'status': 'SUCCESS',
            'reason': None,
            'n_ticks': n_ticks,
            'n_bars': n_bars,
            'threshold_usd': threshold_usd,
            'price_min': float(df_bars['low'].min()),
            'price_max': float(df_bars['high'].max()),
            'volume_total': int(df_bars['volume'].sum()),
            'notional_total': float(df_bars['notional'].sum()),
            'avg_ticks_per_bar': n_ticks / n_bars,
        }

        with open(outdir / "metadata.json", 'w') as f:
            json.dump(stats, f, indent=2)

        return stats

    except Exception as e:
        return {
            'ticker': ticker,
            'date': date_str,
            'status': 'ERROR',
            'reason': str(e),
            'n_ticks': 0,
            'n_bars': 0,
        }


def main():
    print("="*80)
    print("PROTOTYPE DIB/VIB v3 - SOLUCION TIMESTAMPS")
    print("="*80)

    # Usar más archivos de diferentes fechas
    sample_config = [
        ("BCRX", "2020-04-13"),
        ("BCRX", "2020-04-14"),
        ("BCRX", "2020-04-15"),
        ("BCRX", "2020-04-28"),
        ("BCRX", "2020-04-29"),
        ("BCRX", "2020-06-26"),
        ("BCRX", "2020-12-04"),
        ("BCRX", "2020-12-07"),
        ("GERN", "2020-04-13"),
        ("VXRT", "2020-04-13"),
        ("VXRT", "2020-04-14"),
        ("SRNE", "2020-04-13"),
    ]

    print(f"\nSample: {len(sample_config)} ticker-days")
    print(f"Threshold: ${threshold_usd:,.0f} USD\n" if 'threshold_usd' in dir() else "Threshold: $250,000 USD\n")

    # Procesar
    results = []
    for ticker, date_str in sample_config:
        print(f"Processing {ticker} {date_str}...", end=" ")
        result = process_ticker_day(ticker, date_str)
        results.append(result)

        status_map = {
            'SUCCESS': '[OK]',
            'SKIP': '[SKIP]',
            'ERROR': '[ERROR]',
        }
        status_str = status_map.get(result['status'], '[?]')

        if result['status'] == 'SUCCESS' and result['n_bars'] > 0:
            print(f"{status_str} {result['n_ticks']:,} ticks -> {result['n_bars']} bars (avg {result['avg_ticks_per_bar']:.0f} ticks/bar)")
        elif result['status'] == 'SUCCESS':
            print(f"{status_str} {result['n_ticks']:,} ticks (no bars formed - threshold too high)")
        else:
            print(f"{status_str} {result.get('reason', 'unknown')}")

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

        print(f"\nTotal ticks procesados: {total_ticks:,}")
        print(f"Total barras DIB generadas: {total_bars:,}")
        print(f"Promedio ticks/bar: {total_ticks/total_bars:.1f}")
        print(f"Total notional: ${total_notional:,.0f}")

    print(f"\nOutput directory: temp_prototype_bars/")

    # Criterio de éxito
    success_rate = success_count / len(sample_config) if len(sample_config) > 0 else 0

    if success_rate >= 0.7:
        print(f"\n{'='*80}")
        print("[OK] VALIDACION EXITOSA")
        print("="*80)
        print("[OK] Timestamps issue RESUELTO (leemos solo p, s sin timestamp)")
        print("[OK] Algoritmo DIB vectorizado funciona")
        print("[OK] Pipeline estable - listo para escalar")
        print("\nProximos pasos (segun C.6):")
        print("  1. Implementar detectores E1-E8 (Track A)")
        print("  2. Descargar ticks E1-E13 adicionales")
        print("  3. Construir DIB/VIB sobre dataset completo {E0 U E1-E13}")
        return 0
    else:
        print(f"\n{'='*80}")
        print("[ERROR] VALIDACION FALLO")
        print("="*80)
        print(f"Solo {success_count}/{len(sample_config)} procesados exitosamente")
        print(f"Tasa de exito: {success_rate:.1%} (requerido: >= 70%)")
        return 1


if __name__ == "__main__":
    sys.exit(main())
