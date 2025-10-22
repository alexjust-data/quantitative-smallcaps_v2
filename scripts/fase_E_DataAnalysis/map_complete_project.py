#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Complete project data mapper - ALL phases
"""
from pathlib import Path
import polars as pl
import json
from datetime import datetime

def count_items(root, pattern="*"):
    """Count items matching pattern"""
    try:
        return len(list(Path(root).rglob(pattern)))
    except:
        return 0

def get_dir_size_mb(path):
    """Get total size of directory in MB"""
    try:
        total = sum(f.stat().st_size for f in Path(path).rglob('*') if f.is_file())
        return round(total / 1024 / 1024, 2)
    except:
        return 0

def get_sample_schema(parquet_file):
    """Get schema from parquet file"""
    try:
        df = pl.read_parquet(parquet_file)
        return {
            'columns': df.columns,
            'schema': {k: str(v) for k, v in df.schema.items()},
            'rows': len(df),
            'size_mb': round(parquet_file.stat().st_size / 1024 / 1024, 4)
        }
    except Exception as e:
        return {'error': str(e)}

def map_complete_project():
    """Map entire project data structure"""

    print("Mapeando estructura completa del proyecto...")
    structure = {
        'timestamp': datetime.now().isoformat(),
        'project': 'Trading Smallcaps - Quantitative ML Pipeline',
        'phases': {}
    }

    # FASE A: Universo y Referencia
    print("\n=== FASE A: Universo y Referencia ===")
    phase_a = {}

    # raw/polygon/reference
    ref_path = Path('raw/polygon/reference')
    if ref_path.exists():
        tickers_file = ref_path / 'tickers_cs_arcx.parquet'
        splits_file = ref_path / 'splits_cs_arcx.parquet'
        dividends_file = ref_path / 'dividends_cs_arcx.parquet'

        phase_a['raw/polygon/reference'] = {
            'description': 'Reference data from Polygon (tickers, splits, dividends)',
            'files': {
                'tickers_cs_arcx.parquet': tickers_file.exists(),
                'splits_cs_arcx.parquet': splits_file.exists(),
                'dividends_cs_arcx.parquet': dividends_file.exists()
            },
            'sample_schema_tickers': get_sample_schema(tickers_file) if tickers_file.exists() else None,
            'total_size_mb': get_dir_size_mb(ref_path)
        }

    # processed/ref
    proc_ref_path = Path('processed/ref')
    if proc_ref_path.exists():
        phase_a['processed/ref'] = {
            'description': 'Processed reference data',
            'subdirs': [d.name for d in proc_ref_path.iterdir() if d.is_dir()],
            'total_size_mb': get_dir_size_mb(proc_ref_path)
        }

    # processed/universe
    universe_path = Path('processed/universe')
    if universe_path.exists():
        # Check for different universe types
        info_rich_file = next(universe_path.glob('info_rich/*.csv'), None)
        dynamic_dirs = list((universe_path / 'dynamic').glob('date=*')) if (universe_path / 'dynamic').exists() else []

        phase_a['processed/universe'] = {
            'description': 'Universe definitions (static and dynamic)',
            'info_rich_files': count_items(universe_path / 'info_rich', '*.csv'),
            'dynamic_dates': len(dynamic_dirs),
            'total_size_mb': get_dir_size_mb(universe_path),
            'sample_info_rich': get_sample_schema(info_rich_file) if info_rich_file and info_rich_file.suffix == '.parquet' else None
        }

    structure['phases']['FASE_A_Universo'] = phase_a

    # FASE B: OHLCV Daily e Intraday
    print("\n=== FASE B: OHLCV Daily e Intraday ===")
    phase_b = {}

    # raw/polygon/daily_ohlcv
    daily_path = Path('raw/polygon/daily_ohlcv')
    if daily_path.exists():
        tickers = [d for d in daily_path.iterdir() if d.is_dir()]
        ticker_dates = sum(1 for t in tickers for d in t.glob('date=*'))
        parquets = sum(1 for t in tickers for f in t.glob('date=*/daily.parquet'))

        sample_file = next((f for t in tickers for f in t.glob('date=*/daily.parquet')), None)

        phase_b['raw/polygon/daily_ohlcv'] = {
            'description': 'Daily OHLCV bars from Polygon',
            'tickers': len(tickers),
            'ticker_dates': ticker_dates,
            'parquet_files': parquets,
            'structure': '{ticker}/date=YYYY-MM-DD/daily.parquet',
            'total_size_mb': get_dir_size_mb(daily_path),
            'sample_schema': get_sample_schema(sample_file) if sample_file else None
        }

    # raw/polygon/intraday_1m
    intraday_path = Path('raw/polygon/intraday_1m')
    if intraday_path.exists():
        tickers = [d for d in intraday_path.iterdir() if d.is_dir()]
        ticker_dates = sum(1 for t in tickers for d in t.glob('date=*'))
        parquets = sum(1 for t in tickers for f in t.glob('date=*/1m.parquet'))

        sample_file = next((f for t in tickers for f in t.glob('date=*/1m.parquet')), None)

        phase_b['raw/polygon/intraday_1m'] = {
            'description': '1-minute intraday OHLCV bars from Polygon',
            'tickers': len(tickers),
            'ticker_dates': ticker_dates,
            'parquet_files': parquets,
            'structure': '{ticker}/date=YYYY-MM-DD/1m.parquet',
            'total_size_mb': get_dir_size_mb(intraday_path),
            'sample_schema': get_sample_schema(sample_file) if sample_file else None
        }

    # Check for ohlcv_daily and ohlcv_intraday_1m (possible duplicates or newer versions)
    ohlcv_daily_path = Path('raw/polygon/ohlcv_daily')
    if ohlcv_daily_path.exists():
        phase_b['raw/polygon/ohlcv_daily'] = {
            'description': 'Daily OHLCV (alternative location)',
            'total_size_mb': get_dir_size_mb(ohlcv_daily_path)
        }

    ohlcv_intra_path = Path('raw/polygon/ohlcv_intraday_1m')
    if ohlcv_intra_path.exists():
        phase_b['raw/polygon/ohlcv_intraday_1m'] = {
            'description': 'Intraday 1m OHLCV (alternative location)',
            'total_size_mb': get_dir_size_mb(ohlcv_intra_path)
        }

    structure['phases']['FASE_B_OHLCV'] = phase_b

    # FASE C: Ticks/Trades e Info-Rich Universe
    print("\n=== FASE C: Ticks/Trades e Info-Rich ===")
    phase_c = {}

    # processed/daily_cache
    cache_path = Path('processed/daily_cache')
    if cache_path.exists():
        cache_dates = list(cache_path.glob('date=*'))
        cache_parquets = count_items(cache_path, '*.parquet')

        phase_c['processed/daily_cache'] = {
            'description': 'Daily OHLCV cache for fast universe building',
            'dates': len(cache_dates),
            'parquet_files': cache_parquets,
            'total_size_mb': get_dir_size_mb(cache_path)
        }

    # raw/polygon/trades (already mapped in phase D, but belongs to phase C)
    trades_path = Path('raw/polygon/trades')
    if trades_path.exists():
        tickers = [d for d in trades_path.iterdir() if d.is_dir()]
        ticker_days = sum(1 for t in tickers for d in t.glob('date=*'))
        parquets = sum(1 for t in tickers for f in t.glob('date=*/trades.parquet'))
        success_markers = sum(1 for t in tickers for f in t.glob('date=*/_SUCCESS'))

        sample_file = next((f for t in tickers for f in t.glob('date=*/trades.parquet')), None)

        phase_c['raw/polygon/trades'] = {
            'description': 'Raw tick-level trades from Polygon API v3 (info-rich days only)',
            'tickers': len(tickers),
            'ticker_days': ticker_days,
            'trades_parquet': parquets,
            'success_markers': success_markers,
            'structure': '{ticker}/date=YYYY-MM-DD/[trades.parquet, _SUCCESS]',
            'total_size_mb': get_dir_size_mb(trades_path),
            'sample_schema': get_sample_schema(sample_file) if sample_file else None
        }

    structure['phases']['FASE_C_Ticks'] = phase_c

    # FASE D: DIB/VIB + Labels + Weights + ML Dataset
    print("\n=== FASE D: Barras Informacionales + ML ===")
    phase_d = {}

    # processed/bars
    bars_path = Path('processed/bars')
    if bars_path.exists():
        tickers = [d for d in bars_path.iterdir() if d.is_dir()]
        ticker_days = sum(1 for t in tickers for d in t.glob('date=*'))
        parquets = sum(1 for t in tickers for f in t.glob('date=*/dollar_imbalance.parquet'))
        success_markers = sum(1 for t in tickers for f in t.glob('date=*/_SUCCESS'))

        sample_file = next((f for t in tickers for f in t.glob('date=*/dollar_imbalance.parquet')), None)

        phase_d['processed/bars'] = {
            'description': 'Dollar Imbalance Bars (DIB)',
            'tickers': len(tickers),
            'ticker_days': ticker_days,
            'parquet_files': parquets,
            'success_markers': success_markers,
            'total_size_mb': get_dir_size_mb(bars_path),
            'sample_schema': get_sample_schema(sample_file) if sample_file else None
        }

    # processed/labels
    labels_path = Path('processed/labels')
    if labels_path.exists():
        tickers = [d for d in labels_path.iterdir() if d.is_dir()]
        ticker_days = sum(1 for t in tickers for d in t.glob('date=*'))
        parquets = sum(1 for t in tickers for f in t.glob('date=*/labels.parquet'))

        sample_file = next((f for t in tickers for f in t.glob('date=*/labels.parquet')), None)

        phase_d['processed/labels'] = {
            'description': 'Triple Barrier Labels',
            'tickers': len(tickers),
            'ticker_days': ticker_days,
            'parquet_files': parquets,
            'total_size_mb': get_dir_size_mb(labels_path),
            'sample_schema': get_sample_schema(sample_file) if sample_file else None
        }

    # processed/weights
    weights_path = Path('processed/weights')
    if weights_path.exists():
        tickers = [d for d in weights_path.iterdir() if d.is_dir()]
        ticker_days = sum(1 for t in tickers for d in t.glob('date=*'))
        parquets = sum(1 for t in tickers for f in t.glob('date=*/weights.parquet'))

        sample_file = next((f for t in tickers for f in t.glob('date=*/weights.parquet')), None)

        phase_d['processed/weights'] = {
            'description': 'Sample Weights (uniqueness + |ret| + time-decay)',
            'tickers': len(tickers),
            'ticker_days': ticker_days,
            'parquet_files': parquets,
            'total_size_mb': get_dir_size_mb(weights_path),
            'sample_schema': get_sample_schema(sample_file) if sample_file else None
        }

    # processed/datasets
    datasets_path = Path('processed/datasets')
    if datasets_path.exists():
        # Daily
        daily_path = datasets_path / 'daily'
        if daily_path.exists():
            tickers = [d for d in daily_path.iterdir() if d.is_dir()]
            ticker_days = sum(1 for t in tickers for d in t.glob('date=*'))
            parquets = sum(1 for t in tickers for f in t.glob('date=*/dataset.parquet'))

            sample_file = next((f for t in tickers for f in t.glob('date=*/dataset.parquet')), None)

            phase_d['processed/datasets/daily'] = {
                'description': 'Daily ML datasets (bars + labels + weights + features)',
                'tickers': len(tickers),
                'ticker_days': ticker_days,
                'parquet_files': parquets,
                'total_size_mb': get_dir_size_mb(daily_path),
                'sample_schema': get_sample_schema(sample_file) if sample_file else None
            }

        # Global
        global_file = datasets_path / 'global' / 'dataset.parquet'
        if global_file.exists():
            phase_d['processed/datasets/global'] = {
                'description': 'Global concatenated ML dataset',
                'schema': get_sample_schema(global_file)
            }

        # Splits
        train_file = datasets_path / 'splits' / 'train.parquet'
        valid_file = datasets_path / 'splits' / 'valid.parquet'
        if train_file.exists() and valid_file.exists():
            phase_d['processed/datasets/splits'] = {
                'description': 'Train/Valid splits (walk-forward)',
                'train': get_sample_schema(train_file),
                'valid': get_sample_schema(valid_file)
            }

        # Meta
        meta_file = datasets_path / 'meta.json'
        if meta_file.exists():
            phase_d['processed/datasets/meta'] = json.loads(meta_file.read_text())

    structure['phases']['FASE_D_DIB_ML'] = phase_d

    # OTROS: Quotes, Events, Features, Reports
    print("\n=== OTROS: Quotes, Events, Features, Reports ===")
    others = {}

    # raw/polygon/quotes
    quotes_path = Path('raw/polygon/quotes')
    if quotes_path.exists():
        others['raw/polygon/quotes'] = {
            'description': 'Quote data from Polygon',
            'total_size_mb': get_dir_size_mb(quotes_path)
        }

    # processed/events
    events_path = Path('processed/events')
    if events_path.exists():
        others['processed/events'] = {
            'description': 'Event-driven data',
            'total_size_mb': get_dir_size_mb(events_path)
        }

    # processed/features
    features_path = Path('processed/features')
    if features_path.exists():
        others['processed/features'] = {
            'description': 'Engineered features',
            'total_size_mb': get_dir_size_mb(features_path)
        }

    # processed/reports
    reports_path = Path('processed/reports')
    if reports_path.exists():
        others['processed/reports'] = {
            'description': 'Analysis reports',
            'total_size_mb': get_dir_size_mb(reports_path)
        }

    # raw/edgar
    edgar_path = Path('raw/edgar')
    if edgar_path.exists():
        others['raw/edgar'] = {
            'description': 'SEC EDGAR filings data',
            'total_size_mb': get_dir_size_mb(edgar_path)
        }

    structure['phases']['OTROS'] = others

    # SUMMARY
    print("\n=== Calculando resumen global ===")
    structure['summary'] = {
        'total_phases': len([k for k in structure['phases'].keys() if k.startswith('FASE')]),
        'raw_data_size_mb': get_dir_size_mb('raw'),
        'processed_data_size_mb': get_dir_size_mb('processed'),
        'total_project_size_mb': get_dir_size_mb('raw') + get_dir_size_mb('processed')
    }

    return structure

if __name__ == '__main__':
    print("="*80)
    print("MAPEADOR COMPLETO DEL PROYECTO")
    print("="*80)

    structure = map_complete_project()

    # Save to JSON
    output_file = Path('PROJECT_COMPLETE_MAP.json')
    output_file.write_text(json.dumps(structure, indent=2))
    print(f"\n✓ Mapa completo guardado en: {output_file}")

    # Print summary
    print("\n" + "="*80)
    print("RESUMEN GLOBAL")
    print("="*80)
    print(f"Total fases identificadas: {structure['summary']['total_phases']}")
    print(f"Tamaño raw data: {structure['summary']['raw_data_size_mb']:,.1f} MB")
    print(f"Tamaño processed data: {structure['summary']['processed_data_size_mb']:,.1f} MB")
    print(f"Tamaño total proyecto: {structure['summary']['total_project_size_mb']:,.1f} MB")
    print("="*80)
