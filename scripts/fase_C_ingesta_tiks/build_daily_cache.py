#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
build_daily_cache.py
Genera cache diario desde OHLCV 1-min con todas las optimizaciones:
- RVOL 30 sesiones (rolling por filas, no dias calendario)
- Join SCD-2 temporal con market cap
- Idempotencia con MANIFEST.json + _SUCCESS
- ZSTD compression level 2
- Paralelizacion con 8 workers

Uso:
  # Backfill completo
  python build_daily_cache.py \
    --intraday-root raw/polygon/ohlcv_intraday_1m \
    --outdir processed/daily_cache \
    --from 2020-01-01 --to 2025-10-21 \
    --parallel 8

  # Incremental (EOD)
  python build_daily_cache.py \
    --intraday-root raw/polygon/ohlcv_intraday_1m \
    --outdir processed/daily_cache \
    --from 2025-10-22 --to 2025-10-22 \
    --incremental
"""
from __future__ import annotations
import argparse, datetime as dt, json, time, hashlib
from pathlib import Path
from typing import List, Optional
from multiprocessing import Pool
import polars as pl

def log(msg: str):
    print(f"[{dt.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)

def ticker_exists_and_complete(ticker_dir: Path, date_from: dt.date, date_to: dt.date) -> bool:
    """Check si ticker ya tiene datos completos en el rango (para --incremental)"""
    if not ticker_dir.exists():
        return False

    parquet = ticker_dir / "daily.parquet"
    success = ticker_dir / "_SUCCESS"

    if not (parquet.exists() and success.exists()):
        return False

    # Leer fechas existentes
    try:
        df = pl.read_parquet(parquet, columns=["trading_day"])
        dates_existing = set(df["trading_day"].to_list())

        # Generar fechas esperadas (TODO: usar calendario de mercado real)
        cur = date_from
        dates_expected = set()
        while cur <= date_to:
            # Simplificacion: excluir fines de semana
            if cur.weekday() < 5:  # 0-4 = Lun-Vie
                dates_expected.add(cur)
            cur += dt.timedelta(days=1)

        # Si tiene todas las fechas esperadas, skip
        return dates_expected.issubset(dates_existing)
    except Exception as e:
        log(f"[WARN] Error checking {ticker_dir.name}: {e}")
        return False

def list_tickers_from_intraday(root: Path) -> List[str]:
    """Lista todos los tickers que tienen datos 1-min"""
    tickers = []
    for tdir in root.iterdir():
        if tdir.is_dir() and not tdir.name.startswith("_"):
            tickers.append(tdir.name)
    return sorted(tickers)

def load_1m_for_ticker(root: Path, ticker: str, date_from: dt.date, date_to: dt.date) -> pl.DataFrame:
    """
    Carga 1-min para 1 ticker en rango, procesando por mes (evita re-lecturas)
    """
    tdir = root / ticker
    if not tdir.exists():
        return pl.DataFrame()

    # Generar lista de (year, month) en el rango
    months = []
    cur = date_from
    while cur <= date_to:
        ym = (cur.year, cur.month)
        if ym not in months:
            months.append(ym)
        # Avanzar al siguiente mes
        if cur.month == 12:
            cur = dt.date(cur.year + 1, 1, 1)
        else:
            cur = dt.date(cur.year, cur.month + 1, 1)

    # Leer todos los meses a la vez (lazy)
    paths = []
    for y, m in months:
        p = tdir / f"year={y}" / f"month={m:02d}" / "minute.parquet"
        if p.exists():
            paths.append(p)

    if not paths:
        return pl.DataFrame()

    # Lazy read + filter por rango de fechas
    df = (
        pl.scan_parquet(paths)
        .filter(
            (pl.col("date") >= date_from.strftime("%Y-%m-%d")) &
            (pl.col("date") <= date_to.strftime("%Y-%m-%d"))
        )
        .select(["date", "c", "v", "vw", "n"])  # Solo columnas necesarias
        .collect()
    )

    if df.is_empty():
        return df

    # Añadir ticker
    df = df.with_columns(pl.lit(ticker).alias("ticker"))

    return df

def aggregate_to_daily(df_1m: pl.DataFrame) -> pl.DataFrame:
    """
    Agrega 1-min a diario por ticker-fecha
    Calcula: close_d, vol_d, dollar_vol_d, vwap_d, session_rows, has_gaps
    """
    if df_1m.is_empty():
        return pl.DataFrame()

    # Parsear fecha a Date
    df_1m = df_1m.with_columns(
        pl.col("date").str.strptime(pl.Date, "%Y-%m-%d").alias("trading_day")
    )

    # Agregar por ticker-trading_day
    daily = (
        df_1m.group_by(["ticker", "trading_day"])
        .agg([
            pl.col("c").last().alias("close_d"),
            pl.col("v").sum().alias("vol_d"),
            (pl.col("v") * pl.col("vw")).sum().alias("dollar_vol_d_raw"),
            pl.col("v").sum().alias("vol_sum"),  # Para VWAP
            pl.col("n").count().alias("session_rows"),  # Nro de barras 1m
        ])
        .with_columns([
            # VWAP = sum(v*vw) / sum(v) con proteccion divide-by-zero
            (pl.col("dollar_vol_d_raw") / pl.when(pl.col("vol_sum") > 0).then(pl.col("vol_sum")).otherwise(None)).alias("vwap_d"),
            # Dollar volume
            pl.col("dollar_vol_d_raw").alias("dollar_vol_d"),
            # has_gaps: session_rows < 390 (RTH = Regular Trading Hours)
            # Nota: Si incluyes pre/post-market, ajustar umbral
            (pl.col("session_rows") < 390).alias("has_gaps"),
        ])
        .select([
            "ticker", "trading_day", "close_d", "vol_d",
            "dollar_vol_d", "vwap_d", "session_rows", "has_gaps"
        ])
        .sort(["ticker", "trading_day"])
    )

    return daily

def compute_features(daily: pl.DataFrame) -> pl.DataFrame:
    """
    Calcula features:
    - pctchg_d (% change diario)
    - return_d (log return)
    - rvol30 (RVOL 30 SESIONES - rolling por filas, no dias calendario)

    Nota: min_periods=1 permite calcular RVOL desde el primer dia
    """
    if daily.is_empty():
        return daily

    # Calcular por ticker (ordenado por trading_day)
    features = (
        daily.sort(["ticker", "trading_day"])
        .with_columns([
            # Close anterior (por ticker)
            pl.col("close_d").shift(1).over("ticker").alias("close_prev"),
            # MA 30 sesiones (rolling por FILAS, no dias calendario)
            # min_periods=1 permite calcular desde el primer dia disponible
            pl.col("vol_d").rolling_mean(window_size=30, min_periods=1).over("ticker").alias("vol_30s_ma"),
        ])
        .with_columns([
            # % change diario
            ((pl.col("close_d") / pl.col("close_prev")) - 1.0).alias("pctchg_d"),
            # Log return
            (pl.col("close_d") / pl.col("close_prev")).log().alias("return_d"),
            # RVOL30 = vol_d / MA30
            (pl.col("vol_d") / pl.col("vol_30s_ma")).alias("rvol30"),
        ])
        .select([
            "ticker", "trading_day", "close_d", "vol_d", "dollar_vol_d",
            "vwap_d", "pctchg_d", "return_d", "rvol30",
            "session_rows", "has_gaps"
        ])
    )

    return features

def join_market_cap_temporal(
    daily: pl.DataFrame,
    cap_parquet: Optional[str]
) -> pl.DataFrame:
    """
    Join temporal con SCD-2 (tickers_dim) para market cap por fecha
    effective_from <= trading_day < effective_to
    """
    if not cap_parquet or not Path(cap_parquet).exists():
        log(f"[WARN] Cap parquet no encontrado o no especificado, skip market_cap")
        return daily.with_columns(pl.lit(None).alias("market_cap_d"))

    # Leer dimension SCD-2
    dim = pl.read_parquet(cap_parquet).select([
        "ticker", "effective_from", "effective_to", "market_cap"
    ])

    # Normalizar fechas y cerrar open-ended con fecha futura
    dim = dim.with_columns([
        pl.col("effective_from").cast(pl.Date),
        pl.col("effective_to").cast(pl.Date).fill_null(pl.date(2099, 12, 31))  # Fix: effective_to null
    ])

    # Left join y filtro temporal
    joined = (
        daily.join(dim, on="ticker", how="left")
        .filter(
            (pl.col("effective_from") <= pl.col("trading_day")) &
            (pl.col("trading_day") < pl.col("effective_to"))
        )
        # Si hay solapes en SCD-2, quedarse con el registro mas reciente
        .sort(["ticker", "trading_day", "effective_from"], descending=[False, False, True])
        .unique(subset=["ticker", "trading_day"], keep="first")
        .select([*(daily.columns), "market_cap"])
        .rename({"market_cap": "market_cap_d"})
    )

    return joined

def process_ticker(args) -> dict:
    """
    Procesa 1 ticker: lee 1-min, agrega a diario, calcula features
    Retorna dict con metadata para MANIFEST
    """
    ticker, intraday_root, outdir, date_from, date_to, cap_parquet, incremental = args

    ticker_dir = outdir / f"ticker={ticker}"

    # Si incremental y ya existe completo, skip
    if incremental and ticker_exists_and_complete(ticker_dir, date_from, date_to):
        return {"ticker": ticker, "status": "skipped", "days": 0}

    try:
        # 1. Cargar 1-min
        df_1m = load_1m_for_ticker(Path(intraday_root), ticker, date_from, date_to)
        if df_1m.is_empty():
            return {"ticker": ticker, "status": "no_data", "days": 0}

        # 2. Agregar a diario
        daily = aggregate_to_daily(df_1m)

        # 3. Calcular features (rvol30, pctchg, return)
        daily = compute_features(daily)

        # 4. Join market cap temporal (opcional)
        if cap_parquet:
            daily = join_market_cap_temporal(daily, cap_parquet)
        else:
            daily = daily.with_columns(pl.lit(None).alias("market_cap_d"))

        # 5. Escribir parquet con ZSTD
        ticker_dir.mkdir(parents=True, exist_ok=True)
        outp = ticker_dir / "daily.parquet"
        daily.write_parquet(
            outp,
            compression="zstd",
            compression_level=2,
            statistics=False
        )

        # 6. Escribir _SUCCESS
        (ticker_dir / "_SUCCESS").touch()

        return {
            "ticker": ticker,
            "status": "success",
            "days": len(daily),
            "size_bytes": outp.stat().st_size if outp.exists() else 0
        }

    except Exception as e:
        log(f"[ERROR] {ticker}: {e}")
        return {"ticker": ticker, "status": "error", "error": str(e)}

def write_manifest(outdir: Path, metadata: List[dict], args):
    """Escribe MANIFEST.json con metadata del job"""
    manifest = {
        "timestamp": dt.datetime.now().isoformat(),
        "date_from": args.date_from,
        "date_to": args.date_to,
        "total_tickers": len(metadata),
        "success": sum(1 for m in metadata if m["status"] == "success"),
        "skipped": sum(1 for m in metadata if m["status"] == "skipped"),
        "errors": sum(1 for m in metadata if m["status"] == "error"),
        "total_days": sum(m.get("days", 0) for m in metadata),
        "total_bytes": sum(m.get("size_bytes", 0) for m in metadata),
        "tickers": metadata
    }

    # Hash parcial (primeros 10 tickers)
    hash_input = json.dumps(metadata[:10], sort_keys=True).encode()
    manifest["partial_hash"] = hashlib.sha256(hash_input).hexdigest()[:16]

    manifest_path = outdir / "MANIFEST.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    log(f"MANIFEST escrito: {manifest_path}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--intraday-root", required=True, help="raw/polygon/ohlcv_intraday_1m")
    ap.add_argument("--outdir", required=True, help="processed/daily_cache")
    ap.add_argument("--from", dest="date_from", required=True)
    ap.add_argument("--to", dest="date_to", required=True)
    ap.add_argument("--cap-filter-parquet", type=str, default=None, help="tickers_dim.parquet (SCD-2)")
    ap.add_argument("--parallel", type=int, default=8, help="Procesos concurrentes")
    ap.add_argument("--incremental", action="store_true", help="Skip tickers ya completos")
    args = ap.parse_args()

    intraday_root = Path(args.intraday_root)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    date_from = dt.datetime.strptime(args.date_from, "%Y-%m-%d").date()
    date_to = dt.datetime.strptime(args.date_to, "%Y-%m-%d").date()

    log(f"=== BUILD DAILY CACHE ===")
    log(f"Intraday root: {intraday_root}")
    log(f"Output dir: {outdir}")
    log(f"Rango: {date_from} -> {date_to}")
    log(f"Paralelo: {args.parallel} workers")
    log(f"Incremental: {args.incremental}")

    # Listar tickers
    tickers = list_tickers_from_intraday(intraday_root)
    log(f"Tickers encontrados: {len(tickers)}")

    if args.incremental:
        # Filtrar ya completos
        tickers_pending = [
            t for t in tickers
            if not ticker_exists_and_complete(
                outdir / f"ticker={t}", date_from, date_to
            )
        ]
        log(f"Incremental: {len(tickers) - len(tickers_pending)} ya completos, {len(tickers_pending)} pendientes")
        tickers = tickers_pending

    if not tickers:
        log("No hay tickers para procesar")
        return

    # Preparar argumentos para workers
    task_args = [
        (t, str(intraday_root), outdir, date_from, date_to, args.cap_filter_parquet, args.incremental)
        for t in tickers
    ]

    # Procesar en paralelo
    start_time = time.time()

    if args.parallel > 1:
        with Pool(processes=args.parallel) as pool:
            results = pool.map(process_ticker, task_args)
    else:
        results = [process_ticker(task) for task in task_args]

    elapsed = time.time() - start_time

    # Resumen
    success = sum(1 for r in results if r["status"] == "success")
    skipped = sum(1 for r in results if r["status"] == "skipped")
    errors = sum(1 for r in results if r["status"] == "error")

    log(f"=== COMPLETADO ===")
    log(f"Tiempo: {elapsed/60:.1f} min")
    log(f"Success: {success}, Skipped: {skipped}, Errors: {errors}")
    log(f"Velocidad: {success/(elapsed/3600):.1f} tickers/hora")

    # Escribir MANIFEST
    write_manifest(outdir, results, args)

    # _SUCCESS global
    (outdir / "_SUCCESS").touch()
    log(f"Cache completo: {outdir}")

if __name__ == "__main__":
    main()
