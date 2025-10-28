"""
Event Detectors for Multi-Event Strategy (E1, E4, E7, E8)

Based on: C.1_Estrategia_descarga_ticks_eventos.md

Priority Events:
- E1: Volume Explosion (RVOL > 5x)
- E4: Parabolic Move (+50% in ≤5 days)
- E7: First Red Day (FRD) - MOST CRITICAL
- E8: Gap Down Violent (>15% gap down)

Author: Pipeline automation
Date: 2025-10-28
"""

import polars as pl
import numpy as np
from pathlib import Path
from typing import Optional, Literal
from datetime import datetime, timedelta
import logging

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class EventDetector:
    """
    Unified event detection system for E1, E4, E7, E8

    Usage:
        detector = EventDetector()
        df_daily = pl.read_parquet('processed/daily_cache/hybrid/daily.parquet')

        events_e1 = detector.detect_e1_volume_explosion(df_daily)
        events_e4 = detector.detect_e4_parabolic_move(df_daily)
        events_e7 = detector.detect_e7_first_red_day(df_daily)
        events_e8 = detector.detect_e8_gap_down(df_daily)
    """

    def __init__(self):
        self.logger = logger

    # ==================== E1: VOLUME EXPLOSION ====================

    def detect_e1_volume_explosion(
        self,
        df_daily: pl.DataFrame,
        rvol_threshold: float = 5.0,
        window_days: int = 20
    ) -> pl.DataFrame:
        """
        Detect days with volume > 5x average (20-day rolling)

        Parameters:
        -----------
        df_daily : pl.DataFrame
            Daily OHLCV data with columns: [ticker, date, o, h, l, c, v]
        rvol_threshold : float
            Minimum RVOL multiplier (default: 5.0)
        window_days : int
            Rolling window for average volume (default: 20)

        Returns:
        --------
        pl.DataFrame with columns: [ticker, date, event_type, rvol, v, avg_vol]
        """
        self.logger.info(f"Detecting E1 Volume Explosion (RVOL >= {rvol_threshold}x, window={window_days}d)")

        df_events = (
            df_daily
            .sort(["ticker", "date"])
            .with_columns([
                # Average volume over rolling window
                pl.col("v").rolling_mean(window_size=window_days).over("ticker").alias("avg_vol"),
            ])
            .with_columns([
                # RVOL = current volume / average volume
                (pl.col("v") / pl.col("avg_vol")).alias("rvol")
            ])
            .filter(
                (pl.col("rvol") >= rvol_threshold) &
                (pl.col("avg_vol").is_not_null())  # Skip first N days
            )
            .select([
                "ticker",
                "date",
                pl.lit("E1_VolExplosion").alias("event_type"),
                "rvol",
                "v",
                "avg_vol",
                "c"  # Close price for reference
            ])
        )

        self.logger.info(f"Found {len(df_events):,} E1 Volume Explosion events")
        return df_events

    # ==================== E4: PARABOLIC MOVE ====================

    def detect_e4_parabolic_move(
        self,
        df_daily: pl.DataFrame,
        pct_threshold: float = 0.50,
        max_window_days: int = 5
    ) -> pl.DataFrame:
        """
        Detect parabolic moves: +50% gain in ≤5 consecutive days

        Parameters:
        -----------
        df_daily : pl.DataFrame
            Daily OHLCV data with columns: [ticker, date, o, h, l, c, v]
        pct_threshold : float
            Minimum percentage gain (default: 0.50 = 50%)
        max_window_days : int
            Maximum days for the move (default: 5)

        Returns:
        --------
        pl.DataFrame with columns: [ticker, date_start, date_end, pct_change, days, event_type]
        """
        self.logger.info(f"Detecting E4 Parabolic Move (>={pct_threshold*100}% in ≤{max_window_days} days)")

        events = []

        for ticker in df_daily["ticker"].unique():
            df_ticker = df_daily.filter(pl.col("ticker") == ticker).sort("date")

            if len(df_ticker) < max_window_days:
                continue

            # Iterate through all possible windows
            for i in range(len(df_ticker) - 1):
                start_price = df_ticker[i]["o"]  # Open of first day
                start_date = df_ticker[i]["date"]

                # Check windows of 1 to max_window_days
                for j in range(i + 1, min(i + max_window_days + 1, len(df_ticker))):
                    end_price = df_ticker[j]["c"]  # Close of last day
                    end_date = df_ticker[j]["date"]
                    days = j - i

                    pct_change = (end_price - start_price) / start_price

                    if pct_change >= pct_threshold:
                        events.append({
                            "ticker": ticker,
                            "date_start": start_date,
                            "date_end": end_date,
                            "event_type": "E4_Parabolic",
                            "pct_change": pct_change,
                            "days": days,
                            "start_price": start_price,
                            "end_price": end_price
                        })
                        break  # Found parabolic for this starting point

        df_events = pl.DataFrame(events) if events else pl.DataFrame()
        self.logger.info(f"Found {len(df_events):,} E4 Parabolic Move events")
        return df_events

    # ==================== E7: FIRST RED DAY (FRD) - MOST CRITICAL ====================

    def detect_e7_first_red_day(
        self,
        df_daily: pl.DataFrame,
        min_run_days: int = 3,
        min_extension_pct: float = 0.50
    ) -> pl.DataFrame:
        """
        Detect First Red Day (FRD): First red day after ≥3 green days with ≥50% extension

        This is the MOST CRITICAL pattern according to EduTrades playbook.

        Criteria:
        ---------
        - Minimum 3 consecutive green days (c > o)
        - Extension ≥ 50% from run start to peak
        - Current day is red (c < o)

        Parameters:
        -----------
        df_daily : pl.DataFrame
            Daily OHLCV data with columns: [ticker, date, o, h, l, c, v]
        min_run_days : int
            Minimum consecutive green days (default: 3)
        min_extension_pct : float
            Minimum extension from run start (default: 0.50 = 50%)

        Returns:
        --------
        pl.DataFrame with columns: [ticker, date, event_type, run_days, extension_pct, peak_price]
        """
        self.logger.info(f"Detecting E7 First Red Day (≥{min_run_days} greens, ≥{min_extension_pct*100}% extension)")

        df = (
            df_daily
            .sort(["ticker", "date"])
            .with_columns([
                (pl.col("c") > pl.col("o")).alias("is_green"),
                (pl.col("c") < pl.col("o")).alias("is_red"),
            ])
        )

        events = []

        for ticker in df["ticker"].unique():
            df_ticker = df.filter(pl.col("ticker") == ticker).sort("date")

            green_run_days = 0
            run_start_price = None
            run_start_date = None
            run_high = None

            for idx, row in enumerate(df_ticker.iter_rows(named=True)):
                if row["is_green"]:
                    if green_run_days == 0:
                        run_start_price = row["o"]  # Open of first green day
                        run_start_date = row["date"]
                        run_high = row["h"]
                    else:
                        run_high = max(run_high, row["h"])  # Track highest high

                    green_run_days += 1

                elif row["is_red"] and green_run_days >= min_run_days:
                    # Calculate extension from start to peak
                    extension_pct = (run_high - run_start_price) / run_start_price

                    if extension_pct >= min_extension_pct:
                        events.append({
                            "ticker": ticker,
                            "date": row["date"],
                            "event_type": "E7_FirstRedDay",
                            "run_days": green_run_days,
                            "run_start_date": run_start_date,
                            "extension_pct": extension_pct,
                            "peak_price": run_high,
                            "frd_open": row["o"],
                            "frd_close": row["c"],
                            "frd_low": row["l"]
                        })

                    # Reset counter
                    green_run_days = 0
                    run_start_price = None
                    run_start_date = None
                    run_high = None

                else:
                    # Other day type or red without sufficient run - reset
                    green_run_days = 0
                    run_start_price = None
                    run_start_date = None
                    run_high = None

        df_events = pl.DataFrame(events) if events else pl.DataFrame()
        self.logger.info(f"Found {len(df_events):,} E7 First Red Day events")
        return df_events

    # ==================== E8: GAP DOWN VIOLENT ====================

    def detect_e8_gap_down(
        self,
        df_daily: pl.DataFrame,
        gap_threshold: float = -0.15
    ) -> pl.DataFrame:
        """
        Detect violent gap downs: open < prev_close × (1 + gap_threshold)

        Parameters:
        -----------
        df_daily : pl.DataFrame
            Daily OHLCV data with columns: [ticker, date, o, h, l, c, v]
        gap_threshold : float
            Minimum gap percentage (default: -0.15 = -15%)

        Returns:
        --------
        pl.DataFrame with columns: [ticker, date, event_type, gap_pct, prev_close, open]
        """
        self.logger.info(f"Detecting E8 Gap Down Violent (gap <= {gap_threshold*100}%)")

        df_events = (
            df_daily
            .sort(["ticker", "date"])
            .with_columns([
                pl.col("c").shift(1).over("ticker").alias("prev_close")
            ])
            .with_columns([
                ((pl.col("o") - pl.col("prev_close")) / pl.col("prev_close")).alias("gap_pct")
            ])
            .filter(
                (pl.col("gap_pct") <= gap_threshold) &
                (pl.col("prev_close").is_not_null())
            )
            .select([
                "ticker",
                "date",
                pl.lit("E8_GapDownViolent").alias("event_type"),
                "gap_pct",
                "prev_close",
                "o",
                "h",
                "l",
                "c",
                "v"
            ])
        )

        self.logger.info(f"Found {len(df_events):,} E8 Gap Down Violent events")
        return df_events

    # ==================== UNIFIED DETECTION ====================

    def detect_all_events(
        self,
        df_daily: pl.DataFrame,
        events: list[Literal["E1", "E4", "E7", "E8"]] = ["E1", "E4", "E7", "E8"]
    ) -> dict[str, pl.DataFrame]:
        """
        Detect all specified events in one call

        Parameters:
        -----------
        df_daily : pl.DataFrame
            Daily OHLCV data
        events : list
            List of events to detect (default: all 4)

        Returns:
        --------
        dict with keys E1, E4, E7, E8 containing respective DataFrames
        """
        results = {}

        if "E1" in events:
            results["E1"] = self.detect_e1_volume_explosion(df_daily)

        if "E4" in events:
            results["E4"] = self.detect_e4_parabolic_move(df_daily)

        if "E7" in events:
            results["E7"] = self.detect_e7_first_red_day(df_daily)

        if "E8" in events:
            results["E8"] = self.detect_e8_gap_down(df_daily)

        # Summary
        total_events = sum(len(df) for df in results.values())
        self.logger.info(f"Total events detected: {total_events:,}")
        for event_type, df in results.items():
            self.logger.info(f"  {event_type}: {len(df):,}")

        return results


