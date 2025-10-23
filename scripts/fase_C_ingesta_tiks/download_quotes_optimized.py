#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
download_quotes_optimized.py
Descarga quotes (BBO - Best Bid and Offer) de Polygon con:
- Modo watchlists: solo dias info-rich (maxima eficiencia)
Optimizado: PAGE_LIMIT=50k, keep-alive, ZSTD, _SUCCESS, resume, backoff diferenciando errores.

Uso (watchlists):
  python download_quotes_optimized.py \
    --tickers-csv processed/universe/info_rich/info_rich_tickers_20200101_20251021.csv \
    --watchlist-root processed/universe/info_rich/daily \
    --outdir raw/polygon/quotes \
    --from 2020-01-01 --to 2025-10-21 \
    --mode watchlists --page-limit 50000 --rate-limit 0.15 --workers 8 --resume
"""

import os, sys, time, math, argparse, itertools, json
from pathlib import Path
from datetime import datetime, timedelta, date
from typing import List, Dict, Tuple, Optional

import polars as pl
import requests
import certifi

API_BASE = "https://api.polygon.io"
PAGE_LIMIT_DEFAULT = 50_000
TIMEOUT = (10, 60)  # connect, read

def log(msg: str):
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)

def ensure_ssl_env():
    # Hereda o fija SSL_CERT_FILE para Windows
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())

def build_session() -> requests.Session:
    s = requests.Session()
    adapter = requests.adapters.HTTPAdapter(pool_connections=2, pool_maxsize=3, max_retries=0)
    s.mount("https://", adapter)
    # Evita gzip si te daba "Unable to allocate output buffer" (descomenta para forzar sin compresión)
    # s.headers.update({"Accept-Encoding": "identity"})
    return s

def month_iter(dfrom: date, dto: date) -> List[Tuple[date, date]]:
    # Devuelve [(primer_dia_mes, primer_dia_mes_siguiente), ...] intersectado con [dfrom, dto]
    cur = date(dfrom.year, dfrom.month, 1)
    res = []
    while cur <= dto:
        if cur.month == 12:
            nxt = date(cur.year + 1, 1, 1)
        else:
            nxt = date(cur.year, cur.month + 1, 1)
        start = max(cur, dfrom)
        end = min(dto + timedelta(days=1), nxt)  # end exclusive
        if start < end:
            res.append((start, end))
        cur = nxt
    return res

def load_tickers(csv_path: Path) -> List[str]:
    df = pl.read_csv(csv_path)
    col = "ticker" if "ticker" in df.columns else df.columns[0]
    return df[col].unique().to_list()

def load_info_rich_days(watchlist_root: Path, dfrom: date, dto: date, allowed_tickers: Optional[set]) -> Dict[str, List[date]]:
    # Lee todos los watchlist.parquet en [dfrom, dto] y devuelve {ticker: [dates...]} para info_rich True
    out: Dict[str, List[date]] = {}
    today = date.today()
    # paths tipo: processed/universe/info_rich/daily/date=YYYY-MM-DD/watchlist.parquet
    for day in (dfrom + timedelta(n) for n in range((dto - dfrom).days + 1)):
        # Skip future dates (bug fix: avoid API 400 errors for dates > today)
        if day > today:
            continue
        p = watchlist_root / f"date={day.isoformat()}" / "watchlist.parquet"
        if not p.exists():
            continue
        df = pl.read_parquet(p)
        if "info_rich" not in df.columns:
            continue
        sub = df.filter(pl.col("info_rich") == True).select(["ticker"])
        if allowed_tickers:
            sub = sub.filter(pl.col("ticker").is_in(list(allowed_tickers)))
        for t in sub["ticker"].to_list():
            out.setdefault(t, []).append(day)
    return out

def success_marker(path: Path):
    (path / "_SUCCESS").touch(exist_ok=True)

def exists_success(path: Path) -> bool:
    return (path / "_SUCCESS").exists()

def http_get_quotes(session: requests.Session, ticker: str, t_from_iso: str, t_to_iso: str,
                    page_limit: int, api_key: str, cursor: Optional[str] = None) -> dict:
    # v3 quotes con timestamp range; usa paginacion por cursor
    url = f"{API_BASE}/v3/quotes/{ticker}"
    params = {
        "limit": page_limit,
        "sort": "asc",
        "timestamp.gte": f"{t_from_iso}T00:00:00Z",
        "timestamp.lt":  f"{t_to_iso}T00:00:00Z",
        "apiKey": api_key,
    }
    headers = {}
    if cursor:
        # Polygon permite cursor en query o next_url completo; preferimos query limpia
        params["cursor"] = cursor
    r = session.get(url, params=params, headers=headers, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()

def to_parquet_quotes(out_parquet: Path, records: List[dict]):
    if not records:
        # crea parquet vacio con esquema minimo
        schema = {
            "t": pl.Datetime, "bid_price": pl.Float64, "bid_size": pl.Int64,
            "ask_price": pl.Float64, "ask_size": pl.Int64, "conditions": pl.List(pl.Utf8)
        }
        pl.DataFrame(schema=schema).write_parquet(out_parquet, compression="zstd", compression_level=2, statistics=False)
        return
    # Campos tipicos v3 quotes: sip_timestamp (t), bid_price, bid_size, ask_price, ask_size, conditions...
    df = pl.from_records(records)
    # Normalizacion de columnas
    cols = df.columns
    mapping = {}
    if "sip_timestamp" in cols: mapping["sip_timestamp"] = "t"
    # Polygon v3 quotes ya usa bid_price, bid_size, ask_price, ask_size directamente
    if mapping:
        df = df.rename(mapping)
    # Tipos
    if "t" in df.columns:
        df = df.with_columns(pl.col("t").cast(pl.Datetime(time_unit="us")))
    # Escribe
    out_parquet.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(out_parquet, compression="zstd", compression_level=2, statistics=False)

def backoff_sleep(k: int, kind: str, base: float) -> float:
    # Diferencia SSL / memoria / 429
    if kind == "ssl":
        return min(5.0, base)  # rápido para SSL intermitente
    if kind == "mem":
        return min(60.0, base * 2.0 + 2.0)  # más pausado
    if kind == "429":
        return min(60.0, base * 2.0 + 5.0)
    return min(30.0, base)

def download_span(session: requests.Session, ticker: str, span_from: date, span_to: date,
                  outdir: Path, page_limit: int, api_key: str, rate_limit: float,
                  layout: str, resume: bool):
    """
    layout:
     - "months": escribe a year=YYYY/month=MM
     - "watchlists": escribe a date=YYYY-MM-DD (día a día)
    """
    if layout == "months":
        # un span puede ser un mes exacto; escribe un parquet por mes
        y, m = span_from.year, span_from.month
        month_path = outdir / ticker / f"year={y:04d}" / f"month={m:02d}"
        if resume and exists_success(month_path):
            log(f"{ticker} {y}-{m:02d}: resume skip (_SUCCESS)")
            return
        records: List[dict] = []
        cursor = None
        base_sleep = rate_limit
        try:
            while True:
                try:
                    data = http_get_quotes(session, ticker, span_from.isoformat(), span_to.isoformat(),
                                           page_limit, api_key, cursor)
                except requests.HTTPError as e:
                    code = e.response.status_code if e.response is not None else 0
                    if code == 429:
                        sl = backoff_sleep(0, "429", base_sleep)
                        log(f"{ticker} {y}-{m:02d}: 429 Too Many Requests -> sleep {sl}s")
                        time.sleep(sl)
                        continue
                    raise
                except requests.exceptions.SSLError:
                    sl = backoff_sleep(0, "ssl", base_sleep)
                    log(f"{ticker} {y}-{m:02d}: SSL error -> sleep {sl}s")
                    time.sleep(sl); continue
                except requests.exceptions.RequestException as e:
                    sl = backoff_sleep(0, "net", base_sleep)
                    log(f"{ticker} {y}-{m:02d}: NET {e} -> sleep {sl}s")
                    time.sleep(sl); continue

                r = data.get("results", [])
                if r:
                    records.extend(r)
                cursor = data.get("next_url") or data.get("nextUrl") or data.get("next_url".upper())
                # Polygon suele devolver next_url completo; extrae cursor si procede
                if cursor and "cursor=" in cursor:
                    cursor = cursor.split("cursor=")[-1]
                else:
                    cursor = data.get("next_page_token") or None

                time.sleep(rate_limit)
                if not cursor:
                    break

            out_parquet = month_path / "quotes.parquet"
            to_parquet_quotes(out_parquet, records)
            success_marker(month_path)
            log(f"{ticker} {y}-{m:02d}: OK ({len(records):,} quotes)")

        except Exception as e:
            log(f"{ticker} {y}-{m:02d}: ERROR {e}")

    else:
        # layout watchlists: un parquet por día (date=YYYY-MM-DD)
        d = span_from
        day_path = outdir / ticker / f"date={d.isoformat()}"
        if resume and exists_success(day_path):
            log(f"{ticker} {d}: resume skip (_SUCCESS)")
            return
        records: List[dict] = []
        cursor = None
        base_sleep = rate_limit
        try:
            while True:
                try:
                    data = http_get_quotes(session, ticker, d.isoformat(), (d + timedelta(days=1)).isoformat(),
                                           page_limit, api_key, cursor)
                except requests.HTTPError as e:
                    code = e.response.status_code if e.response is not None else 0
                    if code == 429:
                        sl = backoff_sleep(0, "429", base_sleep)
                        log(f"{ticker} {d}: 429 Too Many Requests -> sleep {sl}s")
                        time.sleep(sl); continue
                    raise
                except requests.exceptions.SSLError:
                    sl = backoff_sleep(0, "ssl", base_sleep)
                    log(f"{ticker} {d}: SSL error -> sleep {sl}s")
                    time.sleep(sl); continue
                except requests.exceptions.RequestException as e:
                    sl = backoff_sleep(0, "net", base_sleep)
                    log(f"{ticker} {d}: NET {e} -> sleep {sl}s")
                    time.sleep(sl); continue

                r = data.get("results", [])
                if r:
                    records.extend(r)

                cursor = data.get("next_url") or data.get("nextUrl") or data.get("next_url".upper())
                if cursor and "cursor=" in cursor:
                    cursor = cursor.split("cursor=")[-1]
                else:
                    cursor = data.get("next_page_token") or None

                time.sleep(rate_limit)
                if not cursor:
                    break

            out_parquet = day_path / "quotes.parquet"
            to_parquet_quotes(out_parquet, records)
            success_marker(day_path)
            log(f"{ticker} {d}: OK ({len(records):,} quotes)")

        except Exception as e:
            log(f"{ticker} {d}: ERROR {e}")

def parse_args():
    ap = argparse.ArgumentParser(description="Descarga optimizada de quotes (BBO) Polygon")
    ap.add_argument("--tickers-csv", required=True, help="CSV con columna 'ticker'")
    ap.add_argument("--outdir", required=True, help="Directorio de salida (raw/polygon/quotes)")
    ap.add_argument("--from", dest="date_from", required=True, help="YYYY-MM-DD")
    ap.add_argument("--to", dest="date_to", required=True, help="YYYY-MM-DD")
    ap.add_argument("--mode", choices=["months","watchlists"], default="months")
    ap.add_argument("--watchlist-root", default="processed/universe/info_rich/daily", help="Necesario en modo watchlists")
    ap.add_argument("--page-limit", type=int, default=PAGE_LIMIT_DEFAULT)
    ap.add_argument("--rate-limit", type=float, default=0.15)
    ap.add_argument("--workers", type=int, default=8, help="Procesos concurrentes")
    ap.add_argument("--resume", action="store_true")
    return ap.parse_args()

def chunked(lst: List[str], size: int) -> List[List[str]]:
    return [lst[i:i+size] for i in range(0, len(lst), size)]

def run_batch_worker(args_tuple):
    """Worker function for multiprocessing - must be module-level for Windows compatibility"""
    batch_tasks, outdir, page_limit, api_key, rate_limit, resume = args_tuple
    session = build_session()
    results = []
    for (t, a, b, layout) in batch_tasks:
        try:
            download_span(session, t, a, b, outdir, page_limit, api_key, rate_limit, layout, resume)
            results.append((t, a, b, "ok"))
        except Exception as e:
            log(f"ERROR in worker: {t} {a}: {e}")
            results.append((t, a, b, f"error: {e}"))
    return results

def main():
    ensure_ssl_env()
    args = parse_args()
    api_key = os.getenv("POLYGON_API_KEY")
    if not api_key:
        sys.exit("ERROR: falta POLYGON_API_KEY en el entorno")

    outdir = Path(args.outdir); outdir.mkdir(parents=True, exist_ok=True)
    tickers = load_tickers(Path(args.tickers_csv))
    dfrom = datetime.strptime(args.date_from, "%Y-%m-%d").date()
    dto   = datetime.strptime(args.date_to, "%Y-%m-%d").date()

    # Construye tareas (ticker × spans)
    tasks: List[Tuple[str, date, date, str]] = []
    if args.mode == "months":
        spans = month_iter(dfrom, dto)
        for t in tickers:
            for (a,b) in spans:
                tasks.append((t, a, b, "months"))
    else:
        # watchlists: sólo días info-rich
        days_by_ticker = load_info_rich_days(Path(args.watchlist_root), dfrom, dto, set(tickers))
        for t, days in days_by_ticker.items():
            for d in days:
                tasks.append((t, d, d, "watchlists"))
        log(f"Tareas (watchlists): {sum(len(v) for v in days_by_ticker.values()):,} días info-rich en {len(days_by_ticker)} tickers")

    # Ejecuta en micro-batches (evitar procesos zombis / fuga RAM)
    BATCH = 20  # 20 tareas por micro-batch; ajusta si ves RAM alta
    rate_limit = args.rate_limit
    page_limit = args.page_limit
    resume = args.resume

    from concurrent.futures import ProcessPoolExecutor, as_completed

    log(f"Tickers: {len(tickers):,} | Tareas: {len(tasks):,} | Workers: {args.workers} | Mode: {args.mode}")
    batches = chunked(tasks, BATCH)
    started = time.time()

    # Prepare arguments for each worker
    worker_args = [(bt, outdir, page_limit, api_key, rate_limit, resume) for bt in batches]

    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futs = [ex.submit(run_batch_worker, wa) for wa in worker_args]
        done = 0
        total_ok = 0
        total_err = 0
        for f in as_completed(futs):
            done += 1
            try:
                results = f.result()
                ok_count = sum(1 for r in results if r[3] == "ok")
                err_count = len(results) - ok_count
                total_ok += ok_count
                total_err += err_count
                log(f"Progreso: {done}/{len(batches)} batches ({done/len(batches)*100:.1f}%) | OK: {total_ok:,}, ERR: {total_err}")
            except Exception as e:
                total_err += BATCH
                log(f"Progreso: {done}/{len(batches)} batches - BATCH ERROR: {e}")
    log(f"FIN. Elapsed: {(time.time()-started)/60:.1f} min | Total OK: {total_ok:,} / Total ERR: {total_err}")

if __name__ == "__main__":
    main()
