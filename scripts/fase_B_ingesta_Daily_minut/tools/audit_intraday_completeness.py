#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
audit_intraday_completeness.py

Auditoría exhaustiva de completitud de datos intradía descargados.

Verifica:
1. Tickers descargados vs universo esperado
2. Cobertura temporal por ticker (años/meses)
3. Validez de archivos parquet
4. Gaps en datos
5. Estadísticas de rows por ticker

Uso:
  python tools/audit_intraday_completeness.py \
    --universe processed/universe/cs_xnas_xnys_under2b_2025-10-21.csv \
    --datadir raw/polygon/ohlcv_intraday_1m \
    --windows 2004-01-01:2010-12-31,2011-01-01:2016-12-31,2017-01-01:2025-10-21 \
    --outdir audit_reports
"""
import os
import sys
import io
import argparse
import datetime as dt
from pathlib import Path
from typing import Dict, List, Set, Tuple
from collections import defaultdict
import polars as pl
import json

# UTF-8 encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

def log(msg: str) -> None:
    print(f"[{dt.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)

def parse_windows(s: str) -> List[Tuple[dt.date, dt.date, str]]:
    """Parse window string into list of (start_date, end_date, tag)."""
    windows = []
    for part in s.split(","):
        part = part.strip()
        if not part:
            continue
        start_str, end_str = part.split(":")
        start_date = dt.datetime.strptime(start_str.strip(), "%Y-%m-%d").date()
        end_date = dt.datetime.strptime(end_str.strip(), "%Y-%m-%d").date()
        tag = f"{start_str.strip()}_{end_str.strip()}"
        windows.append((start_date, end_date, tag))
    return windows

def generate_expected_months(start_date: dt.date, end_date: dt.date) -> Set[str]:
    """Generate set of expected year-month strings (YYYY-MM) for date range."""
    expected = set()
    current = start_date.replace(day=1)
    end = end_date.replace(day=1)

    while current <= end:
        expected.add(current.strftime("%Y-%m"))
        # Next month
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)

    return expected

def scan_ticker_data(datadir: Path, ticker: str) -> Dict[str, any]:
    """Scan data for a single ticker and return metadata."""
    ticker_dir = datadir / ticker

    if not ticker_dir.exists():
        return {
            "exists": False,
            "months": [],
            "total_rows": 0,
            "total_files": 0,
            "corrupt_files": [],
            "empty_files": [],
            "date_range": None,
        }

    months = []
    total_rows = 0
    total_files = 0
    corrupt_files = []
    empty_files = []
    min_date = None
    max_date = None

    # Scan year=*/month=* structure
    for year_dir in ticker_dir.glob("year=*"):
        year = year_dir.name.replace("year=", "")
        for month_dir in year_dir.glob("month=*"):
            month = month_dir.name.replace("month=", "")
            parquet_file = month_dir / "minute.parquet"

            if not parquet_file.exists():
                continue

            total_files += 1
            ym = f"{year}-{month}"

            try:
                df = pl.read_parquet(parquet_file)
                rows = df.height

                if rows == 0:
                    empty_files.append(ym)
                else:
                    months.append(ym)
                    total_rows += rows

                    # Get date range
                    if "date" in df.columns:
                        dates = df["date"].unique().sort()
                        file_min = dates.min()
                        file_max = dates.max()

                        if min_date is None or file_min < min_date:
                            min_date = file_min
                        if max_date is None or file_max > max_date:
                            max_date = file_max

            except Exception as e:
                corrupt_files.append({"file": ym, "error": str(e)})

    date_range = None
    if min_date and max_date:
        date_range = f"{min_date} to {max_date}"

    return {
        "exists": True,
        "months": sorted(months),
        "total_rows": total_rows,
        "total_files": total_files,
        "corrupt_files": corrupt_files,
        "empty_files": empty_files,
        "date_range": date_range,
    }

def audit_completeness(universe_csv: Path, datadir: Path, windows: List[Tuple], outdir: Path) -> None:
    """Run full completeness audit."""
    outdir.mkdir(parents=True, exist_ok=True)

    log("="*80)
    log("AUDITORÍA DE COMPLETITUD DE DATOS INTRADÍA")
    log("="*80)

    # 1. Load universe
    log(f"Cargando universo de tickers: {universe_csv}")
    universe_df = pl.read_csv(universe_csv)
    if "ticker" not in universe_df.columns:
        raise ValueError("CSV debe contener columna 'ticker'")

    expected_tickers = set(universe_df["ticker"].drop_nulls().unique().to_list())
    log(f"  Tickers esperados: {len(expected_tickers):,}")

    # 2. Scan downloaded data
    log(f"\nEscaneando datos descargados en: {datadir}")

    ticker_metadata = {}
    downloaded_tickers = set()

    for ticker in sorted(expected_tickers):
        if (len(ticker_metadata) + 1) % 100 == 0:
            log(f"  Progreso: {len(ticker_metadata)+1:,}/{len(expected_tickers):,}")

        metadata = scan_ticker_data(datadir, ticker)
        ticker_metadata[ticker] = metadata

        if metadata["exists"] and metadata["total_rows"] > 0:
            downloaded_tickers.add(ticker)

    missing_tickers = expected_tickers - downloaded_tickers

    log(f"\n{'='*80}")
    log(f"RESUMEN GLOBAL:")
    log(f"  Tickers esperados:    {len(expected_tickers):,}")
    log(f"  Tickers descargados:  {len(downloaded_tickers):,} ({100*len(downloaded_tickers)/len(expected_tickers):.1f}%)")
    log(f"  Tickers faltantes:    {len(missing_tickers):,} ({100*len(missing_tickers)/len(expected_tickers):.1f}%)")
    log(f"{'='*80}\n")

    # 3. Analyze coverage by window
    log("COBERTURA POR VENTANA:")

    window_coverage = {}
    for start_date, end_date, tag in windows:
        expected_months = generate_expected_months(start_date, end_date)

        tickers_with_full_coverage = 0
        tickers_with_partial_coverage = 0
        tickers_with_no_coverage = 0

        coverage_details = []

        for ticker in sorted(downloaded_tickers):
            metadata = ticker_metadata[ticker]
            ticker_months = set(metadata["months"])

            overlap = ticker_months & expected_months
            coverage_pct = 100 * len(overlap) / len(expected_months) if expected_months else 0

            if coverage_pct == 100:
                tickers_with_full_coverage += 1
            elif coverage_pct > 0:
                tickers_with_partial_coverage += 1
            else:
                tickers_with_no_coverage += 1

            missing_months = expected_months - ticker_months
            coverage_details.append({
                "ticker": ticker,
                "coverage_pct": round(coverage_pct, 2),
                "months_present": len(overlap),
                "months_expected": len(expected_months),
                "months_missing": sorted(list(missing_months)),
                "total_rows": metadata["total_rows"],
            })

        window_coverage[tag] = {
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
            "expected_months": len(expected_months),
            "tickers_full_coverage": tickers_with_full_coverage,
            "tickers_partial_coverage": tickers_with_partial_coverage,
            "tickers_no_coverage": tickers_with_no_coverage,
            "coverage_details": coverage_details,
        }

        log(f"\n  Ventana: {tag}")
        log(f"    Período: {start_date} → {end_date}")
        log(f"    Meses esperados: {len(expected_months)}")
        log(f"    Tickers con cobertura 100%:   {tickers_with_full_coverage:,} ({100*tickers_with_full_coverage/len(downloaded_tickers):.1f}%)")
        log(f"    Tickers con cobertura parcial: {tickers_with_partial_coverage:,} ({100*tickers_with_partial_coverage/len(downloaded_tickers):.1f}%)")
        log(f"    Tickers sin datos en ventana:  {tickers_with_no_coverage:,} ({100*tickers_with_no_coverage/len(downloaded_tickers):.1f}%)")

    # 4. Detect issues
    log(f"\n{'='*80}")
    log("DETECCIÓN DE PROBLEMAS:")

    corrupt_count = sum(1 for m in ticker_metadata.values() if m.get("corrupt_files"))
    empty_count = sum(1 for m in ticker_metadata.values() if m.get("empty_files"))

    log(f"  Tickers con archivos corruptos: {corrupt_count}")
    log(f"  Tickers con archivos vacíos:    {empty_count}")

    # 5. Row statistics
    log(f"\n{'='*80}")
    log("ESTADÍSTICAS DE ROWS:")

    total_rows = sum(m["total_rows"] for m in ticker_metadata.values() if m["exists"])
    total_files = sum(m["total_files"] for m in ticker_metadata.values() if m["exists"])

    log(f"  Total rows descargadas:   {total_rows:,}")
    log(f"  Total archivos parquet:   {total_files:,}")
    log(f"  Promedio rows/ticker:     {total_rows/len(downloaded_tickers):,.0f}" if downloaded_tickers else "  N/A")
    log(f"  Promedio archivos/ticker: {total_files/len(downloaded_tickers):.1f}" if downloaded_tickers else "  N/A")

    # 6. Generate reports
    log(f"\n{'='*80}")
    log("GENERANDO REPORTES:")

    # Missing tickers
    missing_file = outdir / "missing_tickers.txt"
    missing_file.write_text("\n".join(sorted(missing_tickers)), encoding="utf-8")
    log(f"  ✓ {missing_file}")

    # Downloaded tickers
    downloaded_file = outdir / "downloaded_tickers.txt"
    downloaded_file.write_text("\n".join(sorted(downloaded_tickers)), encoding="utf-8")
    log(f"  ✓ {downloaded_file}")

    # Detailed metadata JSON
    metadata_file = outdir / "ticker_metadata.json"
    metadata_file.write_text(json.dumps(ticker_metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"  ✓ {metadata_file}")

    # Window coverage JSON
    coverage_file = outdir / "window_coverage.json"
    coverage_file.write_text(json.dumps(window_coverage, indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"  ✓ {coverage_file}")

    # Summary CSV
    summary_data = []
    for ticker in sorted(expected_tickers):
        metadata = ticker_metadata.get(ticker, {})
        summary_data.append({
            "ticker": ticker,
            "downloaded": ticker in downloaded_tickers,
            "total_rows": metadata.get("total_rows", 0),
            "total_files": metadata.get("total_files", 0),
            "months_count": len(metadata.get("months", [])),
            "date_range": metadata.get("date_range", ""),
            "has_corrupt_files": len(metadata.get("corrupt_files", [])) > 0,
            "has_empty_files": len(metadata.get("empty_files", [])) > 0,
        })

    summary_df = pl.DataFrame(summary_data)
    summary_file = outdir / "completeness_summary.csv"
    summary_df.write_csv(summary_file)
    log(f"  ✓ {summary_file}")

    # Tickers needing download (with priority)
    priority_list = []
    for ticker in missing_tickers:
        priority_list.append({
            "ticker": ticker,
            "status": "NOT_DOWNLOADED",
            "priority": "HIGH",
        })

    for ticker in downloaded_tickers:
        metadata = ticker_metadata[ticker]
        if metadata.get("corrupt_files"):
            priority_list.append({
                "ticker": ticker,
                "status": "CORRUPT_FILES",
                "priority": "HIGH",
            })
        elif metadata.get("empty_files"):
            priority_list.append({
                "ticker": ticker,
                "status": "EMPTY_FILES",
                "priority": "MEDIUM",
            })

    priority_df = pl.DataFrame(priority_list)
    priority_file = outdir / "download_priority.csv"
    priority_df.write_csv(priority_file)
    log(f"  ✓ {priority_file}")

    log(f"\n{'='*80}")
    log(f"AUDITORÍA COMPLETADA")
    log(f"Reportes guardados en: {outdir}")
    log(f"{'='*80}\n")

def main():
    ap = argparse.ArgumentParser(description="Auditoría de completitud de datos intradía")
    ap.add_argument("--universe", required=True, help="CSV con universo de tickers esperados")
    ap.add_argument("--datadir", required=True, help="Directorio con datos descargados")
    ap.add_argument("--windows", required=True, help="Ventanas de fechas (formato: YYYY-MM-DD:YYYY-MM-DD,...)")
    ap.add_argument("--outdir", default="audit_reports", help="Directorio para reportes de auditoría")
    args = ap.parse_args()

    universe_csv = Path(args.universe)
    datadir = Path(args.datadir)
    outdir = Path(args.outdir)

    if not universe_csv.exists():
        raise FileNotFoundError(f"No existe: {universe_csv}")
    if not datadir.exists():
        raise FileNotFoundError(f"No existe: {datadir}")

    windows = parse_windows(args.windows)

    audit_completeness(universe_csv, datadir, windows, outdir)

if __name__ == "__main__":
    main()
