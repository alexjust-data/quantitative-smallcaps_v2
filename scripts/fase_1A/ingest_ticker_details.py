#!/usr/bin/env python
# ingest_ticker_details.py
import os, sys, time, argparse, datetime as dt
from pathlib import Path
import requests, polars as pl
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "https://api.polygon.io"
TIMEOUT = 20
MAX_WORKERS = 32

def log(msg): print(f"[{dt.datetime.now():%F %T}] {msg}", flush=True)

def get(api_key, url):
    for k in range(6):
        try:
            r = requests.get(url, timeout=TIMEOUT, headers={"Authorization": f"Bearer {api_key}"})
            if r.status_code == 429:
                time.sleep(int(r.headers.get("Retry-After", "2")))
                continue
            r.raise_for_status()
            return r.json().get("results", {})
        except Exception as e:
            time.sleep(1.5 * (k + 1))
    return {}

def fetch_one(api_key, t):
    url = f"{BASE_URL}/v3/reference/tickers/{t}"
    d = get(api_key, url) or {}
    d["ticker"] = t
    d["as_of_date"] = dt.date.today().isoformat()
    return d

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapdir", required=True, help="Dir del snapshot del paso 1 (ej: raw/polygon/reference/tickers_snapshot/snapshot_date=2025-10-19)")
    ap.add_argument("--outdir", required=True, help="Salida: raw/polygon/reference/ticker_details")
    ap.add_argument("--only-exchanges", default="XNAS,XNYS,ARCX", help="Filtro de exchanges (coma). Vacío = todos")
    ap.add_argument("--max-workers", type=int, default=MAX_WORKERS)
    args = ap.parse_args()

    api_key = os.getenv("POLYGON_API_KEY")
    if not api_key: sys.exit("Falta POLYGON_API_KEY")

    snap = Path(args.snapdir)
    if not snap.exists(): sys.exit("Snapshot no encontrado")

    df = pl.read_parquet(snap / "tickers.parquet")
    if args.only_exchanges:
        allow = set([x.strip().upper() for x in args.only_exchanges.split(",") if x.strip()])
        if "primary_exchange" in df.columns:
            df = df.filter(pl.col("primary_exchange").is_in(list(allow)))

    tickers = df["ticker"].drop_nulls().unique().to_list()
    log(f"Tickers a detallar: {len(tickers):,}")

    outdir = Path(args.outdir) / f"as_of_date={dt.date.today().isoformat()}"
    outdir.mkdir(parents=True, exist_ok=True)

    rows = []
    with ThreadPoolExecutor(max_workers=args.max_workers) as ex:
        futs = {ex.submit(fetch_one, api_key, t): t for t in tickers}
        for i, fut in enumerate(as_completed(futs), 1):
            rows.append(fut.result())
            if i % 1000 == 0: log(f"{i:,} detalles descargados")

    pl.from_dicts(rows).write_parquet(outdir / "details.parquet")
    log(f"Escrito: {outdir/'details.parquet'}")

if __name__ == "__main__":
    main()
