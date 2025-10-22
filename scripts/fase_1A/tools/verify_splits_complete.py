import polars as pl

# Verify splits
df_splits = pl.read_parquet("raw/polygon/reference/splits")
print(f"Total splits: {df_splits.height:,}")

df_s = df_splits.with_columns(pl.col("execution_date").str.slice(0,4).alias("year"))
by_year = df_s.group_by("year").len().sort("year")

print(f"\nYears covered: {by_year.height}")
print("\nFirst 10 years:")
for row in by_year.head(10).iter_rows():
    print(f"  {row[0]}: {row[1]:,}")

print("\nLast 10 years:")
for row in by_year.tail(10).iter_rows():
    print(f"  {row[0]}: {row[1]:,}")

# Split ratio stats
print("\nSplit ratio stats:")
print(f"  Mean: {df_splits['split_from'].mean() / df_splits['split_to'].mean():.4f}")
print(f"  Min ratio: {(df_splits['split_from'] / df_splits['split_to']).min():.4f}")
print(f"  Max ratio: {(df_splits['split_from'] / df_splits['split_to']).max():.4f}")
