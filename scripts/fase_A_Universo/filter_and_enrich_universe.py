#!/usr/bin/env python
"""
Filtrar universo y enriquecer con market cap:
1. Filtrar solo Common Stock (CS) del snapshot
2. Descargar ticker details (market_cap, shares outstanding, etc.)
3. Filtrar por market cap < $2B
4. Guardar universo final
"""
import os
import sys
import time
import datetime as dt
from pathlib import Path
import requests
import polars as pl
from concurrent.futures import ThreadPoolExecutor, as_completed

# Force UTF-8 output
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BASE_URL = "https://api.polygon.io"
TIMEOUT = 20
MAX_WORKERS = 32
RATE_LIMIT = 0.15  # seconds between requests

def log(msg):
    print(f"[{dt.datetime.now():%F %T}] {msg}", flush=True)

def get_ticker_details(api_key, ticker):
    """Fetch ticker details from Polygon API"""
    url = f"{BASE_URL}/v3/reference/tickers/{ticker}"

    for attempt in range(6):
        try:
            time.sleep(RATE_LIMIT)  # Rate limiting
            r = requests.get(url, timeout=TIMEOUT, headers={"Authorization": f"Bearer {api_key}"})

            if r.status_code == 429:
                retry_after = int(r.headers.get("Retry-After", "2"))
                log(f"Rate limited on {ticker}, waiting {retry_after}s")
                time.sleep(retry_after)
                continue

            if r.status_code == 404:
                log(f"Ticker {ticker} not found (404)")
                return {"ticker": ticker, "error": "not_found"}

            r.raise_for_status()
            data = r.json().get("results", {})
            data["ticker"] = ticker
            data["fetch_date"] = dt.date.today().isoformat()
            return data

        except Exception as e:
            log(f"Error on {ticker} (attempt {attempt+1}/6): {e}")
            time.sleep(1.5 * (attempt + 1))

    return {"ticker": ticker, "error": "failed"}

