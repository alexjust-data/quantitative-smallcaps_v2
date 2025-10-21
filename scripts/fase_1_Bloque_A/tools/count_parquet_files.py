import os
from pathlib import Path

base = Path("raw/polygon/reference")

# Count splits
splits_dir = base / "splits"
splits_count = len(list(splits_dir.rglob("*.parquet"))) if splits_dir.exists() else 0

# Count dividends
dividends_dir = base / "dividends"
dividends_count = len(list(dividends_dir.rglob("*.parquet"))) if dividends_dir.exists() else 0

# Count all reference parquet files
all_reference = len(list(base.rglob("*.parquet")))

print(f"Splits parquet files: {splits_count}")
print(f"Dividends parquet files: {dividends_count}")
print(f"Total reference parquet files: {all_reference}")
