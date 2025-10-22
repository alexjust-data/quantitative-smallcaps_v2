#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
benchmark_universe_build.py
Compara build_dynamic_universe.py (original) vs build_dynamic_universe_optimized.py

Validaciones:
1. Cobertura: dias por ticker en cache vs esperado
2. Consistencia: sum(vol_1m) ≈ vol_d (tolerancia 1%)
3. Continuidad: has_gaps coherente con session_rows
4. Ranking: topN generado identico (+-1% por redondeos)

Uso:
  python benchmark_universe_build.py \
    --cache processed/daily_cache \
    --intraday-root raw/polygon/ohlcv_intraday_1m \
    --test-range 2025-10-01:2025-10-21 \
    --sample-tickers 50
"""
from __future__ import annotations
import argparse, datetime as dt, time
from pathlib import Path
import polars as pl
import subprocess

def log(msg: str):
    print(f"[{dt.datetime.now():%H:%M:%S}] {msg}", flush=True)

def run_command(cmd: list[str], desc: str) -> tuple[float, int]:
    """Ejecuta comando y retorna (tiempo_seg, exit_code)"""
    log(f"[RUN] {desc}")
    log(f"  Cmd: {' '.join(cmd)}")

    start = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True)
    elapsed = time.time() - start

    if proc.returncode != 0:
        log(f"[ERROR] {desc} failed:")
        log(proc.stderr)

    return elapsed, proc.returncode

def validate_coverage(cache_root: Path, date_from: dt.date, date_to: dt.date, sample_size: int = 50):
    """
    Validacion 1: Cobertura
    Verifica que cada ticker tenga ~N dias de mercado (excluyendo fines de semana)
    """
    log("\n=== VALIDACION 1: COBERTURA ===")

    # Generar dias esperados (simplificacion: Lun-Vie)
    expected_days = []
    cur = date_from
    while cur <= date_to:
        if cur.weekday() < 5:
            expected_days.append(cur)
        cur += dt.timedelta(days=1)

    expected_count = len(expected_days)
    log(f"Dias de mercado esperados: {expected_count}")

    # Samplear tickers
    ticker_dirs = list(cache_root.glob("ticker=*"))[:sample_size]
    log(f"Validando {len(ticker_dirs)} tickers...")

    coverage_ok = 0
    coverage_warn = 0

    for tdir in ticker_dirs:
        ticker = tdir.name.split("=")[1]
        parquet = tdir / "daily.parquet"

        if not parquet.exists():
            log(f"  {ticker}: FALTA cache")
            continue

        df = pl.read_parquet(parquet, columns=["trading_day"])
        actual_count = len(df)

        # Tolerancia: +-5% (por feriados no modelados)
        if abs(actual_count - expected_count) / expected_count <= 0.05:
            coverage_ok += 1
        else:
            coverage_warn += 1
            log(f"  {ticker}: {actual_count} dias (esperado ~{expected_count})")

    log(f"Cobertura OK: {coverage_ok}/{len(ticker_dirs)}")
    log(f"Cobertura WARN: {coverage_warn}/{len(ticker_dirs)}")

    return coverage_ok / len(ticker_dirs) if ticker_dirs else 0.0

def validate_consistency(cache_root: Path, intraday_root: Path, sample_size: int = 10):
    """
    Validacion 2: Consistencia
    Verifica que vol_d = sum(vol_1m) (tolerancia 1%)
    """
    log("\n=== VALIDACION 2: CONSISTENCIA ===")

    ticker_dirs = list(cache_root.glob("ticker=*"))[:sample_size]
    log(f"Validando {len(ticker_dirs)} tickers...")

    consistent = 0
    inconsistent = 0

    for tdir in ticker_dirs:
        ticker = tdir.name.split("=")[1]
        cache_parquet = tdir / "daily.parquet"

        if not cache_parquet.exists():
            continue

        # Leer cache
        cache = pl.read_parquet(cache_parquet).select(["trading_day", "vol_d"])

        # Samplear 1 dia aleatorio
        if cache.is_empty():
            continue

        sample_day = cache["trading_day"][0]

        # Leer 1-min de ese dia
        tdir_1m = intraday_root / ticker
        if not tdir_1m.exists():
            continue

        y, m = sample_day.year, sample_day.month
        path_1m = tdir_1m / f"year={y}" / f"month={m:02d}" / "minute.parquet"

        if not path_1m.exists():
            continue

        df_1m = (
            pl.scan_parquet(path_1m)
            .filter(pl.col("date") == sample_day.strftime("%Y-%m-%d"))
            .select(["v"])
            .collect()
        )

        if df_1m.is_empty():
            continue

        vol_1m_sum = df_1m["v"].sum()
        vol_d = cache.filter(pl.col("trading_day") == sample_day)["vol_d"][0]

        # Tolerancia 1%
        diff_pct = abs(vol_1m_sum - vol_d) / vol_d if vol_d > 0 else 0.0

        if diff_pct <= 0.01:
            consistent += 1
        else:
            inconsistent += 1
            log(f"  {ticker} {sample_day}: vol_d={vol_d:,}, sum(1m)={vol_1m_sum:,}, diff={diff_pct:.2%}")

    log(f"Consistencia OK: {consistent}/{len(ticker_dirs)}")
    log(f"Inconsistencia: {inconsistent}/{len(ticker_dirs)}")

    return consistent / len(ticker_dirs) if ticker_dirs else 0.0

def validate_continuity(cache_root: Path, sample_size: int = 50):
    """
    Validacion 3: Continuidad
    Verifica que has_gaps sea coherente con session_rows
    """
    log("\n=== VALIDACION 3: CONTINUIDAD ===")

    ticker_dirs = list(cache_root.glob("ticker=*"))[:sample_size]
    log(f"Validando {len(ticker_dirs)} tickers...")

    coherent = 0
    incoherent = 0

    for tdir in ticker_dirs:
        ticker = tdir.name.split("=")[1]
        parquet = tdir / "daily.parquet"

        if not parquet.exists():
            continue

        df = pl.read_parquet(parquet).select(["session_rows", "has_gaps"])

        # Regla: has_gaps = True si session_rows < 390
        check = df.with_columns([
            (pl.col("session_rows") < 390).alias("expected_gaps")
        ])

        mismatches = check.filter(pl.col("has_gaps") != pl.col("expected_gaps"))

        if mismatches.is_empty():
            coherent += 1
        else:
            incoherent += 1
            log(f"  {ticker}: {len(mismatches)} dias con has_gaps incoherente")

    log(f"Continuidad OK: {coherent}/{len(ticker_dirs)}")
    log(f"Continuidad WARN: {incoherent}/{len(ticker_dirs)}")

    return coherent / len(ticker_dirs) if ticker_dirs else 0.0

def validate_ranking(
    original_topn: Path,
    optimized_topn: Path
):
    """
    Validacion 4: Ranking
    Verifica que topN_12m generado sea identico (tolerancia 1%)
    """
    log("\n=== VALIDACION 4: RANKING ===")

    if not original_topn.exists() or not optimized_topn.exists():
        log("[WARN] Falta alguno de los topN_12m, skip")
        return None

    orig = pl.read_parquet(original_topn)
    opt = pl.read_parquet(optimized_topn)

    # Top 200
    orig_top200 = set(orig.head(200)["ticker"].to_list())
    opt_top200 = set(opt.head(200)["ticker"].to_list())

    common = orig_top200 & opt_top200
    diff = (orig_top200 | opt_top200) - common

    pct_match = len(common) / 200

    log(f"Top 200: {len(common)} en comun, {len(diff)} diferentes")
    log(f"Match: {pct_match:.1%}")

    if diff:
        log(f"  Diferentes: {sorted(diff)[:10]} ...")

    return pct_match

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True, help="processed/daily_cache")
    ap.add_argument("--intraday-root", required=True, help="raw/polygon/ohlcv_intraday_1m")
    ap.add_argument("--test-range", required=True, help="2025-10-01:2025-10-21")
    ap.add_argument("--sample-tickers", type=int, default=50)
    args = ap.parse_args()

    cache_root = Path(args.cache)
    intraday_root = Path(args.intraday_root)

    # Parsear rango
    date_from_str, date_to_str = args.test_range.split(":")
    date_from = dt.datetime.strptime(date_from_str, "%Y-%m-%d").date()
    date_to = dt.datetime.strptime(date_to_str, "%Y-%m-%d").date()

    log("=== BENCHMARK UNIVERSE BUILD ===")
    log(f"Cache: {cache_root}")
    log(f"Intraday: {intraday_root}")
    log(f"Test range: {date_from} -> {date_to}")
    log(f"Sample size: {args.sample_tickers}")

    # VALIDACIONES (sin ejecutar scripts, solo validar cache existente)

    # 1. Cobertura
    cov_score = validate_coverage(cache_root, date_from, date_to, args.sample_tickers)

    # 2. Consistencia
    cons_score = validate_consistency(cache_root, intraday_root, min(args.sample_tickers, 10))

    # 3. Continuidad
    cont_score = validate_continuity(cache_root, args.sample_tickers)

    # 4. Ranking (si existen ambos topN)
    # (esto requeriria ejecutar ambos scripts, omitimos por ahora)

    # RESUMEN
    log("\n=== RESUMEN ===")
    log(f"Cobertura:    {cov_score:.1%}")
    log(f"Consistencia: {cons_score:.1%}")
    log(f"Continuidad:  {cont_score:.1%}")

    # Score global
    global_score = (cov_score + cons_score + cont_score) / 3
    log(f"\nScore global: {global_score:.1%}")

    if global_score >= 0.95:
        log("RESULTADO: EXCELENTE - Cache validado")
    elif global_score >= 0.85:
        log("RESULTADO: BUENO - Revisar advertencias")
    else:
        log("RESULTADO: NECESITA ATENCION - Revisar errores")

if __name__ == "__main__":
    main()
