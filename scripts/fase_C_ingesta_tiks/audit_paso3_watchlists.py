#!/usr/bin/env python
"""
Auditoría PASO 3: Watchlists E0 generadas
"""
import polars as pl
from pathlib import Path
import sys

# Cambiar al directorio raíz del proyecto
PROJECT_ROOT = Path(r"D:\04_TRADING_SMALLCAPS")
sys.path.insert(0, str(PROJECT_ROOT))

def audit_daily_cache():
    """Verificar rango de fechas en daily_cache"""
    print("="*80)
    print("AUDITORÍA DAILY CACHE - Rango de Fechas")
    print("="*80)

    cache_dir = PROJECT_ROOT / "processed/daily_cache"

    # Buscar ticker con datos
    all_min = None
    all_max = None
    tickers_checked = 0
    tickers_with_data = 0

    for ticker_dir in list(cache_dir.glob("ticker=*"))[:50]:  # Sample 50 tickers
        parquet_file = ticker_dir / "daily.parquet"
        if not parquet_file.exists():
            continue

        tickers_checked += 1
        df = pl.read_parquet(parquet_file)

        if len(df) == 0:
            continue

        tickers_with_data += 1
        min_date = df["trading_day"].min()
        max_date = df["trading_day"].max()

        if all_min is None or min_date < all_min:
            all_min = min_date
        if all_max is None or max_date > all_max:
            all_max = max_date

    print(f"\nTickers verificados: {tickers_checked}")
    print(f"Tickers con datos: {tickers_with_data}")
    print(f"Fecha mínima (global): {all_min}")
    print(f"Fecha máxima (global): {all_max}")

    # Calcular años cubiertos
    if all_min and all_max:
        years = (all_max - all_min).days / 365.25
        print(f"Años cubiertos: {years:.1f}")

    return all_min, all_max

def audit_watchlists():
    """Verificar watchlists generadas"""
    print("\n" + "="*80)
    print("AUDITORÍA WATCHLISTS E0")
    print("="*80)

    watchlist_dir = PROJECT_ROOT / "processed/universe/info_rich/daily"

    # Contar watchlists
    watchlists = sorted(list(watchlist_dir.glob("date=*/watchlist.parquet")))
    print(f"\nTotal watchlists generadas: {len(watchlists):,}")

    if len(watchlists) == 0:
        print("[ERROR] No se generaron watchlists!")
        return

    # Primera y última fecha
    first_date = watchlists[0].parent.name.replace("date=", "")
    last_date = watchlists[-1].parent.name.replace("date=", "")

    print(f"Primera fecha: {first_date}")
    print(f"Última fecha: {last_date}")

    # Contar ticker-días info-rich
    total_info_rich = 0
    total_tickers_in_watchlists = 0

    print("\nContando ticker-días info-rich...")
    for wl in watchlists:
        df = pl.read_parquet(wl)
        total_tickers_in_watchlists += len(df)
        info_rich_count = df.filter(pl.col("info_rich")).height
        total_info_rich += info_rich_count

    print(f"Total ticker-días en watchlists: {total_tickers_in_watchlists:,}")
    print(f"Total ticker-días info-rich: {total_info_rich:,}")
    print(f"Tasa info-rich: {total_info_rich / total_tickers_in_watchlists * 100:.2f}%")

    # Sample watchlist
    print("\n" + "="*80)
    print("SAMPLE WATCHLIST (última fecha)")
    print("="*80)

    last_wl = pl.read_parquet(watchlists[-1])
    info_rich_sample = last_wl.filter(pl.col("info_rich")).sort("rvol30", descending=True).head(10)

    print(f"\nTickers info-rich en {last_date}: {last_wl.filter(pl.col('info_rich')).height}")
    print("\nTop 10 por RVOL:")
    print(info_rich_sample.select([
        "ticker", "rvol30", "pctchg_d", "dollar_vol_d", "close_d", "market_cap_d"
    ]))

def main():
    print("\n" + "="*80)
    print("AUDITORÍA PASO 3: WATCHLISTS E0 2004-2025")
    print("="*80 + "\n")

    # 1. Verificar rango de fechas en daily_cache
    cache_min, cache_max = audit_daily_cache()

    # 2. Verificar watchlists generadas
    audit_watchlists()

    # 3. Comparar con expectativa
    print("\n" + "="*80)
    print("COMPARACIÓN CON EXPECTATIVA")
    print("="*80)

    print("\nEsperado (según PASO 1 y C.5):")
    print("  - Rango: 2004-01-01 → 2025-10-21")
    print("  - Días trading: ~5,292")
    print("  - Ticker-días info-rich: ~150,000")

    print("\nReal (generado):")
    print(f"  - Rango: {cache_min} → {cache_max}")
    print("  - Días trading: [ver arriba]")
    print("  - Ticker-días info-rich: [ver arriba]")

    if cache_min and str(cache_min) > "2004-01-01":
        print("\n⚠️  [ADVERTENCIA] Daily cache NO cubre 2004-2019")
        print("   Posible causa: OHLCV intraday 1-min solo disponible desde 2020")
        print("   Solución: El daily_cache DEBE generarse desde OHLCV daily (no 1-min) para 2004-2019")

if __name__ == "__main__":
    main()
