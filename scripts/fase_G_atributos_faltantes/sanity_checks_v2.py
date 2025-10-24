#!/usr/bin/env python3
"""
Sanity Checks - Info-rich Universe v2 (2004-2019)

Validaciones:
1. Simetria %chg: UP vs DOWN, distribucion de colas
2. RVOL outliers: Trading halts, splits, errores
3. Crecimiento $vol estacional: 2016-2019 > 2004-2006
"""

import polars as pl
from pathlib import Path
import sys
import json

def load_all_events(watchlist_root: Path):
    """Cargar todos los eventos info-rich con sus fechas"""
    print("Cargando eventos...", file=sys.stderr)

    all_events = []
    for parquet in watchlist_root.rglob("watchlist.parquet"):
        date_str = parquet.parent.name.split("=")[1]
        df = pl.read_parquet(parquet)
        if df.height > 0:
            df = df.with_columns(pl.lit(date_str).alias("date"))
            all_events.append(df)

    if not all_events:
        print("ERROR: No hay eventos", file=sys.stderr)
        return None

    df_all = pl.concat(all_events)
    df_all = df_all.with_columns([
        pl.col("date").str.to_date().alias("date"),
        pl.col("date").str.slice(0, 4).cast(pl.Int32).alias("year")
    ])

    print(f"Eventos cargados: {df_all.height:,}", file=sys.stderr)
    return df_all

def check_pctchg_symmetry(df: pl.DataFrame):
    """1. Validar simetria de %chg"""
    print("\n=== 1. SIMETRIA %CHG ===", file=sys.stderr)

    if "pctchg_d" not in df.columns:
        print("WARNING: No hay columna pctchg_d", file=sys.stderr)
        return {}

    # Stats globales
    stats = {
        "min": float(df["pctchg_d"].min()),
        "p01": float(df["pctchg_d"].quantile(0.01)),
        "p05": float(df["pctchg_d"].quantile(0.05)),
        "p25": float(df["pctchg_d"].quantile(0.25)),
        "median": float(df["pctchg_d"].median()),
        "p75": float(df["pctchg_d"].quantile(0.75)),
        "p95": float(df["pctchg_d"].quantile(0.95)),
        "p99": float(df["pctchg_d"].quantile(0.99)),
        "max": float(df["pctchg_d"].max()),
        "mean": float(df["pctchg_d"].mean()),
        "std": float(df["pctchg_d"].std())
    }

    # Contar UP vs DOWN
    n_up = df.filter(pl.col("pctchg_d") > 0).height
    n_down = df.filter(pl.col("pctchg_d") < 0).height
    n_flat = df.filter(pl.col("pctchg_d") == 0).height
    total = df.height

    stats["n_up"] = n_up
    stats["n_down"] = n_down
    stats["n_flat"] = n_flat
    stats["pct_up"] = round(n_up / total * 100, 2)
    stats["pct_down"] = round(n_down / total * 100, 2)

    # Por periodo (crisis vs normal)
    crisis = df.filter(pl.col("year").is_in([2008, 2009]))
    if crisis.height > 0:
        stats["crisis_std"] = float(crisis["pctchg_d"].std())
        stats["crisis_p99"] = float(crisis["pctchg_d"].quantile(0.99))
        stats["crisis_p01"] = float(crisis["pctchg_d"].quantile(0.01))

    normal = df.filter(pl.col("year").is_in([2004, 2005, 2006, 2007]))
    if normal.height > 0:
        stats["normal_std"] = float(normal["pctchg_d"].std())
        stats["normal_p99"] = float(normal["pctchg_d"].quantile(0.99))
        stats["normal_p01"] = float(normal["pctchg_d"].quantile(0.01))

    print(f"Total eventos: {total:,}", file=sys.stderr)
    print(f"UP: {n_up:,} ({stats['pct_up']}%)", file=sys.stderr)
    print(f"DOWN: {n_down:,} ({stats['pct_down']}%)", file=sys.stderr)
    print(f"Mediana: {stats['median']:.2%}", file=sys.stderr)
    print(f"Std: {stats['std']:.2%}", file=sys.stderr)

    return stats

def check_rvol_outliers(df: pl.DataFrame):
    """2. Validar outliers RVOL"""
    print("\n=== 2. RVOL OUTLIERS ===", file=sys.stderr)

    if "rvol30" not in df.columns:
        print("WARNING: No hay columna rvol30", file=sys.stderr)
        return {}

    stats = {
        "median": float(df["rvol30"].median()),
        "mean": float(df["rvol30"].mean()),
        "p75": float(df["rvol30"].quantile(0.75)),
        "p90": float(df["rvol30"].quantile(0.90)),
        "p95": float(df["rvol30"].quantile(0.95)),
        "p99": float(df["rvol30"].quantile(0.99)),
        "max": float(df["rvol30"].max())
    }

    # Top 20 RVOL extremos
    top_rvol = df.sort("rvol30", descending=True).head(20).select([
        "ticker", "date", "rvol30", "pctchg_d", "dollar_vol_d"
    ])

    stats["top_outliers"] = top_rvol.to_dicts()

    # Contar extremos por rango
    stats["count_gt_10"] = df.filter(pl.col("rvol30") > 10).height
    stats["count_gt_20"] = df.filter(pl.col("rvol30") > 20).height
    stats["count_gt_50"] = df.filter(pl.col("rvol30") > 50).height
    stats["count_gt_100"] = df.filter(pl.col("rvol30") > 100).height

    print(f"Mediana RVOL: {stats['median']:.2f}x", file=sys.stderr)
    print(f"P99 RVOL: {stats['p99']:.2f}x", file=sys.stderr)
    print(f"Max RVOL: {stats['max']:.2f}x", file=sys.stderr)
    print(f"Eventos >50x: {stats['count_gt_50']:,}", file=sys.stderr)

    return stats

