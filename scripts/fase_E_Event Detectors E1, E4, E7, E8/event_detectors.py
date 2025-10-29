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
        Detect parabolic moves: +50% gain in ≤5 consecutive days (SIMPLE VECTORIZED)

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
        self.logger.info(f"Detecting E4 Parabolic Move (>={pct_threshold*100}% in ≤{max_window_days} days) - VECTORIZED")

        # Sort and add shifts for all windows
        df = df_daily.sort(["ticker", "date"])

        events_list = []

        for window in range(1, max_window_days + 1):
            df_window = df.with_columns([
                pl.col("date").alias("date_start"),
                pl.col("o").alias("start_price"),
                pl.col("date").shift(-window).over("ticker").alias("date_end"),
                pl.col("c").shift(-window).over("ticker").alias("end_price"),
                ((pl.col("c").shift(-window).over("ticker") / pl.col("o")) - 1).alias("pct_change"),
                pl.lit(window).alias("days")
            ]).filter(
                (pl.col("pct_change") >= pct_threshold) &
                (pl.col("pct_change").is_not_null())
            ).select([
                "ticker",
                "date_start",
                "date_end",
                pl.lit("E4_Parabolic").alias("event_type"),
                "pct_change",
                "days",
                "start_price",
                "end_price"
            ])

            events_list.append(df_window)

        # Concatenate all windows
        if events_list:
            df_events = pl.concat(events_list).sort(["ticker", "date_start", "days"])
        else:
            df_events = pl.DataFrame()

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

    # ==================== E2: GAP UP SIGNIFICANT ====================

    def detect_e2_gap_up(
        self,
        df_daily: pl.DataFrame,
        gap_threshold: float = 0.10
    ) -> pl.DataFrame:
        """
        Detect significant gap up: open > prev_close * (1 + gap_threshold)

        Parameters:
        -----------
        df_daily : pl.DataFrame
            Daily OHLCV data
        gap_threshold : float
            Minimum gap percentage (default: 0.10 = 10%)

        Returns:
        --------
        pl.DataFrame with columns: [ticker, date, event_type, gap_pct, prev_close, open]
        """
        self.logger.info(f"Detecting E2 Gap Up (gap >= {gap_threshold*100}%)")

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
                (pl.col("gap_pct") >= gap_threshold) &
                (pl.col("prev_close").is_not_null())
            )
            .select([
                "ticker",
                "date",
                pl.lit("E2_GapUp").alias("event_type"),
                "gap_pct",
                "prev_close",
                "o",
                "h",
                "l",
                "c",
                "v"
            ])
        )

        self.logger.info(f"Found {len(df_events):,} E2 Gap Up events")
        return df_events

    # ==================== E3: PRICE SPIKE INTRADAY ====================

    def detect_e3_price_spike_intraday(
        self,
        df_daily: pl.DataFrame,
        spike_threshold: float = 0.20
    ) -> pl.DataFrame:
        """
        Detect intraday price spike: (high - open) / open >= spike_threshold

        NOTE: This is an approximation using daily data. True intraday detection
        requires tick/minute data.

        Parameters:
        -----------
        df_daily : pl.DataFrame
            Daily OHLCV data
        spike_threshold : float
            Minimum intraday gain (default: 0.20 = 20%)

        Returns:
        --------
        pl.DataFrame with columns: [ticker, date, event_type, spike_pct, open, high]
        """
        self.logger.info(f"Detecting E3 Price Spike Intraday (>={spike_threshold*100}% intraday) - APPROXIMATION")

        df_events = (
            df_daily
            .with_columns([
                ((pl.col("h") - pl.col("o")) / pl.col("o")).alias("spike_pct")
            ])
            .filter(
                (pl.col("spike_pct") >= spike_threshold) &
                (pl.col("o") > 0)
            )
            .select([
                "ticker",
                "date",
                pl.lit("E3_PriceSpikeIntraday").alias("event_type"),
                "spike_pct",
                pl.lit(False).alias("intraday_confirmed"),
                "o",
                "h",
                "l",
                "c",
                "v"
            ])
        )

        self.logger.info(f"Found {len(df_events):,} E3 Price Spike Intraday events")
        return df_events

    # ==================== E5: BREAKOUT ATH/52W ====================

    def detect_e5_breakout_ath(
        self,
        df_daily: pl.DataFrame,
        lookback_days: int = 252
    ) -> pl.DataFrame:
        """
        Detect breakout to new high: close >= max(close) over lookback period

        Parameters:
        -----------
        df_daily : pl.DataFrame
            Daily OHLCV data
        lookback_days : int
            Lookback period (default: 252 = ~52 weeks)

        Returns:
        --------
        pl.DataFrame with columns: [ticker, date, event_type, close, prev_high]
        """
        self.logger.info(f"Detecting E5 Breakout ATH (lookback={lookback_days}d)")

        df_events = (
            df_daily
            .sort(["ticker", "date"])
            .with_columns([
                pl.col("c").rolling_max(window_size=lookback_days).over("ticker").shift(1).alias("prev_high")
            ])
            .filter(
                (pl.col("c") >= pl.col("prev_high")) &
                (pl.col("prev_high").is_not_null())
            )
            .select([
                "ticker",
                "date",
                pl.lit("E5_BreakoutATH").alias("event_type"),
                "c",
                "prev_high",
                "o",
                "h",
                "l",
                "v"
            ])
        )

        self.logger.info(f"Found {len(df_events):,} E5 Breakout ATH events")
        return df_events

    # ==================== E6: MULTIPLE GREEN DAYS ====================

    def detect_e6_multiple_green_days(
        self,
        df_daily: pl.DataFrame,
        min_green_days: int = 3
    ) -> pl.DataFrame:
        """
        Detect multiple consecutive green days: close > open for N days

        Parameters:
        -----------
        df_daily : pl.DataFrame
            Daily OHLCV data
        min_green_days : int
            Minimum consecutive green days (default: 3)

        Returns:
        --------
        pl.DataFrame with columns: [ticker, date, event_type, green_days_count]
        """
        self.logger.info(f"Detecting E6 Multiple Green Days (>={min_green_days} consecutive)")

        # Identify green days
        df = (
            df_daily
            .sort(["ticker", "date"])
            .with_columns([
                (pl.col("c") > pl.col("o")).cast(pl.Int32).alias("is_green")
            ])
        )

        # Count consecutive green days using cumulative sum trick
        df = df.with_columns([
            # Lag is_green to detect changes
            pl.col("is_green").shift(1).over("ticker").alias("prev_is_green")
        ])

        df = df.with_columns([
            # Create groups where is_green changes
            (pl.col("is_green") != pl.col("prev_is_green")).cast(pl.Int32).cum_sum().over("ticker").alias("green_group")
        ])

        # Count consecutive greens per group
        df = df.with_columns([
            pl.col("is_green").cum_sum().over(["ticker", "green_group"]).alias("green_days_count")
        ])

        df_events = (
            df
            .filter(
                (pl.col("is_green") == 1) &
                (pl.col("green_days_count") >= min_green_days)
            )
            .select([
                "ticker",
                "date",
                pl.lit("E6_MultipleGreenDays").alias("event_type"),
                "green_days_count",
                "o",
                "h",
                "l",
                "c",
                "v"
            ])
        )

        self.logger.info(f"Found {len(df_events):,} E6 Multiple Green Days events")
        return df_events

    # ==================== E9: CRASH INTRADAY ====================

    def detect_e9_crash_intraday(
        self,
        df_daily: pl.DataFrame,
        crash_threshold: float = -0.30
    ) -> pl.DataFrame:
        """
        Detect intraday crash: (low - open) / open <= crash_threshold

        NOTE: This is an approximation using daily data. True intraday detection
        requires tick/minute data to identify -30% in <2 hours.

        Parameters:
        -----------
        df_daily : pl.DataFrame
            Daily OHLCV data
        crash_threshold : float
            Maximum intraday drop (default: -0.30 = -30%)

        Returns:
        --------
        pl.DataFrame with columns: [ticker, date, event_type, crash_pct, open, low]
        """
        self.logger.info(f"Detecting E9 Crash Intraday (<={crash_threshold*100}% intraday) - APPROXIMATION")

        df_events = (
            df_daily
            .with_columns([
                ((pl.col("l") - pl.col("o")) / pl.col("o")).alias("crash_pct")
            ])
            .filter(
                (pl.col("crash_pct") <= crash_threshold) &
                (pl.col("o") > 0)
            )
            .select([
                "ticker",
                "date",
                pl.lit("E9_CrashIntraday").alias("event_type"),
                "crash_pct",
                pl.lit(False).alias("intraday_confirmed"),
                "o",
                "h",
                "l",
                "c",
                "v"
            ])
        )

        self.logger.info(f"Found {len(df_events):,} E9 Crash Intraday events")
        return df_events

    # ==================== E10: FIRST GREEN DAY BOUNCE ====================

    def detect_e10_first_green_bounce(
        self,
        df_daily: pl.DataFrame,
        min_red_days: int = 3
    ) -> pl.DataFrame:
        """
        Detect first green day after consecutive red days (bounce signal)

        Parameters:
        -----------
        df_daily : pl.DataFrame
            Daily OHLCV data
        min_red_days : int
            Minimum consecutive red days before bounce (default: 3)

        Returns:
        --------
        pl.DataFrame with columns: [ticker, date, event_type, prev_red_days]
        """
        self.logger.info(f"Detecting E10 First Green Day Bounce (after >={min_red_days} red days)")

        # Identify green/red days
        df = (
            df_daily
            .sort(["ticker", "date"])
            .with_columns([
                (pl.col("c") > pl.col("o")).cast(pl.Int32).alias("is_green"),
                (pl.col("c") < pl.col("o")).cast(pl.Int32).alias("is_red")
            ])
        )

        # Count consecutive red days before current day
        df = df.with_columns([
            # Lag is_red to detect changes
            pl.col("is_red").shift(1).over("ticker").alias("prev_is_red")
        ])

        df = df.with_columns([
            # Group red streaks
            (pl.col("is_red") != pl.col("prev_is_red")).cast(pl.Int32).cum_sum().over("ticker").alias("red_group")
        ])

        df = df.with_columns([
            pl.col("is_red").cum_sum().over(["ticker", "red_group"]).alias("red_count")
        ])

        # Shift red_count to get previous streak length
        df = df.with_columns([
            pl.col("red_count").shift(1).over("ticker").fill_null(0).alias("prev_red_days")
        ])

        df_events = (
            df
            .filter(
                (pl.col("is_green") == 1) &
                (pl.col("prev_red_days") >= min_red_days)
            )
            .select([
                "ticker",
                "date",
                pl.lit("E10_FirstGreenBounce").alias("event_type"),
                "prev_red_days",
                "o",
                "h",
                "l",
                "c",
                "v"
            ])
        )

        self.logger.info(f"Found {len(df_events):,} E10 First Green Day Bounce events")
        return df_events

    # ==================== E11: VOLUME SPIKE ON BOUNCE ====================

    def detect_e11_volume_bounce(
        self,
        df_daily: pl.DataFrame,
        rvol_threshold: float = 3.0,
        window_days: int = 20
    ) -> pl.DataFrame:
        """
        Detect volume spike on bounce: RVOL >= 3x AND green day after red days

        Combines volume explosion with bounce pattern.

        Parameters:
        -----------
        df_daily : pl.DataFrame
            Daily OHLCV data
        rvol_threshold : float
            Minimum RVOL multiplier (default: 3.0)
        window_days : int
            Rolling window for average volume (default: 20)

        Returns:
        --------
        pl.DataFrame with columns: [ticker, date, event_type, rvol, prev_red_days]
        """
        self.logger.info(f"Detecting E11 Volume Spike on Bounce (RVOL>={rvol_threshold}x, post-decline)")

        # Calculate RVOL and identify red/green days
        df = (
            df_daily
            .sort(["ticker", "date"])
            .with_columns([
                pl.col("v").rolling_mean(window_size=window_days).over("ticker").alias("avg_vol"),
                (pl.col("c") > pl.col("o")).cast(pl.Int32).alias("is_green"),
                (pl.col("c") < pl.col("o")).cast(pl.Int32).alias("is_red")
            ])
            .with_columns([
                (pl.col("v") / pl.col("avg_vol")).alias("rvol")
            ])
        )

        # Count previous red days (same logic as E10)
        df = df.with_columns([
            # Lag is_red to detect changes
            pl.col("is_red").shift(1).over("ticker").alias("prev_is_red")
        ])

        df = df.with_columns([
            (pl.col("is_red") != pl.col("prev_is_red")).cast(pl.Int32).cum_sum().over("ticker").alias("red_group")
        ])

        df = df.with_columns([
            pl.col("is_red").cum_sum().over(["ticker", "red_group"]).alias("red_count")
        ])

        df = df.with_columns([
            pl.col("red_count").shift(1).over("ticker").fill_null(0).alias("prev_red_days")
        ])

        df_events = (
            df
            .filter(
                (pl.col("rvol") >= rvol_threshold) &
                (pl.col("is_green") == 1) &
                (pl.col("prev_red_days") >= 2) &  # At least 2 red days before
                (pl.col("avg_vol").is_not_null())
            )
            .select([
                "ticker",
                "date",
                pl.lit("E11_VolumeBounce").alias("event_type"),
                "rvol",
                "prev_red_days",
                "v",
                "avg_vol",
                "o",
                "h",
                "l",
                "c"
            ])
        )

        self.logger.info(f"Found {len(df_events):,} E11 Volume Spike on Bounce events")
        return df_events

    # ==================== UNIFIED DETECTION ====================

    def detect_all_events(
        self,
        df_daily: pl.DataFrame,
        events: list[Literal["E1", "E2", "E3", "E4", "E5", "E6", "E7", "E8", "E9", "E10", "E11"]] = ["E1", "E4", "E7", "E8"]
    ) -> dict[str, pl.DataFrame]:
        """
        Detect all specified events in one call

        Parameters:
        -----------
        df_daily : pl.DataFrame
            Daily OHLCV data
        events : list
            List of events to detect (default: E1, E4, E7, E8)

        Returns:
        --------
        dict with keys E1-E11 containing respective DataFrames
        """
        results = {}

        if "E1" in events:
            results["E1"] = self.detect_e1_volume_explosion(df_daily)

        if "E2" in events:
            results["E2"] = self.detect_e2_gap_up(df_daily)

        if "E3" in events:
            results["E3"] = self.detect_e3_price_spike_intraday(df_daily)

        if "E4" in events:
            results["E4"] = self.detect_e4_parabolic_move(df_daily)

        if "E5" in events:
            results["E5"] = self.detect_e5_breakout_ath(df_daily)

        if "E6" in events:
            results["E6"] = self.detect_e6_multiple_green_days(df_daily)

        if "E7" in events:
            results["E7"] = self.detect_e7_first_red_day(df_daily)

        if "E8" in events:
            results["E8"] = self.detect_e8_gap_down(df_daily)

        if "E9" in events:
            results["E9"] = self.detect_e9_crash_intraday(df_daily)

        if "E10" in events:
            results["E10"] = self.detect_e10_first_green_bounce(df_daily)

        if "E11" in events:
            results["E11"] = self.detect_e11_volume_bounce(df_daily)

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
        help="Comma-separated list of events to detect (default: E1,E4,E7,E8). Available: E1-E11"
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
