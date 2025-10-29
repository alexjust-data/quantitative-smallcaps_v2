#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check which events are actually in the watchlist"""

import polars as pl
from pathlib import Path

# Load watchlist
watchlist_path = Path('processed/watchlist_E1_E11.parquet')
df = pl.read_parquet(watchlist_path)

print('=' * 80)
print('VERIFICACION DE EVENTOS EN WATCHLIST')
print('=' * 80)
print()

print(f'Total ticker-dates: {len(df):,}')
print()

# Extract all unique events
all_events = []
for row in df.iter_rows(named=True):
    all_events.extend(row['events'])

unique_events = sorted(set(all_events))

print(f'Eventos unicos encontrados: {len(unique_events)}')
print()

for event in unique_events:
    count = sum(1 for e in all_events if e == event)
    print(f'  {event}: {count:,} ocurrencias')

print()
print('=' * 80)

# Check if E0 is included
if any('E0' in e for e in unique_events):
    print('[OK] E0 esta incluido')
else:
    print('[!] E0 NO esta incluido - solo E1-E11')

print('=' * 80)
