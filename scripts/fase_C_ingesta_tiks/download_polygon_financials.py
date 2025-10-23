#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
download_polygon_financials.py
Descarga financials (quarterly + annual) de Polygon para detectar dilution y cash burn.

Endpoint: /vX/reference/financials

Uso:
  python download_polygon_financials.py \
    --tickers-csv processed/universe/info_rich/info_rich_tickers_20200101_20251021.csv \
    --outdir raw/polygon/financials \
    --timeframes quarterly annual \
    --lookback-quarters 20 \
    --lookback-years 10 \
    --workers 4 \
    --rate-limit 0.5 \
    --resume
"""

import os, sys, time, argparse
from pathlib import Path
from datetime import datetime
from typing import List, Optional

import polars as pl
import requests
import certifi

API_BASE = "https://api.polygon.io"
TIMEOUT = (10, 60)  # connect, read

def log(msg: str):
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)

def ensure_ssl_env():
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())

def build_session() -> requests.Session:
    s = requests.Session()
    adapter = requests.adapters.HTTPAdapter(pool_connections=2, pool_maxsize=3, max_retries=0)
    s.mount("https://", adapter)
    return s

def load_tickers(csv_path: Path) -> List[str]:
    df = pl.read_csv(csv_path)
    col = "ticker" if "ticker" in df.columns else df.columns[0]
    return df[col].unique().to_list()

def success_marker(path: Path):
    (path / "_SUCCESS").touch(exist_ok=True)

def exists_success(path: Path) -> bool:
    return (path / "_SUCCESS").exists()

def http_get_financials(session: requests.Session, ticker: str, timeframe: str,
                        limit: int, api_key: str) -> dict:
    """
    Get financials for ticker.
    timeframe: 'quarterly' or 'annual'
    """
    url = f"{API_BASE}/vX/reference/financials"
    params = {
        "ticker": ticker,
        "timeframe": timeframe,
        "limit": limit,
        "apiKey": api_key,
    }
    r = session.get(url, params=params, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()

def to_parquet_financials(out_parquet: Path, records: List[dict]):
    if not records:
        # Create empty parquet with minimal schema
        schema = {
            "ticker": pl.Utf8,
            "fiscal_period": pl.Utf8,
            "fiscal_year": pl.Utf8,
            "start_date": pl.Utf8,
            "end_date": pl.Utf8,
            "filing_date": pl.Utf8,
        }
        pl.DataFrame(schema=schema).write_parquet(out_parquet, compression="zstd", compression_level=2, statistics=False)
        return

    df = pl.from_dicts(records)
    out_parquet.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(out_parquet, compression="zstd", compression_level=2, statistics=False)

def backoff_sleep(k: int, kind: str, base: float) -> float:
    if kind == "ssl":
        return min(5.0, base)
    if kind == "429":
        return min(60.0, base * 2.0 + 5.0)
    return min(30.0, base)

def download_financials(session: requests.Session, ticker: str, timeframe: str,
                       limit: int, outdir: Path, api_key: str, rate_limit: float,
                       resume: bool):
    """
    Download financials for one ticker and one timeframe (quarterly or annual).
    """
    timeframe_path = outdir / ticker / timeframe
    if resume and exists_success(timeframe_path):
        log(f"{ticker} {timeframe}: resume skip (_SUCCESS)")
        return

    records: List[dict] = []
    base_sleep = rate_limit

    try:
        try:
            data = http_get_financials(session, ticker, timeframe, limit, api_key)
        except requests.HTTPError as e:
            code = e.response.status_code if e.response is not None else 0
            if code == 429:
                sl = backoff_sleep(0, "429", base_sleep)
                log(f"{ticker} {timeframe}: 429 Too Many Requests -> sleep {sl}s")
                time.sleep(sl)
                data = http_get_financials(session, ticker, timeframe, limit, api_key)
            else:
                raise
        except requests.exceptions.SSLError:
            sl = backoff_sleep(0, "ssl", base_sleep)
            log(f"{ticker} {timeframe}: SSL error -> sleep {sl}s")
            time.sleep(sl)
            data = http_get_financials(session, ticker, timeframe, limit, api_key)
        except requests.exceptions.RequestException as e:
            sl = backoff_sleep(0, "net", base_sleep)
            log(f"{ticker} {timeframe}: NET {e} -> sleep {sl}s")
            time.sleep(sl)
            data = http_get_financials(session, ticker, timeframe, limit, api_key)

        results = data.get("results", [])
        if results:
            # Flatten nested financials structure
            for item in results:
                flat = {
                    "ticker": ticker,
                    "cik": item.get("cik"),
                    "fiscal_period": item.get("fiscal_period"),
                    "fiscal_year": item.get("fiscal_year"),
                    "start_date": item.get("start_date"),
                    "end_date": item.get("end_date"),
                    "filing_date": item.get("filing_date"),
                    "acceptance_datetime": item.get("acceptance_datetime"),
                    "timeframe": timeframe,
                }

                # Extract financials fields
                financials = item.get("financials", {})

                # Cash Flow Statement
                cash_flow = financials.get("cash_flow_statement", {})
                flat.update({
                    "net_cash_flow_operating": cash_flow.get("net_cash_flow_from_operating_activities", {}).get("value"),
                    "net_cash_flow_financing": cash_flow.get("net_cash_flow_from_financing_activities", {}).get("value"),
                    "net_cash_flow_investing": cash_flow.get("net_cash_flow_from_investing_activities", {}).get("value"),
                    "free_cash_flow": cash_flow.get("net_cash_flow", {}).get("value"),
                })

                # Balance Sheet
                balance_sheet = financials.get("balance_sheet", {})
                flat.update({
                    "cash_and_equivalents": balance_sheet.get("cash_and_cash_equivalents", {}).get("value"),
                    "total_assets": balance_sheet.get("assets", {}).get("value"),
                    "current_assets": balance_sheet.get("current_assets", {}).get("value"),
                    "current_liabilities": balance_sheet.get("current_liabilities", {}).get("value"),
                    "total_debt": balance_sheet.get("long_term_debt", {}).get("value"),
                    "stockholders_equity": balance_sheet.get("equity", {}).get("value"),
                })

                # Income Statement
                income_statement = financials.get("income_statement", {})
                flat.update({
                    "revenues": income_statement.get("revenues", {}).get("value"),
                    "net_income": income_statement.get("net_income_loss", {}).get("value"),
                    "operating_expenses": income_statement.get("operating_expenses", {}).get("value"),
                    "rd_expenses": income_statement.get("research_and_development_expenses", {}).get("value"),
                })

                # Comprehensive Income
                comprehensive_income = financials.get("comprehensive_income", {})
                flat.update({
                    "basic_eps": comprehensive_income.get("basic_earnings_per_share", {}).get("value"),
                    "diluted_eps": comprehensive_income.get("diluted_earnings_per_share", {}).get("value"),
                    "shares_outstanding": comprehensive_income.get("basic_average_shares", {}).get("value"),
                    "shares_outstanding_diluted": comprehensive_income.get("diluted_average_shares", {}).get("value"),
                })

                records.append(flat)

        time.sleep(rate_limit)

        out_parquet = timeframe_path / "financials.parquet"
        to_parquet_financials(out_parquet, records)
        success_marker(timeframe_path)
        log(f"{ticker} {timeframe}: OK ({len(records)} periods)")

    except Exception as e:
        log(f"{ticker} {timeframe}: ERROR {e}")

def parse_args():
    ap = argparse.ArgumentParser(description="Descarga optimizada de financials Polygon")
    ap.add_argument("--tickers-csv", required=True, help="CSV con columna 'ticker'")
    ap.add_argument("--outdir", required=True, help="Directorio de salida (raw/polygon/financials)")
    ap.add_argument("--timeframes", nargs="+", default=["quarterly", "annual"], help="quarterly, annual, o ambos")
    ap.add_argument("--lookback-quarters", type=int, default=20, help="Quarters historicos (default 20 = 5 years)")
    ap.add_argument("--lookback-years", type=int, default=10, help="Years historicos (default 10)")
    ap.add_argument("--rate-limit", type=float, default=0.5, help="Segundos entre requests")
    ap.add_argument("--workers", type=int, default=4, help="Procesos concurrentes")
    ap.add_argument("--resume", action="store_true")
    return ap.parse_args()

def chunked(lst: List, size: int) -> List[List]:
    return [lst[i:i+size] for i in range(0, len(lst), size)]

def run_batch_worker(args_tuple):
    """Worker function for multiprocessing - must be module-level for Windows compatibility"""
    batch_tasks, outdir, api_key, rate_limit, resume = args_tuple
    session = build_session()
    results = []
    for (ticker, timeframe, limit) in batch_tasks:
        try:
            download_financials(session, ticker, timeframe, limit, outdir, api_key, rate_limit, resume)
            results.append((ticker, timeframe, "ok"))
        except Exception as e:
            log(f"ERROR in worker: {ticker} {timeframe}: {e}")
            results.append((ticker, timeframe, f"error: {e}"))
    return results

def main():
    ensure_ssl_env()
    args = parse_args()
    api_key = os.getenv("POLYGON_API_KEY")
    if not api_key:
        sys.exit("ERROR: falta POLYGON_API_KEY en el entorno")

    outdir = Path(args.outdir); outdir.mkdir(parents=True, exist_ok=True)
    tickers = load_tickers(Path(args.tickers_csv))

    # Build tasks (ticker x timeframe)
    tasks = []
    for ticker in tickers:
        if "quarterly" in args.timeframes:
            tasks.append((ticker, "quarterly", args.lookback_quarters))
        if "annual" in args.timeframes:
            tasks.append((ticker, "annual", args.lookback_years))

    log(f"Tickers: {len(tickers):,} | Tareas: {len(tasks):,} (timeframes: {args.timeframes})")

    # Execute in micro-batches
    BATCH = 10  # 10 tasks per micro-batch
    rate_limit = args.rate_limit
    resume = args.resume

    from concurrent.futures import ProcessPoolExecutor, as_completed

    batches = chunked(tasks, BATCH)
    started = time.time()

    # Prepare arguments for each worker
    worker_args = [(bt, outdir, api_key, rate_limit, resume) for bt in batches]

    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futs = [ex.submit(run_batch_worker, wa) for wa in worker_args]
        done = 0
        total_ok = 0
        total_err = 0
        for f in as_completed(futs):
            done += 1
            try:
                results = f.result()
                ok_count = sum(1 for r in results if r[2] == "ok")
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
