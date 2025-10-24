#!/usr/bin/env python
"""
Crear universo híbrido para small caps sin sesgo de supervivencia:
- Activos < $2B (filtrados por market_cap)
- Inactivos SIN FILTRAR (todos incluidos)

Fundamento: López de Prado - evitar survivorship bias
"""
import sys
import datetime as dt
from pathlib import Path
import polars as pl

# Force UTF-8 output
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

def log(msg):
    print(f"[{dt.datetime.now():%F %T}] {msg}", flush=True)

def main():
    log("=" * 100)
    log("CREACION DE UNIVERSO HIBRIDO - SIN SESGO DE SUPERVIVENCIA")
    log("=" * 100)

    # Paths
    cs_filtered_path = Path("processed/universe/cs_all_xnas_xnys.parquet")
    details_path = Path("raw/polygon/reference/ticker_details/ticker_details_2025-10-24.parquet")
    output_dir = Path("processed/universe")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load CS filtered (10,599 CS en XNAS/XNYS)
    log("\nStep 1: Loading CS filtered tickers...")
    df_cs = pl.read_parquet(cs_filtered_path)
    log(f"Total CS tickers (XNAS/XNYS): {len(df_cs):,}")

    active_cs = df_cs.filter(pl.col("active") == True)
    inactive_cs = df_cs.filter(pl.col("active") == False)
    log(f"  - Activos:   {len(active_cs):,}")
    log(f"  - Inactivos: {len(inactive_cs):,}")

    # Load ticker details (tiene market_cap solo para activos)
    log("\nStep 2: Loading ticker details (market_cap data)...")
    df_details = pl.read_parquet(details_path)
    log(f"Total details descargados: {len(df_details):,}")

    # Filter activos < $2B
    log("\nStep 3: Filtering activos con market_cap < $2B...")
    df_details_with_cap = df_details.filter(
        (pl.col("market_cap").is_not_null()) &
        (pl.col("market_cap") < 2_000_000_000)
    )
    log(f"Activos con market_cap < $2B: {len(df_details_with_cap):,}")

    # Get tickers activos < $2B
    tickers_activos_under_2b = set(df_details_with_cap["ticker"].to_list())

    # Filter CS: activos < $2B
    df_activos_filtered = df_cs.filter(
        (pl.col("active") == True) &
        (pl.col("ticker").is_in(list(tickers_activos_under_2b)))
    )
    log(f"Activos < $2B en CS dataset: {len(df_activos_filtered):,}")

    # Include ALL inactivos (sin filtrar por market_cap)
    df_inactivos_all = df_cs.filter(pl.col("active") == False)
    log(f"Inactivos (TODOS, sin filtrar): {len(df_inactivos_all):,}")

    # Combine: activos filtered + inactivos all
    log("\nStep 4: Creating hybrid universe...")
    df_hybrid = pl.concat([df_activos_filtered, df_inactivos_all])
    log(f"Total universo hibrido: {len(df_hybrid):,}")
    log(f"  - Activos < $2B:    {len(df_activos_filtered):,} ({len(df_activos_filtered)/len(df_hybrid)*100:.1f}%)")
    log(f"  - Inactivos (all):  {len(df_inactivos_all):,} ({len(df_inactivos_all)/len(df_hybrid)*100:.1f}%)")

    # Save hybrid universe
    output_parquet = output_dir / f"cs_xnas_xnys_hybrid_{dt.date.today().isoformat()}.parquet"
    df_hybrid.write_parquet(output_parquet)
    log(f"\nSaved: {output_parquet}")

    # Save as CSV for inspection
    output_csv = output_dir / f"cs_xnas_xnys_hybrid_{dt.date.today().isoformat()}.csv"
    cols_csv = ["ticker", "name", "primary_exchange", "type", "active", "cik"]
    df_hybrid.select([col for col in cols_csv if col in df_hybrid.columns]).write_csv(output_csv)
    log(f"Saved: {output_csv}")

    # Distribution by exchange
    log("\n" + "=" * 100)
    log("DISTRIBUCION POR EXCHANGE")
    log("=" * 100)
    for exchange in ["XNAS", "XNYS"]:
        total = df_hybrid.filter(pl.col("primary_exchange") == exchange).height
        active = df_hybrid.filter(
            (pl.col("primary_exchange") == exchange) & (pl.col("active") == True)
        ).height
        inactive = total - active
        log(f"{exchange}: {total:>6,} total ({active:>5,} activos, {inactive:>5,} inactivos)")

    # Summary
    log("\n" + "=" * 100)
    log("RESUMEN FINAL")
    log("=" * 100)
    log(f"""
UNIVERSO HIBRIDO CREADO:
  Total:              {len(df_hybrid):>6,} tickers

  Composicion:
    - Activos < $2B:  {len(df_activos_filtered):>6,} tickers (filtrados por market_cap)
    - Inactivos ALL:  {len(df_inactivos_all):>6,} tickers (sin filtrar - evita survivorship bias)

  Exchanges:
    - NASDAQ (XNAS):  {df_hybrid.filter(pl.col('primary_exchange') == 'XNAS').height:>6,} tickers
    - NYSE (XNYS):    {df_hybrid.filter(pl.col('primary_exchange') == 'XNYS').height:>6,} tickers

  Archivos generados:
    ✅ {output_parquet}
    ✅ {output_csv}

FUNDAMENTO:
  - Lopez de Prado: "Survivorship bias is one of the most severe biases in backtesting"
  - Incluir delisted es CRITICO para entrenar modelos de pump & dump
  - Los inactivos contienen las señales mas fuertes de pumps terminales
""")
    log("=" * 100)

if __name__ == "__main__":
    main()
