import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import polars as pl

df = pl.read_parquet('raw/polygon/reference/ticker_details/ticker_details_2025-10-24.parquet')

print('Total tickers con detalles descargados:', len(df))
print('\nColumnas disponibles (', len(df.columns), '):', df.columns)
print('\n=== ESTADISTICAS POR COLUMNA ===')
for col in df.columns:
    non_null = df[col].drop_nulls().len()
    pct = (non_null/len(df))*100
    print(f'{col:40s} {non_null:6d} / {len(df)} ({pct:5.1f}%)')

print('\n=== EJEMPLO TICKER ACTIVO (con market_cap) ===')
activo = df.filter(pl.col('market_cap').is_not_null()).head(1)
print(activo.select(['ticker', 'name', 'active', 'market_cap', 'share_class_shares_outstanding',
                     'total_employees', 'sic_description', 'list_date', 'homepage_url']))

print('\n=== EJEMPLO TICKER INACTIVO (sin market_cap) ===')
inactivo = df.filter(pl.col('market_cap').is_null()).head(1)
print(inactivo.select(['ticker', 'name', 'active', 'market_cap', 'share_class_shares_outstanding',
                       'sic_description', 'list_date']))
