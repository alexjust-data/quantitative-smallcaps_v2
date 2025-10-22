#!/usr/bin/env python
# ingest_splits_dividends.py
import os, sys, time, argparse, datetime as dt
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import requests, polars as pl

BASE_URL = "https://api.polygon.io"
LIMIT = 1000
TIMEOUT = 25

def log(msg): print(f"[{dt.datetime.now():%F %T}] {msg}", flush=True)

def http_get(url, api_key, params=None):
    headers = {"Authorization": f"Bearer {api_key}"}
    for k in range(8):
        try:
            r = requests.get(url, headers=headers, params=params or {}, timeout=TIMEOUT)
            if r.status_code == 429:
                time.sleep(int(r.headers.get("Retry-After", "2")))
                continue
            if 500 <= r.status_code < 600:
                time.sleep(1.6 ** k)
                continue
            r.raise_for_status()
            return r.json()
        except Exception:
            time.sleep(1.6 ** k)
    return {}

def fetch_paged(path, api_key, extra_params=None):
    url = f"{BASE_URL}{path}"
    params = {"limit": LIMIT}
    if extra_params: params.update(extra_params)
    cursor = None
    total = 0
    page = 0
    while True:
        page += 1
        p = params.copy()
        if cursor: p["cursor"] = cursor
        data = http_get(url, api_key, p) or {}
        res = data.get("results") or []
        for x in res: yield x
        total += len(res)

        # Log progress every 10K records
        if total % 10000 == 0 and total > 0:
            log(f"{path}: {total:,} filas (pagina {page})")

        # Extraer cursor de next_url (puede ser URL completa o solo cursor)
        next_cursor = data.get("next_url") or data.get("next_url_cursor") or data.get("cursor") or data.get("next_cursor")
        if next_cursor and next_cursor.startswith("http"):
            # Extraer el parámetro cursor de la URL completa
            parsed = urlparse(next_cursor)
            cursor_params = parse_qs(parsed.query)
            next_cursor = cursor_params.get("cursor", [None])[0]
        cursor = next_cursor

        if not cursor: break
    log(f"{path}: {total:,} filas TOTAL")

def clean_splits(df: pl.DataFrame) -> pl.DataFrame:
    if df.height == 0: return df
    cast = {
        "ticker": pl.Utf8, "execution_date": pl.Utf8,
        "split_from": pl.Float64, "split_to": pl.Float64,
        "declared_date": pl.Utf8
    }
    for c,t in cast.items():
        if c in df.columns: df = df.with_columns(pl.col(c).cast(t))
    if all(c in df.columns for c in ("split_from","split_to")):
        df = df.with_columns((pl.col("split_from")/pl.col("split_to")).alias("ratio"))
    if "execution_date" in df.columns:
        df = df.sort(["ticker","execution_date"]).unique(subset=["ticker","execution_date","split_from","split_to"], keep="last")
    return df

def clean_dividends(df: pl.DataFrame) -> pl.DataFrame:
    if df.height == 0: return df
    cast = {
        "ticker": pl.Utf8, "ex_dividend_date": pl.Utf8,
        "cash_amount": pl.Float64, "declaration_date": pl.Utf8,
        "record_date": pl.Utf8, "payable_date": pl.Utf8,
        "frequency": pl.Utf8, "dividend_type": pl.Utf8
    }
    for c,t in cast.items():
        if c in df.columns: df = df.with_columns(pl.col(c).cast(t))
    if "ex_dividend_date" in df.columns and "cash_amount" in df.columns:
        df = df.sort(["ticker","ex_dividend_date"]).unique(subset=["ticker","ex_dividend_date","cash_amount"], keep="last")
    return df

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", required=True, help="Base de salida raw/polygon/reference")
    args = ap.parse_args()

    api_key = os.getenv("POLYGON_API_KEY")
    if not api_key: sys.exit("Falta POLYGON_API_KEY")

    base = Path(args.outdir); base.mkdir(parents=True, exist_ok=True)

    # Splits
    splits = list(fetch_paged("/v3/reference/splits", api_key))
    df_s = clean_splits(pl.from_dicts(splits) if splits else pl.DataFrame())
    if df_s.height:
        # particiona por año de execution_date
        df_s = df_s.with_columns(pl.col("execution_date").str.slice(0,4).alias("year"))
        for year, part in df_s.group_by("year"):
            outdir = base / "splits" / f"year={year[0]}"
            outdir.mkdir(parents=True, exist_ok=True)
            part.drop("year").write_parquet(outdir / "splits.parquet")
        log(f"Splits escritos en {base/'splits'}")

    # Dividends
    dividends = list(fetch_paged("/v3/reference/dividends", api_key))
    df_d = clean_dividends(pl.from_dicts(dividends) if dividends else pl.DataFrame())
    if df_d.height:
        df_d = df_d.with_columns(pl.col("ex_dividend_date").str.slice(0,4).alias("year"))
        for year, part in df_d.group_by("year"):
            outdir = base / "dividends" / f"year={year[0]}"
            outdir.mkdir(parents=True, exist_ok=True)
            part.drop("year").write_parquet(outdir / "dividends.parquet")
        log(f"Dividends escritos en {base/'dividends'}")

if __name__ == "__main__":
    main()