def check_dvol_growth(df: pl.DataFrame):
    """3. Validar crecimiento $vol estacional"""
    print("\n=== 3. CRECIMIENTO $VOL ===", file=sys.stderr)

    if "dollar_vol_d" not in df.columns:
        print("WARNING: No hay columna dvol", file=sys.stderr)
        return {}

    # Stats globales
    stats = {
        "median": float(df["dollar_vol_d"].median()),
        "mean": float(df["dollar_vol_d"].mean()),
        "p50_M": round(float(df["dollar_vol_d"].median()) / 1_000_000, 2),
        "p75_M": round(float(df["dollar_vol_d"].quantile(0.75)) / 1_000_000, 2),
        "p90_M": round(float(df["dollar_vol_d"].quantile(0.90)) / 1_000_000, 2)
    }

    # Por periodo
    periodos = {
        "2004-2007": [2004, 2005, 2006, 2007],
        "2008-2009": [2008, 2009],
        "2010-2014": [2010, 2011, 2012, 2013, 2014],
        "2015-2019": [2015, 2016, 2017, 2018, 2019]
    }

    stats["by_period"] = {}
    for period_name, years in periodos.items():
        period_df = df.filter(pl.col("year").is_in(years))
        if period_df.height > 0:
            stats["by_period"][period_name] = {
                "median_M": round(float(period_df["dollar_vol_d"].median()) / 1_000_000, 2),
                "p75_M": round(float(period_df["dollar_vol_d"].quantile(0.75)) / 1_000_000, 2),
                "p90_M": round(float(period_df["dollar_vol_d"].quantile(0.90)) / 1_000_000, 2),
                "n_events": period_df.height
            }

    # Por año
    yearly_dvol = df.group_by("year").agg([
        (pl.col("dollar_vol_d").median() / 1_000_000).alias("median_M"),
        (pl.col("dollar_vol_d").quantile(0.75) / 1_000_000).alias("p75_M"),
        pl.col("dollar_vol_d").count().alias("n_events")
    ]).sort("year")

    stats["by_year"] = yearly_dvol.to_dicts()

    print(f"Mediana global: ${stats['p50_M']:.2f}M", file=sys.stderr)
    for period, data in stats["by_period"].items():
        print(f"{period}: ${data['median_M']:.2f}M (n={data['n_events']:,})", file=sys.stderr)

    return stats

def check_top_runners_by_period(df: pl.DataFrame, top_years: list):
    """Identificar top runners por periodo critico"""
    print("\n=== 4. TOP RUNNERS POR PERIODO ===", file=sys.stderr)

    results = {}

    for year in top_years:
        year_df = df.filter(pl.col("year") == year)
        if year_df.height == 0:
            continue

        top50 = year_df.group_by("ticker").agg([
            pl.col("date").count().alias("days_info_rich"),
            pl.col("pctchg_d").mean().alias("avg_pctchg"),
            pl.col("rvol30").mean().alias("avg_rvol"),
            pl.col("date").max().alias("last_seen")
        ]).sort("days_info_rich", descending=True).head(50)

        results[str(year)] = top50.to_dicts()

        print(f"\n{year} - Top 10:", file=sys.stderr)
        for i, row in enumerate(top50.head(10).iter_rows(named=True), 1):
            print(f"  {i}. {row['ticker']}: {row['days_info_rich']} dias", file=sys.stderr)

    return results

def main():
    watchlist_root = Path("processed/universe/info_rich/v2_2004_2019/daily")

    if not watchlist_root.exists():
        print(f"ERROR: No existe {watchlist_root}", file=sys.stderr)
        sys.exit(1)

    print("="*60, file=sys.stderr)
    print("SANITY CHECKS - INFO-RICH v2 (2004-2019)", file=sys.stderr)
    print("="*60, file=sys.stderr)

    # Cargar datos
    df = load_all_events(watchlist_root)
    if df is None:
        sys.exit(1)

    # Ejecutar checks
    results = {
        "total_events": df.height,
        "unique_tickers": df["ticker"].n_unique(),
        "date_range": {
            "min": str(df["date"].min()),
            "max": str(df["date"].max())
        }
    }

    results["pctchg_symmetry"] = check_pctchg_symmetry(df)
    results["rvol_outliers"] = check_rvol_outliers(df)
    results["dvol_growth"] = check_dvol_growth(df)

    # Top runners en periodos criticos
    results["top_runners"] = check_top_runners_by_period(df, [2008, 2009, 2016, 2018, 2019])

    # Guardar resultados
    output_file = Path("01_DayBook/fase_03/G_atributos_nuevos/v2_sanity_checks.json")
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w") as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\n{'='*60}", file=sys.stderr)
    print(f"RESULTADOS GUARDADOS: {output_file}", file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)

    # Imprimir resumen a stdout (para capturar)
    print(json.dumps(results, indent=2, default=str))

if __name__ == "__main__":
    main()
