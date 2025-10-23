#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
download_sec_offerings.py
Descarga de EDGAR (SEC) centrada en Offerings & Corporate Actions:
S-3 / S-3ASR / S-1 / 424B5 (y variantes) / FWP + 8-K (metadata).

Fuente: data.sec.gov/submissions API (oficial, sin API key; requiere User-Agent).
Docs SEC: https://www.sec.gov/search-filings/edgar-application-programming-interfaces
Salida:
  processed/edgar/offerings/
    ├─ form=S-3/...
    ├─ form=424B5/...
    ├─ form=8-K/...
    └─ all_filings.parquet (+ .csv), _SUCCESS por partición

Uso (ejemplos):
  # 1) Usando tu dimensión con CIKs (recomendado):
  python scripts/fase_D_edgar/download_sec_offerings.py \
    --tickers-parquet processed/ref/tickers_dim/tickers_dim.parquet \
    --outdir processed/edgar/offerings \
    --user-agent "SmallCapsLab/1.0 (contacto@tu-dominio.com)" \
    --from 2020-01-01 --to 2025-10-21 --resume

  # 2) Lista manual de tickers (CSV con columnas: ticker[,cik]):
  python scripts/fase_D_edgar/download_sec_offerings.py \
    --tickers-csv processed/universe/cs_xnas_xnys_under2b_YYYYMMDD.csv \
    --outdir processed/edgar/offerings \
    --user-agent "SmallCapsLab/1.0 (contacto@tu-dominio.com)" \
    --from 2020-01-01 --to 2025-10-21
