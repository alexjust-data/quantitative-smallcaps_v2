## Ingesta de TRADES desde Polygon (por día) — `ingest_trades_day.py`

Usa Polars y paginación por cursor. Output en Parquet, particionado por año/mes.
Si algún día no quieres usar trades (por coste o latencia), el build_bars.py también acepta 1m aggregates como fallback (reconstruye pseudo-barras; menos preciso, pero útil).

1) Ingesta de TRADES (tick-level) — ingest_trades_day.py

```py
#!/usr/bin/env python
# ingest_trades_day.py
import os, sys, time, argparse, datetime as dt
from pathlib import Path
import urllib.parse as urlparse
from typing import Dict, Any, List, Optional

import requests
import polars as pl

BASE_URL = "https://api.polygon.io"
TIMEOUT = 40
RETRY_MAX = 8
BACKOFF = 1.6
PAGE_LIMIT = 50000  # polygon v3 trades limit

def log(m): print(f"[{dt.datetime.now():%F %T}] {m}", flush=True)

def parse_next_cursor(next_url: Optional[str]) -> Optional[str]:
    if not next_url: return None
    try:
        q = urlparse.urlparse(next_url).query
        qs = urlparse.parse_qs(q)
        cur = qs.get("cursor")
        return cur[0] if cur else None
    except Exception:
        return None

def http_get_json(url: str, params: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
    last = None
    for k in range(1, RETRY_MAX+1):
        try:
            r = requests.get(url, params=params, headers=headers, timeout=TIMEOUT)
            if r.status_code == 429:
                sl = int(r.headers.get("Retry-After","2"))
                log(f"429 -> sleep {sl}s"); time.sleep(sl); continue
            if 500 <= r.status_code < 600:
                sl = min(30, BACKOFF**k)
                log(f"{r.status_code} -> backoff {sl:.1f}s"); time.sleep(sl); continue
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last = e; sl = min(30, BACKOFF**k)
            log(f"GET err {e} -> backoff {sl:.1f}s"); time.sleep(sl)
    raise RuntimeError(f"Failed after {RETRY_MAX} attempts: {last}")

def fetch_trades_day(api_key: str, ticker: str, day: str, limit: int = PAGE_LIMIT) -> List[Dict[str, Any]]:
    url = f"{BASE_URL}/v3/trades/{ticker}"
    headers = {"Authorization": f"Bearer {api_key}"}
    params = {
        "limit": limit,
        "timestamp.gte": f"{day} 04:00:00",
        "timestamp.lte": f"{day} 20:59:59",
        "sort": "timestamp",
        "order": "asc",
    }
    rows: List[Dict[str, Any]] = []
    cursor = None
    pages = 0
    while True:
        p = params.copy()
        if cursor: p["cursor"] = cursor
        data = http_get_json(url, p, headers) or {}
        res = data.get("results") or []
        rows.extend(res)
        pages += 1
        cursor = parse_next_cursor(data.get("next_url")) or data.get("cursor") or data.get("next_cursor")
        if not cursor: break
    log(f"{ticker} {day}: {len(rows)} trades ({pages} pages)")
    return rows

def rows_to_df(rows: List[Dict[str, Any]], ticker: str, day: str) -> pl.DataFrame:
    if not rows:
        return pl.DataFrame({"ticker":[],"day":[],"sip_ts":[],"price":[],"size":[]})
    df = pl.from_dicts(rows)
    # Campos típicos v3/trades: price, size, sip_timestamp, conditions, exchange, id...
    # Estandarizamos mínimos necesarios
    price = df.get_column("price") if "price" in df.columns else pl.Series("price", [], pl.Float64)
    size  = df.get_column("size")  if "size"  in df.columns else pl.Series("size",  [], pl.Float64)
    ts    = df.get_column("sip_timestamp") if "sip_timestamp" in df.columns else pl.Series("sip_timestamp", [], pl.Int64)
    out = pl.DataFrame({
        "ticker": pl.repeat(ticker, len(price), eager=True),
        "day": pl.repeat(day, len(price), eager=True),
        "sip_ts": ts.cast(pl.Int64),
        "price": price.cast(pl.Float64),
        "size": size.cast(pl.Float64),
    })
    return out.sort("sip_ts")

def write_trades(df: pl.DataFrame, outdir: Path, ticker: str, day: str) -> Path:
    if df.height == 0:
        outdir.mkdir(parents=True, exist_ok=True)
        p = outdir / ticker / f"day={day}" / "trades.parquet"
        p.parent.mkdir(parents=True, exist_ok=True)
        df.write_parquet(p)
        return p
    y, m = day[:4], day[5:7]
    p = outdir / ticker / f"year={y}" / f"month={m}" / f"day={day}" / "trades.parquet"
    p.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(p)
    return p

def daterange(d0: str, d1: str):
    a = dt.date.fromisoformat(d0); b = dt.date.fromisoformat(d1)
    cur = a
    while cur <= b:
        yield cur.isoformat()
        cur += dt.timedelta(days=1)

def main():
    import concurrent.futures as cf
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickers-csv", required=True, help="CSV con columna 'ticker'")
    ap.add_argument("--outdir", required=True, help="raw/polygon/trades")
    ap.add_argument("--from", dest="date_from", required=True)
    ap.add_argument("--to", dest="date_to", required=True)
    ap.add_argument("--max-workers", type=int, default=8)
    args = ap.parse_args()

    api_key = os.getenv("POLYGON_API_KEY")
    if not api_key: sys.exit("Falta POLYGON_API_KEY")

    tickers = pl.read_csv(args.tickers_csv)["ticker"].to_list()
    outdir = Path(args.outdir); outdir.mkdir(parents=True, exist_ok=True)

    log(f"TRADES: {len(tickers)} tickers, {args.date_from}→{args.date_to}")
    tasks = []
    with cf.ThreadPoolExecutor(max_workers=args.max_workers) as ex:
        for t in tickers:
            for d in daterange(args.date_from, args.date_to):
                tasks.append(ex.submit(fetch_trades_day, api_key, t, d))
        i=0
        for fut in cf.as_completed(tasks):
            i+=1
            try:
                rows = fut.result()
                if not rows:
                    continue
                t = rows[0].get("T") or rows[0].get("ticker")  # por si viene el campo
                d = dt.datetime.utcfromtimestamp(rows[0]["sip_timestamp"]/1e9).date().isoformat() if "sip_timestamp" in rows[0] else "unknown"
                # fallback: si no pudimos inferir día, no escribimos
                if d == "unknown":
                    continue
                df = rows_to_df(rows, t, d)
                write_trades(df, outdir, t, d)
            except Exception as e:
                log(f"ERROR: {e}")
            if i % 200 == 0: log(f"Progreso {i:,}/{len(tasks):,}")

if __name__ == "__main__":
    main()
```

Uso (ejemplo):
```sh
# universo filtrado a CS XNAS/XNYS (<2B si lo quieres)
UNIV=processed/universe/cs_xnas_xnys_under2b_2025-10-19.csv

python ingest_trades_day.py \
  --tickers-csv "$UNIV" \
  --outdir 01_fase_2/raw/polygon/trades \
  --from 2024-01-01 --to 2024-12-31 \
  --max-workers 8
```

Nota: TRADES es voluminoso. Lo normal es ir por ventanas (año a año, o sectores). Para Bar Construction no necesitas absolutamente todos los años desde el minuto 0; con 2–3 años tienes base excelente para prototipar.

