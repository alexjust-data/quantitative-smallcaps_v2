import polars as pl

print("SPLITS:")
df_s = pl.read_parquet("raw/polygon/reference/splits")
print(f"Total: {df_s.height:,}")

df_s = df_s.with_columns(pl.col("execution_date").str.slice(0,4).alias("year"))
by_year = df_s.group_by("year").len().sort("year")
print("Por ano:")
for row in by_year.iter_rows():
    print(f"  {row[0]}: {row[1]:,}")
