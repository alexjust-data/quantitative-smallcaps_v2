"""
Multi-Event Fuser: Consolidate E1, E4, E7, E8 into single watchlist

Combines individual event files into a unified watchlist where each (ticker, date)
has all its detected events combined.

Output Schema:
- ticker: str
- date: date
- event_types: list[str] (e.g., ['E1', 'E4'] or ['E7'])
- num_events: int (count of simultaneous events)
- event_details: struct (JSON-like metadata for each event)

Usage:
    python multi_event_fuser.py
"""
import polars as pl
from pathlib import Path
import json


def load_event_files(events_dir: Path) -> dict:
    """Load all event parquet files into dictionary"""
    event_files = {
        'E1': events_dir / 'events_e1.parquet',
        'E4': events_dir / 'events_e4.parquet',
        'E7': events_dir / 'events_e7.parquet',
        'E8': events_dir / 'events_e8.parquet'
    }

    events = {}
    print('Loading event files...')
    print('=' * 80)

    for event_code, filepath in event_files.items():
        if filepath.exists():
            df = pl.read_parquet(filepath)
            events[event_code] = df
            file_size_mb = filepath.stat().st_size / (1024 * 1024)
            print(f'{event_code}: {len(df):,} events ({file_size_mb:.2f} MB)')
        else:
            print(f'{event_code}: FILE NOT FOUND')
            events[event_code] = None

    print()
    return events


def normalize_event_data(events: dict) -> pl.DataFrame:
    """
    Normalize all events to common schema (ticker, date, event, details_json)

    Uses JSON string for details to handle different field structures across events
    """

    normalized_dfs = []

    # E1: Volume Explosion
    if events['E1'] is not None:
        df_e1 = events['E1'].select([
            pl.col('ticker'),
            pl.col('date'),
            pl.lit('E1').alias('event'),
            pl.struct([
                pl.col('rvol'),
                pl.col('v').alias('volume'),
                pl.col('avg_vol'),
                pl.col('c').alias('close')
            ]).alias('details')
        ]).with_columns([
            pl.col('details').cast(pl.Utf8).alias('details_json')
        ]).drop('details')
        normalized_dfs.append(df_e1)

    # E4: Parabolic Move
    if events['E4'] is not None:
        df_e4 = events['E4'].select([
            pl.col('ticker'),
            pl.col('date_start').alias('date'),  # Use start date as primary
            pl.lit('E4').alias('event'),
            pl.struct([
                pl.col('pct_change'),
                pl.col('days'),
                pl.col('start_price'),
                pl.col('end_price'),
                pl.col('date_end').cast(pl.Utf8).alias('date_end')  # Convert date to string for JSON
            ]).alias('details')
        ]).with_columns([
            pl.col('details').cast(pl.Utf8).alias('details_json')
        ]).drop('details')
        normalized_dfs.append(df_e4)

    # E7: First Red Day
    if events['E7'] is not None:
        df_e7 = events['E7'].select([
            pl.col('ticker'),
            pl.col('date'),
            pl.lit('E7').alias('event'),
            pl.struct([
                pl.col('run_days'),
                pl.col('run_start_date').cast(pl.Utf8).alias('run_start_date'),  # Convert date to string
                pl.col('extension_pct'),
                pl.col('peak_price'),
                pl.col('frd_open'),
                pl.col('frd_close'),
                pl.col('frd_low')
            ]).alias('details')
        ]).with_columns([
            pl.col('details').cast(pl.Utf8).alias('details_json')
        ]).drop('details')
        normalized_dfs.append(df_e7)

    # E8: Gap Down Violent
    if events['E8'] is not None:
        df_e8 = events['E8'].select([
            pl.col('ticker'),
            pl.col('date'),
            pl.lit('E8').alias('event'),
            pl.struct([
                pl.col('gap_pct'),
                pl.col('prev_close'),
                pl.col('o').alias('open'),
                pl.col('h').alias('high'),
                pl.col('l').alias('low'),
                pl.col('c').alias('close'),
                pl.col('v').alias('volume')
            ]).alias('details')
        ]).with_columns([
            pl.col('details').cast(pl.Utf8).alias('details_json')
        ]).drop('details')
        normalized_dfs.append(df_e8)

    # Concatenate all events
    df_all = pl.concat(normalized_dfs)

    # Remove duplicate event types per (ticker, date)
    # E.g., if E4 appears twice for same ticker/date, keep only one
    df_all = df_all.unique(subset=['ticker', 'date', 'event'])

    return df_all


def fuse_events(df_normalized: pl.DataFrame) -> pl.DataFrame:
    """
    Fuse events by (ticker, date) into single rows with aggregated event info

    Output columns:
    - ticker
    - date
    - event_types: list[str] (sorted alphabetically)
    - num_events: int
    - event_details: list[str] (JSON strings for each event)
    """

    df_fused = df_normalized.group_by(['ticker', 'date']).agg([
        pl.col('event').sort().alias('event_types'),
        pl.col('event').count().alias('num_events'),
        pl.col('details_json').alias('event_details')
    ]).sort(['date', 'ticker'])

    return df_fused


