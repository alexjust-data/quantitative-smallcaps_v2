"""
Analiza todos los parquets de daily_cache con estadísticas completas por ticker.

Uso:
    python analyze_all_tickers.py --cache-dir processed/daily_cache
    python analyze_all_tickers.py --cache-dir processed/daily_cache --ticker DOW.WD
    python analyze_all_tickers.py --cache-dir processed/daily_cache --output custom_path.json

Output por defecto: 01_DayBook/fase_01/C_v2_ingesta_tiks_2004_2025/notebooks/stats_daily_cache.json
"""

import polars as pl
from pathlib import Path
import json
from typing import Dict, Any, Optional
from datetime import datetime
import argparse


def analyze_single_parquet(parquet_path: Path, ticker_name: str) -> Dict[str, Any]:
    """Analiza un parquet individual con estadísticas completas."""

    try:
        df = pl.read_parquet(parquet_path)

        if len(df) == 0:
            return {
                'ticker': ticker_name,
                'status': 'empty',
                'error': 'DataFrame vacío'
            }

        # Información básica
        stats = {
            'ticker': ticker_name,
            'status': 'success',
            'path': str(parquet_path),

            # Dimensiones
            'dimensions': {
                'rows': len(df),
                'columns': len(df.columns),
                'column_names': df.columns,
            },

            # Rango temporal
            'temporal': {
                'min_date': str(df['trading_day'].min()),
                'max_date': str(df['trading_day'].max()),
                'total_days': len(df),
                'date_range_calendar': (df['trading_day'].max() - df['trading_day'].min()).days,
            },

            # Estadísticas por columna numérica
            'columns_stats': {},

            # Conteo de NULLs
            'null_counts': {},

            # Valores únicos para columnas categóricas
            'unique_values': {},
        }

        # Calcular años de datos
        years = stats['temporal']['date_range_calendar'] / 365.25
        stats['temporal']['years_covered'] = round(years, 2)

        # Analizar cada columna
        for col in df.columns:
            dtype = str(df[col].dtype)

            # Contar NULLs
            null_count = df[col].null_count()
            null_pct = 100 * null_count / len(df)
            stats['null_counts'][col] = {
                'count': null_count,
                'percentage': round(null_pct, 2)
            }

            # Estadísticas para columnas numéricas
            if df[col].dtype in [pl.Float64, pl.Float32, pl.Int64, pl.Int32, pl.UInt32]:
                try:
                    col_stats = df.select([
                        pl.col(col).min().alias('min'),
                        pl.col(col).max().alias('max'),
                        pl.col(col).mean().alias('mean'),
                        pl.col(col).median().alias('median'),
                        pl.col(col).std().alias('std'),
                        pl.col(col).quantile(0.25).alias('q25'),
                        pl.col(col).quantile(0.75).alias('q75'),
                    ]).to_dicts()[0]

                    # Convertir a tipos nativos de Python para JSON
                    stats['columns_stats'][col] = {
                        k: float(v) if v is not None else None
                        for k, v in col_stats.items()
                    }
                except Exception as e:
                    stats['columns_stats'][col] = {'error': str(e)}

            # Valores únicos para columnas categóricas o booleanas
            if df[col].dtype in [pl.Utf8, pl.Boolean] or col in ['ticker', 'has_gaps']:
                try:
                    unique_vals = df[col].unique().to_list()
                    if len(unique_vals) <= 20:  # Solo si no hay demasiados valores
                        stats['unique_values'][col] = unique_vals
                    else:
                        stats['unique_values'][col] = f'{len(unique_vals)} valores únicos'
                except Exception as e:
                    stats['unique_values'][col] = {'error': str(e)}

        # Estadísticas específicas del dominio
        if 'rvol30' in df.columns:
            rvol_high = df.filter(pl.col('rvol30') >= 2.0).shape[0]
            stats['domain_stats'] = {
                'rvol30_gte_2': {
                    'count': rvol_high,
                    'percentage': round(100 * rvol_high / len(df), 2)
                }
            }

        if 'pctchg_d' in df.columns:
            pctchg_high = df.filter(pl.col('pctchg_d').abs() >= 0.15).shape[0]
            if 'domain_stats' not in stats:
                stats['domain_stats'] = {}
            stats['domain_stats']['pctchg_abs_gte_15pct'] = {
                'count': pctchg_high,
                'percentage': round(100 * pctchg_high / len(df), 2)
            }

        if 'dollar_vol_d' in df.columns:
            dvol_high = df.filter(pl.col('dollar_vol_d') >= 5_000_000).shape[0]
            if 'domain_stats' not in stats:
                stats['domain_stats'] = {}
            stats['domain_stats']['dollar_vol_gte_5M'] = {
                'count': dvol_high,
                'percentage': round(100 * dvol_high / len(df), 2)
            }

        # Calcular E0 days (días que cumplen todos los criterios)
        if all(col in df.columns for col in ['rvol30', 'pctchg_d', 'dollar_vol_d', 'close_d']):
            e0_days = df.filter(
                (pl.col('rvol30') >= 2.0) &
                (pl.col('pctchg_d').abs() >= 0.15) &
                (pl.col('dollar_vol_d') >= 5_000_000) &
                (pl.col('close_d') >= 0.20) &
                (pl.col('close_d') <= 20.0)
            ).shape[0]

            if 'domain_stats' not in stats:
                stats['domain_stats'] = {}
            stats['domain_stats']['e0_days'] = {
                'count': e0_days,
                'percentage': round(100 * e0_days / len(df), 2)
            }

        return stats

    except Exception as e:
        return {
            'ticker': ticker_name,
            'status': 'error',
            'error': str(e),
            'path': str(parquet_path)
        }


