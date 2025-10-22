#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
build_dynamic_universe_optimized.py
Genera universo dinamico 'info-rich' desde CACHE DIARIO (no desde 1-min).

Optimizaciones:
- Lee del cache diario (velocidad 10-30x)
- RVOL ya calculado (30 sesiones)
- Config YAML para umbrales
- ZSTD compression
- Lazy reading Polars

Uso:
  # Backfill completo
  python build_dynamic_universe_optimized.py \
    --daily-cache processed/daily_cache \
    --outdir processed/universe/info_rich \
    --from 2020-01-01 --to 2025-10-21 \
    --config configs/universe_config.yaml

  # EOD (dia D)
  python build_dynamic_universe_optimized.py \
    --daily-cache processed/daily_cache \
    --outdir processed/universe/info_rich \
    --from 2025-10-22 --to 2025-10-22
"""
from __future__ import annotations
import argparse, datetime as dt, yaml
from pathlib import Path
from typing import Optional
import polars as pl

def log(msg: str):
    print(f"[{dt.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)

def load_config(config_path: Optional[str]) -> dict:
    """Carga config YAML o usa defaults"""
    defaults = {
        "thresholds": {
            "rvol": 2.0,
            "pctchg": 0.15,
            "dvol": 5_000_000,
            "min_price": 0.5,
            "max_price": 20.0,
            "cap_max": 2_000_000_000
        }
    }

    if not config_path or not Path(config_path).exists():
        log("[WARN] Config no encontrado, usando defaults")
        return defaults

    with open(config_path) as f:
        cfg = yaml.safe_load(f)

    # Merge con defaults
    return {**defaults, **cfg}

def list_ticker_caches(cache_root: Path) -> list[Path]:
    """Lista todos los ticker=XYZ/daily.parquet"""
    paths = []
    for tdir in cache_root.glob("ticker=*"):
        if tdir.is_dir():
            p = tdir / "daily.parquet"
            if p.exists():
                paths.append(p)
    return paths

def load_cache_for_range(cache_root: Path, date_from: dt.date, date_to: dt.date) -> pl.DataFrame:
    """
    Carga TODOS los tickers desde cache, filtra por rango de fechas (lazy)
    Proyecta solo columnas necesarias (consistencia con schema del cache)
    """
    paths = list_ticker_caches(cache_root)

    if not paths:
        log("[ERROR] No se encontraron caches de tickers")
        return pl.DataFrame()

    log(f"Cargando {len(paths)} tickers desde cache...")

    # Lazy scan + filter por rango + proyeccion columnas exactas
    df = (
        pl.scan_parquet(paths)
        .filter(
            (pl.col("trading_day") >= date_from) &
            (pl.col("trading_day") <= date_to)
        )
        .select([
            "ticker", "trading_day", "close_d", "pctchg_d", "rvol30",
            "vol_d", "dollar_vol_d", "vwap_d", "market_cap_d"
        ])
        .collect()
    )

    log(f"Cargados {len(df)} registros ticker-dia")
    return df

def apply_cap_filter(df: pl.DataFrame, cap_max: Optional[float]) -> pl.DataFrame:
    """Filtra por market cap maximo (si disponible)"""
    if not cap_max:
        return df

    # market_cap_d puede ser null si no hubo join en cache
    filtered = df.filter(
        (pl.col("market_cap_d").is_null()) |
        (pl.col("market_cap_d") <= cap_max)
    )

    dropped = len(df) - len(filtered)
    if dropped > 0:
        log(f"Filtro cap_max={cap_max:,}: {dropped} ticker-dias excluidos")

    return filtered

def label_info_rich(
    df: pl.DataFrame,
    rvol_th: float,
    pctchg_th: float,
    dvol_th: float,
    min_price: float,
    max_price: float
) -> pl.DataFrame:
    """
    Etiqueta info_rich basado en umbrales
    RVOL y pctchg_d ya calculados en cache
    """
    if df.is_empty():
        return df

    labeled = (
        df.with_columns([
            # Reglas individuales
            (pl.col("rvol30") >= rvol_th).alias("r_rvol"),
            (pl.col("pctchg_d").abs() >= pctchg_th).alias("r_chg"),
            (pl.col("dollar_vol_d") >= dvol_th).alias("r_dvol"),
            ((pl.col("close_d") >= min_price) & (pl.col("close_d") <= max_price)).alias("r_px"),
        ])
        .with_columns([
            # Combinacion AND
            (pl.col("r_rvol") & pl.col("r_chg") & pl.col("r_dvol") & pl.col("r_px")).alias("info_rich")
        ])
    )

    return labeled

def save_watchlist_daily(df: pl.DataFrame, outdir: Path, day: dt.date):
    """Guarda watchlist del dia con ZSTD"""
    if df.is_empty():
        return

    ddir = outdir / "daily" / f"date={day.strftime('%Y-%m-%d')}"
    ddir.mkdir(parents=True, exist_ok=True)

    outp = ddir / "watchlist.parquet"
    df.write_parquet(
        outp,
        compression="zstd",
        compression_level=2,
        statistics=False
    )

    log(f"{day}: {df.filter(pl.col('info_rich')).height} tickers info-rich -> {outp}")

def update_topN_12m(outdir: Path, df_all: pl.DataFrame, top_k: int = 200):
    """
    Actualiza topN_12m "corriente" (rolling 12 meses hasta hoy)
    df_all: TODOS los dias procesados hasta ahora
    """
    if df_all.is_empty():
        return

    # Tomar ultimos ~252 dias de mercado por ticker
    # Simplificacion: tail(252) por ticker ordenado
    last_252 = (
        df_all.sort(["ticker", "trading_day"])
        .group_by("ticker", maintain_order=True)
        .tail(252)
    )

    # Ranking por dias info_rich
    ranks = (
        last_252.group_by("ticker")
        .agg([
            pl.col("info_rich").sum().alias("days_info_rich_252"),
            pl.col("trading_day").max().alias("last_seen"),
        ])
        .sort(["days_info_rich_252", "last_seen"], descending=[True, True])
    )

    hist_path = outdir / "topN_12m.parquet"
    ranks.write_parquet(
        hist_path,
        compression="zstd",
        compression_level=2
    )

    csv_path = outdir / "topN_12m.csv"
    ranks.head(top_k).write_csv(csv_path)

    log(f"TopN_12m actualizado: {len(ranks)} tickers, top {top_k} -> {csv_path}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--daily-cache", required=True, help="processed/daily_cache")
    ap.add_argument("--outdir", required=True, help="processed/universe/info_rich")
    ap.add_argument("--from", dest="date_from", required=True)
    ap.add_argument("--to", dest="date_to", required=True)
    ap.add_argument("--config", type=str, default=None, help="configs/universe_config.yaml")
    args = ap.parse_args()

    cache_root = Path(args.daily_cache)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    date_from = dt.datetime.strptime(args.date_from, "%Y-%m-%d").date()
    date_to = dt.datetime.strptime(args.date_to, "%Y-%m-%d").date()

    # Cargar config
    cfg = load_config(args.config)
    th = cfg["thresholds"]

    log(f"=== BUILD DYNAMIC UNIVERSE (OPTIMIZED) ===")
    log(f"Cache: {cache_root}")
    log(f"Output: {outdir}")
    log(f"Rango: {date_from} -> {date_to}")
    log(f"Umbrales: RVOL>={th['rvol']}, |%chg|>={th['pctchg']}, $vol>=${th['dvol']:,}")
    log(f"Precio: [{th['min_price']}, {th['max_price']}], Cap<${th['cap_max']:,}")

    # Cargar cache completo (lazy + filter por rango)
    df_all = load_cache_for_range(cache_root, date_from, date_to)

    if df_all.is_empty():
        log("[ERROR] No hay datos en cache para el rango")
        return

    # Filtro de market cap (primero)
    df_all = apply_cap_filter(df_all, th.get("cap_max"))

    # Filtro de precio (previo a etiquetar, reduce ruido)
    df_all = df_all.filter(
        (pl.col("close_d") >= th["min_price"]) &
        (pl.col("close_d") <= th["max_price"])
    )

    # Etiquetar info_rich con RVOL/%chg/$vol
    df_all = label_info_rich(
        df_all,
        th["rvol"], th["pctchg"], th["dvol"],
        th["min_price"], th["max_price"]
    )

    # Guardar watchlist por dia
    days = sorted(df_all["trading_day"].unique().to_list())
    log(f"Generando watchlists para {len(days)} dias...")

    for day in days:
        df_day = df_all.filter(pl.col("trading_day") == day)
        save_watchlist_daily(df_day, outdir, day)

    # Actualizar topN_12m "corriente"
    update_topN_12m(outdir, df_all, top_k=200)

    log(f"=== COMPLETADO ===")
    log(f"Watchlists: {outdir / 'daily'}")
    log(f"TopN_12m: {outdir / 'topN_12m.parquet'}")

if __name__ == "__main__":
    main()
