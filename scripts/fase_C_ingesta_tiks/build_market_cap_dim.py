#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
build_market_cap_dim.py
Construye dimension SCD-2 de market cap desde snapshots de ticker_details.

Fuente: raw/polygon/reference/ticker_details/as_of_date=YYYY-MM-DD/details.parquet

Output: processed/ref/market_cap_dim/market_cap_dim.parquet
Schema: ticker, effective_from, effective_to, market_cap, shares_outstanding

Estrategia:
1. Consolidar snapshots en SCD-2 (effective_from, effective_to)
2. Imputar market_cap faltante con close_d × shares_outstanding (opcional)
3. Cerrar rangos abiertos con 2099-12-31

Uso:
  # Generar SCD-2 desde snapshots
  python build_market_cap_dim.py \
    --details-root raw/polygon/reference/ticker_details \
    --outdir processed/ref/market_cap_dim

  # Con imputacion desde daily_cache
  python build_market_cap_dim.py \
    --details-root raw/polygon/reference/ticker_details \
    --outdir processed/ref/market_cap_dim \
    --daily-cache processed/daily_cache \
    --impute
"""
from __future__ import annotations
import argparse, datetime as dt, json
from pathlib import Path
from typing import Optional
import polars as pl

def log(msg: str):
    print(f"[{dt.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)

def list_ticker_details_snapshots(root: Path) -> list[tuple[dt.date, Path]]:
    """
    Lista snapshots de ticker_details ordenados por fecha
    Returns: [(date, path_to_details.parquet)]
    """
    snapshots = []
    for as_of_dir in root.glob("as_of_date=*"):
        if as_of_dir.is_dir():
            date_str = as_of_dir.name.split("=")[1]
            try:
                as_of_date = dt.datetime.strptime(date_str, "%Y-%m-%d").date()
                details_path = as_of_dir / "details.parquet"
                if details_path.exists():
                    snapshots.append((as_of_date, details_path))
            except ValueError:
                log(f"[WARN] Ignorando directorio con formato invalido: {as_of_dir.name}")
                continue

    snapshots.sort(key=lambda x: x[0])
    return snapshots

def load_snapshots(snapshots: list[tuple[dt.date, Path]]) -> pl.DataFrame:
    """
    Carga todos los snapshots y añade columna as_of_date
    Proyecta solo: ticker, market_cap, shares_outstanding, as_of_date

    ROBUSTO: Usa coalesce para shares_outstanding (soporta múltiples nombres de columna)
    """
    if not snapshots:
        return pl.DataFrame()

    dfs = []
    for as_of_date, path in snapshots:
        raw_df = pl.read_parquet(path)

        # Detectar qué columnas de shares están disponibles
        available_cols = raw_df.columns
        shares_candidates = []

        # Orden de preferencia: share_class > weighted > shares_outstanding
        if "share_class_shares_outstanding" in available_cols:
            shares_candidates.append(pl.col("share_class_shares_outstanding").cast(pl.Float64))
        if "weighted_shares_outstanding" in available_cols:
            shares_candidates.append(pl.col("weighted_shares_outstanding").cast(pl.Float64))
        if "shares_outstanding" in available_cols:
            shares_candidates.append(pl.col("shares_outstanding").cast(pl.Float64))

        if not shares_candidates:
            log(f"[WARN] Snapshot {as_of_date} no tiene columnas de shares_outstanding, usando null")
            shares_expr = pl.lit(None).cast(pl.Float64).alias("shares_outstanding")
        else:
            shares_expr = pl.coalesce(shares_candidates).alias("shares_outstanding")

        df = raw_df.select([
            "ticker",
            pl.col("market_cap").cast(pl.Float64).alias("market_cap"),
            shares_expr,
        ])
        df = df.with_columns(pl.lit(as_of_date).alias("as_of_date"))
        dfs.append(df)

    all_snapshots = pl.concat(dfs)
    log(f"Cargados {len(all_snapshots)} registros desde {len(snapshots)} snapshots")

    return all_snapshots

def build_scd2(snapshots_df: pl.DataFrame) -> pl.DataFrame:
    """
    Construye SCD-2: effective_from, effective_to

    Reglas:
    - effective_from = as_of_date del snapshot
    - effective_to = as_of_date del siguiente snapshot (o null si es el ultimo)
    - Si market_cap o shares no cambian entre snapshots consecutivos, NO crear nuevo registro
    """
    if snapshots_df.is_empty():
        return pl.DataFrame()

    # Ordenar por ticker y fecha
    sorted_df = snapshots_df.sort(["ticker", "as_of_date"])

    # Detectar cambios en market_cap o shares_outstanding
    scd2 = (
        sorted_df
        .with_columns([
            # Valores anteriores (por ticker)
            pl.col("market_cap").shift(1).over("ticker").alias("prev_cap"),
            pl.col("shares_outstanding").shift(1).over("ticker").alias("prev_shares"),
        ])
        .with_columns([
            # Detectar cambio (o primer registro)
            (
                (pl.col("market_cap") != pl.col("prev_cap")) |
                (pl.col("shares_outstanding") != pl.col("prev_shares")) |
                (pl.col("prev_cap").is_null())
            ).alias("is_change")
        ])
        .filter(pl.col("is_change"))  # Solo registros con cambios
        .with_columns([
            pl.col("as_of_date").alias("effective_from"),
            # effective_to = siguiente as_of_date del mismo ticker (o null)
            pl.col("as_of_date").shift(-1).over("ticker").alias("effective_to")
        ])
        .select([
            "ticker", "effective_from", "effective_to",
            "market_cap", "shares_outstanding"
        ])
    )

    # Cerrar rangos abiertos (effective_to null -> 2099-12-31)
    scd2 = scd2.with_columns([
        pl.col("effective_to").fill_null(pl.date(2099, 12, 31))
    ])

    log(f"SCD-2 generada: {len(scd2)} periodos de validez")

    return scd2

def impute_market_cap_from_cache(
    scd2: pl.DataFrame,
    cache_root: Path
) -> pl.DataFrame:
    """
    Imputa market_cap faltante usando close_d × shares_outstanding desde daily_cache

    Estrategia:
    - Para cada (ticker, periodo SCD-2) donde market_cap es null pero shares != null:
      - Cargar daily_cache del ticker
      - Filtrar por rango [effective_from, effective_to)
      - Calcular: market_cap_imputed = close_d × shares_outstanding
      - Tomar mediana de market_cap_imputed en el periodo
    """
    if scd2.is_empty():
        return scd2

    # Tickers con market_cap null pero shares disponible
    to_impute = scd2.filter(
        pl.col("market_cap").is_null() &
        pl.col("shares_outstanding").is_not_null()
    )

    if to_impute.is_empty():
        log("No hay market_caps para imputar")
        return scd2

    log(f"Imputando market_cap para {len(to_impute)} periodos...")

    imputed_caps = []

    for row in to_impute.iter_rows(named=True):
        ticker = row["ticker"]
        eff_from = row["effective_from"]
        eff_to = row["effective_to"]
        shares = row["shares_outstanding"]

        # Cargar daily_cache del ticker
        cache_path = cache_root / f"ticker={ticker}" / "daily.parquet"
        if not cache_path.exists():
            continue

        try:
            daily = pl.read_parquet(cache_path, columns=["trading_day", "close_d"])

            # ESTRATEGIA MEJORADA: Si el rango [eff_from, eff_to) tiene pocos datos,
            # usar los ultimos 30 dias disponibles en daily_cache
            daily_period = daily.filter(
                (pl.col("trading_day") >= eff_from) &
                (pl.col("trading_day") < eff_to)
            )

            # Si tenemos <5 dias en el rango SCD-2, usar ultimos 30 dias disponibles
            if len(daily_period) < 5:
                daily_period = daily.sort("trading_day").tail(30)

            if daily_period.is_empty():
                continue

            # Calcular market_cap_imputed = close_d × shares
            daily_period = daily_period.with_columns([
                (pl.col("close_d") * shares).alias("cap_imputed")
            ])

            # Mediana del periodo (mas robusta que promedio)
            cap_median = daily_period["cap_imputed"].median()

            imputed_caps.append({
                "ticker": ticker,
                "effective_from": eff_from,
                "effective_to": eff_to,
                "market_cap_imputed": cap_median
            })

        except Exception as e:
            log(f"[WARN] Error imputando {ticker}: {e}")
            continue

    if not imputed_caps:
        log("No se pudo imputar ningún market_cap")
        return scd2

    # Crear DF con imputaciones
    imputed_df = pl.DataFrame(imputed_caps)

    # Join con SCD-2 original
    scd2_final = (
        scd2.join(
            imputed_df,
            on=["ticker", "effective_from", "effective_to"],
            how="left"
        )
        .with_columns([
            # Coalesce: usar market_cap original, si no, imputado
            pl.coalesce([pl.col("market_cap"), pl.col("market_cap_imputed")]).alias("market_cap")
        ])
        .select(["ticker", "effective_from", "effective_to", "market_cap", "shares_outstanding"])
    )

    log(f"Imputados {len(imputed_caps)} market_caps")

    return scd2_final

def write_dimension(dim: pl.DataFrame, outdir: Path):
    """Escribe dimension SCD-2 con ZSTD + MANIFEST + _SUCCESS"""
    if dim.is_empty():
        log("[ERROR] Dimension vacia, no se escribe")
        return

    outdir.mkdir(parents=True, exist_ok=True)

    # Escribir parquet
    dim_path = outdir / "market_cap_dim.parquet"
    dim.write_parquet(
        dim_path,
        compression="zstd",
        compression_level=2,
        statistics=True
    )

    # MANIFEST
    manifest = {
        "timestamp": dt.datetime.now().isoformat(),
        "total_tickers": dim["ticker"].n_unique(),
        "total_periods": len(dim),
        "date_range": {
            "min": dim["effective_from"].min().isoformat(),
            "max": dim["effective_to"].max().isoformat(),
        },
        "market_cap_coverage": {
            "total": len(dim),
            "with_cap": dim.filter(pl.col("market_cap").is_not_null()).height,
            "with_shares": dim.filter(pl.col("shares_outstanding").is_not_null()).height,
        }
    }

    manifest_path = outdir / "MANIFEST.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    # _SUCCESS
    (outdir / "_SUCCESS").touch()

    log(f"Dimension escrita: {dim_path}")
    log(f"Tickers unicos: {manifest['total_tickers']}")
    log(f"Periodos SCD-2: {manifest['total_periods']}")
    log(f"Cobertura market_cap: {manifest['market_cap_coverage']['with_cap']} / {manifest['total_periods']} "
        f"({100*manifest['market_cap_coverage']['with_cap']/manifest['total_periods']:.1f}%)")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--details-root", required=True, help="raw/polygon/reference/ticker_details")
    ap.add_argument("--outdir", required=True, help="processed/ref/market_cap_dim")
    ap.add_argument("--daily-cache", type=str, default=None, help="processed/daily_cache (para imputacion)")
    ap.add_argument("--impute", action="store_true", help="Imputar market_cap faltante desde daily_cache")
    args = ap.parse_args()

    details_root = Path(args.details_root)
    outdir = Path(args.outdir)

    log("=== BUILD MARKET CAP DIMENSION (SCD-2) ===")
    log(f"Details root: {details_root}")
    log(f"Output dir: {outdir}")
    log(f"Imputacion: {args.impute}")

    # 1. Listar snapshots
    snapshots = list_ticker_details_snapshots(details_root)
    if not snapshots:
        log("[ERROR] No se encontraron snapshots de ticker_details")
        return

    log(f"Snapshots encontrados: {len(snapshots)}")
    for date, path in snapshots:
        log(f"  - {date}: {path}")

    # 2. Cargar snapshots
    snapshots_df = load_snapshots(snapshots)

    # 3. Construir SCD-2
    scd2 = build_scd2(snapshots_df)

    # 4. (Opcional) Imputar market_cap faltante
    if args.impute and args.daily_cache:
        cache_root = Path(args.daily_cache)
        if cache_root.exists():
            scd2 = impute_market_cap_from_cache(scd2, cache_root)
        else:
            log(f"[WARN] Daily cache no encontrado: {cache_root}")

    # 5. Escribir dimension
    write_dimension(scd2, outdir)

    log("=== COMPLETADO ===")

if __name__ == "__main__":
    main()
