#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Nasdaq Short Sale Volume (on-exchange) - TXT diarios → Parquet por fecha.

Ejemplo:
  python download_nasdaq_short_volume.py \
    --outdir raw/nasdaq/short_volume \
    --from 2025-01-01 --to 2025-01-31 --resume

Ajuste de URL si cambia el host/ruta:
  --url-template "https://ftp.nasdaqtrader.com/dynamic/shorts/nyse/NASDAQshvol{yyyymmdd}.txt"
"""

from __future__ import annotations
import argparse, sys, time, io
from datetime import datetime, timedelta
from pathlib import Path
import requests, polars as pl

DEFAULT_TEMPLATE = (
  # Cambia a la ruta exacta que uses (NasdaqTrader/FTP o HTTPS espejo)
  "https://ftp.nasdaqtrader.com/files/shorts/NASDAQshvol{yyyymmdd}.txt"
)

TIMEOUT=30
RETRIES=4

def drange(d1,d2):
    a = datetime.fromisoformat(d1).date()
    b = datetime.fromisoformat(d2).date()
    cur = a
    one = timedelta(days=1)
    while cur<=b:
        yield cur
        cur += one

def build_url(tmpl, dt):
    return tmpl.format(yyyymmdd=f"{dt.year:04d}{dt.month:02d}{dt.day:02d}")

def fetch_txt(url:str)->str|None:
    s = requests.Session()
    s.headers.update({"Accept":"text/plain"})
    for k in range(RETRIES):
        try:
            r = s.get(url, timeout=TIMEOUT)
            if r.status_code==200 and r.content:
                for enc in ("utf-8","latin-1","cp1252"):
                    try:
                        return r.content.decode(enc)
                    except: pass
                return r.text
            if r.status_code in (404,429,500,502,503,504):
                time.sleep(min(20.0, 1.5**(k+1)))
                continue
            r.raise_for_status()
        except Exception:
            time.sleep(min(20.0, 1.5**(k+1)))
    return None

def parse_nasdaq_txt(text:str)->pl.DataFrame:
    # Nasdaq suele usar tab o coma. Autodetect simple:
    sep = "," if text.count(",")>text.count("\t") else "\t"
    df = pl.read_csv(io.StringIO(text), separator=sep, infer_schema_length=10000, ignore_errors=True)
    # Normalizar algunos nombres frecuentes:
    rename={}
    for c in df.columns:
        cl = c.lower()
        if cl in ("symbol","issue_symbol","ticker"):
            rename[c]="symbol"
        elif cl in ("shortvolume","short_volume"):
            rename[c]="shortVolume"
        elif cl in ("shortexemptvolume","short_exempt_volume"):
            rename[c]="shortExemptVolume"
        elif cl in ("totalvolume","total_volume","volume"):
            rename[c]="totalVolume"
        elif cl in ("market","exchange"):
            rename[c]="market"
    if rename: df = df.rename(rename)
    # Añadimos columnas mínimas si faltan
    for c in ("symbol","shortVolume","totalVolume"):
        if c not in df.columns:
            df = df.with_columns(pl.lit(None).alias(c))
    return df

def main():
    ap = argparse.ArgumentParser(description="Nasdaq daily short sale volume (on-exchange) → Parquet")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--from", dest="date_from", required=True)
    ap.add_argument("--to", dest="date_to", required=True)
    ap.add_argument("--url-template", default=DEFAULT_TEMPLATE)
    ap.add_argument("--resume", action="store_true")
    args = ap.parse_args()

    outdir = Path(args.outdir); outdir.mkdir(parents=True, exist_ok=True)

    for d in drange(args.date_from, args.date_to):
        part = outdir / f"date={d.isoformat()}"
        if args.resume and (part/"_SUCCESS").exists():
            print(f"[RESUME] {d} skip"); continue
        url = build_url(args.url_template, d)
        print(f"[GET] {d} -> {url}")
        txt = fetch_txt(url)
        if not txt:
            print(f"[WARN] {d} sin datos"); continue
        try:
            df = parse_nasdaq_txt(txt)
            part.mkdir(parents=True, exist_ok=True)
            (part/"shorts.parquet").write_bytes(
                df.write_parquet(compression="zstd", compression_level=3)
            )
            (part/"_SUCCESS").write_text("")
            print(f"[OK] {d} filas={df.height}")
        except Exception as e:
            print(f"[ERR] {d} parse/escritura: {e}", file=sys.stderr)

if __name__=="__main__":
    main()
