#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
build_dynamic_universe.py
Genera universo dinámico 'info-rich' desde 1-min:
- Por ticker-día: %chg, RVOL(30d), dollar_volume
- Etiqueta info_rich con umbrales configurables
- Emite watchlists diarias y Top-N 12m

Uso (ejemplos):
  # Backfill de todo un rango
  python build_dynamic_universe.py \
    --intraday-root raw/polygon/ohlcv_intraday_1m \
    --outdir processed/universe/info_rich \
    --from 2017-01-01 --to 2025-10-21 \
    --rvol-th 2.0 --pctchg-th 0.15 --dvol-th 5000000 \
    --cap-filter-parquet processed/ref/tickers_dim/tickers_dim.parquet \
    --cap-max 2000000000

  # Solo un día (útil en diario)
  python build_dynamic_universe.py \
    --intraday-root raw/polygon/ohlcv_intraday_1m \
    --outdir processed/universe/info_rich \
    --from 2025-10-21 --to 2025-10-21
"""
from __future__ import annotations
import argparse, datetime as dt
from pathlib import Path
from typing import List, Optional
import polars as pl

def log(msg: str): print(msg, flush=True)

def month_paths_for_day(root: Path, day: dt.date) -> List[Path]:
    ym = f"year={day.year}/month={day.month:02d}"
    paths = []
    for tdir in root.iterdir():
        if not tdir.is_dir(): continue
        p = tdir / f"{ym}/minute.parquet"
        if p.exists(): paths.append(p)
    return paths

def load_minute_for_day(paths: List[Path], day: dt.date) -> pl.DataFrame:
    if not paths: return pl.DataFrame()
    df = pl.read_parquet(paths, parallel="auto", use_statistics=True)
    dstr = day.strftime("%Y-%m-%d")
    # Asumimos columnas: ticker, date, minute, o,h,l,c,v,vw,n,t
    df = df.filter(pl.col("date") == dstr)
    return df

def minute_to_daily(df: pl.DataFrame) -> pl.DataFrame:
    if df.is_empty():
        return df
    # Agregado diario
    agg = (
        df.group_by("ticker")
          .agg([
              pl.col("c").last().alias("close_d"),
              pl.col("v").sum().alias("vol_d"),
              (pl.col("v") * pl.col("vw")).sum().alias("dollar_vol_d")
          ])
          .with_columns([
              # date está fija en todo df filtrado por día, recógela de la primera fila por ticker
              pl.lit(df.select("date").to_series()[0]).alias("date")
          ])
    )
    return agg.select(["ticker","date","close_d","vol_d","dollar_vol_d"])

def compute_features_daily(all_daily: pl.DataFrame) -> pl.DataFrame:
    if all_daily.is_empty():
        return all_daily
    # Calcula %chg y RVOL(30d) por ticker
    out = (
        all_daily
        .sort(["ticker","date"])
        .with_columns([
            pl.col("date").str.strptime(pl.Date, "%Y-%m-%d").alias("d"),
        ])
        .group_by("ticker", maintain_order=True)
        .agg([
            pl.col("d"),
            pl.col("close_d"),
            pl.col("vol_d"),
            pl.col("dollar_vol_d"),
        ])
        .explode(["d","close_d","vol_d","dollar_vol_d"])
        .with_columns([
            pl.col("close_d").shift(1).over("ticker").alias("close_prev"),
        ])
        .with_columns([
            ((pl.col("close_d") / pl.col("close_prev")) - 1.0).alias("pctchg_d"),
            # RVOL(30d) = vol_d / MA30(vol_d)
            pl.col("vol_d").rolling_mean(window_size=30).over("ticker").alias("vol_ma30"),
        ])
        .with_columns([
            (pl.col("vol_d") / pl.col("vol_ma30")).alias("rvol30"),
            pl.col("d").dt.strftime("%Y-%m-%d").alias("date"),
        ])
        .select(["ticker","date","close_d","pctchg_d","vol_d","rvol30","dollar_vol_d"])
    )
    return out

def apply_cap_filter(df: pl.DataFrame, cap_parquet: Optional[str], cap_max: Optional[float]) -> pl.DataFrame:
    if not cap_parquet or not cap_max: return df
    if not Path(cap_parquet).exists(): 
        log(f"[WARN] cap parquet no encontrado: {cap_parquet} (se omite filtro)")
        return df
    dim = pl.read_parquet(cap_parquet).select(["ticker","effective_from","effective_to","market_cap"])
    # quedarnos con el último registro vigente (si tu SCD-2 tiene intervals abiertos)
    # Aquí asumimos snapshot; si quieres estricta validez por fecha, une por rango date∈[eff_from, eff_to)
    dim_last = dim.group_by("ticker").agg(pl.col("market_cap").last().alias("market_cap"))
    out = df.join(dim_last, on="ticker", how="left")
    out = out.filter((pl.col("market_cap").is_null()) | (pl.col("market_cap") <= cap_max))
    return out

def label_info_rich(df: pl.DataFrame, rvol_th: float, pctchg_th: float, dvol_th: float,
                    min_price: float, max_price: float) -> pl.DataFrame:
    if df.is_empty(): return df
    return (
        df.with_columns([
            (pl.col("rvol30") >= rvol_th).alias("r_rvol"),
            (pl.col("pctchg_d").abs() >= pctchg_th).alias("r_chg"),
            (pl.col("dollar_vol_d") >= dvol_th).alias("r_dvol"),
            ((pl.col("close_d") >= min_price) & (pl.col("close_d") <= max_price)).alias("r_px"),
        ])
        .with_columns([
            (pl.col("r_rvol") & pl.col("r_chg") & pl.col("r_dvol") & pl.col("r_px")).alias("info_rich")
        ])
    )

def save_watchlist_daily(df: pl.DataFrame, outdir: Path, day: dt.date):
    if df.is_empty(): return
    ddir = outdir / "daily" / f"date={day.strftime('%Y-%m-%d')}"
    ddir.mkdir(parents=True, exist_ok=True)
    df.write_parquet(ddir / "watchlist.parquet")

def update_topN_12m(outdir: Path, df_day: pl.DataFrame, day: dt.date, top_k: int = 200):
    # Carga histórico (si existe), concat y corta a 252 sesiones aprox.
    hist_path = outdir / "topN_12m.parquet"
    if hist_path.exists():
        hist = pl.read_parquet(hist_path)
        base = pl.concat([hist, df_day.select(["ticker","date","info_rich"])], how="vertical_relaxed")
    else:
        base = df_day.select(["ticker","date","info_rich"])

    # Mantener solo últimos ~252 días por ticker
    base = (
        base
        .with_columns(pl.col("date").str.strptime(pl.Date, "%Y-%m-%d"))
        .sort(["ticker","date"])
        .group_by("ticker", maintain_order=True)
        .tail(252)  # últimas 252 observaciones por ticker si hubiera más
    )

    # Ranking por nº de días info_rich y recencia
    ranks = (
        base.group_by("ticker")
            .agg([
                pl.col("info_rich").sum().alias("days_info_rich_252"),
                pl.col("date").max().alias("last_seen"),
            ])
            .sort(["days_info_rich_252","last_seen"], descending=[True, True])
    )
    ranks.write_parquet(hist_path)
    ranks.head(top_k).write_csv(outdir / "topN_12m.csv")

def daterange(d0: dt.date, d1: dt.date):
    cur = d0
    while cur <= d1:
        yield cur
        cur += dt.timedelta(days=1)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--intraday-root", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--from", dest="date_from", required=True)
    ap.add_argument("--to", dest="date_to", required=True)
    ap.add_argument("--rvol-th", type=float, default=2.0)
    ap.add_argument("--pctchg-th", type=float, default=0.15)   # 15%
    ap.add_argument("--dvol-th", type=float, default=5_000_000)  # $5M
    ap.add_argument("--min-price", type=float, default=0.5)
    ap.add_argument("--max-price", type=float, default=20.0)
    ap.add_argument("--cap-filter-parquet", type=str, default=None)
    ap.add_argument("--cap-max", type=float, default=None)
    args = ap.parse_args()

    root = Path(args.intraday_root)
    outdir = Path(args.outdir); outdir.mkdir(parents=True, exist_ok=True)

    d0 = dt.datetime.strptime(args.date_from, "%Y-%m-%d").date()
    d1 = dt.datetime.strptime(args.date_to,   "%Y-%m-%d").date()

    for day in daterange(d0, d1):
        # 1) cargar sólo los parquets del mes correspondiente
        mpaths = month_paths_for_day(root, day)
        if not mpaths:
            continue
        df_min = load_minute_for_day(mpaths, day)
        if df_min.is_empty():
            continue

        # 2) a diario por ticker
        df_day = minute_to_daily(df_min)

        # 3) backfill para poder calcular RVOL rolling (necesita histórico)
        #    – leemos hasta 40 días atrás (colchón) del mismo mes/meses contiguos
        #    *Simplificación*: usamos solo este día (en producción,
        #    puedes precargar diario histórico desde un parquet cache.)
        #    Aquí calculamos features con lo que hay (el RVOL arrancará tras 30 días efectivos)
        features = compute_features_daily(df_day)

        # 4) filtros opcionales por market cap
        features = apply_cap_filter(features, args.cap_filter_parquet, args.cap_max)

        # 5) etiquetar info_rich
        features = label_info_rich(
            features, args.rvol_th, args.pctchg_th, args.dvol_th,
            args.min_price, args.max_price
        )

        # 6) guardar watchlist diaria y actualizar topN 12m
        save_watchlist_daily(features, outdir, day)
        update_topN_12m(outdir, features, day)

        log(f"{day}: {features.filter(pl.col('info_rich')).height} tickers info-rich")

if __name__ == "__main__":
    main()