def analyze_all_cache(cache_dir: Path, output_file: Optional[Path] = None) -> Dict[str, Any]:
    """Analiza todos los tickers en el cache."""

    ticker_dirs = [d for d in cache_dir.iterdir() if d.is_dir() and d.name.startswith('ticker=')]

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Encontrados {len(ticker_dirs)} tickers")

    results = {
        'timestamp': datetime.now().isoformat(),
        'cache_dir': str(cache_dir),
        'total_tickers': len(ticker_dirs),
        'tickers': []
    }

    for i, ticker_dir in enumerate(ticker_dirs, 1):
        ticker_name = ticker_dir.name.replace('ticker=', '')
        parquet_path = ticker_dir / 'daily.parquet'

        if not parquet_path.exists():
            results['tickers'].append({
                'ticker': ticker_name,
                'status': 'missing',
                'error': 'Archivo daily.parquet no encontrado'
            })
            continue

        stats = analyze_single_parquet(parquet_path, ticker_name)
        results['tickers'].append(stats)

        if i % 100 == 0:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Procesados {i}/{len(ticker_dirs)} tickers...")

    # Estadísticas globales
    success_tickers = [t for t in results['tickers'] if t['status'] == 'success']
    error_tickers = [t for t in results['tickers'] if t['status'] == 'error']
    empty_tickers = [t for t in results['tickers'] if t['status'] == 'empty']

    results['summary'] = {
        'success': len(success_tickers),
        'error': len(error_tickers),
        'empty': len(empty_tickers),
        'missing': len(ticker_dirs) - len(success_tickers) - len(error_tickers) - len(empty_tickers),
    }

    if success_tickers:
        total_rows = sum(t['dimensions']['rows'] for t in success_tickers)
        total_e0_days = sum(
            t.get('domain_stats', {}).get('e0_days', {}).get('count', 0)
            for t in success_tickers
        )

        results['summary']['total_rows'] = total_rows
        results['summary']['total_e0_days'] = total_e0_days
        results['summary']['avg_rows_per_ticker'] = round(total_rows / len(success_tickers), 1)
        results['summary']['avg_e0_days_per_ticker'] = round(total_e0_days / len(success_tickers), 1)

    if output_file:
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Resultados guardados en {output_file}")

    return results


def print_ticker_analysis(stats: Dict[str, Any], verbose: bool = True):
    """Imprime análisis de un ticker en formato legible."""

    print(f"\n{'='*80}")
    print(f"TICKER: {stats['ticker']}")
    print(f"{'='*80}")

    if stats['status'] != 'success':
        print(f"❌ STATUS: {stats['status']}")
        print(f"ERROR: {stats.get('error', 'N/A')}")
        return

    print(f"✅ STATUS: {stats['status']}")
    print(f"PATH: {stats['path']}")

    # Dimensiones
    print(f"\n📊 DIMENSIONES:")
    print(f"  Filas: {stats['dimensions']['rows']:,}")
    print(f"  Columnas: {stats['dimensions']['columns']}")
    if verbose:
        print(f"  Nombres: {', '.join(stats['dimensions']['column_names'])}")

    # Temporal
    print(f"\n📅 RANGO TEMPORAL:")
    print(f"  Desde: {stats['temporal']['min_date']}")
    print(f"  Hasta: {stats['temporal']['max_date']}")
    print(f"  Días trading: {stats['temporal']['total_days']:,}")
    print(f"  Días calendario: {stats['temporal']['date_range_calendar']:,}")
    print(f"  Años cubiertos: {stats['temporal']['years_covered']}")

    # NULLs
    print(f"\n🔍 VALORES NULL:")
    for col, null_info in stats['null_counts'].items():
        if null_info['count'] > 0:
            print(f"  {col}: {null_info['count']:,} ({null_info['percentage']:.1f}%)")

    # Estadísticas de columnas
    if verbose and stats['columns_stats']:
        print(f"\n📈 ESTADÍSTICAS NUMÉRICAS:")
        for col, col_stats in stats['columns_stats'].items():
            if 'error' in col_stats:
                print(f"  {col}: ERROR - {col_stats['error']}")
                continue

            print(f"  {col}:")
            for stat_name, value in col_stats.items():
                if value is not None:
                    if isinstance(value, float):
                        print(f"    {stat_name}: {value:,.4f}")
                    else:
                        print(f"    {stat_name}: {value}")

    # Valores únicos
    if verbose and stats['unique_values']:
        print(f"\n🏷️  VALORES ÚNICOS:")
        for col, values in stats['unique_values'].items():
            if isinstance(values, list):
                print(f"  {col}: {values}")
            else:
                print(f"  {col}: {values}")

    # Estadísticas de dominio (E0)
    if 'domain_stats' in stats:
        print(f"\n🎯 ESTADÍSTICAS E0 (Info-Rich):")
        for metric, info in stats['domain_stats'].items():
            print(f"  {metric}: {info['count']:,} días ({info['percentage']:.1f}%)")


