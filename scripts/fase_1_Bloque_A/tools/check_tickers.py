import polars as pl

print("="*80)
print("1. REFERENCE UNIVERSE")
print("="*80)

df = pl.read_parquet("raw/polygon/reference/tickers_snapshot/snapshot_date=2025-10-19/tickers.parquet")
print(f"Total tickers: {df.height:,}")

# Distribucion alfabetica
df = df.with_columns(pl.col("ticker").str.slice(0, 1).alias("first_letter"))
by_letter = df.group_by("first_letter").len().sort("first_letter")
letters = [row[0] for row in by_letter.iter_rows()]
counts = {row[0]: row[1] for row in by_letter.iter_rows()}

print("\nDistribucion alfabetica:")
alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
for letter in alphabet:
    count = counts.get(letter, 0)
    if count == 0:
        print(f"  {letter}: MISSING!")
    elif count < 100:
        print(f"  {letter}: {count:,} (low)")
    else:
        print(f"  {letter}: {count:,}")

# Verificar coverage
missing = set(alphabet) - set(letters)
if missing:
    print(f"\n⚠ MISSING: {sorted(missing)}")
else:
    print(f"\n✓ OK: Cobertura completa A-Z")

print("\n"+"="*80)
print("2. TICKER DETAILS")
print("="*80)

df_d = pl.read_parquet("raw/polygon/reference/ticker_details/as_of_date=2025-10-19/details.parquet")
print(f"Total details: {df_d.height:,}")
print(f"Tickers unicos: {df_d['ticker'].n_unique():,}")

# Distribucion alfabetica
df_d = df_d.with_columns(pl.col("ticker").str.slice(0, 1).alias("first_letter"))
by_letter_d = df_d.group_by("first_letter").len().sort("first_letter")
letters_d = [row[0] for row in by_letter_d.iter_rows()]
counts_d = {row[0]: row[1] for row in by_letter_d.iter_rows()}

print("\nDistribucion alfabetica:")
for letter in alphabet:
    count = counts_d.get(letter, 0)
    if count == 0:
        print(f"  {letter}: MISSING!")
    elif count < 50:
        print(f"  {letter}: {count:,} (low)")
    else:
        print(f"  {letter}: {count:,}")

missing_d = set(alphabet) - set(letters_d)
if missing_d:
    print(f"\n⚠ MISSING: {sorted(missing_d)}")
else:
    print(f"\n✓ OK: Cobertura completa A-Z")
