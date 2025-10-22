#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
build_topn_runners.py
Construye TopN12m (runners recurrentes) para un horizonte largo (p.ej. 5 años).

- Input: processed/universe/info_rich/daily/date=YYYY-MM-DD/watchlist.parquet
         (columnas mínimas: ticker, date, info_rich)
- Output:
  processed/universe/info_rich/topn12m/rolling/month_end/topn_YYYY-MM.parquet
  processed/universe/info_rich/topn12m/annual/topn_YYYY-12-31.parquet
  processed/universe/info_rich/topn12m/topn12m_index.parquet

Uso:
  python build_topn_runners.py \
    --daily-root processed/universe/info_rich/daily \
    --outdir processed/universe/info_rich/topn12m \
    --from 2020-01-01 --to 2025-10-21 \
    --k 200 \
    --snap monthly
"""
from __future__ import annotations
import argparse, datetime as dt
from pathlib import Path
from typing import List
import polars as pl

def log(s: str): print(s, flush=True)

def list_daily_paths(root: Path, d0: dt.date, d1: dt.date) -> List[Path]:
    # Espera subcarpetas: daily/date=YYYY-MM-DD/watchlist.parquet
    paths = []
    cur = d0
    while cur <= d1:
        p = root / f"date={cur:%Y-%m-%d}" / "watchlist.parquet"
        if p.exists():
            paths.append(p)
        cur += dt.timedelta(days=1)
    return paths

def load_daily_watchlists(paths: List[Path]) -> pl.DataFrame:
    if not paths:
        return pl.DataFrame(schema={"ticker": pl.Utf8, "date": pl.Utf8, "info_rich": pl.Boolean})
    df = pl.read_parquet(paths, use_statistics=True)
    # Asegurar columnas mínimas
    need = {"ticker","date","info_rich"}
    missing = need - set(df.columns)
    if missing:
        raise ValueError(f"Faltan columnas {missing} en watchlist.parquet")
    # Normalizar fecha
    return df.select([
        pl.col("ticker").cast(pl.Utf8),
        pl.col("date").cast(pl.Utf8),
        pl.col("info_rich").cast(pl.Boolean)
    ]).with_columns(pl.col("date").str.strptime(pl.Date, "%Y-%m-%d"))

def month_ends_between(d0: dt.date, d1: dt.date) -> List[dt.date]:
    out = []
    y, m = d0.year, d0.month
    while (y < d1.year) or (y == d1.year and m <= d1.month):
        if m == 12:
            last = dt.date(y, 12, 31)
            y, m = y+1, 1
        else:
            last = dt.date(y, m+1, 1) - dt.timedelta(days=1)
            m += 1
        if last >= d0 and last <= d1:
            out.append(last)
    return out

def year_ends_between(d0: dt.date, d1: dt.date) -> List[dt.date]:
    out = []
    for y in range(d0.year, d1.year+1):
        de = dt.date(y, 12, 31)
        if de >= d0 and de <= d1:
            out.append(de)
    return out

def compute_topn_window(df_daily: pl.DataFrame, asof: dt.date, k: int, win_days: int = 252) -> pl.DataFrame:
    # filtra ventana [asof - win_days, asof]
    start = asof - dt.timedelta(days=win_days)
    sub = df_daily.filter((pl.col("date") > start) & (pl.col("date") <= asof))
    if sub.is_empty():
        return pl.DataFrame()
    # suma de días info_rich y última vez visto
    ranks = (
        sub.group_by("ticker")
           .agg([
               pl.col("info_rich").sum().alias("days_info_rich_win"),
               pl.col("date").max().alias("last_seen")
           ])
           .sort(["days_info_rich_win","last_seen"], descending=[True, True])
           .with_columns([
               pl.lit(asof).alias("asof_date"),
               pl.int_range(1, pl.len()+1).alias("rank")
           ])
           .select(["asof_date","rank","ticker","days_info_rich_win","last_seen"])
    )
    if k and k > 0:
        ranks = ranks.head(k)
    return ranks

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--daily-root", required=True, help="processed/universe/info_rich/daily")
    ap.add_argument("--outdir", required=True, help="processed/universe/info_rich/topn12m")
    ap.add_argument("--from", dest="date_from", required=True)
    ap.add_argument("--to", dest="date_to", required=True)
    ap.add_argument("--k", type=int, default=200, help="Top-N a guardar por snapshot")
    ap.add_argument("--snap", choices=["monthly","annual","both"], default="both",
                    help="Snapshots mensuales, anuales, o ambos")
    ap.add_argument("--win-days", type=int, default=252, help="Tamaño de ventana (≈252 sesiones ~ 12 meses)")
    args = ap.parse_args()

    root = Path(args.daily_root)
    outdir = Path(args.outdir); (outdir / "rolling" / "month_end").mkdir(parents=True, exist_ok=True)
    (outdir / "annual").mkdir(parents=True, exist_ok=True)

    d0 = dt.datetime.strptime(args.date_from, "%Y-%m-%d").date()
    d1 = dt.datetime.strptime(args.date_to,   "%Y-%m-%d").date()

    # cargar todos los watchlists del rango
    paths = list_daily_paths(root, d0, d1)
    if not paths:
        log("No se encontraron watchlists en el rango.")
        return
    df = load_daily_watchlists(paths)

    # índice de snapshots
    idx_rows = []

    # 1) Snap mensual (último día de mes)
    if args.snap in ("monthly", "both"):
        for asof in month_ends_between(d0, d1):
            ranks = compute_topn_window(df, asof, args.k, args.win_days)
            if ranks.is_empty(): 
                continue
            outp = outdir / "rolling" / "month_end" / f"topn_{asof:%Y-%m}.parquet"
            ranks.write_parquet(outp)
            idx_rows.append(pl.DataFrame({
                "asof_date":[asof], "snapshot_type":["month_end"], "path":[str(outp)]
            }))
            log(f"[monthly] {asof}: {len(ranks)} filas -> {outp}")

    # 2) Snap anual (31-Dic)
    if args.snap in ("annual", "both"):
        for asof in year_ends_between(d0, d1):
            ranks = compute_topn_window(df, asof, args.k, args.win_days)
            if ranks.is_empty(): 
                continue
            outp = outdir / "annual" / f"topn_{asof:%Y}.parquet"
            ranks.write_parquet(outp)
            idx_rows.append(pl.DataFrame({
                "asof_date":[asof], "snapshot_type":["year_end"], "path":[str(outp)]
            }))
            log(f"[annual]  {asof}: {len(ranks)} filas -> {outp}")

    if idx_rows:
        idx = pl.concat(idx_rows, how="vertical_relaxed")
        idx = idx.sort("asof_date")
        idx.write_parquet(outdir / "topn12m_index.parquet")
        log(f"Índice escrito: {outdir/'topn12m_index.parquet'}")

if __name__ == "__main__":
    main()
