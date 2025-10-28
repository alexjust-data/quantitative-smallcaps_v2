"""
Generate Daily OHLCV from 1-minute bars

Purpose: Create daily_ohlcv.parquet files for event detectors E1, E4, E7, E8

Input:  raw/polygon/ohlcv_intraday_1m/{TICKER}/date={YYYY-MM-DD}/ohlcv_1m.parquet
Output: processed/daily_ohlcv/{TICKER}/daily_ohlcv.parquet

Schema Output:
- ticker: str
- date: Date (trading_day)
- o: float (open first minute)
- h: float (high of day)
- l: float (low of day)
- c: float (close last minute)
- v: int (sum of volume)

Author: Pipeline automation
Date: 2025-10-28
"""

import polars as pl
from pathlib import Path
import logging
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Optional
import argparse

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def aggregate_ticker_to_daily(ticker_dir: Path, outdir: Path) -> dict:
    """
    Aggregate all 1-min bars for a ticker into daily OHLCV

    Parameters:
    -----------
    ticker_dir : Path
        Directory containing date={YYYY-MM-DD}/ohlcv_1m.parquet files
    outdir : Path
        Output directory for daily_ohlcv.parquet

    Returns:
    --------
    dict with status info
    """
    ticker = ticker_dir.name

    try:
        # Find all 1-min files
        minute_files = list(ticker_dir.rglob('minute.parquet'))

        if len(minute_files) == 0:
            return {"ticker": ticker, "status": "skip", "reason": "no_files", "days": 0}

        # Load all days
        df_list = []
        for file in minute_files:
            date_str = file.parent.name.split('=')[1]  # Extract YYYY-MM-DD

            df_min = pl.read_parquet(file)

            if len(df_min) == 0:
                continue

            # Sort by timestamp to ensure correct first/last minute
            df_min = df_min.sort("t")

            # Aggregate to daily
            daily_row = {
                "ticker": ticker,
                "date": pl.lit(date_str).str.to_date(),
                "o": df_min[0]["o"],  # First minute open
                "h": df_min["h"].max(),  # Highest high
                "l": df_min["l"].min(),  # Lowest low
                "c": df_min[-1]["c"],  # Last minute close
                "v": df_min["v"].sum(),  # Total volume
            }

            df_list.append(pl.DataFrame([daily_row]))

        if len(df_list) == 0:
            return {"ticker": ticker, "status": "skip", "reason": "no_data", "days": 0}

        # Concatenate all days
        df_daily = pl.concat(df_list).sort("date")

        # Save
        ticker_outdir = outdir / ticker
        ticker_outdir.mkdir(parents=True, exist_ok=True)

        outfile = ticker_outdir / "daily_ohlcv.parquet"
        df_daily.write_parquet(outfile)

        # Success marker
        (ticker_outdir / "_SUCCESS").touch()

        return {
            "ticker": ticker,
            "status": "success",
            "days": len(df_daily),
            "outfile": str(outfile)
        }

    except Exception as e:
        logger.error(f"Error processing {ticker}: {e}")
        return {
            "ticker": ticker,
            "status": "error",
            "error": str(e),
            "days": 0
        }


def process_all_tickers(
    bars_1m_root: Path,
    outdir: Path,
    parallel: int = 8,
    resume: bool = True
) -> None:
    """
    Process all tickers in parallel

    Parameters:
    -----------
    bars_1m_root : Path
        Root directory with 1-min bars (raw/polygon/ohlcv_intraday_1m)
    outdir : Path
        Output directory (processed/daily_ohlcv)
    parallel : int
        Number of parallel workers
    resume : bool
        Skip tickers that already have _SUCCESS marker
    """

    # Find all ticker directories
    ticker_dirs = [d for d in bars_1m_root.iterdir() if d.is_dir()]

    logger.info(f"Found {len(ticker_dirs)} tickers to process")
    logger.info(f"Output directory: {outdir}")
    logger.info(f"Parallel workers: {parallel}")
    logger.info(f"Resume mode: {resume}")
    print()

    # Filter for resume
    if resume:
        ticker_dirs_todo = []
        for ticker_dir in ticker_dirs:
            ticker = ticker_dir.name
            success_marker = outdir / ticker / "_SUCCESS"
            if not success_marker.exists():
                ticker_dirs_todo.append(ticker_dir)

        logger.info(f"Resume: {len(ticker_dirs) - len(ticker_dirs_todo)} already done, {len(ticker_dirs_todo)} remaining")
        ticker_dirs = ticker_dirs_todo

    if len(ticker_dirs) == 0:
        logger.info("No tickers to process (all done or empty)")
        return

    print()

    # Process in parallel
    results = {
        "success": 0,
        "skip": 0,
        "error": 0,
        "total_days": 0
    }

    with ProcessPoolExecutor(max_workers=parallel) as executor:
        futures = {
            executor.submit(aggregate_ticker_to_daily, ticker_dir, outdir): ticker_dir.name
            for ticker_dir in ticker_dirs
        }

        for i, future in enumerate(as_completed(futures), 1):
            ticker = futures[future]
            result = future.result()

            if result["status"] == "success":
                results["success"] += 1
                results["total_days"] += result["days"]
            elif result["status"] == "skip":
                results["skip"] += 1
            else:
                results["error"] += 1

            if i % 100 == 0 or i == len(ticker_dirs):
                logger.info(
                    f"Progress: {i}/{len(ticker_dirs)} | "
                    f"Success: {results['success']} | "
                    f"Skip: {results['skip']} | "
                    f"Error: {results['error']} | "
                    f"Total days: {results['total_days']:,}"
                )

    print()
    logger.info("="*60)
    logger.info("DAILY OHLCV GENERATION COMPLETED")
    logger.info("="*60)
    logger.info(f"Tickers processed: {results['success']:,}")
    logger.info(f"Tickers skipped: {results['skip']:,}")
    logger.info(f"Tickers with errors: {results['error']:,}")
    logger.info(f"Total days aggregated: {results['total_days']:,}")
    logger.info(f"Output directory: {outdir}")
    logger.info("="*60)


def main():
    parser = argparse.ArgumentParser(
        description="Generate daily OHLCV from 1-minute bars for event detectors"
    )
    parser.add_argument(
        "--bars-1m-root",
        type=str,
        required=True,
        help="Root directory with 1-min bars (e.g. raw/polygon/ohlcv_intraday_1m)"
    )
    parser.add_argument(
        "--outdir",
        type=str,
        required=True,
        help="Output directory (e.g. processed/daily_ohlcv)"
    )
    parser.add_argument(
        "--parallel",
        type=int,
        default=8,
        help="Number of parallel workers (default: 8)"
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip tickers with existing _SUCCESS markers"
    )

    args = parser.parse_args()

    bars_1m_root = Path(args.bars_1m_root)
    outdir = Path(args.outdir)

    if not bars_1m_root.exists():
        logger.error(f"Input directory does not exist: {bars_1m_root}")
        return

    outdir.mkdir(parents=True, exist_ok=True)

    process_all_tickers(
        bars_1m_root=bars_1m_root,
        outdir=outdir,
        parallel=args.parallel,
        resume=args.resume
    )


if __name__ == "__main__":
    main()