# ==================== CLI INTERFACE ====================

def main():
    """Command-line interface for event detection"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Detect trading events E1, E4, E7, E8 from daily OHLCV data"
    )
    parser.add_argument(
        "--daily-cache",
        type=str,
        required=True,
        help="Path to daily cache parquet file (e.g. processed/daily_cache/hybrid/daily.parquet)"
    )
    parser.add_argument(
        "--outdir",
        type=str,
        required=True,
        help="Output directory for event files"
    )
    parser.add_argument(
        "--events",
        type=str,
        default="E1,E4,E7,E8",
        help="Comma-separated list of events to detect (default: E1,E4,E7,E8)"
    )

    args = parser.parse_args()

    # Load daily data
    logger.info(f"Loading daily cache from: {args.daily_cache}")
    df_daily = pl.read_parquet(args.daily_cache)
    logger.info(f"Loaded {len(df_daily):,} daily records for {df_daily['ticker'].n_unique()} tickers")

    # Detect events
    detector = EventDetector()
    events_to_detect = args.events.split(",")
    results = detector.detect_all_events(df_daily, events=events_to_detect)

    # Save results
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    for event_type, df_events in results.items():
        if len(df_events) > 0:
            outfile = outdir / f"events_{event_type.lower()}.parquet"
            df_events.write_parquet(outfile)
            logger.info(f"Saved {len(df_events):,} {event_type} events to {outfile}")
        else:
            logger.warning(f"No {event_type} events detected")

    logger.info("Event detection completed successfully")


if __name__ == "__main__":
    main()
