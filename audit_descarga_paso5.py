#!/usr/bin/env python3
"""
Auditoría completa de la descarga PASO 5 (ticks E0).
"""
from pathlib import Path
from datetime import datetime
import polars as pl
from collections import defaultdict

def format_size(bytes_size: int) -> str:
    """Formatea bytes a unidades legibles."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} PB"

def get_file_size(path: Path) -> int:
    """Obtiene tamaño de archivo."""
    try:
        return path.stat().st_size
    except:
        return 0

def audit_downloads():
    """Audita el estado de la descarga de ticks."""

    print("=" * 80)
    print("AUDITORÍA PASO 5: DESCARGA TICKS E0 (2004-2025)")
    print("=" * 80)
    print(f"Timestamp: {datetime.now():%Y-%m-%d %H:%M:%S}")
    print()

    trades_dir = Path('raw/polygon/trades')
    watchlists_dir = Path('processed/universe/info_rich/daily')

    # =====================================================================
    # 1. ANÁLISIS DE WATCHLISTS (EVENTOS E0)
    # =====================================================================
    print("1. ANÁLISIS DE WATCHLISTS E0")
    print("-" * 80)

    watchlist_files = list(watchlists_dir.glob('date=*/watchlist.parquet'))
    print(f"Watchlists totales: {len(watchlist_files):,}")

    total_e0_events = 0
    e0_by_year = defaultdict(int)
    unique_tickers_e0 = set()

    for wf in watchlist_files:
        try:
            df = pl.read_parquet(wf)
            e0_events = df.filter(pl.col('info_rich') == True)
            count = len(e0_events)
            total_e0_events += count

            # Extraer año del path
            date_str = wf.parent.name.split('=')[1]
            year = date_str[:4]
            e0_by_year[year] += count

            # Tickers únicos
            for ticker in e0_events['ticker'].to_list():
                unique_tickers_e0.add(ticker)
        except Exception as e:
            print(f"Error leyendo {wf}: {e}")

    print(f"Eventos E0 totales: {total_e0_events:,}")
    print(f"Tickers únicos con E0: {len(unique_tickers_e0):,}")
    print()

    print("Eventos E0 por año:")
    for year in sorted(e0_by_year.keys()):
        print(f"  {year}: {e0_by_year[year]:,}")
    print()

    # =====================================================================
    # 2. ANÁLISIS DE DESCARGAS COMPLETADAS
    # =====================================================================
    print("2. ANÁLISIS DE DESCARGAS COMPLETADAS")
    print("-" * 80)

    # Contar _SUCCESS files
    success_files = list(trades_dir.rglob('_SUCCESS'))
    completed_days = len(success_files)

    print(f"Días descargados (_SUCCESS): {completed_days:,}")

    # Contar trades.parquet files
    trades_files = list(trades_dir.rglob('trades.parquet'))
    print(f"Archivos trades.parquet: {len(trades_files):,}")

    # Tickers descargados
    ticker_dirs = [d for d in trades_dir.iterdir() if d.is_dir()]
    print(f"Tickers con descargas: {len(ticker_dirs):,}")
    print()

    # =====================================================================
    # 3. ANÁLISIS DE TAMAÑOS
    # =====================================================================
    print("3. ANÁLISIS DE TAMAÑOS")
    print("-" * 80)

    total_size = 0
    file_count = 0
    size_by_ticker = {}

    for ticker_dir in ticker_dirs:
        ticker_size = 0
        for trades_file in ticker_dir.rglob('trades.parquet'):
            size = get_file_size(trades_file)
            ticker_size += size
            total_size += size
            file_count += 1

        if ticker_size > 0:
            size_by_ticker[ticker_dir.name] = ticker_size

    print(f"Tamaño total descargado: {format_size(total_size)}")
    print(f"Archivos procesados: {file_count:,}")

    if completed_days > 0:
        avg_size = total_size / completed_days
        print(f"Tamaño promedio/día: {format_size(avg_size)}")
    print()

    # TOP 10 tickers por tamaño
    print("TOP 10 tickers por tamaño:")
    sorted_tickers = sorted(size_by_ticker.items(), key=lambda x: x[1], reverse=True)[:10]
    for i, (ticker, size) in enumerate(sorted_tickers, 1):
        print(f"  {i:2d}. {ticker:6s}: {format_size(size)}")
    print()

    # =====================================================================
    # 4. PROYECCIÓN FINAL
    # =====================================================================
    print("4. PROYECCIÓN FINAL")
    print("-" * 80)

    # Días objetivo con event-window=1
    # 29,555 eventos E0 × ~2.77 promedio (con ventana ±1 día)
    total_days_target = 82_012  # Según log del script

    progress_pct = (completed_days / total_days_target) * 100
    remaining_days = total_days_target - completed_days

    print(f"Días objetivo: {total_days_target:,}")
    print(f"Días completados: {completed_days:,}")
    print(f"Progreso: {progress_pct:.1f}%")
    print(f"Días restantes: {remaining_days:,}")
    print()

    if completed_days > 0:
        # Proyectar tamaño final
        avg_size_per_day = total_size / completed_days
        projected_total = avg_size_per_day * total_days_target
        projected_gb = projected_total / (1024**3)
        projected_tb = projected_gb / 1024

        remaining_size = projected_total - total_size
        remaining_gb = remaining_size / (1024**3)

        print("TAMAÑO FINAL PROYECTADO:")
        print(f"  Total: {format_size(projected_total)} ({projected_gb:.2f} GB / {projected_tb:.2f} TB)")
        print(f"  Descargado: {format_size(total_size)} ({progress_pct:.1f}%)")
        print(f"  Falta: {format_size(remaining_size)} ({remaining_gb:.2f} GB)")
        print()

        # Comparar con estimación original
        original_estimate_gb = 2_600  # 2.6 TB según C.5
        difference = projected_gb - original_estimate_gb
        difference_pct = (difference / original_estimate_gb) * 100

        print("COMPARACIÓN CON ESTIMACIÓN ORIGINAL:")
        print(f"  Estimación C.5: 2,600 GB (2.6 TB)")
        print(f"  Proyección real: {projected_gb:.0f} GB ({projected_tb:.2f} TB)")
        print(f"  Diferencia: {difference:+,.0f} GB ({difference_pct:+.1f}%)")
        print()

    # =====================================================================
    # 5. ANÁLISIS DE COBERTURA
    # =====================================================================
    print("5. ANÁLISIS DE COBERTURA")
    print("-" * 80)

    # Extraer fechas de los archivos descargados
    downloaded_dates = set()
    downloaded_by_ticker = defaultdict(set)

    for ticker_dir in ticker_dirs[:100]:  # Sample para velocidad
        for date_dir in ticker_dir.glob('date=*'):
            if (date_dir / '_SUCCESS').exists():
                date_str = date_dir.name.split('=')[1]
                downloaded_dates.add(date_str)
                downloaded_by_ticker[ticker_dir.name].add(date_str)

    print(f"Fechas únicas descargadas (sample): {len(downloaded_dates):,}")

    # Tickers con más días descargados (sample)
    if downloaded_by_ticker:
        top_coverage = sorted(downloaded_by_ticker.items(),
                             key=lambda x: len(x[1]), reverse=True)[:10]
        print()
        print("TOP 10 tickers por días descargados (sample):")
        for i, (ticker, dates) in enumerate(top_coverage, 1):
            print(f"  {i:2d}. {ticker:6s}: {len(dates):,} días")

    print()

    # =====================================================================
    # 6. ESTADÍSTICAS DE TICKS
    # =====================================================================
    print("6. ESTADÍSTICAS DE TICKS (SAMPLE)")
    print("-" * 80)

    # Sample de archivos para analizar conteo de ticks
    sample_files = trades_files[:100] if len(trades_files) > 100 else trades_files

    total_ticks_sample = 0
    tick_counts = []

    for trades_file in sample_files[:50]:  # Limitar a 50 para velocidad
        try:
            df = pl.read_parquet(trades_file)
            count = len(df)
            total_ticks_sample += count
            tick_counts.append(count)
        except Exception as e:
            continue

    if tick_counts:
        avg_ticks = sum(tick_counts) / len(tick_counts)
        min_ticks = min(tick_counts)
        max_ticks = max(tick_counts)

        print(f"Archivos analizados: {len(tick_counts)}")
        print(f"Total ticks (sample): {total_ticks_sample:,}")
        print(f"Ticks promedio/día: {avg_ticks:,.0f}")
        print(f"Ticks mín/día: {min_ticks:,}")
        print(f"Ticks máx/día: {max_ticks:,}")

        # Proyectar ticks totales
        if completed_days > 0:
            projected_total_ticks = (total_ticks_sample / len(tick_counts)) * total_days_target
            print(f"Ticks totales proyectados: {projected_total_ticks:,.0f}")

    print()
    print("=" * 80)
    print("FIN DE AUDITORÍA")
    print("=" * 80)

if __name__ == '__main__':
    audit_downloads()
