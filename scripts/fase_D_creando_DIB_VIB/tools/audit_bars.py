#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Quick audit of generated bars"""
import polars as pl
from pathlib import Path
import random
import json

bars_root = Path('processed/bars')

# Collect all files
all_files = []
for t in bars_root.iterdir():
    if not t.is_dir():
        continue
    for d in t.glob('date=*'):
        parquets = list(d.glob('*.parquet'))
        if parquets:
            all_files.append((t.name, d.name.split('=')[1], parquets[0]))

print(f"Total bar files found: {len(all_files):,}")

# Sample 30 random files
random.seed(42)
sample_files = random.sample(all_files, min(30, len(all_files)))

total_bars = 0
total_size = 0
samples = []
schema_issues = 0

expected_cols = {'t_open', 't_close', 'o', 'h', 'l', 'c', 'v', 'n', 'dollar', 'imbalance_score'}

for ticker, day, fpath in sample_files:
    try:
        df = pl.read_parquet(fpath)
        size_mb = fpath.stat().st_size / 1024 / 1024
        total_bars += len(df)
        total_size += size_mb

        # Check schema
        if not expected_cols.issubset(set(df.columns)):
            schema_issues += 1
            print(f"Schema issue: {ticker} {day} - missing cols: {expected_cols - set(df.columns)}")

        samples.append({
            'ticker': ticker,
            'day': day,
            'bars': len(df),
            'size_mb': round(size_mb, 4)
        })
    except Exception as e:
        print(f"ERROR reading {ticker} {day}: {e}")

print("\nSample of 10 files:")
for s in samples[:10]:
    print(f"  {s['ticker']:6s} {s['day']}: {s['bars']:4d} bars, {s['size_mb']:7.4f} MB")

avg_bars = total_bars / len(sample_files)
avg_size = total_size / len(sample_files)

print(f"\nSample stats (n={len(sample_files)}):")
print(f"  Avg bars/file: {avg_bars:.1f}")
print(f"  Avg size/file: {avg_size:.4f} MB")
print(f"  Schema issues: {schema_issues}")

print(f"\nEstimated total (11,054 files):")
print(f"  Total bars: ~{avg_bars * 11054:,.0f}")
print(f"  Total size: ~{avg_size * 11054:.1f} MB (~{avg_size * 11054 / 1024:.2f} GB)")

# Check one file in detail
sample_ticker, sample_day, sample_file = sample_files[0]
df = pl.read_parquet(sample_file)
print(f"\nDetailed sample: {sample_ticker} {sample_day}")
print(f"  Rows: {len(df)}")
print(f"  Columns: {df.columns}")
print(f"  Schema: {df.schema}")
print(f"\n  First 3 bars:")
print(df.head(3))

# Summary
result = {
    'total_files': len(all_files),
    'sample_size': len(sample_files),
    'avg_bars_per_file': round(avg_bars, 1),
    'avg_size_mb_per_file': round(avg_size, 4),
    'estimated_total_bars': int(avg_bars * 11054),
    'estimated_total_size_gb': round(avg_size * 11054 / 1024, 2),
    'schema_issues': schema_issues
}

with open('audit_bars_summary.json', 'w') as f:
    json.dump(result, f, indent=2)

print(f"\nSummary saved to audit_bars_summary.json")
