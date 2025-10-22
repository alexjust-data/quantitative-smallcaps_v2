#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
analyze_complete_tickers.py

Análisis profundo de tickers con cobertura 100% en ventanas temporales.

Verifica:
1. Qué tickers tienen 100% cobertura en cada ventana
2. Tickers con 100% en múltiples/todas las ventanas
3. Calidad de datos (continuidad, gaps diarios, volumen)
4. Estadísticas descriptivas (rows/día, n trades, etc.)
5. Comparación con tickers parciales

Uso:
  python tools/analyze_complete_tickers.py \
    --coverage-json audit_reports/intraday_1m_2025-10-21/window_coverage.json \
    --metadata-json audit_reports/intraday_1m_2025-10-21/ticker_metadata.json \
    --datadir raw/polygon/ohlcv_intraday_1m \
    --outdir audit_reports/complete_tickers_analysis
"""
import os
import sys
import io
import argparse
import datetime as dt
from pathlib import Path
from typing import Dict, List, Set, Tuple
from collections import defaultdict, Counter
import polars as pl
import json

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

def log(msg: str) -> None:
    print(f"[{dt.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)

def load_json(path: Path) -> dict:
    """Load JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def get_complete_tickers_by_window(coverage_data: dict) -> Dict[str, Set[str]]:
    """Extract tickers with 100% coverage per window."""
    complete_by_window = {}

    for window_tag, window_data in coverage_data.items():
        complete_tickers = set()
        for detail in window_data["coverage_details"]:
            if detail["coverage_pct"] == 100.0:
                complete_tickers.add(detail["ticker"])
        complete_by_window[window_tag] = complete_tickers

    return complete_by_window

def analyze_ticker_quality(datadir: Path, ticker: str) -> Dict:
    """Deep quality analysis of a single ticker's data."""
    ticker_dir = datadir / ticker

    if not ticker_dir.exists():
        return {"error": "Directory not found"}

    all_data = []
    files_read = 0

    # Collect all data
    for year_dir in sorted(ticker_dir.glob("year=*")):
        for month_dir in sorted(year_dir.glob("month=*")):
            parquet_file = month_dir / "minute.parquet"
            if not parquet_file.exists():
                continue

            try:
                df = pl.read_parquet(parquet_file)
                if df.height > 0:
                    all_data.append(df)
                    files_read += 1
            except Exception as e:
                return {"error": f"Failed to read {parquet_file}: {e}"}

    if not all_data:
        return {"error": "No data found"}

    # Combine all data
    full_df = pl.concat(all_data, how="vertical_relaxed")

    # Quality metrics
    total_rows = full_df.height
    unique_dates = full_df["date"].n_unique()
    unique_minutes = full_df["minute"].n_unique()

    # Date range
    min_date = full_df["date"].min()
    max_date = full_df["date"].max()

    # Trading days analysis
    date_counts = full_df.group_by("date").agg(pl.count().alias("minutes_per_day"))
    avg_minutes_per_day = date_counts["minutes_per_day"].mean()
    min_minutes_per_day = date_counts["minutes_per_day"].min()
    max_minutes_per_day = date_counts["minutes_per_day"].max()

    # Volume analysis
    total_volume = full_df["v"].sum() if "v" in full_df.columns else 0
    avg_volume_per_minute = full_df["v"].mean() if "v" in full_df.columns else 0

    # Trade count analysis
    total_trades = full_df["n"].sum() if "n" in full_df.columns else 0
    avg_trades_per_minute = full_df["n"].mean() if "n" in full_df.columns else 0

    # Price analysis
    if all(col in full_df.columns for col in ["o", "h", "l", "c"]):
        price_range = {
            "min_low": full_df["l"].min(),
            "max_high": full_df["h"].max(),
            "avg_close": full_df["c"].mean(),
        }
    else:
        price_range = None

    # Check for duplicates
    duplicates = full_df.filter(pl.col("minute").is_duplicated()).height

    # Check for gaps in trading days
    dates = sorted(full_df["date"].unique().to_list())
    gaps = []
    for i in range(len(dates) - 1):
        current = dt.datetime.strptime(dates[i], "%Y-%m-%d").date()
        next_date = dt.datetime.strptime(dates[i + 1], "%Y-%m-%d").date()
        days_diff = (next_date - current).days

        # If gap > 7 days (more than weekend), consider it a gap
        if days_diff > 7:
            gaps.append({
                "from": dates[i],
                "to": dates[i + 1],
                "days": days_diff
            })

    return {
        "total_rows": total_rows,
        "unique_dates": unique_dates,
        "unique_minutes": unique_minutes,
        "date_range": f"{min_date} to {max_date}",
        "files_read": files_read,
        "avg_minutes_per_day": round(avg_minutes_per_day, 1) if avg_minutes_per_day else 0,
        "min_minutes_per_day": min_minutes_per_day,
        "max_minutes_per_day": max_minutes_per_day,
        "total_volume": int(total_volume) if total_volume else 0,
        "avg_volume_per_minute": round(avg_volume_per_minute, 2) if avg_volume_per_minute else 0,
        "total_trades": int(total_trades) if total_trades else 0,
        "avg_trades_per_minute": round(avg_trades_per_minute, 2) if avg_trades_per_minute else 0,
        "price_range": price_range,
        "duplicates": duplicates,
        "gaps_count": len(gaps),
        "major_gaps": gaps[:5] if len(gaps) > 0 else [],  # Top 5 gaps
    }

