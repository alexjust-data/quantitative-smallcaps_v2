import pathlib, pandas as pd
def load_csv_minute(csv_root: str, symbol: str, date: str):
    p = pathlib.Path(csv_root) / symbol / f"date={date}" / "minute.csv"
    if not p.exists():
        return pd.DataFrame(columns=["t","open","high","low","close","volume"])
    df = pd.read_csv(p)
    if "t" in df.columns:
        df["t"] = pd.to_datetime(df["t"], utc=True, errors="coerce")
    return df[["t","open","high","low","close","volume"]].dropna().sort_values("t")
