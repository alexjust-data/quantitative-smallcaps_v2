#!/usr/bin/env python3
"""
Analiza por que solo se descargo el 82.2% de los dias objetivo.
Identifica patrones en los dias faltantes.
"""
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import polars as pl

def is_weekend(date_str: str) -> bool:
    """Verifica si una fecha es fin de semana."""
    dt = datetime.strptime(date_str, '%Y-%m-%d')
    return dt.weekday() >= 5  # 5=sabado, 6=domingo

def get_us_holidays_2004_2025() -> set:
    """
    Retorna conjunto de dias festivos del NYSE 2004-2025.
    Lista simplificada de festivos principales.
    """
    holidays = set()

    # Festivos fijos conocidos (lista parcial)
    fixed_holidays = {
        '2020-01-01', '2020-01-20', '2020-02-17', '2020-04-10', '2020-05-25',
        '2020-07-03', '2020-09-07', '2020-11-26', '2020-12-25',
        '2021-01-01', '2021-01-18', '2021-02-15', '2021-04-02', '2021-05-31',
        '2021-07-05', '2021-09-06', '2021-11-25', '2021-12-24',
        '2022-01-17', '2022-02-21', '2022-04-15', '2022-05-30', '2022-06-20',
        '2022-07-04', '2022-09-05', '2022-11-24', '2022-12-26',
        '2023-01-02', '2023-01-16', '2023-02-20', '2023-04-07', '2023-05-29',
        '2023-06-19', '2023-07-04', '2023-09-04', '2023-11-23', '2023-12-25',
        '2024-01-01', '2024-01-15', '2024-02-19', '2024-03-29', '2024-05-27',
        '2024-06-19', '2024-07-04', '2024-09-02', '2024-11-28', '2024-12-25',
        '2025-01-01', '2025-01-20', '2025-02-17', '2025-04-18', '2025-05-26',
        '2025-06-19', '2025-07-04', '2025-09-01', '2025-11-27', '2025-12-25',
    }

    holidays.update(fixed_holidays)
    return holidays

