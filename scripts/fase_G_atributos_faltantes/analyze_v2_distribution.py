#!/usr/bin/env python3
"""
Análisis de distribución temporal - Info-rich Universe v2 (2004-2019)

Validaciones:
1. Densidad temporal: eventos por año/mes
2. Top runners: tickers más activos por periodo
3. Sanity checks: simetría %chg, outliers RVOL, crecimiento $vol
"""

import polars as pl
from pathlib import Path
import sys

def analyze_temporal_density(watchlist_root: Path):
    """Analizar densidad temporal de eventos info-rich"""
    print("\n=== DENSIDAD TEMPORAL ===\n")

    events = []
    for parquet in watchlist_root.rglob("watchlist.parquet"):
        date_str = parquet.parent.name.split("=")[1]
        df = pl.read_parquet(parquet)
        events.append({
            "date": date_str,
            "n_tickers": df.height
        })

    if not events:
        print("ERROR: No se encontraron watchlists")
        return None

    df_events = pl.DataFrame(events)
    df_events = df_events.with_columns([
        pl.col("date").str.to_date().alias("date"),
        pl.col("date").str.slice(0, 4).cast(pl.Int32).alias("year"),
        pl.col("date").str.slice(0, 7).alias("year_month")
    ])

    # Por año
    yearly = df_events.group_by("year").agg([
        pl.col("n_tickers").sum().alias("total_events"),
        pl.col("date").count().alias("trading_days"),
        pl.col("n_tickers").mean().alias("avg_per_day"),
        pl.col("n_tickers").median().alias("median_per_day"),
        pl.col("n_tickers").max().alias("max_day")
    ]).sort("year")

    print("Eventos info-rich por año:")
    print(yearly)

    # Top 5 años con más señal
    print("\n\nTop 5 años con más eventos:")
    print(yearly.sort("total_events", descending=True).head(5))

    # Por mes (últimos 24 meses)
    monthly = df_events.group_by("year_month").agg([
        pl.col("n_tickers").sum().alias("total_events"),
        pl.col("n_tickers").mean().alias("avg_per_day")
    ]).sort("year_month", descending=True).head(24)

    print("\n\nÚltimos 24 meses (2018-2019):")
    print(monthly)

    return df_events

def analyze_top_runners(watchlist_root: Path, top_years: list):
    """Identificar top runners por periodo"""
    print("\n\n=== TOP RUNNERS POR PERIODO ===\n")

    for year in top_years:
        year_tickers = []
        for parquet in watchlist_root.rglob("watchlist.parquet"):
            date_str = parquet.parent.name.split("=")[1]
            if not date_str.startswith(str(year)):
                continue

            df = pl.read_parquet(parquet)
            if df.height > 0:
                year_tickers.append(df.with_columns(pl.lit(date_str).alias("date")))

        if not year_tickers:
            print(f"\n{year}: Sin datos")
            continue

        df_year = pl.concat(year_tickers)
        top50 = df_year.group_by("ticker").agg([
            pl.col("date").count().alias("days_info_rich"),
            pl.col("date").max().alias("last_seen")
        ]).sort("days_info_rich", descending=True).head(50)

        print(f"\n{year} - Top 10 tickers más activos:")
        print(top50.head(10))

def sanity_checks(watchlist_root: Path, daily_cache_root: Path):
    """Validaciones de calidad de datos"""
    print("\n\n=== SANITY CHECKS ===\n")

    # Cargar todos los eventos
    all_events = []
    for parquet in watchlist_root.rglob("watchlist.parquet"):
        df = pl.read_parquet(parquet)
        if df.height > 0:
            all_events.append(df)

    if not all_events:
        print("ERROR: No hay eventos para analizar")
        return

    df_all = pl.concat(all_events)

    print(f"Total eventos info-rich: {df_all.height:,}")
    print(f"Tickers únicos: {df_all['ticker'].n_unique():,}")

    # 1. Simetría %chg
    if "pctchg_d" in df_all.columns:
        print("\n1. SIMETRÍA %chg:")
        pctchg_stats = df_all.select([
            pl.col("pctchg_d").min().alias("min"),
            pl.col("pctchg_d").quantile(0.25).alias("p25"),
            pl.col("pctchg_d").median().alias("median"),
            pl.col("pctchg_d").quantile(0.75).alias("p75"),
            pl.col("pctchg_d").max().alias("max"),
            pl.col("pctchg_d").std().alias("std")
        ])
        print(pctchg_stats)

        # Contar eventos up vs down
        n_up = df_all.filter(pl.col("pctchg_d") > 0).height
        n_down = df_all.filter(pl.col("pctchg_d") < 0).height
        print(f"\nEventos UP: {n_up:,} ({n_up/df_all.height*100:.1f}%)")
        print(f"Eventos DOWN: {n_down:,} ({n_down/df_all.height*100:.1f}%)")

    # 2. RVOL outliers
    if "rvol30" in df_all.columns:
        print("\n2. RVOL OUTLIERS:")
        rvol_stats = df_all.select([
            pl.col("rvol30").median().alias("median"),
            pl.col("rvol30").quantile(0.90).alias("p90"),
            pl.col("rvol30").quantile(0.95).alias("p95"),
            pl.col("rvol30").quantile(0.99).alias("p99"),
            pl.col("rvol30").max().alias("max")
        ])
        print(rvol_stats)

        # Top 10 RVOL extremos
        top_rvol = df_all.sort("rvol30", descending=True).head(10).select(["ticker", "rvol30"])
        print("\nTop 10 RVOL extremos:")
        print(top_rvol)

    # 3. Crecimiento $vol por año
    if "dvol" in df_all.columns:
        print("\n3. CRECIMIENTO $VOL:")
        # Esto requiere cargar fechas de los watchlists
        # Por ahora, solo stats globales
        dvol_stats = df_all.select([
            pl.col("dvol").median().alias("median"),
            pl.col("dvol").mean().alias("mean"),
            (pl.col("dvol") / 1_000_000).quantile(0.50).alias("p50_M"),
            (pl.col("dvol") / 1_000_000).quantile(0.75).alias("p75_M"),
            (pl.col("dvol") / 1_000_000).quantile(0.90).alias("p90_M")
        ])
        print(dvol_stats)

def main():
    watchlist_root = Path("processed/universe/info_rich/v2_2004_2019/daily")
    daily_cache_root = Path("processed/daily_cache/v2_2004_2019")

    if not watchlist_root.exists():
        print(f"ERROR: No existe {watchlist_root}")
        sys.exit(1)

    print("="*60)
    print("ANÁLISIS INFO-RICH UNIVERSE v2 (2004-2019)")
    print("="*60)

    # 1. Densidad temporal
    df_events = analyze_temporal_density(watchlist_root)

    if df_events is not None:
        # Identificar top años
        yearly = df_events.group_by("year").agg(
            pl.col("n_tickers").sum().alias("total")
        ).sort("total", descending=True)
        top_years = yearly.head(5)["year"].to_list()

        # 2. Top runners
        analyze_top_runners(watchlist_root, top_years)

    # 3. Sanity checks
    sanity_checks(watchlist_root, daily_cache_root)

    print("\n" + "="*60)
    print("ANÁLISIS COMPLETADO")
    print("="*60)

if __name__ == "__main__":
    main()
