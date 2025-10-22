#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
select_universe_cs.py
Filtra el universo descargado para obtener solo Common Stocks (CS) de XNAS/XNYS.
Opcionalmente aplica filtro de market cap máximo para small-caps.

Uso:
    python select_universe_cs.py \
        --snapdir raw/polygon/reference/tickers_snapshot/snapshot_date=2025-10-19 \
        --details raw/polygon/reference/ticker_details \
        --cap-max 2000000000 \
        --out-csv processed/universe/cs_xnas_xnys_under2b.csv \
        --out-parquet processed/universe/cs_xnas_xnys_under2b.parquet
"""
import argparse
from pathlib import Path
import polars as pl

def main():
    ap = argparse.ArgumentParser(description="Selecciona universo CS de XNAS/XNYS")
    ap.add_argument("--snapdir", required=True,
                    help="Directorio del snapshot: .../tickers_snapshot/snapshot_date=YYYY-MM-DD")
    ap.add_argument("--details", required=False,
                    help="Directorio de ticker details (opcional, para filtro market cap)")
    ap.add_argument("--cap-max", type=float, default=None,
                    help="Market cap máximo en USD (ej: 2000000000 para <$2B)")
    ap.add_argument("--out-csv", required=True,
                    help="Archivo CSV de salida con lista de tickers")
    ap.add_argument("--out-parquet", required=False,
                    help="Archivo Parquet de salida (opcional, con metadatos)")
    args = ap.parse_args()

    # Leer snapshot
    snap_path = Path(args.snapdir)
    if not snap_path.exists():
        raise FileNotFoundError(f"Snapshot no encontrado: {snap_path}")

    df = pl.read_parquet(snap_path)
    print(f"Total tickers en snapshot: {df.height:,}")

    # Filtrar: solo Common Stock (CS) en XNAS/XNYS
    # ARCX se excluye porque es principalmente ETFs
    df = df.filter(
        (pl.col("type") == "CS") &
        (pl.col("primary_exchange").is_in(["XNAS", "XNYS"]))
    )
    print(f"Tickers CS en XNAS/XNYS: {df.height:,}")

    # Aplicar filtro de market cap si se especifica
    if args.details and args.cap_max is not None:
        details_path = Path(args.details)
        if details_path.exists():
            # Buscar archivos de details
            detail_files = list(details_path.rglob("*.parquet"))
            if detail_files:
                det = pl.concat([pl.read_parquet(f) for f in detail_files])

                # Buscar columna de market cap (puede tener varios nombres)
                mcap_cols = [c for c in det.columns
                            if c.lower() in ("market_cap", "marketcap", "market_capitalization")]

                if mcap_cols:
                    mcap_col = mcap_cols[0]
                    det = det.select(["ticker", mcap_col]).rename({mcap_col: "market_cap"})

                    # Join con datos de market cap
                    df = df.join(det, on="ticker", how="left")

                    # Filtrar por market cap
                    pre_filter = df.height
                    df = df.filter(
                        pl.col("market_cap").is_not_null() &
                        (pl.col("market_cap") < args.cap_max)
                    )
                    print(f"Tickers con market_cap < ${args.cap_max:,.0f}: {df.height:,} "
                          f"(excluidos {pre_filter - df.height:,} sin datos o > cap)")
                else:
                    print(f"ADVERTENCIA: No se encontró columna market_cap en details")
        else:
            print(f"ADVERTENCIA: Directorio details no existe: {details_path}")

    # Seleccionar columnas para output
    out_cols = ["ticker", "name", "primary_exchange", "type", "sector", "industry",
                "cik", "list_date", "active"]
    out_cols = [c for c in out_cols if c in df.columns]
    df = df.select(out_cols).unique(subset=["ticker"]).sort("ticker")

    # Escribir CSV (lista simple de tickers)
    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    df.select(["ticker"]).write_csv(out_csv)
    print(f"\n✓ CSV creado: {out_csv}")
    print(f"  Total tickers: {df.height:,}")

    # Escribir Parquet (con metadatos completos)
    if args.out_parquet:
        out_pq = Path(args.out_parquet)
        out_pq.parent.mkdir(parents=True, exist_ok=True)
        df.write_parquet(out_pq)
        print(f"✓ Parquet creado: {out_pq}")

    # Estadísticas finales
    print(f"\n=== UNIVERSO FINAL ===")
    print(f"Total tickers CS (XNAS/XNYS): {df.height:,}")

    if "primary_exchange" in df.columns:
        print(f"\nDistribución por exchange:")
        by_exch = df.group_by("primary_exchange").len().sort("len", descending=True)
        for row in by_exch.iter_rows():
            exch_name = {"XNAS": "NASDAQ", "XNYS": "NYSE"}.get(row[0], row[0])
            print(f"  {exch_name}: {row[1]:,} ({row[1]/df.height*100:.1f}%)")

if __name__ == "__main__":
    main()
