"""
Build Daily OHLCV from 1-Minute Bars

Aggregates 1m bars (minute.parquet) to daily OHLCV resolution.
This is the foundational dataset for event detectors E1, E4, E7, E8.

Why we need this:
- Event detectors operate at "day resolution" (E7: first red day, E8: gap down)
- They need real OHLCV: open (first minute), high/low (intraday extremes), close (last minute)
- daily_cache only has close_d and vol_d, no open/high/low
- Detecting events at minute resolution would be inefficient and conceptually wrong

Architecture flow:
  1. Daily OHLCV → detect interesting days (E1/E4/E7/E8)
  2. Download ticks for those specific days (±1, ±3, ±5)
  3. Build DIB/VIB intraday for those days
  4. Label and train ML models on intraday data

Usage:
    python build_daily_ohlcv_from_1m.py \\
        --intraday-root raw/polygon/ohlcv_intraday_1m \\
        --outdir processed/daily_ohlcv \\
        --parallel 8 \\
        --resume
"""

import polars as pl
from pathlib import Path
import argparse
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed
from tqdm import tqdm
import logging

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def process_ticker(ticker_dir: Path, outdir: Path) -> dict:
    """
    Aggregate all 1m bars for a ticker to daily OHLCV

    Args:
        ticker_dir: Path to ticker (e.g., raw/polygon/ohlcv_intraday_1m/AAPL)
        outdir: Output directory root

    Returns:
        dict with ticker, status, days_count, reason
    """
    ticker = ticker_dir.name

    try:
        # Find all minute.parquet files for this ticker
        minute_files = list(ticker_dir.rglob('minute.parquet'))

        if len(minute_files) == 0:
            return {"ticker": ticker, "status": "skip", "days": 0, "reason": "no_minute_files"}

        # Read and concatenate all minute files
        dfs = []
        for file in minute_files:
            df = pl.read_parquet(file)
            dfs.append(df)

        df_all = pl.concat(dfs)

        if len(df_all) == 0:
            return {"ticker": ticker, "status": "skip", "days": 0, "reason": "empty"}

        # Aggregate to daily
        # CRITICAL: Order by timestamp within each day to get correct open/close
        df_daily = (
            df_all
            .sort(["date", "t"])  # Sort by date first, then timestamp
            .group_by("date")
            .agg([
                # Open: o of the row with minimum t (first minute)
                pl.col("o").first().alias("o"),

                # High: maximum of all h values
                pl.col("h").max().alias("h"),

                # Low: minimum of all l values
                pl.col("l").min().alias("l"),

                # Close: c of the row with maximum t (last minute)
                pl.col("c").last().alias("c"),

                # Volume: sum of all v
                pl.col("v").sum().alias("v"),

                # Trades: sum of all n
                pl.col("n").sum().alias("n"),

                # Dollar volume: sum(v * c)
                (pl.col("v") * pl.col("c")).sum().alias("dollar"),
            ])
            .with_columns([
                pl.lit(ticker).alias("ticker"),
                pl.col("date").str.to_date().alias("date")
            ])
            .select(["ticker", "date", "o", "h", "l", "c", "v", "n", "dollar"])
            .sort("date")
        )

        if len(df_daily) == 0:
            return {"ticker": ticker, "status": "skip", "days": 0, "reason": "no_days_after_agg"}

        # Save output
        ticker_outdir = outdir / ticker
        ticker_outdir.mkdir(parents=True, exist_ok=True)

        outfile = ticker_outdir / "daily.parquet"
        df_daily.write_parquet(outfile)

        # Success marker
        (ticker_outdir / "_SUCCESS").touch()

        return {"ticker": ticker, "status": "success", "days": len(df_daily), "reason": None}

    except Exception as e:
        return {"ticker": ticker, "status": "error", "days": 0, "reason": str(e)[:200]}


def main():
    parser = argparse.ArgumentParser(
        description="Build daily OHLCV from 1m bars",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example:
    python build_daily_ohlcv_from_1m.py \\
        --intraday-root raw/polygon/ohlcv_intraday_1m \\
        --outdir processed/daily_ohlcv \\
        --parallel 8 \\
        --resume

Output schema per ticker (processed/daily_ohlcv/<TICKER>/daily.parquet):
    ticker: str
    date: date
    o: float64      (open: first minute)
    h: float64      (high: intraday max)
    l: float64      (low: intraday min)
    c: float64      (close: last minute)
    v: float64      (volume: sum)
    n: int64        (trades: sum)
    dollar: float64 (dollar volume: sum(v*c))
        """
    )
    parser.add_argument("--intraday-root", type=str, required=True,
                        help="Root directory with 1m bars (e.g., raw/polygon/ohlcv_intraday_1m)")
    parser.add_argument("--outdir", type=str, required=True,
                        help="Output directory for daily OHLCV")
    parser.add_argument("--parallel", type=int, default=8,
                        help="Number of parallel workers (default: 8)")
    parser.add_argument("--resume", action="store_true",
                        help="Skip tickers that already have _SUCCESS marker")

    args = parser.parse_args()

    intraday_root = Path(args.intraday_root)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    logger.info("="*60)
    logger.info("BUILD DAILY OHLCV FROM 1M BARS")
    logger.info("="*60)
    logger.info(f"Intraday root: {intraday_root}")
    logger.info(f"Output:        {outdir}")
    logger.info(f"Workers:       {args.parallel}")
    logger.info(f"Resume:        {args.resume}")
    logger.info("")

    # Find all ticker directories (skip _batch_temp)
    ticker_dirs = [
        d for d in intraday_root.iterdir()
        if d.is_dir() and d.name != '_batch_temp'
    ]

    logger.info(f"Found {len(ticker_dirs):,} ticker directories")

    # Filter already done if resume
    if args.resume:
        ticker_dirs = [
            d for d in ticker_dirs
            if not (outdir / d.name / "_SUCCESS").exists()
        ]
        logger.info(f"Resume mode: {len(ticker_dirs):,} tickers remaining")

    if len(ticker_dirs) == 0:
        logger.info("No tickers to process!")
        return

    # Process in parallel
    results = {"success": 0, "skip": 0, "error": 0}
    total_days = 0
    errors = []

    with ProcessPoolExecutor(max_workers=args.parallel) as executor:
        futures = {executor.submit(process_ticker, td, outdir): td for td in ticker_dirs}

        with tqdm(total=len(ticker_dirs), desc="Processing tickers") as pbar:
            for future in as_completed(futures):
                result = future.result()
                results[result["status"]] += 1
                total_days += result["days"]

                if result["status"] == "error":
                    errors.append(f"{result['ticker']}: {result['reason']}")

                pbar.update(1)
                pbar.set_postfix({
                    "success": results["success"],
                    "skip": results["skip"],
                    "error": results["error"],
                    "days": f"{total_days:,}"
                })

    logger.info("")
    logger.info("="*60)
    logger.info("SUMMARY")
    logger.info("="*60)
    logger.info(f"Success: {results['success']:,} tickers")
    logger.info(f"Skip:    {results['skip']:,} tickers")
    logger.info(f"Error:   {results['error']:,} tickers")
    logger.info(f"Total trading days: {total_days:,}")
    logger.info("")

    if errors:
        logger.info(f"First 10 errors:")
        for err in errors[:10]:
            logger.info(f"  {err}")
        logger.info("")

    logger.info(f"Output directory: {outdir}")
    logger.info("="*60)
    logger.info("OK Daily OHLCV build completed")
    logger.info("="*60)


if __name__ == "__main__":
    main()
