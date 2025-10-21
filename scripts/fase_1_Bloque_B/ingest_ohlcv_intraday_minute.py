#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ingest_ohlcv_intraday_minute.py  (version STREAMING, sin fuga de memoria)

- Descarga OHLCV 1-min de Polygon paginando con cursor.
- Escribe cada pagina directamente a disco por anio/mes (sin acumular en RAM).
- Usa requests.Session() con pool=1 (TLS estable) y SIN hilos internos.
- Idempotente: mergea y deduplica por 'minute'.

Uso tipico con launcher externo (paralelismo fuera):
  export POLYGON_API_KEY="tu_api_key"
  python ingest_ohlcv_intraday_minute.py \
    --tickers-csv processed/universe/cs_xnas_xnys_under2b_2025-10-21.csv \
    --outdir raw/polygon/ohlcv_intraday_1m \
    --from 2004-01-01 --to 2010-12-31 \
    --rate-limit 0.20 \
    --max-tickers-per-process 40
"""
import os, sys, io, gc, time, argparse, datetime as dt
from pathlib import Path
from typing import Dict, Any, Optional
import urllib.parse as urlparse

import requests
import polars as pl
from dotenv import load_dotenv
import certifi

# stdout/stderr UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

load_dotenv()

BASE_URL   = "https://api.polygon.io"
TIMEOUT    = 40
RETRY_MAX  = 8
BACKOFF    = 1.6
PAGE_LIMIT = 10000  # Desatascado: reduce "buffer allocation" errors
ADJUSTED   = True

def log(m: str) -> None:
    print(f"[{dt.datetime.now():%Y-%m-%d %H:%M:%S}] {m}", flush=True)

def parse_next_cursor(next_url: Optional[str]) -> Optional[str]:
    if not next_url:
        return None
    try:
        q = urlparse.urlparse(next_url).query
        qs = urlparse.parse_qs(q)
        cur = qs.get("cursor")
        return cur[0] if cur else None
    except Exception:
        return None

def build_session() -> requests.Session:
    s = requests.Session()
    # Pool mejorado para reutilizar conexiones SSL (evita overhead de handshake)
    adapter = requests.adapters.HTTPAdapter(pool_connections=2, pool_maxsize=3, max_retries=0)
    s.mount("https://", adapter)
    # Desactivar gzip para evitar "Unable to allocate output buffer"
    s.headers.update({"Accept-Encoding": "identity"})
    return s

def http_get_json(session: requests.Session, url: str, params: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
    last_error = None
    for k in range(1, RETRY_MAX + 1):
        try:
            r = session.get(url, params=params, headers=headers, timeout=TIMEOUT)
            if r.status_code == 429:
                sl = int(r.headers.get("Retry-After", "2"))
                log(f"429 Rate Limit -> sleep {sl}s")
                time.sleep(sl); continue
            if 500 <= r.status_code < 600:
                sl = min(30, BACKOFF ** k)
                log(f"{r.status_code} Server Error -> backoff {sl:.1f}s")
                time.sleep(sl); continue
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last_error = e
            msg = str(e).lower()
            if "certificate" in msg or "ssl" in msg:
                sl = 2  # retry rapido para SSL/TLS
            elif "allocate" in msg or "buffer" in msg or "decompress" in msg:
                sl = min(60, BACKOFF ** (k + 2))  # mas lento si es memoria/compresion
            else:
                sl = min(30, BACKOFF ** k)
            log(f"GET error {e} -> backoff {sl:.1f}s")
            time.sleep(sl)
    raise RuntimeError(f"Failed after {RETRY_MAX} attempts: {last_error}")

def normalize_page(results: list, ticker: str) -> pl.DataFrame:
    if not results:
        return pl.DataFrame({"ticker":[], "date":[], "minute":[], "t":[], "o":[], "h":[], "l":[], "c":[], "v":[], "n":[], "vw":[]})
    df = pl.from_dicts(results)
    # columnas esperadas de /v2/aggs: t, o, h, l, c, v, n, vw
    picks = {}
    for col, typ in [("t", pl.Int64), ("o", pl.Float64), ("h", pl.Float64),
                     ("l", pl.Float64), ("c", pl.Float64), ("v", pl.Float64),
                     ("n", pl.Int64), ("vw", pl.Float64)]:
        picks[col] = (df[col].cast(typ) if col in df.columns else pl.Series(name=col, values=[], dtype=typ))
    out = pl.DataFrame(picks)
    if out.height == 0:
        return pl.DataFrame({"ticker":[], "date":[], "minute":[], "t":[], "o":[], "h":[], "l":[], "c":[], "v":[], "n":[], "vw":[]})
    ts = pl.from_epoch(pl.col("t")/1000, time_unit="s")
    out = out.with_columns([
        ts.dt.strftime("%Y-%m-%d").alias("date"),
        ts.dt.strftime("%Y-%m-%d %H:%M").alias("minute"),
        pl.lit(ticker).alias("ticker")
    ]).select(["ticker","date","minute","t","o","h","l","c","v","n","vw"])
    return out

def write_page_by_month(df: pl.DataFrame, outdir: Path, ticker: str) -> int:
    """Escribe una pagina normalizada, particionando por anio/mes, merge idempotente."""
    if df.is_empty():
        return 0
    df = df.with_columns(pl.col("date").str.slice(0,7).alias("ym"))
    files = 0
    for ym, part in df.group_by("ym"):
        year, month = ym[0].split("-")
        pdir = outdir / ticker / f"year={year}" / f"month={month}"
        pdir.mkdir(parents=True, exist_ok=True)
        outp = pdir / "minute.parquet"
        part = part.drop("ym").sort(["date","minute"])
        if outp.exists():
            old = pl.read_parquet(outp)
            merged = pl.concat([old, part], how="vertical_relaxed")\
                       .unique(subset=["minute"], keep="last")\
                       .sort(["date","minute"])
            merged.write_parquet(outp)
            del old, merged
        else:
            part.write_parquet(outp)
        files += 1
        del part
    return files

def fetch_and_stream_write(session: requests.Session, api_key: str, ticker: str, from_date: str, to_date: str,
                           rate_limit_s: Optional[float], outdir: Path) -> str:
    url = f"{BASE_URL}/v2/aggs/ticker/{ticker}/range/1/minute/{from_date}/{to_date}"
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    params = {"adjusted": str(ADJUSTED).lower(), "sort": "asc", "limit": PAGE_LIMIT}

    cursor = None
    pages = 0
    rows_total = 0
    files_total = 0

    while True:
        p = params.copy()
        if cursor: p["cursor"] = cursor
        data = http_get_json(session, url, p, headers) or {}
        results = data.get("results") or []
        pages += 1
        rows_total += len(results)

        # normaliza y escribe esta pagina directamente
        df_page = normalize_page(results, ticker)
        files_total += write_page_by_month(df_page, outdir, ticker)

        # Extraer cursor ANTES de deletear data
        cursor = parse_next_cursor(data.get("next_url")) if data else None

        del df_page, results, data
        gc.collect()

        if not cursor:
            break
        if rate_limit_s and rate_limit_s > 0:
            time.sleep(rate_limit_s)

    return f"{ticker}: {rows_total:,} rows, {files_total} files ({pages} pages) [1m]"

def main():
    ap = argparse.ArgumentParser(description="Descarga OHLCV 1-min (streaming por pagina, sin acumulacion en RAM)")
    ap.add_argument("--tickers-csv", required=True, help="CSV con columna 'ticker'")
    ap.add_argument("--outdir", required=True, help="raw/polygon/ohlcv_intraday_1m")
    ap.add_argument("--from", dest="date_from", required=True, help="YYYY-MM-DD")
    ap.add_argument("--to", dest="date_to", required=True, help="YYYY-MM-DD")
    ap.add_argument("--rate-limit", type=float, default=0.125, help="segundos entre paginas (por proceso)")
    ap.add_argument("--max-tickers-per-process", type=int, default=30,
                    help="Max. tickers que procesara este proceso antes de salir (libera RAM). 0=sin limite")
    # (Compatibilidad) Aceptamos --max-workers pero lo ignoramos adrede:
    ap.add_argument("--max-workers", type=int, default=1, help="(IGNORADO) Paralelismo lo maneja el launcher.")
    args = ap.parse_args()

    api_key = os.getenv("POLYGON_API_KEY")
    if not api_key:
        sys.exit("ERROR: variable POLYGON_API_KEY no establecida")

    # TLS en Windows: configurar certificados SSL
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    log(f"Running INGESTOR: {__file__}")
    log(f"SSL_CERT_FILE={os.getenv('SSL_CERT_FILE')}")

    tickers = pl.read_csv(args.tickers_csv)["ticker"].drop_nulls().unique().to_list()
    outdir = Path(args.outdir); outdir.mkdir(parents=True, exist_ok=True)
    rate_limit = args.rate_limit if args.rate_limit and args.rate_limit > 0 else None

    session = build_session()

    log(f"Tickers: {len(tickers):,} | {args.date_from} -> {args.date_to} | rate={rate_limit}s/page")
    processed = 0
    results = []

    for t in tickers:
        try:
            res = fetch_and_stream_write(session, api_key, t, args.date_from, args.date_to, rate_limit, outdir)
            results.append(res)
        except Exception as e:
            results.append(f"{t}: ERROR {e}")
        processed += 1

        # checkpoint de progreso
        if processed % 25 == 0:
            log(f"Progreso {processed:,}/{len(tickers):,}")
            # flush a archivo de log incremental
            (outdir / "minute_download.partial.log").write_text("\n".join(results), encoding="utf-8")

        # kill-restart para liberar memoria a tope
        if args.max_tickers_per_process and processed >= args.max_tickers_per_process:
            log(f"Alcanzado --max-tickers-per-process={args.max_tickers_per_process}. Saliendo limpio para liberar RAM.")
            break

        gc.collect()

    # Log final (de lo procesado en este proceso)
    ok = sum("ERROR" not in r for r in results)
    err = len(results) - ok
    log_file = outdir / "minute_download.log"
    # append en vez de overwrite
    with open(log_file, "a", encoding="utf-8") as f:
        f.write("\n".join(results) + "\n")

    log(f"OK: {ok:,} | ERRORES: {err:,} | Log: {log_file}")

if __name__ == "__main__":
    main()
