#!/usr/bin/env python3
"""
Auditoría completa de toda la data descargada en fase_01.

Este script:
1. Escanea toda la data descargada de Polygon (trades, minute bars, quotes, etc)
2. Identifica qué granularidades tenemos disponibles
3. Selecciona muestras estratégicas para validación externa
4. Genera reporte detallado de qué tenemos y qué se puede comparar

Usage:
    python audit_fase01_data.py --raw-root ../../../../../../raw/polygon
"""

import argparse
import json
import pathlib
import sys
from datetime import datetime
from typing import Dict, List, Tuple
import pandas as pd


def scan_directory_structure(root: pathlib.Path) -> Dict[str, Dict]:
    """
    Escanea la estructura de directorios y cuenta archivos por tipo de data.

    Returns:
        Dict con estructura: {data_type: {symbol: [dates]}}
    """
    structure = {}

    if not root.exists():
        print(f"[ERROR] Root directory does not exist: {root}")
        return structure

    # Escanear subdirectorios principales
    for data_type_dir in root.iterdir():
        if not data_type_dir.is_dir():
            continue

        data_type = data_type_dir.name
        structure[data_type] = {}

        print(f"\n[SCANNING] {data_type}/")

        # Escanear símbolos dentro de cada tipo de data
        symbol_count = 0
        file_count = 0

        for symbol_dir in data_type_dir.iterdir():
            if not symbol_dir.is_dir() or symbol_dir.name.startswith("_"):
                continue

            symbol = symbol_dir.name
            dates = []

            # Buscar archivos parquet en subdirectorios de fecha
            for date_dir in symbol_dir.rglob("date=*"):
                if date_dir.is_dir():
                    date_str = date_dir.name.replace("date=", "")
                    parquet_files = list(date_dir.glob("*.parquet"))
                    if parquet_files:
                        dates.append(date_str)
                        file_count += len(parquet_files)

            # También buscar en estructura year/month
            for parquet_file in symbol_dir.rglob("*.parquet"):
                if parquet_file.name not in ["_SUCCESS"]:
                    file_count += 1

            if dates or list(symbol_dir.rglob("*.parquet")):
                structure[data_type][symbol] = sorted(dates) if dates else ["[year/month structure]"]
                symbol_count += 1

        print(f"  -> {symbol_count} symbols, {file_count} files")

    return structure


def analyze_data_granularity(structure: Dict[str, Dict]) -> Dict[str, any]:
    """
    Analiza qué granularidades de data tenemos disponibles.

    Returns:
        Dict con análisis de granularidades disponibles
    """
    analysis = {
        "tick_level": [],      # trades, quotes
        "minute_level": [],    # intraday_1m, ohlcv_intraday_1m
        "daily_level": [],     # daily_ohlcv, ohlcv_daily
        "other": []
    }

    for data_type, symbols in structure.items():
        if not symbols:
            continue

        if data_type in ["trades", "quotes"]:
            analysis["tick_level"].append({
                "type": data_type,
                "symbol_count": len(symbols),
                "sample_symbols": list(symbols.keys())[:5]
            })
        elif "1m" in data_type.lower() or "intraday" in data_type.lower():
            analysis["minute_level"].append({
                "type": data_type,
                "symbol_count": len(symbols),
                "sample_symbols": list(symbols.keys())[:5]
            })
        elif "daily" in data_type.lower():
            analysis["daily_level"].append({
                "type": data_type,
                "symbol_count": len(symbols),
                "sample_symbols": list(symbols.keys())[:5]
            })
        else:
            analysis["other"].append({
                "type": data_type,
                "symbol_count": len(symbols),
                "sample_symbols": list(symbols.keys())[:5]
            })

    return analysis


def suggest_comparison_strategy(analysis: Dict) -> Dict[str, List]:
    """
    Sugiere estrategia de comparación basada en data disponible.

    Returns:
        Dict con estrategias por nivel de granularidad
    """
    strategies = {}

    # Tick-level comparisons
    if analysis["tick_level"]:
        strategies["tick_level"] = {
            "our_data": [item["type"] for item in analysis["tick_level"]],
            "external_vendors": [
                "Polygon Flat Files (if available)",
                "FirstRate Data (paid)",
                "QuantQuote (paid)"
            ],
            "feasibility": "DIFÍCIL - Most vendors don't provide tick data on free tier",
            "recommendation": "Compare aggregated minute bars from our ticks vs vendor minute bars"
        }

    # Minute-level comparisons
    if analysis["minute_level"]:
        strategies["minute_level"] = {
            "our_data": [item["type"] for item in analysis["minute_level"]],
            "external_vendors": [
                "Alpha Vantage (FREE - 5 calls remaining)",
                "Twelve Data (FREE - 6/8 calls remaining)",
                "IEX Cloud (FREE tier available)",
                "Finnhub (FREE tier available)"
            ],
            "feasibility": "ALTA - Multiple free vendors support minute bars",
            "recommendation": "PRIMARY COMPARISON - Use Alpha Vantage + Twelve Data for validation",
            "expected_match_rate": "85-95% (minute vs minute bars)"
        }

    # Daily-level comparisons
    if analysis["daily_level"]:
        strategies["daily_level"] = {
            "our_data": [item["type"] for item in analysis["daily_level"]],
            "external_vendors": [
                "Yahoo Finance (FREE - unlimited)",
                "Alpha Vantage (FREE)",
                "Twelve Data (FREE)",
                "IEX Cloud (FREE)"
            ],
            "feasibility": "MUY ALTA - Daily data widely available",
            "recommendation": "Use Yahoo Finance for broad validation, others for confirmation",
            "expected_match_rate": "95-99% (daily OHLCV should match closely)"
        }

    return strategies