def main():
    parser = argparse.ArgumentParser(description='Analiza parquets de daily_cache')
    parser.add_argument('--cache-dir', type=str, default='processed/daily_cache',
                        help='Directorio del daily_cache')
    parser.add_argument('--ticker', type=str, default=None,
                        help='Analizar un ticker específico')
    parser.add_argument('--output', type=str,
                        default='01_DayBook/fase_01/C_v2_ingesta_tiks_2004_2025/notebooks/stats_daily_cache.json',
                        help='Archivo JSON de salida para estadísticas globales')
    parser.add_argument('--verbose', action='store_true',
                        help='Mostrar estadísticas detalladas')
    parser.add_argument('--top', type=int, default=None,
                        help='Mostrar solo los top N tickers con más días E0')

    args = parser.parse_args()
    cache_dir = Path(args.cache_dir)

    if not cache_dir.exists():
        print(f"❌ ERROR: Directorio {cache_dir} no existe")
        return

    # Analizar un ticker específico
    if args.ticker:
        ticker_dir = cache_dir / f'ticker={args.ticker}'
        parquet_path = ticker_dir / 'daily.parquet'

        if not parquet_path.exists():
            print(f"❌ ERROR: No se encontró {parquet_path}")
            return

        stats = analyze_single_parquet(parquet_path, args.ticker)
        print_ticker_analysis(stats, verbose=True)
        return

    # Analizar todos los tickers
    results = analyze_all_cache(cache_dir, Path(args.output) if args.output else None)

    # Imprimir resumen
    print(f"\n{'='*80}")
    print(f"RESUMEN GLOBAL")
    print(f"{'='*80}")
    print(f"Total tickers: {results['total_tickers']}")
    print(f"  ✅ Exitosos: {results['summary']['success']}")
    print(f"  ❌ Errores: {results['summary']['error']}")
    print(f"  📭 Vacíos: {results['summary']['empty']}")
    print(f"  ❓ Faltantes: {results['summary']['missing']}")

    if 'total_rows' in results['summary']:
        print(f"\nFilas totales: {results['summary']['total_rows']:,}")
        print(f"Días E0 totales: {results['summary']['total_e0_days']:,}")
        print(f"Promedio filas/ticker: {results['summary']['avg_rows_per_ticker']:.1f}")
        print(f"Promedio días E0/ticker: {results['summary']['avg_e0_days_per_ticker']:.1f}")

    # Mostrar top tickers con más días E0
    if args.top:
        success_tickers = [t for t in results['tickers'] if t['status'] == 'success']
        success_tickers.sort(
            key=lambda t: t.get('domain_stats', {}).get('e0_days', {}).get('count', 0),
            reverse=True
        )

        print(f"\n{'='*80}")
        print(f"TOP {args.top} TICKERS CON MÁS DÍAS E0")
        print(f"{'='*80}")

        for i, ticker_stats in enumerate(success_tickers[:args.top], 1):
            e0_count = ticker_stats.get('domain_stats', {}).get('e0_days', {}).get('count', 0)
            e0_pct = ticker_stats.get('domain_stats', {}).get('e0_days', {}).get('percentage', 0)
            total_days = ticker_stats['dimensions']['rows']

            print(f"{i}. {ticker_stats['ticker']}: {e0_count} días E0 ({e0_pct:.1f}%) de {total_days} total")

    # Mostrar análisis detallado si se solicita
    if args.verbose and not args.top:
        for ticker_stats in results['tickers'][:10]:  # Primeros 10 solo
            print_ticker_analysis(ticker_stats, verbose=True)


if __name__ == '__main__':
    main()
