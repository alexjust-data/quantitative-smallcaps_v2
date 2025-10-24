import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import polars as pl

# Cargar dimensión SCD-2 existente
dim = pl.read_parquet('processed/ref/tickers_dim/tickers_dim.parquet')

print('='*80)
print('DIMENSIÓN SCD-2 EXISTENTE')
print('='*80)
print(f'\nTotal registros: {len(dim):,}')
print(f'Tickers únicos: {dim["ticker"].n_unique():,}')
print(f'\nColumnas ({len(dim.columns)}):')
print(dim.columns)

# Verificar rangos de fechas
print(f'\n--- RANGOS DE FECHAS ---')
print(f'effective_from: {dim["effective_from"].min()} → {dim["effective_from"].max()}')
effective_to_not_null = dim.filter(pl.col("effective_to").is_not_null())
if len(effective_to_not_null) > 0:
    print(f'effective_to (no null): {effective_to_not_null["effective_to"].min()} → {effective_to_not_null["effective_to"].max()}')

# Contar registros abiertos vs cerrados
abiertos = len(dim.filter(pl.col('effective_to').is_null()))
cerrados = len(dim.filter(pl.col('effective_to').is_not_null()))
print(f'\nRegistros abiertos (effective_to = null): {abiertos:,}')
print(f'Registros cerrados (effective_to != null): {cerrados:,}')

# Verificar si están nuestros 8,686 tickers
universo = pl.read_parquet('processed/universe/cs_xnas_xnys_hybrid_enriched_2025-10-24.parquet')
tickers_universo = set(universo['ticker'].unique().to_list())
tickers_dim = set(dim['ticker'].unique().to_list())

print(f'\n--- COBERTURA DEL UNIVERSO ---')
print(f'Tickers en universo: {len(tickers_universo):,}')
print(f'Tickers en SCD-2: {len(tickers_dim):,}')

en_ambos = tickers_universo & tickers_dim
solo_universo = tickers_universo - tickers_dim
solo_dim = tickers_dim - tickers_universo

print(f'En ambos: {len(en_ambos):,} ({len(en_ambos)/len(tickers_universo)*100:.1f}%)')
print(f'Solo en universo (faltantes en SCD-2): {len(solo_universo):,}')
print(f'Solo en SCD-2 (no en universo): {len(solo_dim):,}')

if len(solo_universo) > 0:
    print(f'\nEjemplos de tickers en universo pero NO en SCD-2:')
    for i, t in enumerate(sorted(list(solo_universo))[:10]):
        print(f'  {i+1}. {t}')

# Verificar datos del snapshot original
print(f'\n--- SNAPSHOT ORIGINAL ---')
snapshot = pl.read_parquet('raw/polygon/reference/tickers_snapshot/snapshot_date=2025-10-24/tickers_all.parquet')
print(f'Tickers en snapshot 2025-10-24: {snapshot["ticker"].n_unique():,}')
print(f'Snapshot date: {snapshot["snapshot_date"][0]}')

tickers_snapshot = set(snapshot['ticker'].unique().to_list())
universo_en_snapshot = tickers_universo & tickers_snapshot
print(f'Nuestro universo en snapshot 2025-10-24: {len(universo_en_snapshot):,} ({len(universo_en_snapshot)/len(tickers_universo)*100:.1f}%)')

print('\n' + '='*80)
print('CONCLUSIÓN')
print('='*80)
print(f'La dimensión SCD-2 existente tiene {len(dim):,} registros de un snapshot antiguo (oct 2025).')
print(f'Necesitamos actualizar la dimensión SCD-2 con nuestro nuevo universo de {len(tickers_universo):,} tickers.')
print(f'Snapshot más reciente disponible: 2025-10-24')
