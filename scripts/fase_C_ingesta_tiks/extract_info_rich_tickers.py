#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
extract_info_rich_tickers.py
Extrae tickers info-rich desde watchlists diarias para usar en descarga de ticks.

Uso:
  # Extraer tickers info-rich de una semana
  python extract_info_rich_tickers.py \
    --watchlist-root processed/universe/info_rich/daily \
    --from 2025-10-15 --to 2025-10-21 \
    --outdir processed/universe/info_rich

  # Incluir TopN_12m (top 200 runners)
  python extract_info_rich_tickers.py \
    --watchlist-root processed/universe/info_rich/daily \
    --from 2025-10-15 --to 2025-10-21 \
    --outdir processed/universe/info_rich \
    --topn processed/universe/info_rich/topN_12m.parquet \
    --top-k 200

Output:
  - {outdir}/info_rich_tickers_{from}_{to}.csv       (solo info-rich del periodo)
  - {outdir}/info_rich_plus_topN_{from}_{to}.csv     (info-rich + TopN runners)
"""
from __future__ import annotations
import argparse, datetime as dt
from pathlib import Path
from typing import Optional
import polars as pl

def log(msg: str):
    print(f"[{dt.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)

def list_watchlists(root: Path, date_from: dt.date, date_to: dt.date) -> list[Path]:
    """Lista watchlists en el rango de fechas"""
    watchlists = []
    cur = date_from
    while cur <= date_to:
        date_dir = root / f"date={cur.strftime('%Y-%m-%d')}"
        watchlist_path = date_dir / "watchlist.parquet"
        if watchlist_path.exists():
            watchlists.append(watchlist_path)
        cur += dt.timedelta(days=1)

    return sorted(watchlists)

def extract_info_rich_tickers(watchlists: list[Path]) -> pl.DataFrame:
    """
    Lee todas las watchlists, filtra info_rich=True, retorna tickers únicos
    """
    if not watchlists:
        log("[WARN] No se encontraron watchlists")
        return pl.DataFrame(schema={"ticker": pl.Utf8})

    log(f"Leyendo {len(watchlists)} watchlists...")

    dfs = []
    for path in watchlists:
        try:
            df = pl.read_parquet(path)
            dfs.append(df)
        except Exception as e:
            log(f"[WARN] Error leyendo {path}: {e}")

    if not dfs:
        return pl.DataFrame(schema={"ticker": pl.Utf8})

    # Concatenar todas las watchlists
    all_data = pl.concat(dfs, how="vertical_relaxed")

    # Filtrar info_rich=True y obtener tickers únicos
    info_rich_tickers = (
        all_data
        .filter(pl.col("info_rich"))
        .select("ticker")
        .unique()
        .sort("ticker")
    )

    log(f"Tickers info-rich encontrados: {len(info_rich_tickers)}")

    return info_rich_tickers

def load_topn_tickers(topn_path: Path, top_k: int) -> pl.DataFrame:
    """
    Carga TopN_12m y retorna los top K tickers
    """
    if not topn_path.exists():
        log(f"[WARN] TopN no encontrado: {topn_path}")
        return pl.DataFrame(schema={"ticker": pl.Utf8})

    topn = pl.read_parquet(topn_path)

    # Ordenar por days_info_rich y last_seen, tomar top K
    top_tickers = (
        topn
        .sort(["days_info_rich_252", "last_seen"], descending=[True, True])
        .select("ticker")
        .head(top_k)
    )

    log(f"TopN tickers cargados: {len(top_tickers)}")

    return top_tickers

def merge_tickers(info_rich: pl.DataFrame, topn: pl.DataFrame) -> pl.DataFrame:
    """
    Merge de tickers info-rich + TopN (únicos)
    """
    if topn.is_empty():
        return info_rich

    merged = (
        pl.concat([info_rich, topn], how="vertical_relaxed")
        .unique()
        .sort("ticker")
    )

    log(f"Tickers merged: {len(merged)} (info-rich: {len(info_rich)}, topN: {len(topn)})")

    return merged

def write_csv(tickers: pl.DataFrame, output_path: Path):
    """Escribe CSV con tickers"""
    if tickers.is_empty():
        log(f"[WARN] No hay tickers para escribir en {output_path}")
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)
    tickers.write_csv(output_path)

    log(f"CSV escrito: {output_path} ({len(tickers)} tickers)")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--watchlist-root", required=True, help="processed/universe/info_rich/daily")
    ap.add_argument("--from", dest="date_from", required=True, help="YYYY-MM-DD")
    ap.add_argument("--to", dest="date_to", required=True, help="YYYY-MM-DD")
    ap.add_argument("--outdir", required=True, help="processed/universe/info_rich")
    ap.add_argument("--topn", type=str, default=None, help="processed/universe/info_rich/topN_12m.parquet")
    ap.add_argument("--top-k", type=int, default=200, help="Top K tickers de TopN_12m (default: 200)")
    args = ap.parse_args()

    watchlist_root = Path(args.watchlist_root)
    outdir = Path(args.outdir)

    date_from = dt.datetime.strptime(args.date_from, "%Y-%m-%d").date()
    date_to = dt.datetime.strptime(args.date_to, "%Y-%m-%d").date()

    log("=== EXTRACT INFO-RICH TICKERS ===")
    log(f"Watchlist root: {watchlist_root}")
    log(f"Rango: {date_from} -> {date_to}")
    log(f"Output dir: {outdir}")

    # 1. Listar watchlists
    watchlists = list_watchlists(watchlist_root, date_from, date_to)

    if not watchlists:
        log("[ERROR] No se encontraron watchlists en el rango")
        return

    log(f"Watchlists encontradas: {len(watchlists)}")

    # 2. Extraer tickers info-rich
    info_rich_tickers = extract_info_rich_tickers(watchlists)

    if info_rich_tickers.is_empty():
        log("[ERROR] No se encontraron tickers info-rich")
        return

    # 3. Escribir CSV de info-rich
    date_range_str = f"{date_from.strftime('%Y%m%d')}_{date_to.strftime('%Y%m%d')}"
    info_rich_csv = outdir / f"info_rich_tickers_{date_range_str}.csv"
    write_csv(info_rich_tickers, info_rich_csv)

    # 4. (Opcional) Merge con TopN_12m
    if args.topn:
        topn_path = Path(args.topn)
        topn_tickers = load_topn_tickers(topn_path, args.top_k)

        merged_tickers = merge_tickers(info_rich_tickers, topn_tickers)

        merged_csv = outdir / f"info_rich_plus_topN_{date_range_str}.csv"
        write_csv(merged_tickers, merged_csv)

    log("=== COMPLETADO ===")
    log(f"Info-rich CSV: {info_rich_csv}")
    if args.topn:
        log(f"Merged CSV: {merged_csv}")

if __name__ == "__main__":
    main()
