import polars as pl

df = pl.read_parquet("raw/polygon/reference/dividends")
print(f"Total dividends: {df.height:,}")

df = df.with_columns(pl.col("ex_dividend_date").str.slice(0,4).alias("year"))
by_year = df.group_by("year").len().sort("year")

print("\nDistribucion por ano:")
for row in by_year.iter_rows():
    print(f"  {row[0]}: {row[1]:,}")
