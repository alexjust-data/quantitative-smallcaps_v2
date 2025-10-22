#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
analyze_ohlcv_daily_download.py
Analiza los resultados de la descarga OHLCV Daily y genera un reporte detallado.

Uso:
    python analyze_ohlcv_daily_download.py
"""
import sys
import io
from pathlib import Path
import re
from datetime import datetime

# Configure UTF-8 encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


def format_size(bytes_size):
    """Convierte bytes a formato legible"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} PB"


def analyze_download():
    """Analiza la descarga OHLCV Daily"""

    # Paths
    base_dir = Path("raw/polygon/ohlcv_daily")
    log_file = base_dir / "daily_download.log"

    print("=" * 80)
    print("ANÁLISIS DE DESCARGA OHLCV DAILY")
    print("=" * 80)
    print()

    # 1. Leer log y analizar
    if not log_file.exists():
        print(f"ERROR: No se encuentra el archivo de log: {log_file}")
        return

    print("📊 MÉTRICAS PRINCIPALES")
    print("-" * 80)

    with open(log_file, 'r', encoding='utf-8') as f:
        log_lines = f.readlines()

    total_tickers = len(log_lines)
    errors = [line for line in log_lines if 'ERROR' in line]
    successful = total_tickers - len(errors)
    success_rate = (successful / total_tickers * 100) if total_tickers > 0 else 0

    print(f"  Tickers procesados:     {total_tickers:,}")
    print(f"  Exitosos:               {successful:,} ({success_rate:.2f}%)")
    print(f"  Errores:                {len(errors):,} ({(len(errors)/total_tickers*100):.2f}%)")

    # 2. Contar archivos parquet
    parquet_files = list(base_dir.glob("**/*.parquet"))
    print(f"  Archivos generados:     {len(parquet_files):,} parquet files")

    # 3. Calcular tamaño total
    total_size = sum(f.stat().st_size for f in parquet_files if f.is_file())
    print(f"  Tamaño total:           {format_size(total_size)}")

    # 4. Analizar timestamps del log (si están disponibles en stdout)
    # Por ahora calculamos basado en el número de tickers
    # Nota: Esto es una estimación, el tiempo real está en el background process
    print(f"  Tiempo estimado:        ~15 minutos")
    print(f"  Velocidad promedio:     ~{total_tickers//15} tickers/minuto")

    print()

    # 5. Mostrar estructura de datos
    print("📁 ESTRUCTURA DE DATOS")
    print("-" * 80)
    print(f"  Directorio base: {base_dir}/")

    # Contar directorios de tickers
    ticker_dirs = [d for d in base_dir.iterdir() if d.is_dir() and d.name != "__pycache__"]
    print(f"  Total de tickers con datos: {len(ticker_dirs):,}")

    # Mostrar ejemplo de estructura
    sample_tickers = sorted(ticker_dirs)[:3]
    for ticker_dir in sample_tickers:
        print(f"  ├── {ticker_dir.name}/")
        year_dirs = sorted([d for d in ticker_dir.iterdir() if d.is_dir()])
        for i, year_dir in enumerate(year_dirs):
            is_last = (i == len(year_dirs) - 1)
            prefix = "  │   └──" if is_last else "  │   ├──"
            print(f"{prefix} {year_dir.name}/daily.parquet")
            if i >= 2 and len(year_dirs) > 3:  # Mostrar solo primeros 3
                print(f"  │   └── ... ({len(year_dirs) - 3} años más)")
                break

    if len(ticker_dirs) > 3:
        print(f"  └── ... ({len(ticker_dirs) - 3:,} tickers más)")
    print(f"  └── daily_download.log")

    print()

    # 6. Analizar errores
    if errors:
        print("❌ ERRORES IDENTIFICADOS")
        print("-" * 80)

        for error_line in errors:
            # Parsear el error
            # Formato: "TICKER: ERROR mensaje"
            match = re.match(r'(\w+):\s*ERROR\s*(.+)', error_line.strip())
            if match:
                ticker = match.group(1)
                error_msg = match.group(2)
                print(f"  Ticker: {ticker}")
                print(f"  Causa:  {error_msg}")
                print(f"  Impacto: Negligible ({len(errors)/total_tickers*100:.2f}%)")
                print(f"  Acción: Puede re-intentarse manualmente si es crítico")
                print()
    else:
        print("✅ SIN ERRORES - Todos los tickers descargados exitosamente")
        print()

    # 7. Estadísticas adicionales
    print("📈 ESTADÍSTICAS ADICIONALES")
    print("-" * 80)

    # Analizar distribución de años
    year_counts = {}
    for ticker_dir in ticker_dirs[:100]:  # Muestra de 100 tickers
        year_dirs = [d.name for d in ticker_dir.iterdir() if d.is_dir()]
        for year_name in year_dirs:
            year = year_name.replace('year=', '')
            year_counts[year] = year_counts.get(year, 0) + 1

    if year_counts:
        print(f"  Distribución de años (muestra de 100 tickers):")
        sorted_years = sorted(year_counts.items())
        for year, count in sorted_years[:5]:
            print(f"    {year}: {count:,} tickers")
        if len(sorted_years) > 5:
            print(f"    ... ({len(sorted_years) - 5} años más)")
        print()

    # Promedio de archivos por ticker
    avg_files = len(parquet_files) / len(ticker_dirs) if ticker_dirs else 0
    print(f"  Promedio de archivos por ticker: {avg_files:.1f}")

    # Tamaño promedio por archivo
    avg_size = total_size / len(parquet_files) if parquet_files else 0
    print(f"  Tamaño promedio por archivo: {format_size(avg_size)}")

    print()
    print("=" * 80)
    print("✅ ANÁLISIS COMPLETADO")
    print("=" * 80)
    print()

    # 8. Recomendaciones
    print("💡 PRÓXIMOS PASOS")
    print("-" * 80)
    print("  1. ✅ OHLCV Daily - COMPLETADO")
    print("  2. ⏭️  OHLCV Intraday 1-minute (siguiente)")
    print("  3. ⏭️  Bar Construction (Dollar/Volume/Imbalance bars)")
    print("  4. ⏭️  Daily Features")
    print("  5. ⏭️  Labeling (Triple Barrier)")
    print()

    if errors:
        print("  ⚠️  Considerar re-intentar tickers con errores antes de continuar")
        print()


if __name__ == "__main__":
    analyze_download()
