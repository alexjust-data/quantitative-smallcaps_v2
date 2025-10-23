#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
SEC Fails-to-Deliver (FTD) — ZIP mensuales → Parquet particionado por year/month.

Ejemplo:
  python download_sec_ftd.py \
    --outdir raw/sec/ftd \
    --from 2020-01 --to 2025-09 \
    --resume

Si necesitas ajustar la URL:
  --url-template "https://www.sec.gov/files/data/fails-deliver-data/cnsfails{yyyymm}.zip"
"""

from __future__ import annotations
import argparse, sys, io, zipfile, time
from pathlib import Path
from datetime import datetime
from dateutil.relativedelta import relativedelta  # pip install python-dateutil
import requests, polars as pl

DEFAULT_TEMPLATE = "https://www.sec.gov/files/data/fails-deliver-data/cnsfails{yyyymm}.zip"
TIMEOUT = 60
RETRIES = 3

def month_range(mfrom:str, mto:str):
    """ mfrom/mto formato YYYY-MM """
    cur = datetime.strptime(mfrom, "%Y-%m")
    end = datetime.strptime(mto, "%Y-%m")
    while cur <= end:
        yield cur.year, cur.month
        cur += relativedelta(months=1)

def build_url(tmpl:str, year:int, month:int)->str:
    return tmpl.format(yyyymm=f"{year:04d}{month:02d}")

def fetch_zip(url:str)->bytes|None:
    s = requests.Session()
    s.headers.update({"Accept":"application/zip, application/octet-stream, */*",
                      "User-Agent":"SmallCaps-FTD/1.0 (contacto@tu-dominio.com)"})
    for k in range(RETRIES):
        try:
            r = s.get(url, timeout=TIMEOUT)
            if r.status_code==200 and r.content:
                return r.content
            if r.status_code in (404,429,500,502,503,504):
                time.sleep(min(20.0, 1.7**(k+1)))
                continue
            r.raise_for_status()
        except Exception:
            time.sleep(min(20.0, 1.7**(k+1)))
    return None

def read_first_table_from_zip(b:bytes)->pl.DataFrame:
    """
    Lee el primer fichero tabular (CSV/TXT) del ZIP y lo carga en Polars.
    SEC FTD suele venir como TXT/CSV delimitado por coma o tab.
    """
    with zipfile.ZipFile(io.BytesIO(b)) as zf:
        names = zf.namelist()
        # elige el primero con extensión plausible
        candidates = [n for n in names if n.lower().endswith((".txt",".csv",".dat",".tsv"))]
        if not candidates:
            raise RuntimeError("No table-like file found in ZIP")
        with zf.open(candidates[0]) as f:
            raw = f.read()
            # decodificación robusta
            for enc in ("utf-8","latin-1","cp1252"):
                try:
                    txt = raw.decode(enc)
                    break
                except Exception:
                    txt = None
            if txt is None:
                txt = raw.decode("latin-1","ignore")
    # autodetect separador
    sep = "," if txt.count(",")>txt.count("\t") else "\t"
    if txt.count("|")>max(txt.count(","), txt.count("\t")):
        sep="|"
    df = pl.read_csv(io.StringIO(txt), separator=sep, ignore_errors=True, infer_schema_length=200000)
    return df

def normalize_ftd(df: pl.DataFrame) -> pl.DataFrame:
    """
    Normaliza nombres y tipos comunes: settlement_date, cusip, symbol, quantity_fails, price.
    """
    ren = {}
    for c in df.columns:
        cl = c.lower().strip()
        if "settlement" in cl and "date" in cl:
            ren[c]="settlement_date"
        elif cl=="cusip":
            ren[c]="cusip"
        elif cl in ("symbol","ticker"):
            ren[c]="symbol"
        elif ("quantity" in cl and "fail" in cl) or cl in ("fails","qty","quantity"):
            ren[c]="quantity_fails"
        elif "price" in cl:
            ren[c]="price"
    if ren:
        df = df.rename(ren)

    # Tipos
    if "settlement_date" in df.columns:
        # puede venir YYYYMMDD o YYYY-MM-DD
        def norm_date(s:str)->str:
            s = str(s)
            if len(s)==8 and s.isdigit():
                return f"{s[:4]}-{s[4:6]}-{s[6:]}"
            return s
        df = df.with_columns(
            pl.col("settlement_date").map_elements(norm_date).alias("settlement_date")
        )
    # cast numéricos
    for c in ("quantity_fails","price"):
        if c in df.columns:
            df = df.with_columns(pl.col(c).cast(pl.Float64, strict=False))

    return df

def main():
    ap = argparse.ArgumentParser(description="SEC FTD mensual (ZIP) → Parquet particionado year/month")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--from", dest="month_from", required=True, help="YYYY-MM")
    ap.add_argument("--to", dest="month_to", required=True, help="YYYY-MM")
    ap.add_argument("--url-template", default=DEFAULT_TEMPLATE)
    ap.add_argument("--resume", action="store_true")
    args = ap.parse_args()

    outdir = Path(args.outdir); outdir.mkdir(parents=True, exist_ok=True)

    for y, m in month_range(args.month_from, args.month_to):
        part = outdir / f"year={y:04d}/month={m:02d}"
        succ = part / "_SUCCESS"
        if args.resume and succ.exists():
            print(f"[RESUME] {y}-{m:02d} skip"); continue
        url = build_url(args.url_template, y, m)
        print(f"[GET] {y}-{m:02d} -> {url}")
        b = fetch_zip(url)
        if not b:
            print(f"[WARN] {y}-{m:02d} sin ZIP"); continue
        try:
            df = read_first_table_from_zip(b)
            df = normalize_ftd(df)
            part.mkdir(parents=True, exist_ok=True)
            (part/"ftd.parquet").write_bytes(df.write_parquet(compression="zstd", compression_level=3))
            succ.write_text("")
            print(f"[OK] {y}-{m:02d} filas={df.height}")
        except Exception as e:
            print(f"[ERR] {y}-{m:02d} parse/escritura: {e}", file=sys.stderr)

if __name__=="__main__":
    main()
