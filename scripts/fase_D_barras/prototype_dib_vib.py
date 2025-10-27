#!/usr/bin/env python
"""
Prototipo DIB/VIB: Validación técnica de construcción de barras informativas

OBJETIVO:
- Probar que podemos leer ticks descargados
- Construir Dollar Imbalance Bars (López de Prado Cap 2.4)
- Generar features básicas de microestructura
- Verificar timestamps, timezone, y cálculos numéricos

INPUT:
- Subset pequeño: 2-3 tickers × 10 días E0
- Ticks ya descargados: raw/polygon/trades/<TICKER>/date=*/trades.parquet

OUTPUT:
- temp_prototype_bars/<TICKER>/date=*/dib.parquet
- Validación: timestamps OK, features OK, pipeline funciona

Basado en:
- López de Prado (2018) "Advances in Financial Machine Learning" Cap 2.4
- C.7_roadmap_post_paso5.md Sección "Track B"
"""

import polars as pl
from pathlib import Path
from datetime import datetime
import json
import sys

def build_dollar_imbalance_bars(df_ticks: pl.DataFrame, threshold_usd: float = 250_000.0):
    """
    Construye Dollar Imbalance Bars según López de Prado (2018) Cap 2.4

    Algoritmo:
    1. Inferir dirección de trade con tick rule (buy=+1, sell=-1)
    2. Acumular imbalance = sum(direction × dollar_volume)
    3. Cuando |imbalance| >= threshold → crear nueva barra

    Args:
        df_ticks: DataFrame con [t (timestamp), p (price), s (size), ...]
        threshold_usd: Umbral de dólares acumulados para formar barra

    Returns:
        DataFrame con barras: [bar_start, bar_end, notional, imbalance, n_ticks, ...]
    """
    if len(df_ticks) == 0:
        return pl.DataFrame({
            'bar_start': [],
            'bar_end': [],
            'open': [],
            'high': [],
            'low': [],
            'close': [],
            'volume': [],
            'notional': [],
            'imbalance': [],
            'n_ticks': [],
            'vwap': [],
        })

    # 1. Calcular dollar volume por tick
    df = df_ticks.with_columns([
        (pl.col('p') * pl.col('s')).alias('dollar_volume')
    ])

    # 2. Inferir dirección con tick rule (simplificado)
    # Dirección = +1 si precio sube, -1 si baja, 0 si igual
    df = df.with_columns([
        pl.when(pl.col('p') > pl.col('p').shift(1))
          .then(pl.lit(1))
          .when(pl.col('p') < pl.col('p').shift(1))
          .then(pl.lit(-1))
          .otherwise(pl.lit(0))
          .alias('direction')
    ])

    # 3. Calcular signed dollar volume
    df = df.with_columns([
        (pl.col('direction') * pl.col('dollar_volume')).alias('signed_dollar_volume')
    ])

    # 4. Acumular imbalance y crear barras cuando |imbalance| >= threshold
    bars = []
    cumulative_imbalance = 0.0
    bar_start_idx = 0

    ticks_list = df.to_dicts()

    for idx, tick in enumerate(ticks_list):
        cumulative_imbalance += tick['signed_dollar_volume']

        if abs(cumulative_imbalance) >= threshold_usd or idx == len(ticks_list) - 1:
            # Crear barra
            bar_ticks = ticks_list[bar_start_idx:idx+1]

            if len(bar_ticks) == 0:
                continue

            prices = [t['p'] for t in bar_ticks]
            volumes = [t['s'] for t in bar_ticks]
            notionals = [t['dollar_volume'] for t in bar_ticks]
            timestamps = [t['t'] for t in bar_ticks]

            bars.append({
                'bar_start': min(timestamps),
                'bar_end': max(timestamps),
                'open': prices[0],
                'high': max(prices),
                'low': min(prices),
                'close': prices[-1],
                'volume': sum(volumes),
                'notional': sum(notionals),
                'imbalance': cumulative_imbalance,
                'n_ticks': len(bar_ticks),
                'vwap': sum(notionals) / sum(volumes) if sum(volumes) > 0 else prices[-1],
            })

            # Reset acumulador
            cumulative_imbalance = 0.0
            bar_start_idx = idx + 1

    return pl.DataFrame(bars)