"""
from __future__ import annotations
import os, sys, re, time, argparse, json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import requests
import polars as pl

EDGAR_BASE = "https://data.sec.gov"
SUBMISSIONS_URL = EDGAR_BASE + "/submissions/CIK{cik}.json"  # 10 dígitos, con ceros

FORMS_TARGET = {
    "S-1","S-3","S-3ASR",
    "424B5","424B2","424B3","424B4","424B7","424B8",
    "FWP","8-K"
}

# Palabras clave (detección rápida; mejora con NLP si quieres):
KEYWORDS = [
    r"\bat[-\s]?the[-\s]?market\b", r"\batm\b",
    r"\bregistered direct\b", r"\bpipe\b",
    r"\bwarrant(s)?\b", r"\bshelf\b",
    r"\bequity distribution agreement\b", r"\boffering\b"
]

TIMEOUT = (10, 60)
REQ_SLEEP = 0.25  # 4 req/seg por cortesía SEC; ajusta si hace falta. Ver guía EDGAR. 
CHUNK = 500  # máximo filings a retener por CIK tras filtrar

def log(msg:str):
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)

def ensure_out(path: Path):
    path.mkdir(parents=True, exist_ok=True)

def success_marker(path: Path):
    (path / "_SUCCESS").touch(exist_ok=True)

def normalize_cik(raw: str) -> str:
    s = re.sub(r"\D", "", str(raw or ""))
    return s.zfill(10) if s else ""

def build_sec_session(user_agent: str) -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": user_agent,
        "Accept": "application/json, text/plain, */*",
        "Connection": "keep-alive",
    })
    return s

def acc_to_paths(accession_no: str, primary_doc: str) -> Tuple[str,str,str]:
    # accession sin guiones para path
    acc_nodash = accession_no.replace("-", "")
    base = f"https://www.sec.gov/Archives/edgar/data"
    # Ojo: para construir la ruta completa se necesita el CIK sin ceros a la izquierda y el accession sin guiones.
    # No lo devolvemos aquí; devolvemos los sufijos típicos
    return (acc_nodash, primary_doc, base)

def build_urls(cik: str, accession_no: str, primary_doc: str) -> Dict[str,str]:
    # CIK para ruta de archivos va sin ceros a la izquierda
    cik_nolead = str(int(cik))
    acc_nodash = accession_no.replace("-", "")
    base_arch = f"https://www.sec.gov/Archives/edgar/data/{cik_nolead}/{acc_nodash}"
    return {
        "filing_index_url": f"{base_arch}/{accession_no}-index.html",
        "primary_doc_url":  f"{base_arch}/{primary_doc}" if primary_doc else base_arch,
        "filing_dir_url":   base_arch
    }

def keyword_hits(text: str) -> Dict[str,int]:
    hits = {}
    low = text.lower()
    for pat in KEYWORDS:
        m = re.findall(pat, low, flags=re.IGNORECASE)
        if m:
            hits[pat] = len(m)
    return hits

def fetch_submissions(session: requests.Session, cik: str) -> Optional[dict]:
    url = SUBMISSIONS_URL.format(cik=cik)
    for k in range(3):
        try:
            r = session.get(url, timeout=TIMEOUT)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.json()
        except Exception as e:
            log(f"CIK {cik}: error {e} (reintento {k+1}/3)")
            time.sleep(REQ_SLEEP * (k+1))
    return None

def parse_filings(sub_json: dict, frm: datetime, to: datetime) -> pl.DataFrame:
    """
    Devuelve un DataFrame (polars) con meta de filings filtrados por date + FORMS_TARGET.
    """
    if not sub_json or "filings" not in sub_json or "recent" not in sub_json["filings"]:
        return pl.DataFrame(schema={"dummy": pl.Int64}).head(0)

    r = sub_json["filings"]["recent"]
    # Campos paralelos (columnar) que expone la SEC
    cols = ["accessionNumber","filingDate","reportDate","acceptanceDateTime",
            "act","form","fileNumber","filmNumber","items","primaryDocument","primaryDocDescription"]
    data = {c: r.get(c, []) for c in cols}
    df = pl.DataFrame(data) if data["form"] else pl.DataFrame(schema={"dummy": pl.Int64}).head(0)

    if df.height == 0:
        return df

    # Replace empty strings with null before parsing dates
    df = df.with_columns([
        pl.when(pl.col("filingDate") == "").then(None).otherwise(pl.col("filingDate")).alias("filingDate"),
        pl.when(pl.col("reportDate") == "").then(None).otherwise(pl.col("reportDate")).alias("reportDate"),
        pl.when(pl.col("acceptanceDateTime") == "").then(None).otherwise(pl.col("acceptanceDateTime")).alias("acceptanceDateTime"),
    ])

    df = df.with_columns([
        pl.col("filingDate").str.strptime(pl.Date, "%Y-%m-%d").alias("filing_date"),
        pl.col("reportDate").str.strptime(pl.Date, "%Y-%m-%d").alias("report_date"),
        pl.col("acceptanceDateTime").str.strptime(pl.Datetime, "%Y-%m-%dT%H:%M:%S%.fZ").alias("accept_dt"),
    ]).filter(
        pl.col("filing_date").is_not_null() &
        (pl.col("filing_date") >= pl.lit(frm.date())) &
        (pl.col("filing_date") <= pl.lit(to.date())) &
        (pl.col("form").is_in(list(FORMS_TARGET)))
    )

    # recorta tamaño por CIK
    if df.height > CHUNK:
        df = df.sort("filing_date", descending=True).head(CHUNK)

    return df

def download_primary_doc(session: requests.Session, url: str) -> Optional[str]:
    try:
        r = session.get(url, timeout=TIMEOUT)
        if r.status_code == 200 and r.text:
            return r.text
    except Exception:
        pass
    return None

def main():
    ap = argparse.ArgumentParser(description="SEC EDGAR offerings downloader (S-3/424B5/8-K)")
    gsrc = ap.add_mutually_exclusive_group(required=True)
    gsrc.add_argument("--tickers-parquet", type=str, help="Parquet con columnas: ticker, cik (recomendado)")
    gsrc.add_argument("--tickers-csv", type=str, help="CSV con columnas: ticker[,cik]")

    ap.add_argument("--outdir", type=str, required=True)
    ap.add_argument("--user-agent", type=str, required=True, help='Ej: "SmallCapsLab/1.0 (email@dominio.com)"')
    ap.add_argument("--from", dest="date_from", type=str, required=True, help="YYYY-MM-DD")
    ap.add_argument("--to", dest="date_to", type=str, required=True, help="YYYY-MM-DD")
    ap.add_argument("--download-html", action="store_true", help="Bajar primary document (html/txt) y marcar keywords")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--max", dest="max_ciks", type=int, default=None, help="Límite CIKs (debug)")
    args = ap.parse_args()

    outdir = Path(args.outdir)
    ensure_out(outdir)
    session = build_sec_session(args.user_agent)

    # Cargar universo tickers → CIK
    if args.tickers_parquet:
        dfu = pl.read_parquet(args.tickers_parquet)
    else:
        dfu = pl.read_csv(args.tickers_csv)

    # Normaliza CIK y ticker
    cols = [c.lower() for c in dfu.columns]
    dfu = dfu.rename({c: c.lower() for c in dfu.columns})
    if "ticker" not in dfu.columns:
        sys.exit("ERROR: falta columna 'ticker' en el universo")
    if "cik" not in dfu.columns:
        log("WARNING: No hay columna 'cik' - intentaremos continuar sin CIK (no recomendado).")
        dfu = dfu.with_columns(pl.lit("").alias("cik"))

    dfu = dfu.select(["ticker","cik"]).unique().with_columns(
        pl.col("cik").map_elements(normalize_cik).alias("cik_norm")
    ).with_columns(
        pl.when(pl.col("cik_norm") == "")
          .then(None)
          .otherwise(pl.col("cik_norm"))
          .alias("cik_norm")
    ).drop("cik").rename({"cik_norm":"cik"})

    # Filtra filas sin CIK (podrías mapear tickers→CIK con otra tabla si lo deseas)
    dfc = dfu.filter(pl.col("cik").is_not_null())
    if args.max_ciks:
        dfc = dfc.head(args.max_ciks)

    frm = datetime.strptime(args.date_from, "%Y-%m-%d")
    to  = datetime.strptime(args.date_to,   "%Y-%m-%d")

    all_rows = []
    ok_count = 0

    for i, row in enumerate(dfc.iter_rows(named=True), start=1):
        ticker = row["ticker"]
        cik = row["cik"]

        cik_dir = outdir / f"cik={cik}"
        ensure_out(cik_dir)
        part_all = outdir / "all"
        ensure_out(part_all)

        if args.resume and (cik_dir / "_SUCCESS").exists():
            log(f"{i}/{dfc.height} {ticker} ({cik}) : RESUME skip (ya procesado)")
            continue

        time.sleep(REQ_SLEEP)  # cortesía SEC
        sub_json = fetch_submissions(session, cik)
        if not sub_json:
            log(f"{i}/{dfc.height} {ticker} ({cik}) : sin submissions")
            continue

        dff = parse_filings(sub_json, frm, to)
        if dff.height == 0:
            log(f"{i}/{dfc.height} {ticker} ({cik}) : 0 filings target")
            success_marker(cik_dir)
            continue

        dff = dff.with_columns([
            pl.lit(ticker).alias("ticker"),
            pl.lit(cik).alias("cik"),
        ])

        # Construye URLs y descarga opcional del primary doc
        recs = []
        for rec in dff.iter_rows(named=True):
            urls = build_urls(cik, rec["accessionNumber"], rec["primaryDocument"])
            kw = {}
            if args.download_html and rec["form"] in ("S-3","S-3ASR","424B5","424B2","424B3","424B4","424B7","424B8","FWP","8-K"):
                html = download_primary_doc(session, urls["primary_doc_url"])
                if html:
                    kw = keyword_hits(html)
            recs.append({
                "ticker": rec["ticker"],
                "cik": rec["cik"],
                "form": rec["form"],
                "filing_date": rec["filing_date"],
                "report_date": rec["report_date"],
                "accept_dt": rec["accept_dt"],
                "accession_no": rec["accessionNumber"],
                "primary_doc": rec["primaryDocument"],
                "primary_desc": rec.get("primaryDocDescription"),
                "items": rec.get("items"),  # útil para 8-K
                **urls,
                "keyword_flags": json.dumps(kw) if kw else None,
            })

        dfo = pl.DataFrame(recs)

        # Partición por form y por año (ordenado)
        for frm_name, dfp in dfo.group_by("form"):
            frm_val = frm_name[0] if isinstance(frm_name, tuple) else frm_name
            out_part = outdir / f"form={frm_val}"
            ensure_out(out_part)
            # más partición por año para tamaños cómodos
            year = dfp["filing_date"].dt.year().cast(pl.Int32)
            for y, dfy in dfp.with_columns(year.alias("year")).group_by("year"):
                y_val = y[0] if isinstance(y, tuple) else y
                outf = out_part / f"year={int(y_val)}" / "filings.parquet"
                ensure_out(outf.parent)
                mode = "append" if outf.exists() else "wb"
                dfy.drop("year").write_parquet(outf, compression="zstd", compression_level=2)
        # All-in-one (append)
        allf = outdir / "all" / "all_filings.parquet"
        mode = "append" if allf.exists() else "wb"
        dfo.write_parquet(allf, compression="zstd", compression_level=2)

        success_marker(cik_dir)
        ok_count += 1
        log(f"{i}/{dfc.height} {ticker} ({cik}) : OK {dff.height} filings")

    # índice simple
    if ok_count:
        success_marker(outdir)
        log(f"COMPLETADO. CIKs con datos: {ok_count}/{dfc.height}")

if __name__ == "__main__":
    main()