def analyze_missing_days():
    """Analiza los dias faltantes en la descarga."""

    print("=" * 80)
    print("ANALISIS DE DIAS FALTANTES (17.8% missing)")
    print("=" * 80)
    print()

    trades_dir = Path('raw/polygon/trades')
    watchlists_dir = Path('processed/universe/info_rich/daily')

    # =====================================================================
    # 1. CARGAR EVENTOS E0 Y EXPANDIR CON EVENT-WINDOW=1
    # =====================================================================
    print("1. CARGANDO EVENTOS E0 Y EXPANDIENDO VENTANAS...")
    print("-" * 80)

    watchlist_files = list(watchlists_dir.glob('date=*/watchlist.parquet'))
    print(f"Watchlists encontrados: {len(watchlist_files):,}")

    # Diccionario: ticker -> set(fechas esperadas)
    expected_days = defaultdict(set)
    e0_event_count = 0

    holidays = get_us_holidays_2004_2025()

    for wf in watchlist_files:
        try:
            df = pl.read_parquet(wf)
            e0_events = df.filter(pl.col('info_rich') == True)

            if len(e0_events) == 0:
                continue

            # Extraer fecha del evento
            date_str = wf.parent.name.split('=')[1]
            event_date = datetime.strptime(date_str, '%Y-%m-%d')
            e0_event_count += len(e0_events)

            # Expandir con event-window=1 (+-1 dia)
            for ticker in e0_events['ticker'].to_list():
                for offset in range(-1, 2):  # -1, 0, +1
                    expanded_date = event_date + timedelta(days=offset)
                    expanded_str = expanded_date.strftime('%Y-%m-%d')

                    # Solo agregar si no es fin de semana ni festivo
                    if not is_weekend(expanded_str) and expanded_str not in holidays:
                        expected_days[ticker].add(expanded_str)

        except Exception as e:
            print(f"Error leyendo {wf}: {e}")

    # Calcular total esperado
    total_expected = sum(len(dates) for dates in expected_days.values())

    print(f"Eventos E0: {e0_event_count:,}")
    print(f"Tickers unicos: {len(expected_days):,}")
    print(f"Dias esperados (sin weekends/holidays): {total_expected:,}")
    print()

    # =====================================================================
    # 2. CONTAR DIAS DESCARGADOS
    # =====================================================================
    print("2. CONTANDO DIAS DESCARGADOS...")
    print("-" * 80)

    # Diccionario: ticker -> set(fechas descargadas)
    downloaded_days = defaultdict(set)

    ticker_dirs = [d for d in trades_dir.iterdir() if d.is_dir()]

    for ticker_dir in ticker_dirs:
        ticker = ticker_dir.name
        for date_dir in ticker_dir.glob('date=*'):
            if (date_dir / '_SUCCESS').exists():
                date_str = date_dir.name.split('=')[1]
                downloaded_days[ticker].add(date_str)

    total_downloaded = sum(len(dates) for dates in downloaded_days.values())

    print(f"Tickers con descargas: {len(downloaded_days):,}")
    print(f"Dias descargados: {total_downloaded:,}")
    print()

    # =====================================================================
    # 3. CALCULAR DIAS FALTANTES
    # =====================================================================
    print("3. CALCULANDO DIAS FALTANTES...")
    print("-" * 80)

    missing_by_ticker = {}
    missing_dates = []

    for ticker, expected_dates in expected_days.items():
        downloaded_dates = downloaded_days.get(ticker, set())
        missing = expected_dates - downloaded_dates

        if missing:
            missing_by_ticker[ticker] = missing
            for date_str in missing:
                missing_dates.append({
                    'ticker': ticker,
                    'date': date_str,
                    'year': date_str[:4]
                })

    total_missing = sum(len(dates) for dates in missing_by_ticker.values())

    print(f"Dias faltantes: {total_missing:,}")
    print(f"Tickers con dias faltantes: {len(missing_by_ticker):,}")
    print()

    # Progreso
    progress = (total_downloaded / total_expected) * 100 if total_expected > 0 else 0
    print(f"PROGRESO REAL: {progress:.1f}%")
    print(f"  Esperados: {total_expected:,}")
    print(f"  Descargados: {total_downloaded:,}")
    print(f"  Faltantes: {total_missing:,}")
    print()

    # =====================================================================
    # 4. ANALIZAR PATRONES DE DIAS FALTANTES
    # =====================================================================
    print("4. PATRONES EN DIAS FALTANTES")
    print("-" * 80)

    if missing_dates:
        missing_df = pl.DataFrame(missing_dates)

        # Por ano
        print("Dias faltantes por ano:")
        missing_by_year = missing_df.group_by('year').count().sort('year')
        for row in missing_by_year.iter_rows(named=True):
            print(f"  {row['year']}: {row['count']:,}")
        print()

        # TOP 20 tickers con mas dias faltantes
        print("TOP 20 tickers con mas dias faltantes:")
        ticker_missing_counts = Counter()
        for ticker, dates in missing_by_ticker.items():
            ticker_missing_counts[ticker] = len(dates)

        for i, (ticker, count) in enumerate(ticker_missing_counts.most_common(20), 1):
            pct = (count / len(expected_days[ticker])) * 100
            print(f"  {i:2d}. {ticker:6s}: {count:3d} dias faltantes ({pct:.1f}% de sus eventos)")
        print()

        # Sample de fechas faltantes
        print("Sample de fechas faltantes (primeras 20):")
        for i, row in enumerate(missing_df.head(20).iter_rows(named=True), 1):
            print(f"  {i:2d}. {row['ticker']:6s} @ {row['date']}")

    print()

    # =====================================================================
    # 5. VERIFICAR SI FALTAN DIAS POR POLYGON API
    # =====================================================================
    print("5. DIAGNOSTICO DE CAUSAS POSIBLES")
    print("-" * 80)

    # Verificar si hay tickers sin ningun dato descargado
    tickers_sin_datos = set(expected_days.keys()) - set(downloaded_days.keys())

    if tickers_sin_datos:
        print(f"Tickers sin NINGUN dato descargado: {len(tickers_sin_datos)}")
        print("Sample (primeros 20):")
        for i, ticker in enumerate(sorted(tickers_sin_datos)[:20], 1):
            expected_count = len(expected_days[ticker])
            print(f"  {i:2d}. {ticker:6s}: {expected_count} dias esperados, 0 descargados")
        print()

    # Verificar tickers con descarga parcial
    tickers_parciales = [t for t in missing_by_ticker.keys() if t in downloaded_days]

    if tickers_parciales:
        print(f"Tickers con descarga PARCIAL: {len(tickers_parciales)}")
        print("Sample (primeros 10):")
        for i, ticker in enumerate(sorted(tickers_parciales)[:10], 1):
            expected_count = len(expected_days[ticker])
            downloaded_count = len(downloaded_days[ticker])
            missing_count = len(missing_by_ticker[ticker])
            pct = (downloaded_count / expected_count) * 100
            print(f"  {i:2d}. {ticker:6s}: {downloaded_count}/{expected_count} ({pct:.1f}%), faltan {missing_count}")
        print()

    # Posibles causas
    print("POSIBLES CAUSAS DE DIAS FALTANTES:")
    print("  1. Polygon API no tiene datos para esos dias (ticker muy pequeno)")
    print("  2. Ticker no existia en esa fecha (IPO posterior)")
    print("  3. Ticker inactivo/delisted en esa fecha")
    print("  4. Errores de red/timeout durante descarga (si script se interrumpio)")
    print("  5. Dias de bajo volumen sin trades registrados")
    print()

    # =====================================================================
    # 6. COMPARACION CON TARGET ORIGINAL
    # =====================================================================
    print("6. COMPARACION CON TARGET ORIGINAL")
    print("-" * 80)

    original_target = 82_012  # Segun PASO 5
    difference = original_target - total_expected

    print(f"Target original (con weekends/holidays): {original_target:,}")
    print(f"Target ajustado (sin weekends/holidays): {total_expected:,}")
    print(f"Diferencia: {difference:,} ({(difference/original_target)*100:.1f}%)")
    print()
    print("NOTA: La diferencia se debe a que el target original incluia")
    print("      weekends y festivos que no son dias de trading.")
    print()

    print("=" * 80)
    print("FIN DE ANALISIS")
    print("=" * 80)

if __name__ == '__main__':
    analyze_missing_days()
