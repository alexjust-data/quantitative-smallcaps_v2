#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
FINRA Reg SHO Daily Short Sale Volume (TXT diarios) - Off-exchange
Descarga y parsea TXT por día → Parquet particionado por date=YYYY-MM-DD.

Ejemplo:
  python download_finra_short_volume_txt.py \
    --outdir raw/finra/regsho_daily_txt \
    --from 2025-01-01 --to 2025-01-31 \
    --resume \
    --workers 4

Si necesitas ajustar la URL:
  --url-template "https://cdn.finra.org/equity/regsho/daily/{yyyy}/FNRA_REGSHO_{yyyymmdd}.txt"
"""

from __future__ import annotations
import argparse, sys, time
from pathlib import Path
from datetime import datetime, timedelta
import io, requests
import polars as pl
from multiprocessing import Pool
from functools import partial

DEFAULT_TEMPLATE = (
  # Ajustable. Muchos deployments públicos usan un árbol por año y fichero por día.
  # Cambia si FINRA usa otro patrón en tu entorno.
  "https://cdn.finra.org/equity/regsho/daily/{yyyy}/{yyyymmdd}.txt"
)

TIMEOUT = 30
RETRIES = 4

def drange(d1:str, d2:str):
    a = datetime.fromisoformat(d1).date()
    b = datetime.fromisoformat(d2).date()
    cur = a
    one = timedelta(days=1)
    out=[]
    while cur<=b:
        out.append(cur)
        cur += one
    return out

def build_url(tmpl:str, dt):
    return tmpl.format(
        yyyy = f"{dt.year:04d}",
        yyyymmdd = f"{dt.year:04d}{dt.month:02d}{dt.day:02d}"
    )

def get_txt(url:str)->str|None:
    s = requests.Session()
    s.headers.update({"Accept":"text/plain"})
    for k in range(RETRIES):
        try:
            r = s.get(url, timeout=TIMEOUT)
            if r.status_code==200 and r.content:
                # FINRA suele entregar CSV/TSV/TXT; intentamos decodificación robusta
                for enc in ("utf-8","latin-1","cp1252"):
                    try:
                        return r.content.decode(enc)
                    except Exception:
                        continue
                return r.text
            if r.status_code in (404, 429, 500, 502, 503, 504):
                time.sleep(min(20.0, 1.5**(k+1)))
                continue
            r.raise_for_status()
        except Exception:
            time.sleep(min(20.0, 1.5**(k+1)))
    return None

def parse_txt(text:str)->pl.DataFrame:
    """
    Intento genérico: autodetectar separador (coma, tab, pipe).
    Normaliza nombres de columnas más comunes del Reg SHO daily FINRA.
    """
    # Autodetección simple
    sep = "," if text.count(",")>text.count("\t") else "\t"
    if text.count("|")>max(text.count(","), text.count("\t")):
        sep="|"
    # Cargar con inferencia
    df = pl.read_csv(io.StringIO(text), separator=sep, infer_schema_length=10000, ignore_errors=True)
    # Normalizar nombres
    cols = {c.lower(): c for c in df.columns}
    # Mapeos frecuentes
    rename_map = {}
    for k in list(df.columns):
        kl = k.lower()
        if kl in ("tradedate","date","settlementdate"):
            rename_map[k]="tradeDate"
        elif kl in ("symbol","issuesymbol","ticker"):
            rename_map[k]="symbol"
        elif kl in ("shortvolume","short_sale_volume","shortsalevolume"):
            rename_map[k]="shortVolume"
        elif kl in ("shortexemptvolume","short_exempt_volume","shortexempt"):
            rename_map[k]="shortExemptVolume"
        elif kl in ("totalvolume","total_volume","volume"):
            rename_map[k]="totalVolume"
        elif kl in ("market","exch","exchange"):
            rename_map[k]="market"
    if rename_map:
        df = df.rename(rename_map)
    # Añadir columnas faltantes si procede
    for col in ("tradeDate","symbol","shortVolume","totalVolume"):
        if col not in df.columns:
            df = df.with_columns(pl.lit(None).alias(col))
    return df

def process_single_day(args_tuple):
    """Process a single day (for multiprocessing)"""
    d, outdir, url_template, resume = args_tuple
    part = outdir / f"date={d.isoformat()}"

    if resume and (part / "_SUCCESS").exists():
        print(f"[RESUME] {d} skip")
        return None

    url = build_url(url_template, d)
    print(f"[GET] {d} -> {url}")
    txt = get_txt(url)
    if not txt:
        print(f"[WARN] {d} sin datos o no encontrado")
        return None

    try:
        df = parse_txt(txt)
        part.mkdir(parents=True, exist_ok=True)
        df.write_parquet(
            part/"regsho.parquet",
            compression="zstd",
            compression_level=3
        )
        (part/"_SUCCESS").write_text("")
        print(f"[OK] {d} filas={df.height}")
        return d
    except Exception as e:
        print(f"[ERR] {d} parse/escritura: {e}", file=sys.stderr)
        return None

def main():
    ap = argparse.ArgumentParser(description="FINRA Reg SHO (TXT diarios) → Parquet particionado")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--from", dest="date_from", required=True)
    ap.add_argument("--to", dest="date_to", required=True)
    ap.add_argument("--url-template", default=DEFAULT_TEMPLATE)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--workers", type=int, default=1, help="Parallel workers (default: 1, recommended: 4)")
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    dates = drange(args.date_from, args.date_to)
    print(f"[INFO] Processing {len(dates)} days with {args.workers} workers")

    if args.workers == 1:
        # Sequential mode (original behavior)
        for d in dates:
            process_single_day((d, outdir, args.url_template, args.resume))
    else:
        # Parallel mode
        tasks = [(d, outdir, args.url_template, args.resume) for d in dates]
        with Pool(processes=args.workers) as pool:
            results = pool.map(process_single_day, tasks)

        success_count = sum(1 for r in results if r is not None)
        print(f"[DONE] {success_count}/{len(dates)} days processed successfully")

if __name__=="__main__":
    main()
