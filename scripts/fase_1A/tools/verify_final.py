import polars as pl

df = pl.read_parquet("raw/polygon/reference/dividends")
print(f"Total dividends: {df.height:,}")

df2 = df.with_columns(pl.col("ex_dividend_date").str.slice(0,4).alias("year"))
by_year = df2.group_by("year").len().sort("year")

print("\nPrimeros 10 anos:")
for row in by_year.head(10).iter_rows():
    print(f"  {row[0]}: {row[1]:,}")

print("...")

print("Ultimos 10 anos:")
for row in by_year.tail(10).iter_rows():
    print(f"  {row[0]}: {row[1]:,}")
