#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Comprehensive data structure mapper for ML pipeline
"""
from pathlib import Path
import polars as pl
import json

def count_files(root, pattern="*"):
    """Count files matching pattern"""
    return len(list(Path(root).rglob(pattern)))

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

def map_complete_structure():
    """Map entire data structure"""

    structure = {
        'timestamp': '2025-10-22T20:00:00',
        'summary': {},
        'directories': {}
    }

    # 1. RAW TRADES
    print("Mapping raw/polygon/trades...")
    trades_root = Path('raw/polygon/trades')
    if trades_root.exists():
        tickers = [d for d in trades_root.iterdir() if d.is_dir()]
        total_days = sum(1 for t in tickers for d in t.glob('date=*'))
        total_parquets = sum(1 for t in tickers for d in t.glob('date=*/trades.parquet'))
        total_success = sum(1 for t in tickers for d in t.glob('date=*/_SUCCESS'))

        # Sample file
        sample_file = next((f for t in tickers for f in t.glob('date=*/trades.parquet')), None)
        sample_schema = get_sample_schema(sample_file) if sample_file else None

        structure['directories']['raw/polygon/trades'] = {
            'description': 'Raw tick-level trades from Polygon API v3',
            'tickers': len(tickers),
            'ticker_sample': [t.name for t in tickers[:5]],
            'total_ticker_days': total_days,
            'files': {
                'trades.parquet': total_parquets,
                '_SUCCESS': total_success
            },
            'structure': '{ticker}/date=YYYY-MM-DD/[trades.parquet, _SUCCESS]',
            'sample_schema': sample_schema
        }

    # 2. PROCESSED BARS
    print("Mapping processed/bars...")
    bars_root = Path('processed/bars')
    if bars_root.exists():
        tickers = [d for d in bars_root.iterdir() if d.is_dir()]
        total_days = sum(1 for t in tickers for d in t.glob('date=*'))
        total_parquets = sum(1 for t in tickers for d in t.glob('date=*/dollar_imbalance.parquet'))
        total_success = sum(1 for t in tickers for d in t.glob('date=*/_SUCCESS'))

        sample_file = next((f for t in tickers for f in t.glob('date=*/dollar_imbalance.parquet')), None)
        sample_schema = get_sample_schema(sample_file) if sample_file else None

        structure['directories']['processed/bars'] = {
            'description': 'Dollar Imbalance Bars (DIB) - information-driven bars',
            'tickers': len(tickers),
            'ticker_sample': [t.name for t in tickers[:5]],
            'total_ticker_days': total_days,
            'files': {
                'dollar_imbalance.parquet': total_parquets,
                '_SUCCESS': total_success
            },
            'structure': '{ticker}/date=YYYY-MM-DD/[dollar_imbalance.parquet, _SUCCESS]',
            'sample_schema': sample_schema
        }

    # 3. PROCESSED LABELS
    print("Mapping processed/labels...")
    labels_root = Path('processed/labels')
    if labels_root.exists():
        tickers = [d for d in labels_root.iterdir() if d.is_dir()]
        total_days = sum(1 for t in tickers for d in t.glob('date=*'))
        total_parquets = sum(1 for t in tickers for d in t.glob('date=*/labels.parquet'))

        sample_file = next((f for t in tickers for f in t.glob('date=*/labels.parquet')), None)
        sample_schema = get_sample_schema(sample_file) if sample_file else None

        structure['directories']['processed/labels'] = {
            'description': 'Triple Barrier labels (PT/SL/Vertical)',
            'tickers': len(tickers),
            'ticker_sample': [t.name for t in tickers[:5]],
            'total_ticker_days': total_days,
            'files': {
                'labels.parquet': total_parquets
            },
            'structure': '{ticker}/date=YYYY-MM-DD/labels.parquet',
            'sample_schema': sample_schema
        }

    # 4. PROCESSED WEIGHTS
    print("Mapping processed/weights...")
    weights_root = Path('processed/weights')
    if weights_root.exists():
        tickers = [d for d in weights_root.iterdir() if d.is_dir()]
        total_days = sum(1 for t in tickers for d in t.glob('date=*'))
        total_parquets = sum(1 for t in tickers for d in t.glob('date=*/weights.parquet'))

        sample_file = next((f for t in tickers for f in t.glob('date=*/weights.parquet')), None)
        sample_schema = get_sample_schema(sample_file) if sample_file else None

        structure['directories']['processed/weights'] = {
            'description': 'Sample weights (uniqueness + |ret| + time-decay)',
            'tickers': len(tickers),
            'ticker_sample': [t.name for t in tickers[:5]],
            'total_ticker_days': total_days,
            'files': {
                'weights.parquet': total_parquets
            },
            'structure': '{ticker}/date=YYYY-MM-DD/weights.parquet',
            'sample_schema': sample_schema
        }

    # 5. PROCESSED DATASETS
    print("Mapping processed/datasets...")
    datasets_root = Path('processed/datasets')
    if datasets_root.exists():
        # Daily
        daily_root = datasets_root / 'daily'
        if daily_root.exists():
            tickers = [d for d in daily_root.iterdir() if d.is_dir()]
            total_days = sum(1 for t in tickers for d in t.glob('date=*'))
            total_parquets = sum(1 for t in tickers for d in t.glob('date=*/dataset.parquet'))

            sample_file = next((f for t in tickers for f in t.glob('date=*/dataset.parquet')), None)
            sample_schema = get_sample_schema(sample_file) if sample_file else None

            structure['directories']['processed/datasets/daily'] = {
                'description': 'Daily ML datasets (bars + labels + weights + features)',
                'tickers': len(tickers),
                'ticker_sample': [t.name for t in tickers[:5]],
                'total_ticker_days': total_days,
                'files': {
                    'dataset.parquet': total_parquets
                },
                'structure': '{ticker}/date=YYYY-MM-DD/dataset.parquet',
                'sample_schema': sample_schema
            }

        # Global
        global_file = datasets_root / 'global' / 'dataset.parquet'
        if global_file.exists():
            global_schema = get_sample_schema(global_file)
            structure['directories']['processed/datasets/global'] = {
                'description': 'Global concatenated dataset (all ticker-days)',
                'files': {
                    'dataset.parquet': 1
                },
                'schema': global_schema
            }

        # Splits
        train_file = datasets_root / 'splits' / 'train.parquet'
        valid_file = datasets_root / 'splits' / 'valid.parquet'
        if train_file.exists() and valid_file.exists():
            train_schema = get_sample_schema(train_file)
            valid_schema = get_sample_schema(valid_file)

            structure['directories']['processed/datasets/splits'] = {
                'description': 'Train/Valid splits (walk-forward with purging)',
                'files': {
                    'train.parquet': 1,
                    'valid.parquet': 1
                },
                'train': train_schema,
                'valid': valid_schema
            }

        # Meta
        meta_file = datasets_root / 'meta.json'
        if meta_file.exists():
            meta = json.loads(meta_file.read_text())
            structure['directories']['processed/datasets/meta'] = meta

    # Summary
    structure['summary'] = {
        'total_tickers': len([d for d in Path('raw/polygon/trades').iterdir() if d.is_dir()]) if Path('raw/polygon/trades').exists() else 0,
        'total_ticker_days': sum(1 for d in Path('raw/polygon/trades').rglob('date=*') if d.is_dir()) if Path('raw/polygon/trades').exists() else 0,
        'total_raw_trades_files': count_files('raw/polygon/trades', 'trades.parquet'),
        'total_bar_files': count_files('processed/bars', 'dollar_imbalance.parquet'),
        'total_label_files': count_files('processed/labels', 'labels.parquet'),
        'total_weight_files': count_files('processed/weights', 'weights.parquet'),
        'total_daily_dataset_files': count_files('processed/datasets/daily', 'dataset.parquet'),
        'global_dataset_rows': structure['directories'].get('processed/datasets/global', {}).get('schema', {}).get('rows', 0),
        'train_rows': structure['directories'].get('processed/datasets/splits', {}).get('train', {}).get('rows', 0),
        'valid_rows': structure['directories'].get('processed/datasets/splits', {}).get('valid', {}).get('rows', 0)
    }

    return structure

if __name__ == '__main__':
    print("Mapping complete data structure...")
    structure = map_complete_structure()

    # Save to JSON
    output_file = Path('DATA_STRUCTURE_MAP.json')
    output_file.write_text(json.dumps(structure, indent=2))
    print(f"\nComplete map saved to: {output_file}")

    # Print summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    for key, value in structure['summary'].items():
        print(f"{key:.<50} {value:>15,}")