def select_strategic_samples(structure: Dict[str, Dict], n_samples: int = 10) -> List[Tuple[str, str]]:
    """
    Selecciona muestras estratégicas para validación.

    Criteria:
    - High volume tickers (NVDA, AAPL, SPY)
    - Low volume tickers (small caps)
    - Recent dates (2025)
    - Different market conditions

    Returns:
        List of (symbol, date) tuples
    """
    samples = []

    # Priority symbols
    priority_symbols = ["WOLF", "NVDA", "AAPL", "SPY", "AMC", "TSLA", "GME"]

    # Get minute data structure
    minute_data = None
    for data_type, symbols in structure.items():
        if "1m" in data_type.lower() or "minute" in data_type.lower():
            minute_data = symbols
            break

    if not minute_data:
        print("[WARN] No minute data found for sampling")
        return samples

    # Select from priority symbols
    for symbol in priority_symbols:
        if symbol in minute_data:
            dates = minute_data[symbol]
            if dates and dates[0] != "[year/month structure]":
                # Pick a recent date
                recent_dates = [d for d in dates if d.startswith("2025")]
                if recent_dates:
                    samples.append((symbol, recent_dates[-1]))
                elif dates:
                    samples.append((symbol, dates[-1]))

        if len(samples) >= n_samples:
            break

    # Fill remaining with random small caps
    if len(samples) < n_samples:
        for symbol, dates in minute_data.items():
            if symbol not in priority_symbols:
                if dates and dates[0] != "[year/month structure]":
                    recent_dates = [d for d in dates if d.startswith("2025")]
                    if recent_dates:
                        samples.append((symbol, recent_dates[-1]))
                        if len(samples) >= n_samples:
                            break

    return samples


def main():
    parser = argparse.ArgumentParser(description="Audit all fase_01 downloaded data")
    parser.add_argument("--raw-root", required=True, help="Path to raw/polygon directory")
    parser.add_argument("--output", default="audit_fase01_report.json", help="Output report file")
    parser.add_argument("--samples", type=int, default=10, help="Number of strategic samples")

    args = parser.parse_args()

    raw_root = pathlib.Path(args.raw_root).resolve()

    print("=" * 70)
    print("AUDITORÍA DE DATA FASE_01")
    print("=" * 70)
    print(f"Root: {raw_root}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print()

    # 1. Scan directory structure
    print("[STEP 1] Scanning directory structure...")
    structure = scan_directory_structure(raw_root)

    # 2. Analyze granularity
    print("\n[STEP 2] Analyzing data granularity...")
    analysis = analyze_data_granularity(structure)

    print("\n--- GRANULARITY ANALYSIS ---")
    print(f"Tick-level data types: {len(analysis['tick_level'])}")
    for item in analysis["tick_level"]:
        print(f"  • {item['type']}: {item['symbol_count']} symbols")

    print(f"\nMinute-level data types: {len(analysis['minute_level'])}")
    for item in analysis["minute_level"]:
        print(f"  * {item['type']}: {item['symbol_count']} symbols")

    print(f"\nDaily-level data types: {len(analysis['daily_level'])}")
    for item in analysis["daily_level"]:
        print(f"  * {item['type']}: {item['symbol_count']} symbols")

    # 3. Suggest comparison strategy
    print("\n[STEP 3] Suggesting comparison strategy...")
    strategies = suggest_comparison_strategy(analysis)

    print("\n--- COMPARISON STRATEGIES ---")
    for level, strategy in strategies.items():
        print(f"\n{level.upper().replace('_', ' ')}:")
        print(f"  Our data: {', '.join(strategy['our_data'])}")
        print(f"  External vendors: {', '.join(strategy['external_vendors'])}")
        print(f"  Feasibility: {strategy['feasibility']}")
        print(f"  Recommendation: {strategy['recommendation']}")
        if "expected_match_rate" in strategy:
            print(f"  Expected match rate: {strategy['expected_match_rate']}")

    # 4. Select strategic samples
    print("\n[STEP 4] Selecting strategic samples...")
    samples = select_strategic_samples(structure, args.samples)

    print(f"\n--- STRATEGIC SAMPLES ({len(samples)}) ---")
    for symbol, date in samples:
        print(f"  * {symbol} @ {date}")

    # 5. Generate report
    report = {
        "timestamp": datetime.now().isoformat(),
        "raw_root": str(raw_root),
        "structure": {k: {sym: (dates if isinstance(dates, list) else "structured")
                          for sym, dates in v.items()}
                      for k, v in structure.items()},
        "analysis": analysis,
        "strategies": strategies,
        "strategic_samples": [{"symbol": s, "date": d} for s, d in samples]
    }

    output_file = pathlib.Path(args.output)
    with open(output_file, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\n[DONE] Report saved to: {output_file}")
    print("=" * 70)


if __name__ == "__main__":
    main()
