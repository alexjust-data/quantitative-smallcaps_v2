#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
analyze_intraday_footprint.py
Escanea raw/polygon/ohlcv_intraday_1m/ y estima la "pesadez" (heavy-ness) de cada ticker
sin cargar datos a RAM: usa metadatos de Parquet (pyarrow) para contar filas/bytes.

Salidas:
- CSV: processed/reports/intraday_1m_footprint_<timestamp>.csv
- CSV: processed/reports/heavy_tickers.csv     (columna: ticker)
- CSV: processed/reports/normal_tickers.csv    (columna: ticker)
- MD : processed/reports/intraday_1m_footprint_<timestamp>.md (resumen)

Heaviness score (0-100) basado en:
  - total_rows (minutos) normalizado
  - total_bytes normalizado
  - meses (archivos) normalizado
Clasificación por umbrales (configurables):
  - heavy   si score >= heavy_th (p. ej. 70)
  - medium  si score >= medium_th (p. ej. 40)
  - light   resto

Uso:
  python tools/analyze_intraday_footprint.py \
    --root raw/polygon/ohlcv_intraday_1m \
    --out processed/reports \
    --heavy-th 70 --medium-th 40
"""
from __future__ import annotations
import os, sys, io, argparse, time, math
from pathlib import Path
from typing import Dict, List, Tuple
import polars as pl
import pyarrow.parquet as pq

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

def log(m: str) -> None:
    print(m, flush=True)

def iter_parquets(ticker_dir: Path):
    # Espera estructura ticker/year=*/month=*/minute.parquet
    if not ticker_dir.exists():
        return
    for ydir in sorted(ticker_dir.glob("year=*")):
        year = ydir.name.split("=")[-1]
        for mdir in sorted(ydir.glob("month=*")):
            month = mdir.name.split("=")[-1]
            fp = mdir / "minute.parquet"
            if fp.exists():
                yield year, month, fp

def parquet_rows_and_size(fp: Path) -> Tuple[int, int]:
    # Usa metadatos (rápido y sin RAM). num_rows puede ser 0 si faltan row groups.
    try:
        pf = pq.ParquetFile(str(fp))
        nrows = pf.metadata.num_rows if pf.metadata is not None else 0
    except Exception:
        # Si hay corrupción puntual, considera 0 filas y cuenta bytes
        nrows = 0
    size = fp.stat().st_size
    return nrows, size

def quantile_rank(values: List[float], x: float) -> float:
    # Devuelve percentil 0..100 (posición relativa) para x respecto a 'values'
    if not values:
        return 0.0
    vs = sorted(values)
    # búsqueda binaria simple
    lo, hi = 0, len(vs)
    while lo < hi:
        mid = (lo + hi) // 2
        if vs[mid] <= x: lo = mid + 1
        else: hi = mid
    return 100.0 * lo / max(1, len(vs) - 1)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, help="Directorio raíz de intradía 1m (raw/polygon/ohlcv_intraday_1m)")
    ap.add_argument("--out", required=True, help="Directorio de salida para reports")
    ap.add_argument("--heavy-th", type=float, default=70.0, help="Umbral score para heavy (0-100)")
    ap.add_argument("--medium-th", type=float, default=40.0, help="Umbral score para medium (0-100)")
    args = ap.parse_args()

    root = Path(args.root)
    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")

    tickers = [p.name for p in root.iterdir() if p.is_dir()]
    log(f"Escaneando {len(tickers):,} tickers en {root} ...")

    rows_list: List[Dict] = []
    for i, t in enumerate(sorted(tickers)):
        tdir = root / t
        months = 0
        files = 0
        total_rows = 0
        total_bytes = 0
        first_ym = None
        last_ym = None
        for year, month, fp in iter_parquets(tdir):
            files += 1
            months += 1
            nrows, nbytes = parquet_rows_and_size(fp)
            total_rows += nrows
            total_bytes += nbytes
            ym = f"{year}-{month}"
            if first_ym is None or ym < first_ym:
                first_ym = ym
            if last_ym is None or ym > last_ym:
                last_ym = ym
        rows_list.append({
            "ticker": t,
            "files": files,
            "months": months,
            "total_rows": total_rows,
            "total_bytes": total_bytes,
            "first_month": first_ym or "",
            "last_month": last_ym or "",
            "years_span": (int(last_ym[:4]) - int(first_ym[:4]) + 1) if (first_ym and last_ym) else 0
        })
        if (i+1) % 100 == 0:
            log(f"  ... {i+1:,}/{len(tickers):,} tickers escaneados")

    if not rows_list:
        log("No se encontraron datos. ¿Ruta correcta?")
        sys.exit(1)

    df = pl.DataFrame(rows_list)
    # Evita divisiones por cero
    df = df.with_columns([
        pl.when(pl.col("files") > 0).then(pl.col("total_rows") / pl.col("files")).otherwise(0.0).alias("avg_rows_per_file"),
        pl.when(pl.col("months") > 0).then(pl.col("total_rows") / pl.col("months")).otherwise(0.0).alias("avg_rows_per_month"),
    ])

    # Rankings percentiles (0..100). Convertimos a listas Python para la función.
    rows_vals  = df["total_rows"].to_list()
    bytes_vals = df["total_bytes"].to_list()
    mons_vals  = df["months"].to_list()

    score_rows  = [quantile_rank(rows_vals,  x) for x in rows_vals]
    score_bytes = [quantile_rank(bytes_vals, x) for x in bytes_vals]
    score_mons  = [quantile_rank(mons_vals,  x) for x in mons_vals]

    # Score final: media ponderada (ajusta pesos si quieres)
    w_rows, w_bytes, w_mons = 0.5, 0.3, 0.2
    score = [round(w_rows*a + w_bytes*b + w_mons*c, 2) for a,b,c in zip(score_rows, score_bytes, score_mons)]

    df = df.with_columns([
        pl.Series("score_rows",  score),
        pl.Series("score_bytes", score_bytes),
        pl.Series("score_months",score_mons),
    ])

    # Clasificación por umbrales
    heavy_th  = float(args.heavy_th)
    medium_th = float(args.medium_th)

    df = df.with_columns([
        pl.when(pl.col("score_rows") >= heavy_th)
          .then(pl.lit("heavy"))
          .when(pl.col("score_rows") >= medium_th)
          .then(pl.lit("medium"))
          .otherwise(pl.lit("light")).alias("class_rows"),

        pl.when(pl.col("score_bytes") >= heavy_th)
          .then(pl.lit("heavy"))
          .when(pl.col("score_bytes") >= medium_th)
          .then(pl.lit("medium"))
          .otherwise(pl.lit("light")).alias("class_bytes"),

        pl.when(pl.col("score_months") >= heavy_th)
          .then(pl.lit("heavy"))
          .when(pl.col("score_months") >= medium_th)
          .then(pl.lit("medium"))
          .otherwise(pl.lit("light")).alias("class_months"),

        pl.when(pl.Series(score) >= heavy_th)
          .then(pl.lit("heavy"))
          .when(pl.Series(score) >= medium_th)
          .then(pl.lit("medium"))
          .otherwise(pl.lit("light")).alias("class_overall")
    ]).with_columns([
        pl.Series("score_overall", score)
    ])

    # Orden útil
    df = df.sort(["class_overall","score_overall","total_rows","total_bytes"], descending=[True,True,True,True])

    # Salidas
    report_csv = outdir / f"intraday_1m_footprint_{ts}.csv"
    df.write_csv(report_csv)

    heavy = df.filter(pl.col("class_overall") == "heavy").select(["ticker"])
    normal = df.filter(pl.col("class_overall") != "heavy").select(["ticker"])

    heavy_file  = outdir / "heavy_tickers.csv"
    normal_file = outdir / "normal_tickers.csv"
    heavy.write_csv(heavy_file)
    normal.write_csv(normal_file)

    # Markdown resumen (top 30)
    top_md = outdir / f"intraday_1m_footprint_{ts}.md"
    top = df.head(30).select([
        "ticker","class_overall","score_overall","months","files","total_rows","total_bytes","first_month","last_month"
    ])
    with open(top_md, "w", encoding="utf-8") as f:
        f.write("# Intraday 1m Footprint — Top 30 por heaviness\n\n")
        f.write(top.to_pandas().to_markdown(index=False))

    log(f"\n✅ Reporte CSV: {report_csv}")
    log(f"✅ Heavy list : {heavy_file}  (tickers={heavy.height})")
    log(f"✅ Normal list: {normal_file} (tickers={normal.height})")
    log(f"📝 Resumen MD : {top_md}")

if __name__ == "__main__":
    main()