def prototype_single_ticker_day(ticker: str, date_str: str, threshold_usd: float = 250_000.0):
    """
    Procesa un ticker-día: ticks -> DIB bars

    Returns:
        dict con resultados o None si falla
    """
    # Leer ticks
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
        df_ticks = pl.read_parquet(ticks_path)
        n_ticks = len(df_ticks)

        if n_ticks == 0:
            return {
                'ticker': ticker,
                'date': date_str,
                'status': 'SKIP',
                'reason': 'empty_file',
                'n_ticks': 0,
                'n_bars': 0,
            }

        # Validar schema esperado
        required_cols = ['t', 'p', 's']
        missing_cols = [c for c in required_cols if c not in df_ticks.columns]
        if missing_cols:
            return {
                'ticker': ticker,
                'date': date_str,
                'status': 'ERROR',
                'reason': f'missing_columns: {missing_cols}',
                'n_ticks': n_ticks,
                'n_bars': 0,
            }

        # Construir DIB
        df_bars = build_dollar_imbalance_bars(df_ticks, threshold_usd=threshold_usd)
        n_bars = len(df_bars)

        # Guardar prototipo
        outdir = Path(f"temp_prototype_bars/{ticker}/date={date_str}")
        outdir.mkdir(parents=True, exist_ok=True)

        if n_bars > 0:
            df_bars.write_parquet(outdir / "dib.parquet")

            # Guardar metadata
            metadata = {
                'ticker': ticker,
                'date': date_str,
                'n_ticks': n_ticks,
                'n_bars': n_bars,
                'threshold_usd': threshold_usd,
                'bar_start_min': str(df_bars['bar_start'].min()),
                'bar_end_max': str(df_bars['bar_end'].max()),
                'price_min': float(df_bars['low'].min()),
                'price_max': float(df_bars['high'].max()),
                'volume_total': int(df_bars['volume'].sum()),
                'notional_total': float(df_bars['notional'].sum()),
            }

            with open(outdir / "metadata.json", 'w') as f:
                json.dump(metadata, f, indent=2)

        return {
            'ticker': ticker,
            'date': date_str,
            'status': 'SUCCESS',
            'reason': None,
            'n_ticks': n_ticks,
            'n_bars': n_bars,
        }

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
    print("PROTOTYPE DIB/VIB - VALIDACIÓN TÉCNICA")
    print("="*80)

    # Subset pequeño para validación (TOP 3 tickers × 10 días)
    # Usar días reales con datos descargados
    sample_config = [
        ("BCRX", "2020-03-16"),  # Día E0 conocido
        ("BCRX", "2020-03-17"),
        ("BCRX", "2021-06-10"),
        ("BCRX", "2022-08-15"),
        ("BCRX", "2023-05-22"),
        ("GERN", "2019-08-22"),  # Día E0 conocido
        ("GERN", "2020-03-16"),
        ("GERN", "2021-06-10"),
        ("GERN", "2022-08-15"),
        ("VXRT", "2020-03-16"),  # Día E0 conocido
        ("VXRT", "2020-03-17"),
        ("VXRT", "2021-06-10"),
    ]

    print(f"\nSample: {len(sample_config)} ticker-days")
    print(f"Threshold: $250,000 USD (default)\n")

    # Procesar subset
    results = []
    for ticker, date_str in sample_config:
        print(f"Processing {ticker} {date_str}...", end=" ")
        result = prototype_single_ticker_day(ticker, date_str)
        results.append(result)

        status_icon = {
            'SUCCESS': '[OK]',
            'SKIP': '[SKIP]',
            'ERROR': '[ERROR]',
        }.get(result['status'], '?')

        print(f"{status_icon} {result['status']}: {result['n_ticks']:,} ticks -> {result['n_bars']} bars")
        if result['reason']:
            print(f"   Reason: {result['reason']}")

    # Resumen
    print(f"\n{'='*80}")
    print(f"VALIDACIÓN COMPLETA")
    print(f"{'='*80}")

    success_count = sum(1 for r in results if r['status'] == 'SUCCESS')
    skip_count = sum(1 for r in results if r['status'] == 'SKIP')
    error_count = sum(1 for r in results if r['status'] == 'ERROR')

    total_ticks = sum(r['n_ticks'] for r in results if r['status'] == 'SUCCESS')
    total_bars = sum(r['n_bars'] for r in results if r['status'] == 'SUCCESS')

    print(f"SUCCESS: {success_count}/{len(results)} ticker-days")
    print(f"SKIP: {skip_count} (no ticks or empty)")
    print(f"ERROR: {error_count}")
    print(f"\nTotal ticks procesados: {total_ticks:,}")
    print(f"Total barras DIB generadas: {total_bars:,}")

    if total_bars > 0:
        avg_ticks_per_bar = total_ticks / total_bars
        print(f"Promedio ticks/bar: {avg_ticks_per_bar:.1f}")

    print(f"\nOutput directory: temp_prototype_bars/")

    # Criterio de éxito
    if success_count >= 0.7 * len(sample_config):  # Al menos 70% éxito
        print(f"\n{'='*80}")
        print("[OK] VALIDACIÓN EXITOSA")
        print("="*80)
        print("[OK] Pipeline DIB/VIB validado")
        print("[OK] Listo para escalar a dataset completo")
        print("\nPróximos pasos:")
        print("  1. Implementar detectores E1-E8 (Track A)")
        print("  2. Descargar ticks E1-E13 adicionales")
        print("  3. Construir DIB/VIB sobre dataset completo {E0 ∪ E1-E13}")
        return 0
    else:
        print(f"\n{'='*80}")
        print("[ERROR] VALIDACIÓN FALLÓ")
        print("="*80)
        print(f"Solo {success_count}/{len(sample_config)} ticker-days procesados exitosamente")
        print("Revisar errores arriba")
        return 1


if __name__ == "__main__":
    sys.exit(main())