def analyze_complete_tickers(coverage_json: Path, metadata_json: Path, datadir: Path, outdir: Path):
    """Run deep analysis on complete tickers."""
    outdir.mkdir(parents=True, exist_ok=True)

    log("="*80)
    log("ANÁLISIS PROFUNDO DE TICKERS 100% COMPLETOS")
    log("="*80)

    # Load data
    log("\nCargando datos de cobertura y metadatos...")
    coverage_data = load_json(coverage_json)
    metadata = load_json(metadata_json)

    # Get complete tickers by window
    complete_by_window = get_complete_tickers_by_window(coverage_data)

    log(f"\nTickers con 100% cobertura por ventana:")
    for window_tag, tickers in complete_by_window.items():
        log(f"  {window_tag}: {len(tickers)} tickers")

    # Find tickers complete in multiple windows
    all_windows = set(complete_by_window.keys())

    complete_in_all = set.intersection(*[complete_by_window[w] for w in all_windows])
    complete_in_two = set()
    complete_in_one = set()

    for ticker in set.union(*[complete_by_window[w] for w in all_windows]):
        windows_count = sum(1 for w in all_windows if ticker in complete_by_window[w])
        if windows_count == len(all_windows):
            continue  # Already in complete_in_all
        elif windows_count == 2:
            complete_in_two.add(ticker)
        elif windows_count == 1:
            complete_in_one.add(ticker)

    log(f"\n{'='*80}")
    log(f"DISTRIBUCIÓN DE COMPLETITUD:")
    log(f"  Tickers completos en TODAS las ventanas ({len(all_windows)}): {len(complete_in_all)}")
    log(f"  Tickers completos en 2 ventanas:           {len(complete_in_two)}")
    log(f"  Tickers completos en 1 ventana:            {len(complete_in_one)}")
    log(f"{'='*80}\n")

    if complete_in_all:
        log(f"🏆 TICKERS CON COBERTURA 100% EN TODAS LAS VENTANAS:")
        for ticker in sorted(complete_in_all):
            log(f"  • {ticker}")
    else:
        log(f"⚠️  NINGÚN TICKER tiene cobertura 100% en todas las ventanas")

    # Detailed analysis of all complete tickers
    log(f"\n{'='*80}")
    log(f"ANÁLISIS DE CALIDAD DE DATOS (esto puede tardar)...")
    log(f"{'='*80}\n")

    quality_analysis = {}
    all_complete = set.union(*[complete_by_window[w] for w in all_windows])

    for i, ticker in enumerate(sorted(all_complete), 1):
        if i % 10 == 0 or i == len(all_complete):
            log(f"  Progreso: {i}/{len(all_complete)}")

        quality = analyze_ticker_quality(datadir, ticker)

        # Add window completion info
        windows_complete = [w for w in all_windows if ticker in complete_by_window[w]]
        quality["windows_complete"] = windows_complete
        quality["windows_count"] = len(windows_complete)

        quality_analysis[ticker] = quality

    # Generate statistics
    log(f"\n{'='*80}")
    log(f"ESTADÍSTICAS DESCRIPTIVAS:")
    log(f"{'='*80}\n")

    # Filter out error entries
    valid_quality = {t: q for t, q in quality_analysis.items() if "error" not in q}

    if valid_quality:
        total_rows_list = [q["total_rows"] for q in valid_quality.values()]
        unique_dates_list = [q["unique_dates"] for q in valid_quality.values()]
        avg_minutes_list = [q["avg_minutes_per_day"] for q in valid_quality.values()]

        log(f"Total rows (suma de todos los tickers): {sum(total_rows_list):,}")
        log(f"Promedio rows por ticker: {sum(total_rows_list)/len(total_rows_list):,.0f}")
        log(f"Mediana rows por ticker: {sorted(total_rows_list)[len(total_rows_list)//2]:,}")
        log(f"Min rows: {min(total_rows_list):,}")
        log(f"Max rows: {max(total_rows_list):,}")
        log(f"\nPromedio días únicos por ticker: {sum(unique_dates_list)/len(unique_dates_list):.1f}")
        log(f"Promedio minutos/día: {sum(avg_minutes_list)/len(avg_minutes_list):.1f}")

        # Tickers with gaps
        tickers_with_gaps = [(t, q["gaps_count"]) for t, q in valid_quality.items() if q["gaps_count"] > 0]
        log(f"\nTickers con gaps (>7 días): {len(tickers_with_gaps)}/{len(valid_quality)}")

        if tickers_with_gaps:
            log(f"\nTop 10 tickers con más gaps:")
            for ticker, gap_count in sorted(tickers_with_gaps, key=lambda x: x[1], reverse=True)[:10]:
                log(f"  {ticker}: {gap_count} gaps")

        # Tickers with duplicates
        tickers_with_dups = [(t, q["duplicates"]) for t, q in valid_quality.items() if q["duplicates"] > 0]
        if tickers_with_dups:
            log(f"\n⚠️  Tickers con duplicados:")
            for ticker, dup_count in sorted(tickers_with_dups, key=lambda x: x[1], reverse=True):
                log(f"  {ticker}: {dup_count} filas duplicadas")
        else:
            log(f"\n✓ Ningún ticker tiene duplicados")

    # By-window analysis
    log(f"\n{'='*80}")
    log(f"ANÁLISIS POR VENTANA:")
    log(f"{'='*80}\n")

    for window_tag in sorted(all_windows):
        tickers = complete_by_window[window_tag]
        log(f"\n{window_tag} ({len(tickers)} tickers):")

        window_quality = {t: q for t, q in quality_analysis.items()
                         if t in tickers and "error" not in q}

        if window_quality:
            total = sum(q["total_rows"] for q in window_quality.values())
            avg = total / len(window_quality)
            log(f"  Total rows: {total:,}")
            log(f"  Promedio rows/ticker: {avg:,.0f}")

            # Top 5 tickers by rows
            top_5 = sorted(window_quality.items(), key=lambda x: x[1]["total_rows"], reverse=True)[:5]
            log(f"  Top 5 tickers por volumen de datos:")
            for ticker, q in top_5:
                log(f"    • {ticker}: {q['total_rows']:,} rows, {q['unique_dates']} días")

    # Save reports
    log(f"\n{'='*80}")
    log(f"GENERANDO REPORTES:")
    log(f"{'='*80}\n")

    # Complete tickers lists
    for window_tag, tickers in complete_by_window.items():
        filename = outdir / f"complete_100pct_{window_tag}.txt"
        filename.write_text("\n".join(sorted(tickers)), encoding="utf-8")
        log(f"  ✓ {filename}")

    # Tickers complete in all windows
    if complete_in_all:
        filename = outdir / "complete_ALL_windows.txt"
        filename.write_text("\n".join(sorted(complete_in_all)), encoding="utf-8")
        log(f"  ✓ {filename}")

    # Tickers complete in 2 windows
    if complete_in_two:
        filename = outdir / "complete_TWO_windows.txt"
        filename.write_text("\n".join(sorted(complete_in_two)), encoding="utf-8")
        log(f"  ✓ {filename}")

    # Quality analysis JSON
    quality_file = outdir / "quality_analysis.json"
    quality_file.write_text(json.dumps(quality_analysis, indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"  ✓ {quality_file}")

    # Summary CSV
    summary_data = []
    for ticker in sorted(all_complete):
        q = quality_analysis.get(ticker, {})
        if "error" in q:
            continue

        summary_data.append({
            "ticker": ticker,
            "windows_count": q["windows_count"],
            "windows": ",".join(q["windows_complete"]),
            "total_rows": q["total_rows"],
            "unique_dates": q["unique_dates"],
            "date_range": q["date_range"],
            "avg_minutes_per_day": q["avg_minutes_per_day"],
            "total_volume": q["total_volume"],
            "total_trades": q["total_trades"],
            "has_gaps": q["gaps_count"] > 0,
            "gaps_count": q["gaps_count"],
            "has_duplicates": q["duplicates"] > 0,
            "duplicates": q["duplicates"],
        })

    if summary_data:
        summary_df = pl.DataFrame(summary_data)
        summary_file = outdir / "complete_tickers_summary.csv"
        summary_df.write_csv(summary_file)
        log(f"  ✓ {summary_file}")

        # Detailed breakdown by windows_count
        breakdown_file = outdir / "completeness_breakdown.txt"
        with open(breakdown_file, "w", encoding="utf-8") as f:
            f.write("="*80 + "\n")
            f.write("DESGLOSE DE TICKERS POR NÚMERO DE VENTANAS COMPLETAS\n")
            f.write("="*80 + "\n\n")

            for count in [3, 2, 1]:
                tickers = [row["ticker"] for row in summary_data if row["windows_count"] == count]
                f.write(f"\n{count} ventana(s) completas ({len(tickers)} tickers):\n")
                f.write("-" * 80 + "\n")

                for ticker in sorted(tickers):
                    q = quality_analysis[ticker]
                    f.write(f"{ticker}:\n")
                    f.write(f"  Ventanas: {', '.join(q['windows_complete'])}\n")
                    f.write(f"  Rows: {q['total_rows']:,}\n")
                    f.write(f"  Días únicos: {q['unique_dates']}\n")
                    f.write(f"  Rango: {q['date_range']}\n")
                    if q['gaps_count'] > 0:
                        f.write(f"  ⚠️  Gaps detectados: {q['gaps_count']}\n")
                    if q['duplicates'] > 0:
                        f.write(f"  ⚠️  Duplicados: {q['duplicates']}\n")
                    f.write("\n")

        log(f"  ✓ {breakdown_file}")

    log(f"\n{'='*80}")
    log(f"ANÁLISIS COMPLETADO")
    log(f"Reportes guardados en: {outdir}")
    log(f"{'='*80}\n")

def main():
    ap = argparse.ArgumentParser(description="Análisis profundo de tickers 100% completos")
    ap.add_argument("--coverage-json", required=True, help="JSON con datos de cobertura por ventana")
    ap.add_argument("--metadata-json", required=True, help="JSON con metadata de tickers")
    ap.add_argument("--datadir", required=True, help="Directorio con datos descargados")
    ap.add_argument("--outdir", default="audit_reports/complete_tickers_analysis",
                    help="Directorio para reportes de análisis")
    args = ap.parse_args()

    coverage_json = Path(args.coverage_json)
    metadata_json = Path(args.metadata_json)
    datadir = Path(args.datadir)
    outdir = Path(args.outdir)

    if not coverage_json.exists():
        raise FileNotFoundError(f"No existe: {coverage_json}")
    if not metadata_json.exists():
        raise FileNotFoundError(f"No existe: {metadata_json}")
    if not datadir.exists():
        raise FileNotFoundError(f"No existe: {datadir}")

    analyze_complete_tickers(coverage_json, metadata_json, datadir, outdir)

if __name__ == "__main__":
    main()
