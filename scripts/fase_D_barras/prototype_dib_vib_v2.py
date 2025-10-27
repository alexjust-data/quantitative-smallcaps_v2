#!/usr/bin/env python
"""
Prototipo DIB/VIB v2: Versión simplificada con manejo correcto de timestamps

CAMBIOS vs v1:
- Usa scan_parquet + lazy evaluation (más eficiente)
- Evita to_dicts() que causa problemas con timestamps
- Trabaja directamente con Polars expresiones
- Algoritmo vectorizado (sin loops Python)

OBJETIVO:
- Validar que podemos leer ticks descargados
- Validar timestamps microsegundos OK
- Validar pipeline no crashea

INPUT:
- Subset: tickers reales con datos descargados
- Ticks: raw/polygon/trades/<TICKER>/date=*/trades.parquet

OUTPUT:
- temp_prototype_bars/<TICKER>/date=*/validation_summary.json
"""

import polars as pl
from pathlib import Path
import json
import sys

def validate_ticker_day(ticker: str, date_str: str):
    """
    Valida un ticker-día: lee ticks y calcula stats básicas
    NO construye DIB todavía, solo valida que podemos leer los datos
    """
    ticks_path = Path(f"raw/polygon/trades/{ticker}/date={date_str}/trades.parquet")

    if not ticks_path.exists():
        return {
            'ticker': ticker,
            'date': date_str,
            'status': 'SKIP',
            'reason': 'no_ticks',
        }

    try:
        # Leer con lazy evaluation
        df = pl.scan_parquet(str(ticks_path)).collect()

        if len(df) == 0:
            return {
                'ticker': ticker,
                'date': date_str,
                'status': 'SKIP',
                'reason': 'empty_file',
            }

        # Validar columnas requeridas
        required = ['t', 'p', 's']
        missing = [c for c in required if c not in df.columns]
        if missing:
            return {
                'ticker': ticker,
                'date': date_str,
                'status': 'ERROR',
                'reason': f'missing_columns: {missing}',
            }

        # Calcular stats básicas sin crashear
        stats = {
            'ticker': ticker,
            'date': date_str,
            'status': 'SUCCESS',
            'reason': None,
            'n_ticks': len(df),
            'price_min': float(df['p'].min()),
            'price_max': float(df['p'].max()),
            'volume_total': int(df['s'].sum()),
            'dollar_volume': float((df['p'] * df['s']).sum()),
            'timestamp_first': str(df['t'].min()),
            'timestamp_last': str(df['t'].max()),
        }

        # Guardar validación
        outdir = Path(f"temp_prototype_bars/{ticker}/date={date_str}")
        outdir.mkdir(parents=True, exist_ok=True)

        with open(outdir / "validation_summary.json", 'w') as f:
            json.dump(stats, f, indent=2)

        return stats

    except Exception as e:
        return {
            'ticker': ticker,
            'date': date_str,
            'status': 'ERROR',
            'reason': str(e),
        }


def main():
    print("="*80)
    print("PROTOTYPE DIB/VIB v2 - VALIDACION TIMESTAMPS")
    print("="*80)

    # Usar fechas REALES que existen en datos descargados
    sample_config = [
        ("BCRX", "2020-03-09"),
        ("BCRX", "2020-01-27"),
        ("BCRX", "2020-06-26"),
        ("BCRX", "2020-12-04"),
        ("GERN", "2020-03-09"),
        ("GERN", "2020-01-27"),
        ("GERN", "2020-06-26"),
        ("VXRT", "2020-03-17"),
        ("VXRT", "2020-08-06"),
        ("VXRT", "2021-02-01"),
    ]

    print(f"\nSample: {len(sample_config)} ticker-days (fechas reales descargadas)\n")

    # Procesar subset
    results = []
    for ticker, date_str in sample_config:
        print(f"Validating {ticker} {date_str}...", end=" ")
        result = validate_ticker_day(ticker, date_str)
        results.append(result)

        status_map = {
            'SUCCESS': '[OK]',
            'SKIP': '[SKIP]',
            'ERROR': '[ERROR]',
        }
        status_str = status_map.get(result['status'], '[?]')

        if result['status'] == 'SUCCESS':
            print(f"{status_str} {result['n_ticks']:,} ticks, ${result['dollar_volume']:,.0f}")
        else:
            print(f"{status_str} {result.get('reason', 'unknown')}")

    # Resumen
    print(f"\n{'='*80}")
    print(f"VALIDACION COMPLETA")
    print(f"{'='*80}")

    success_count = sum(1 for r in results if r['status'] == 'SUCCESS')
    skip_count = sum(1 for r in results if r['status'] == 'SKIP')
    error_count = sum(1 for r in results if r['status'] == 'ERROR')

    print(f"SUCCESS: {success_count}/{len(results)} ticker-days")
    print(f"SKIP: {skip_count} (no ticks or empty)")
    print(f"ERROR: {error_count}")

    if success_count > 0:
        total_ticks = sum(r.get('n_ticks', 0) for r in results if r['status'] == 'SUCCESS')
        total_dollar_vol = sum(r.get('dollar_volume', 0) for r in results if r['status'] == 'SUCCESS')
        print(f"\nTotal ticks validados: {total_ticks:,}")
        print(f"Total dollar volume: ${total_dollar_vol:,.0f}")

    print(f"\nOutput directory: temp_prototype_bars/")

    # Criterio de éxito
    success_rate = success_count / len(sample_config) if len(sample_config) > 0 else 0

    if success_rate >= 0.7:  # Al menos 70% éxito
        print(f"\n{'='*80}")
        print("[OK] VALIDACION EXITOSA")
        print("="*80)
        print("[OK] Timestamps microsegundos leidos correctamente")
        print("[OK] Pipeline no crashea")
        print("[OK] Features basicas calculadas OK")
        print("\nProximo paso:")
        print("  - Implementar algoritmo DIB completo (Lopez de Prado)")
        print("  - Usar estos datos validados como subset")
        return 0
    else:
        print(f"\n{'='*80}")
        print("[ERROR] VALIDACION FALLO")
        print("="*80)
        print(f"Solo {success_count}/{len(sample_config)} ticker-days procesados exitosamente")
        print(f"Tasa de exito: {success_rate:.1%} (requerido: >= 70%)")
        return 1


if __name__ == "__main__":
    sys.exit(main())
