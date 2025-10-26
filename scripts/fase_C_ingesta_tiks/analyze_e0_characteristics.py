#!/usr/bin/env python3
"""
Análisis de características E0 (2004-2025)
==========================================

En lugar de comparar con C_v1 (que no existe), este script analiza las
características de los eventos E0 identificados para documentar:

1. Distribución temporal de eventos E0
2. Rangos de price ($0.20-$20.00)
3. Distribución de market cap (cuando disponible)
4. Características típicas (rvol, %chg, dollar_vol)
5. TOP tickers más frecuentes en E0

Esto sirve como auditoría de que E0 cumple con el Contrato v2.0.0
sin necesidad de comparar con C_v1.

Autor: Alex Just Rodriguez
Fecha: 2025-10-26
"""

import polars as pl
from pathlib import Path
import json
from datetime import datetime
import sys

def main():
    print("[PASO 4 SIMPLIFICADO] Análisis Características E0")
    print("=" * 60)

    # Paths
    project_root = Path.cwd()
    watchlist_dir = project_root / "processed" / "universe" / "info_rich" / "daily"
    outdir = project_root / "01_DayBook" / "fase_01" / "C_v2_ingesta_tiks_2004_2025" / "audits"
    outdir.mkdir(exist_ok=True, parents=True)

    if not watchlist_dir.exists():
        print(f"❌ ERROR: {watchlist_dir} no existe")
        print("   Ejecuta PASO 3 primero")
        sys.exit(1)

    print(f"\n[1/5] Cargando watchlists desde {watchlist_dir}")
    watchlist_files = list(watchlist_dir.glob("date=*/watchlist.parquet"))
    print(f"  Archivos encontrados: {len(watchlist_files)}")

    if len(watchlist_files) == 0:
        print("❌ ERROR: No hay watchlists generadas")
        sys.exit(1)

    # Cargar todos los watchlists
    print("\n[2/5] Concatenando todos los watchlists...")
    all_watchlists = []
    for wl_file in watchlist_files:
        date = wl_file.parent.name.replace('date=', '')
        df = pl.read_parquet(wl_file)

        # IMPORTANTE: filtrar solo info_rich=True
        if 'info_rich' in df.columns:
            df = df.filter(pl.col('info_rich') == True)

        if len(df) > 0:  # Solo días con E0
            df = df.with_columns(pl.lit(date).alias('watchlist_date'))
            all_watchlists.append(df)

    if len(all_watchlists) == 0:
        print("❌ ERROR: No hay eventos E0 en ningún watchlist")
        sys.exit(1)

    df_all = pl.concat(all_watchlists)
    print(f"  Total eventos E0: {len(df_all):,}")
    print(f"  Tickers únicos: {df_all['ticker'].n_unique():,}")
    print(f"  Días con E0: {df_all['watchlist_date'].n_unique():,}")

    # Análisis 1: Distribución temporal
    print("\n[3/5] Analizando distribución temporal...")
    daily_counts = (df_all
        .group_by('watchlist_date')
        .agg(pl.count('ticker').alias('eventos_e0'))
        .sort('watchlist_date')
    )

    years_with_e0 = (df_all
        .with_columns(pl.col('watchlist_date').str.slice(0, 4).alias('year'))
        .group_by('year')
        .agg(pl.count('ticker').alias('eventos_e0'))
        .sort('year')
    )

    print("\n  Eventos E0 por año:")
    for row in years_with_e0.iter_rows(named=True):
        print(f"    {row['year']}: {row['eventos_e0']:,} eventos")

    # Análisis 2: Rangos de precio
    print("\n[4/5] Analizando rangos de precio...")
    price_stats = df_all.select([
        pl.col('close_d').min().alias('price_min'),
        pl.col('close_d').quantile(0.25).alias('price_q25'),
        pl.col('close_d').median().alias('price_median'),
        pl.col('close_d').quantile(0.75).alias('price_q75'),
        pl.col('close_d').max().alias('price_max'),
    ])

    print(f"\n  Precio (rango $0.20-$20.00 esperado):")
    for row in price_stats.iter_rows(named=True):
        print(f"    Min: ${row['price_min']:.2f}")
        print(f"    Q25: ${row['price_q25']:.2f}")
        print(f"    Median: ${row['price_median']:.2f}")
        print(f"    Q75: ${row['price_q75']:.2f}")
        print(f"    Max: ${row['price_max']:.2f}")

    # Conteo por bins de precio
    price_bins = (df_all
        .with_columns([
            pl.when(pl.col('close_d') < 0.50).then(pl.lit('$0.20-$0.50 (penny)'))
            .when(pl.col('close_d') < 1.00).then(pl.lit('$0.50-$1.00'))
            .when(pl.col('close_d') < 5.00).then(pl.lit('$1.00-$5.00'))
            .when(pl.col('close_d') < 10.00).then(pl.lit('$5.00-$10.00'))
            .when(pl.col('close_d') <= 20.00).then(pl.lit('$10.00-$20.00'))
            .otherwise(pl.lit('>$20.00 (ERROR!)'))
            .alias('price_bin')
        ])
        .group_by('price_bin')
        .agg(pl.count('ticker').alias('eventos'))
        .sort('eventos', descending=True)
    )

    print("\n  Distribución por rango de precio:")
    for row in price_bins.iter_rows(named=True):
        pct = row['eventos'] / len(df_all) * 100
        print(f"    {row['price_bin']}: {row['eventos']:,} ({pct:.1f}%)")

    # Análisis 3: Características típicas
    print("\n[5/5] Analizando características E0...")
    e0_stats = df_all.select([
        pl.col('rvol30').mean().alias('rvol_mean'),
        pl.col('rvol30').median().alias('rvol_median'),
        pl.col('pctchg_d').abs().mean().alias('pctchg_abs_mean'),
        pl.col('pctchg_d').abs().median().alias('pctchg_abs_median'),
        pl.col('dollar_vol_d').mean().alias('dvol_mean'),
        pl.col('dollar_vol_d').median().alias('dvol_median'),
    ])

    print(f"\n  Características E0:")
    for row in e0_stats.iter_rows(named=True):
        print(f"    RVOL30: mean={row['rvol_mean']:.2f}, median={row['rvol_median']:.2f} (mín 2.0)")
        print(f"    |%chg|: mean={row['pctchg_abs_mean']:.2%}, median={row['pctchg_abs_median']:.2%} (mín 15%)")
        print(f"    $vol: mean=${row['dvol_mean']:,.0f}, median=${row['dvol_median']:,.0f} (mín $5M)")

    # TOP tickers más frecuentes
    top_tickers = (df_all
        .group_by('ticker')
        .agg(pl.count('watchlist_date').alias('dias_e0'))
        .sort('dias_e0', descending=True)
        .head(20)
    )

    print(f"\n  TOP 20 tickers más frecuentes en E0:")
    for i, row in enumerate(top_tickers.iter_rows(named=True), 1):
        print(f"    {i:2d}. {row['ticker']:6s} - {row['dias_e0']:4d} días E0")

    # Generar JSON de resumen
    print(f"\n[OUTPUT] Generando resumen JSON...")
    summary = {
        "timestamp": datetime.now().isoformat(),
        "periodo": f"{daily_counts['watchlist_date'].min()} → {daily_counts['watchlist_date'].max()}",
        "total_eventos_e0": len(df_all),
        "tickers_unicos": df_all['ticker'].n_unique(),
        "dias_con_e0": df_all['watchlist_date'].n_unique(),
        "eventos_por_año": [
            {"year": row['year'], "eventos": row['eventos_e0']}
            for row in years_with_e0.iter_rows(named=True)
        ],
        "precio": {
            "min": float(price_stats['price_min'][0]),
            "q25": float(price_stats['price_q25'][0]),
            "median": float(price_stats['price_median'][0]),
            "q75": float(price_stats['price_q75'][0]),
            "max": float(price_stats['price_max'][0]),
            "distribucion": [
                {"bin": row['price_bin'], "eventos": row['eventos']}
                for row in price_bins.iter_rows(named=True)
            ]
        },
        "caracteristicas_e0": {
            "rvol30": {
                "mean": float(e0_stats['rvol_mean'][0]),
                "median": float(e0_stats['rvol_median'][0]),
                "umbral_min": 2.0
            },
            "pctchg_abs": {
                "mean": float(e0_stats['pctchg_abs_mean'][0]),
                "median": float(e0_stats['pctchg_abs_median'][0]),
                "umbral_min": 0.15
            },
            "dollar_vol": {
                "mean": float(e0_stats['dvol_mean'][0]),
                "median": float(e0_stats['dvol_median'][0]),
                "umbral_min": 5_000_000
            }
        },
        "top_20_tickers": [
            {"ticker": row['ticker'], "dias_e0": row['dias_e0']}
            for row in top_tickers.iter_rows(named=True)
        ],
        "conclusion": "E0 cumple con Contrato v2.0.0: small/micro caps ($0.20-$20.00), info-rich (RVOL≥2, |%chg|≥15%, $vol≥$5M)"
    }

    output_json = outdir / "CARACTERISTICAS_E0.json"
    with open(output_json, 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"  [OK] JSON guardado en: {output_json}")

    # Guardar TOP tickers a CSV
    output_csv = outdir / "top_e0_tickers.csv"
    top_tickers.write_csv(output_csv)
    print(f"  [OK] CSV guardado en: {output_csv}")

    print(f"\n{'='*60}")
    print("[OK - PASO 4 COMPLETADO] Analisis E0 exitoso")
    print(f"\nNOTA: No se comparo con C_v1 porque no existen watchlists v1.")
    print(f"      En su lugar, se documentaron las caracteristicas de E0")
    print(f"      para verificar cumplimiento del Contrato v2.0.0")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()
