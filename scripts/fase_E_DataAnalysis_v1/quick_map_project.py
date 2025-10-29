#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ULTRA-FAST project mapper using system commands and sampling
"""
from pathlib import Path
import json
import subprocess
from datetime import datetime

def fast_count_dirs(path):
    """Fast directory count using system command"""
    try:
        result = subprocess.run(
            f'powershell -Command "(Get-ChildItem -Path \'{path}\' -Directory | Measure-Object).Count"',
            shell=True, capture_output=True, text=True, timeout=5
        )
        return int(result.stdout.strip()) if result.returncode == 0 else 0
    except:
        return 0

def fast_count_files(path, pattern="*.parquet"):
    """Fast file count using system command"""
    try:
        result = subprocess.run(
            f'powershell -Command "(Get-ChildItem -Path \'{path}\' -Filter \'{pattern}\' -Recurse -File | Measure-Object).Count"',
            shell=True, capture_output=True, text=True, timeout=10
        )
        return int(result.stdout.strip()) if result.returncode == 0 else 0
    except:
        return 0

def fast_dir_size(path):
    """Fast directory size using system command (MB)"""
    try:
        result = subprocess.run(
            f'powershell -Command "((Get-ChildItem -Path \'{path}\' -Recurse -File | Measure-Object -Property Length -Sum).Sum / 1MB)"',
            shell=True, capture_output=True, text=True, timeout=10
        )
        return round(float(result.stdout.strip()), 2) if result.returncode == 0 else 0
    except:
        return 0

def sample_first_file(path, pattern="*.parquet"):
    """Get first file matching pattern"""
    try:
        p = Path(path)
        return next(p.rglob(pattern), None)
    except:
        return None

def quick_schema(file_path):
    """Quick schema extraction"""
    try:
        import polars as pl
        df = pl.read_parquet(file_path)
        return {
            'columns': df.columns,
            'rows_sample': len(df),
            'size_mb': round(file_path.stat().st_size / 1024 / 1024, 4)
        }
    except:
        return None

def quick_map():
    """Ultra-fast mapping using sampling and system commands"""

    print("ULTRA-FAST MAPPER - Usando comandos del sistema y muestreo")
    print("="*80)

    structure = {
        'timestamp': datetime.now().isoformat(),
        'method': 'fast_sampling_with_system_commands',
        'phases': {}
    }

    # FASE A: Universo
    print("\nFASE A: Universo...")
    phase_a = {}

    ref_path = Path('raw/polygon/reference')
    if ref_path.exists():
        phase_a['raw/polygon/reference'] = {
            'files': [f.name for f in ref_path.glob('*.parquet')],
            'size_mb': fast_dir_size(ref_path)
        }

    proc_ref = Path('processed/ref')
    if proc_ref.exists():
        phase_a['processed/ref'] = {
            'subdirs': fast_count_dirs(proc_ref),
            'size_mb': fast_dir_size(proc_ref)
        }

    universe_path = Path('processed/universe')
    if universe_path.exists():
        phase_a['processed/universe'] = {
            'size_mb': fast_dir_size(universe_path),
            'subdirs': [d.name for d in universe_path.iterdir() if d.is_dir()][:5]  # Sample
        }

    structure['phases']['FASE_A_Universo'] = phase_a

    # FASE B: OHLCV
    print("FASE B: OHLCV Daily/Intraday...")
    phase_b = {}

    for name, path in [
        ('daily_ohlcv', 'raw/polygon/daily_ohlcv'),
        ('intraday_1m', 'raw/polygon/intraday_1m'),
        ('ohlcv_daily', 'raw/polygon/ohlcv_daily'),
        ('ohlcv_intraday_1m', 'raw/polygon/ohlcv_intraday_1m')
    ]:
        p = Path(path)
        if p.exists():
            print(f"  Mapeando {name}...")
            tickers = fast_count_dirs(p)
            # Estimate ticker-days: count subdirs in first 3 tickers
            sample_tickers = [d for d in p.iterdir() if d.is_dir()][:3]
            avg_dates = sum(fast_count_dirs(t) for t in sample_tickers) / max(len(sample_tickers), 1)
            est_ticker_days = int(tickers * avg_dates)

            sample_file = sample_first_file(p)

            phase_b[f'raw/polygon/{name}'] = {
                'tickers': tickers,
                'ticker_days_estimated': est_ticker_days,
                'size_mb': fast_dir_size(p),
                'sample_schema': quick_schema(sample_file) if sample_file else None
            }

    structure['phases']['FASE_B_OHLCV'] = phase_b

    # FASE C: Ticks
    print("FASE C: Ticks/Trades...")
    phase_c = {}

    cache_path = Path('processed/daily_cache')
    if cache_path.exists():
        phase_c['processed/daily_cache'] = {
            'dates': fast_count_dirs(cache_path),
            'size_mb': fast_dir_size(cache_path)
        }

    trades_path = Path('raw/polygon/trades')
    if trades_path.exists():
        print("  Mapeando trades...")
        tickers = fast_count_dirs(trades_path)
        # Sample estimation
        sample_tickers = [d for d in trades_path.iterdir() if d.is_dir()][:5]
        avg_days = sum(fast_count_dirs(t) for t in sample_tickers) / max(len(sample_tickers), 1)
        est_ticker_days = int(tickers * avg_days)

        sample_file = sample_first_file(trades_path, 'trades.parquet')

        phase_c['raw/polygon/trades'] = {
            'tickers': tickers,
            'ticker_days_estimated': est_ticker_days,
            'size_mb': fast_dir_size(trades_path),
            'sample_schema': quick_schema(sample_file) if sample_file else None
        }

    structure['phases']['FASE_C_Ticks'] = phase_c

    # FASE D: DIB + ML
    print("FASE D: DIB + Labels + Weights + ML...")
    phase_d = {}

    for name, path in [
        ('bars', 'processed/bars'),
        ('labels', 'processed/labels'),
        ('weights', 'processed/weights')
    ]:
        p = Path(path)
        if p.exists():
            print(f"  Mapeando {name}...")
            tickers = fast_count_dirs(p)
            sample_tickers = [d for d in p.iterdir() if d.is_dir()][:3]
            avg_days = sum(fast_count_dirs(t) for t in sample_tickers) / max(len(sample_tickers), 1)
            est_ticker_days = int(tickers * avg_days)

            sample_file = sample_first_file(p)

            phase_d[f'processed/{name}'] = {
                'tickers': tickers,
                'ticker_days_estimated': est_ticker_days,
                'size_mb': fast_dir_size(p),
                'sample_schema': quick_schema(sample_file) if sample_file else None
            }

    # Datasets
    datasets_path = Path('processed/datasets')
    if datasets_path.exists():
        daily = datasets_path / 'daily'
        if daily.exists():
            tickers = fast_count_dirs(daily)
            sample_tickers = [d for d in daily.iterdir() if d.is_dir()][:3]
            avg_days = sum(fast_count_dirs(t) for t in sample_tickers) / max(len(sample_tickers), 1)

            phase_d['processed/datasets/daily'] = {
                'tickers': tickers,
                'ticker_days_estimated': int(tickers * avg_days),
                'size_mb': fast_dir_size(daily)
            }

        global_file = datasets_path / 'global' / 'dataset.parquet'
        if global_file.exists():
            phase_d['processed/datasets/global'] = quick_schema(global_file)

        train_file = datasets_path / 'splits' / 'train.parquet'
        valid_file = datasets_path / 'splits' / 'valid.parquet'
        if train_file.exists():
            phase_d['processed/datasets/splits'] = {
                'train': quick_schema(train_file),
                'valid': quick_schema(valid_file) if valid_file.exists() else None
            }

    structure['phases']['FASE_D_DIB_ML'] = phase_d

    # OTROS
    print("OTROS: Quotes, Events, Reports...")
    others = {}

    for name, path in [
        ('quotes', 'raw/polygon/quotes'),
        ('edgar', 'raw/edgar'),
        ('events', 'processed/events'),
        ('features', 'processed/features'),
        ('reports', 'processed/reports')
    ]:
        p = Path(path)
        if p.exists():
            others[path] = {
                'size_mb': fast_dir_size(p)
            }

    structure['phases']['OTROS'] = others

    # SUMMARY
    print("\nCalculando totales...")
    structure['summary'] = {
        'raw_data_mb': fast_dir_size('raw'),
        'processed_data_mb': fast_dir_size('processed'),
        'total_mb': fast_dir_size('raw') + fast_dir_size('processed')
    }

    return structure

if __name__ == '__main__':
    import time
    t0 = time.time()

    result = quick_map()

    # Save
    output = Path('PROJECT_COMPLETE_MAP_FAST.json')
    output.write_text(json.dumps(result, indent=2))

    elapsed = time.time() - t0
    print(f"\n{'='*80}")
    print(f"✓ Completado en {elapsed:.1f} segundos")
    print(f"✓ Guardado en: {output}")
    print(f"\nTOTALES:")
    print(f"  Raw data: {result['summary']['raw_data_mb']:,.1f} MB")
    print(f"  Processed data: {result['summary']['processed_data_mb']:,.1f} MB")
    print(f"  TOTAL: {result['summary']['total_mb']:,.1f} MB")
    print(f"{'='*80}")
