import polars as pl

# Leer el universo descargado
df = pl.read_parquet("raw/polygon/reference/tickers_snapshot/snapshot_date=2025-10-19")

# Filtrar por CS y ARCX
df_arcx_cs = df.filter(
    (pl.col("type") == "CS") &
    (pl.col("primary_exchange") == "ARCX")
)

print(f"Total CS en ARCX (NYSE Arca): {df_arcx_cs.height:,}")

if df_arcx_cs.height > 0:
    print("\nEjemplos de tickers CS en ARCX:")
    examples = df_arcx_cs.select(["ticker", "name", "primary_exchange", "type", "active"]).head(20)
    for row in examples.iter_rows():
        status = "Activo" if row[4] else "Delisted"
        print(f"  {row[0]:8s} | {row[1][:40]:40s} | {row[2]:4s} | {row[3]} | {status}")

# Resumen completo
print("\n=== CONFIRMACION FINAL ===")
df_cs_target = df.filter(
    (pl.col("type") == "CS") &
    (pl.col("primary_exchange").is_in(["XNAS", "XNYS", "ARCX"]))
)

print(f"Total universo descargado: {df.height:,} tickers")
print(f"Total CS (Common Stock): {df.filter(pl.col('type') == 'CS').height:,} tickers")
print(f"Total CS en NASDAQ/NYSE/ARCA: {df_cs_target.height:,} tickers")
print("\nDesglose por exchange:")
by_exch = df_cs_target.group_by("primary_exchange").len().sort("primary_exchange")
for row in by_exch.iter_rows():
    exch_name = {"XNAS": "NASDAQ", "XNYS": "NYSE", "ARCX": "NYSE Arca"}.get(row[0], row[0])
    print(f"  - {exch_name:12s}: {row[1]:,} tickers CS")

print("\n¿El universo esta filtrado por tipo CS? NO - contiene todos los tipos")
print("¿El universo contiene CS de NASDAQ/NYSE/ARCA? SI - {0:,} tickers CS".format(df_cs_target.height))
print("\nNOTA: El universo descargado es COMPLETO (todos los tipos), pero")
print("      podemos filtrar facilmente por tipo=CS y exchange=XNAS/XNYS/ARCX")