def add_ml_features(df_fused: pl.DataFrame) -> pl.DataFrame:
    """
    Add ML-ready features for model training

    New columns:
    - has_e1: bool (volume explosion present)
    - has_e4: bool (parabolic move present)
    - has_e7: bool (first red day present)
    - has_e8: bool (gap down violent present)
    - event_combination: str (e.g., "E1_E4", "E4_E7_E8")
    - is_multi_event: bool (num_events > 1)
    """

    df_ml = df_fused.with_columns([
        # Binary flags for each event type
        pl.col('event_types').list.contains('E1').alias('has_e1'),
        pl.col('event_types').list.contains('E4').alias('has_e4'),
        pl.col('event_types').list.contains('E7').alias('has_e7'),
        pl.col('event_types').list.contains('E8').alias('has_e8'),

        # Event combination as string (for grouping/analysis)
        pl.col('event_types').list.join('_').alias('event_combination'),

        # Multi-event flag
        (pl.col('num_events') > 1).alias('is_multi_event')
    ])

    return df_ml


def generate_summary_stats(df_watchlist: pl.DataFrame) -> dict:
    """Generate summary statistics for the watchlist"""

    stats = {
        'total_entries': len(df_watchlist),
        'unique_tickers': df_watchlist['ticker'].n_unique(),
        'date_range': {
            'min': str(df_watchlist['date'].min()),
            'max': str(df_watchlist['date'].max())
        },
        'event_distribution': {
            'single_event': df_watchlist.filter(pl.col('num_events') == 1).shape[0],
            'multi_event': df_watchlist.filter(pl.col('num_events') > 1).shape[0]
        },
        'event_type_counts': {
            'E1': df_watchlist.filter(pl.col('has_e1')).shape[0],
            'E4': df_watchlist.filter(pl.col('has_e4')).shape[0],
            'E7': df_watchlist.filter(pl.col('has_e7')).shape[0],
            'E8': df_watchlist.filter(pl.col('has_e8')).shape[0]
        },
        'top_combinations': df_watchlist.group_by('event_combination').agg([
            pl.len().alias('count')
        ]).sort('count', descending=True).head(10).to_dicts()
    }

    return stats


def main():
    print('=' * 80)
    print('MULTI-EVENT FUSER: Consolidating E1, E4, E7, E8')
    print('=' * 80)
    print()

    # Paths
    EVENTS_DIR = Path('processed/events')
    OUTDIR = Path('processed/watchlist')
    OUTDIR.mkdir(parents=True, exist_ok=True)

    OUTFILE = OUTDIR / 'multi_event_watchlist.parquet'
    METADATA_FILE = OUTDIR / 'watchlist_metadata.json'

    # 1. Load event files
    events = load_event_files(EVENTS_DIR)

    # 2. Normalize to common schema
    print('Normalizing event schemas...')
    df_normalized = normalize_event_data(events)
    print(f'Total normalized events: {len(df_normalized):,}')
    print()

    # 3. Fuse events by (ticker, date)
    print('Fusing events by (ticker, date)...')
    df_fused = fuse_events(df_normalized)
    print(f'Total watchlist entries: {len(df_fused):,}')
    print()

    # 4. Add ML features
    print('Adding ML features...')
    df_watchlist = add_ml_features(df_fused)
    print('ML features added: has_e1, has_e4, has_e7, has_e8, event_combination, is_multi_event')
    print()

    # 5. Generate summary statistics
    print('Generating summary statistics...')
    stats = generate_summary_stats(df_watchlist)
    print()

    # 6. Save outputs
    print('Saving outputs...')
    print('=' * 80)

    # Save parquet
    df_watchlist.write_parquet(OUTFILE)
    file_size_mb = OUTFILE.stat().st_size / (1024 * 1024)
    print(f'[OK] Watchlist: {OUTFILE}')
    print(f'     Size: {file_size_mb:.2f} MB')
    print(f'     Rows: {len(df_watchlist):,}')
    print()

    # Save metadata
    with open(METADATA_FILE, 'w') as f:
        json.dump(stats, f, indent=2)
    print(f'[OK] Metadata: {METADATA_FILE}')
    print()

    # 7. Print summary
    print('=' * 80)
    print('SUMMARY STATISTICS')
    print('=' * 80)
    print()
    print(f'Total watchlist entries: {stats["total_entries"]:,}')
    print(f'Unique tickers: {stats["unique_tickers"]:,}')
    print(f'Date range: {stats["date_range"]["min"]} -> {stats["date_range"]["max"]}')
    print()
    print('Event Distribution:')
    print(f'  Single event days: {stats["event_distribution"]["single_event"]:,}')
    print(f'  Multi-event days: {stats["event_distribution"]["multi_event"]:,}')
    print()
    print('Event Type Coverage:')
    for event_type, count in stats['event_type_counts'].items():
        print(f'  {event_type}: {count:,} days')
    print()
    print('Top 10 Event Combinations:')
    for combo in stats['top_combinations']:
        print(f'  {combo["event_combination"]}: {combo["count"]:,} days')
    print()
    print('=' * 80)
    print('[OK] MULTI-EVENT FUSER COMPLETED')
    print('=' * 80)


if __name__ == '__main__':
    main()