def main():
    log("=" * 100)
    log("FILTRADO Y ENRIQUECIMIENTO DE UNIVERSO")
    log("=" * 100)

    # Get API key
    api_key = os.getenv("POLYGON_API_KEY")
    if not api_key:
        log("ERROR: POLYGON_API_KEY not found in environment")
        sys.exit(1)

    # Paths
    snapshot_path = Path("raw/polygon/reference/tickers_snapshot/snapshot_date=2025-10-24/tickers_all.parquet")
    output_dir = Path("processed/universe")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Load snapshot and filter CS only
    log("\nStep 1: Loading snapshot and filtering Common Stock (CS)...")
    df_snapshot = pl.read_parquet(snapshot_path)
    log(f"Total tickers in snapshot: {len(df_snapshot):,}")

    # Filter: only CS (Common Stock) - KEEP BOTH ACTIVE AND INACTIVE (no survivorship bias)
    df_cs = df_snapshot.filter(pl.col("type") == "CS")
    log(f"Common Stock (CS) tickers (active + inactive): {len(df_cs):,}")

    # Show active/inactive breakdown
    active_count = df_cs.filter(pl.col("active") == True).height
    inactive_count = df_cs.filter(pl.col("active") == False).height
    log(f"  - Active CS: {active_count:,} ({active_count/len(df_cs)*100:.1f}%)")
    log(f"  - Inactive CS (delisted): {inactive_count:,} ({inactive_count/len(df_cs)*100:.1f}%)")
    log(f"  IMPORTANT: Keeping BOTH active and inactive to avoid survivorship bias!")

    # Filter: only XNAS (NASDAQ) and XNYS (NYSE) - but keep delisted ones too
    df_cs_filtered = df_cs.filter(
        pl.col("primary_exchange").is_in(["XNAS", "XNYS"])
    )
    log(f"CS tickers on XNAS/XNYS (active + inactive): {len(df_cs_filtered):,}")

    # Show breakdown by exchange and active status
    log(f"\nBreakdown by exchange and status:")
    for exchange in ["XNAS", "XNYS"]:
        total = df_cs_filtered.filter(pl.col("primary_exchange") == exchange).height
        active = df_cs_filtered.filter(
            (pl.col("primary_exchange") == exchange) & (pl.col("active") == True)
        ).height
        inactive = total - active
        log(f"  {exchange}: {total:,} total ({active:,} active, {inactive:,} inactive)")

    # Get ticker list
    tickers = df_cs_filtered["ticker"].drop_nulls().unique().sort().to_list()
    log(f"\nTickers to enrich: {len(tickers):,}")

    # Save filtered CS tickers
    output_cs = output_dir / "cs_all_xnas_xnys.parquet"
    df_cs_filtered.write_parquet(output_cs)
    log(f"Saved filtered CS tickers: {output_cs}")

    # Step 2: Download ticker details with market cap
    log("\n" + "=" * 100)
    log("Step 2: Downloading ticker details (market_cap, shares, etc.)...")
    log(f"This will take ~{len(tickers) * RATE_LIMIT / 60:.1f} minutes with rate limit {RATE_LIMIT}s")
    log("=" * 100)

    details_dir = Path("raw/polygon/reference/ticker_details")
    details_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    errors = []
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(get_ticker_details, api_key, ticker): ticker for ticker in tickers}

        for i, future in enumerate(as_completed(futures), 1):
            result = future.result()
            rows.append(result)

            if "error" in result:
                errors.append(result["ticker"])

            if i % 100 == 0:
                elapsed = time.time() - start_time
                rate = i / elapsed
                remaining = (len(tickers) - i) / rate if rate > 0 else 0
                log(f"Progress: {i:,}/{len(tickers):,} ({i/len(tickers)*100:.1f}%) | "
                    f"Rate: {rate:.1f} req/s | ETA: {remaining/60:.1f} min | Errors: {len(errors)}")

    elapsed_total = time.time() - start_time
    log(f"\nDownload completed in {elapsed_total/60:.1f} minutes")
    log(f"Success: {len(rows) - len(errors):,} | Errors: {len(errors):,}")

    # Save details
    df_details = pl.from_dicts(rows)
    details_file = details_dir / f"ticker_details_{dt.date.today().isoformat()}.parquet"
    df_details.write_parquet(details_file)
    log(f"Saved ticker details: {details_file}")

    # Step 3: Filter by market cap < $2B
    log("\n" + "=" * 100)
    log("Step 3: Filtering by market cap < $2B...")
    log("=" * 100)

    # Check market_cap column
    if "market_cap" not in df_details.columns:
        log("WARNING: market_cap column not found in details")
        log(f"Available columns: {df_details.columns}")
        return

    # Filter market cap < 2B
    df_under_2b = df_details.filter(
        (pl.col("market_cap").is_not_null()) &
        (pl.col("market_cap") < 2_000_000_000)
    )

    log(f"Tickers with market_cap data: {df_details.filter(pl.col('market_cap').is_not_null()).height:,}")
    log(f"Tickers with market_cap < $2B: {len(df_under_2b):,}")

    # Save final universe (active + inactive, filtered by market cap)
    output_final = output_dir / f"cs_xnas_xnys_under2b_all_{dt.date.today().isoformat()}.parquet"
    df_under_2b.write_parquet(output_final)
    log(f"Saved final universe: {output_final}")

    # Also save as CSV for easy inspection
    output_csv = output_dir / f"cs_xnas_xnys_under2b_all_{dt.date.today().isoformat()}.csv"

    # Select columns for CSV (check which exist first)
    csv_cols = ["ticker", "name", "market_cap", "primary_exchange", "active", "cik"]
    if "weighted_shares_outstanding" in df_under_2b.columns:
        csv_cols.insert(3, "weighted_shares_outstanding")
    if "currency_name" in df_under_2b.columns:
        csv_cols.append("currency_name")

    df_under_2b.select([col for col in csv_cols if col in df_under_2b.columns]).write_csv(output_csv)
    log(f"Saved final universe CSV: {output_csv}")

    # Count active/inactive in final universe
    final_active = df_under_2b.filter(pl.col("active") == True).height if "active" in df_under_2b.columns else 0
    final_inactive = len(df_under_2b) - final_active

    # Summary statistics
    log("\n" + "=" * 100)
    log("SUMMARY (NO SURVIVORSHIP BIAS - INCLUDES DELISTED)")
    log("=" * 100)
    log(f"Initial snapshot:                    {len(df_snapshot):>10,} tickers")
    log(f"Common Stock (CS) all:               {len(df_cs):>10,} tickers ({len(df_cs)/len(df_snapshot)*100:.1f}%)")
    log(f"  - Active CS:                       {active_count:>10,} tickers ({active_count/len(df_cs)*100:.1f}%)")
    log(f"  - Inactive CS (delisted):          {inactive_count:>10,} tickers ({inactive_count/len(df_cs)*100:.1f}%)")
    log(f"CS on XNAS/XNYS (all):               {len(df_cs_filtered):>10,} tickers")
    log(f"With market_cap data:                {df_details.filter(pl.col('market_cap').is_not_null()).height:>10,} tickers")
    log(f"Final (CS + XNAS/XNYS + <$2B + ALL): {len(df_under_2b):>10,} tickers")
    log(f"  - Active in final:                 {final_active:>10,} tickers ({final_active/len(df_under_2b)*100:.1f}%)")
    log(f"  - Inactive in final (delisted):    {final_inactive:>10,} tickers ({final_inactive/len(df_under_2b)*100:.1f}%)")
    log("=" * 100)
    log("NOTE: Keeping delisted tickers avoids survivorship bias in backtesting!")

    if len(errors) > 0:
        log(f"\nErrors ({len(errors)}): {', '.join(errors[:20])}" + ("..." if len(errors) > 20 else ""))

if __name__ == "__main__":
    main()
