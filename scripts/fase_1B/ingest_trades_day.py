#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ingest_trades_day.py
Descarga trades tick-level desde Polygon.io por día.
Útil para Bar Construction de alta precisión (Dollar/Volume/Imbalance Bars).

NOTA: Los trades son muy voluminosos. Recomendado empezar con ventanas pequeñas
(ej: 1-2 años) o subconjunto de tickers para prototipar.

Uso:
    export POLYGON_API_KEY="tu_api_key"
    python ingest_trades_day.py \
        --tickers-csv processed/universe/cs_xnas_xnys_under2b.csv \
        --outdir raw/polygon/trades \
        --from 2024-01-01 \
        --to 2024-12-31 \
        --max-workers 8
"""
import os
import sys
import time
import argparse
import datetime as dt
from pathlib import Path
import urllib.parse as urlparse
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import polars as pl

# Configuración
BASE_URL = "https://api.polygon.io"
TIMEOUT = 40
RETRY_MAX = 8
BACKOFF = 1.6
PAGE_LIMIT = 50000  # polygon v3/trades limit

def log(m):
    print(f"[{dt.datetime.now():%Y-%m-%d %H:%M:%S}] {m}", flush=True)

def parse_next_cursor(next_url: Optional[str]) -> Optional[str]:
    """Extrae cursor de URL completa retornada por Polygon"""
    if not next_url:
        return None
    try:
        q = urlparse.urlparse(next_url).query
        qs = urlparse.parse_qs(q)
        cur = qs.get("cursor")
        return cur[0] if cur else None
    except Exception:
        return None

def http_get_json(url: str, params: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
    """GET con reintentos exponenciales y manejo de rate limits"""
    last_error = None
    for attempt in range(1, RETRY_MAX + 1):
        try:
            r = requests.get(url, params=params, headers=headers, timeout=TIMEOUT)

            if r.status_code == 429:
                sleep_time = int(r.headers.get("Retry-After", "2"))
                log(f"429 Rate Limit -> sleep {sleep_time}s")
                time.sleep(sleep_time)
                continue

            if 500 <= r.status_code < 600:
                sleep_time = min(30, BACKOFF ** attempt)
                log(f"{r.status_code} Server Error -> backoff {sleep_time:.1f}s")
                time.sleep(sleep_time)
                continue

            r.raise_for_status()
            return r.json()

        except Exception as e:
            last_error = e
            sleep_time = min(30, BACKOFF ** attempt)
            log(f"GET error {e} -> backoff {sleep_time:.1f}s")
            time.sleep(sleep_time)

    raise RuntimeError(f"Failed after {RETRY_MAX} attempts: {last_error}")

def fetch_trades_day(api_key: str, ticker: str, day: str, limit: int = PAGE_LIMIT) -> List[Dict[str, Any]]:
    """Descarga todos los trades para un ticker en un día específico"""
    url = f"{BASE_URL}/v3/trades/{ticker}"
    headers = {"Authorization": f"Bearer {api_key}"}

    # Timestamps para el día completo (pre-market to after-hours)
    params = {
        "limit": limit,
        "timestamp.gte": f"{day} 04:00:00",  # Pre-market start
        "timestamp.lte": f"{day} 20:59:59",  # After-hours end
        "sort": "timestamp",
        "order": "asc",
    }

    rows: List[Dict[str, Any]] = []
    cursor = None
    pages = 0

    while True:
        p = params.copy()
        if cursor:
            p["cursor"] = cursor

        data = http_get_json(url, p, headers) or {}
        results = data.get("results") or []
        rows.extend(results)
        pages += 1

        # Extraer cursor
        cursor = (parse_next_cursor(data.get("next_url")) or
                 data.get("cursor") or
                 data.get("next_cursor"))

        if not cursor:
            break

    log(f"{ticker} {day}: {len(rows):,} trades ({pages} pages)")
    return rows

def rows_to_df(rows: List[Dict[str, Any]], ticker: str, day: str) -> pl.DataFrame:
    """Convierte resultados JSON a DataFrame Polars"""
    if not rows:
        return pl.DataFrame({
            "ticker": [],
            "day": [],
            "sip_ts": [],
            "price": [],
            "size": []
        })

    df = pl.from_dicts(rows)

    # Campos típicos v3/trades: price, size, sip_timestamp, conditions, exchange, id...
    # Estandarizamos mínimos necesarios para Bar Construction
    price = (df.get_column("price") if "price" in df.columns
            else pl.Series("price", [], pl.Float64))

    size = (df.get_column("size") if "size" in df.columns
           else pl.Series("size", [], pl.Float64))

    ts = (df.get_column("sip_timestamp") if "sip_timestamp" in df.columns
         else pl.Series("sip_timestamp", [], pl.Int64))

    out = pl.DataFrame({
        "ticker": pl.repeat(ticker, len(price), eager=True),
        "day": pl.repeat(day, len(price), eager=True),
        "sip_ts": ts.cast(pl.Int64),
        "price": price.cast(pl.Float64),
        "size": size.cast(pl.Float64),
    })

    return out.sort("sip_ts")

def write_trades(df: pl.DataFrame, outdir: Path, ticker: str, day: str) -> Path:
    """Escribe trades particionados por ticker/year/month/day"""
    if df.height == 0:
        # Crear archivo vacío para marcar que el día fue procesado
        p = outdir / ticker / f"day={day}" / "trades.parquet"
        p.parent.mkdir(parents=True, exist_ok=True)
        df.write_parquet(p)
        return p

    # Partición normal: ticker/year=YYYY/month=MM/day=YYYY-MM-DD/trades.parquet
    y, m = day[:4], day[5:7]
    p = outdir / ticker / f"year={y}" / f"month={m}" / f"day={day}" / "trades.parquet"
    p.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(p)
    return p

def daterange(d0: str, d1: str):
    """Genera rango de fechas entre d0 y d1 (inclusive)"""
    a = dt.date.fromisoformat(d0)
    b = dt.date.fromisoformat(d1)
    cur = a
    while cur <= b:
        yield cur.isoformat()
        cur += dt.timedelta(days=1)

def main():
    ap = argparse.ArgumentParser(description="Descarga trades tick-level desde Polygon")
    ap.add_argument("--tickers-csv", required=True,
                    help="CSV con columna 'ticker'")
    ap.add_argument("--outdir", required=True,
                    help="Directorio de salida (ej: raw/polygon/trades)")
    ap.add_argument("--from", dest="date_from", required=True,
                    help="Fecha inicio YYYY-MM-DD")
    ap.add_argument("--to", dest="date_to", required=True,
                    help="Fecha fin YYYY-MM-DD")
    ap.add_argument("--max-workers", type=int, default=8,
                    help="Workers paralelos (default: 8)")
    args = ap.parse_args()

    api_key = os.getenv("POLYGON_API_KEY")
    if not api_key:
        sys.exit("ERROR: variable POLYGON_API_KEY no establecida")

    # Leer lista de tickers
    tickers = pl.read_csv(args.tickers_csv)["ticker"].to_list()
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    # Generar tareas (ticker, día)
    tasks = []
    for t in tickers:
        for d in daterange(args.date_from, args.date_to):
            tasks.append((t, d))

    log(f"TRADES: {len(tickers):,} tickers × {len(list(daterange(args.date_from, args.date_to)))} días")
    log(f"Total tareas: {len(tasks):,}")
    log(f"Workers: {args.max_workers}")

    results = []

    with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        # Enviar todas las tareas
        futures = {
            executor.submit(fetch_trades_day, api_key, t, d): (t, d)
            for t, d in tasks
        }

        # Procesar resultados
        for i, future in enumerate(as_completed(futures), 1):
            ticker, day = futures[future]
            try:
                rows = future.result()

                if not rows:
                    results.append(f"{ticker} {day}: 0 trades (día sin datos)")
                    continue

                # Inferir ticker y día de los datos (fallback si no viene en respuesta)
                inferred_ticker = rows[0].get("T") or rows[0].get("ticker") or ticker
                if "sip_timestamp" in rows[0]:
                    inferred_day = dt.datetime.utcfromtimestamp(
                        rows[0]["sip_timestamp"] / 1e9
                    ).date().isoformat()
                else:
                    inferred_day = day

                df = rows_to_df(rows, inferred_ticker, inferred_day)
                write_trades(df, outdir, inferred_ticker, inferred_day)
                results.append(f"{ticker} {day}: {df.height:,} trades")

            except Exception as e:
                results.append(f"{ticker} {day}: ERROR {e}")

            if i % 200 == 0:
                log(f"Progreso {i:,}/{len(tasks):,}")

    # Guardar log de resultados
    ok = sum("ERROR" not in r for r in results)
    err = len(results) - ok

    log_file = outdir / "trades_download.log"
    log_file.write_text("\n".join(results), encoding="utf-8")

    log(f"\n=== COMPLETADO ===")
    log(f"OK: {ok:,} | ERRORES: {err:,}")
    log(f"Log: {log_file}")

if __name__ == "__main__":
    main()
