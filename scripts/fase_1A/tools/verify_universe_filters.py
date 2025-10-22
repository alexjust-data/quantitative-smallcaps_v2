import polars as pl

# Leer el universo descargado
df = pl.read_parquet("raw/polygon/reference/tickers_snapshot/snapshot_date=2025-10-19")

print(f"Total tickers en universo: {df.height:,}\n")

# Verificar distribución por tipo
print("=== Distribución por TIPO ===")
by_type = df.group_by("type").len().sort("len", descending=True)
for row in by_type.iter_rows():
    print(f"  {row[0]:20s}: {row[1]:,} ({row[1]/df.height*100:.1f}%)")

print("\n=== Distribución por EXCHANGE ===")
by_exchange = df.group_by("primary_exchange").len().sort("len", descending=True)
for row in by_exchange.head(10).iter_rows():
    print(f"  {row[0]:20s}: {row[1]:,} ({row[1]/df.height*100:.1f}%)")

# Filtrar por CS (Common Stock)
df_cs = df.filter(pl.col("type") == "CS")
print(f"\n=== Tickers tipo CS (Common Stock) ===")
print(f"Total CS: {df_cs.height:,} ({df_cs.height/df.height*100:.1f}% del total)\n")

# Filtrar por exchanges objetivo: XNAS, XNYS, ARCX
target_exchanges = ["XNAS", "XNYS", "ARCX"]
df_cs_target = df_cs.filter(pl.col("primary_exchange").is_in(target_exchanges))

print(f"=== CS en NASDAQ/NYSE/ARCA ===")
print(f"Total CS en XNAS/XNYS/ARCX: {df_cs_target.height:,}\n")

print("Distribución por exchange:")
by_exch = df_cs_target.group_by("primary_exchange").len().sort("len", descending=True)
for row in by_exch.iter_rows():
    exch_name = {"XNAS": "NASDAQ", "XNYS": "NYSE", "ARCX": "NYSE Arca"}[row[0]]
    print(f"  {row[0]} ({exch_name}): {row[1]:,} ({row[1]/df_cs_target.height*100:.1f}%)")

# Verificar status activo/delisted
print(f"\n=== Status de tickers CS en NASDAQ/NYSE/ARCA ===")
by_active = df_cs_target.group_by("active").len().sort("active", descending=True)
for row in by_active.iter_rows():
    status = "Activo" if row[0] else "Delisted"
    print(f"  {status}: {row[1]:,} ({row[1]/df_cs_target.height*100:.1f}%)")

# Mostrar algunos ejemplos
print(f"\n=== Ejemplos de tickers CS activos en NASDAQ/NYSE/ARCA ===")
examples = df_cs_target.filter(pl.col("active") == True).select(["ticker", "name", "primary_exchange", "type"]).head(10)
for row in examples.iter_rows():
    print(f"  {row[0]:8s} | {row[1][:40]:40s} | {row[2]:4s} | {row[3]}")

print(f"\n=== RESUMEN ===")
print(f"✓ Universo total: {df.height:,} tickers")
print(f"✓ Tipo CS: {df_cs.height:,} tickers ({df_cs.height/df.height*100:.1f}%)")
print(f"✓ CS en XNAS/XNYS/ARCX: {df_cs_target.height:,} tickers")
print(f"✓ CS activos en XNAS/XNYS/ARCX: {df_cs_target.filter(pl.col('active') == True).height:,} tickers")
print(f"✓ CS delisted en XNAS/XNYS/ARCX: {df_cs_target.filter(pl.col('active') == False).height:,} tickers")
