import os, argparse, pathlib, json
import pandas as pd
import polars as pl
from vendors.polygon_client import fetch_polygon_1min
from utils.compare_minute import compare_ohlcv

def load_our_minute(our_minute_root: str, symbol: str, date: str) -> pd.DataFrame:
    p = pathlib.Path(our_minute_root) / symbol / f"date={date}" / "minute.parquet"
    if not p.exists():
        return pd.DataFrame(columns=["t","open","high","low","close","volume"])
    df = pl.read_parquet(p).to_pandas()
    if "t" in df.columns:
        t = pd.to_datetime(df["t"], unit="us", utc=True, errors="coerce")
    elif "t_close" in df.columns:
        t = pd.to_datetime(df["t_close"], unit="us", utc=True, errors="coerce")
    else:
        raise RuntimeError("minute.parquet must contain 't' (µs) or 't_close' (µs).")
    cols = {"o":"open","h":"high","l":"low","c":"close","v":"volume"}
    for src,dst in cols.items():
        if src in df.columns and dst not in df.columns:
            df[dst] = df[src]
    out = pd.DataFrame({
        "t": t,
        "open": df.get("open"),
        "high": df.get("high"),
        "low": df.get("low"),
        "close": df.get("close"),
        "volume": df.get("volume"),
    }).dropna()
    return out

def load_our_from_dib(our_dib_root: str, symbol: str, date: str) -> pd.DataFrame:
    p = pathlib.Path(our_dib_root) / symbol / f"date={date}" / "dollar_imbalance.parquet"
    if not p.exists():
        return pd.DataFrame(columns=["t","open","high","low","close","volume"])
    df = pl.read_parquet(p)
    df = df.with_columns((pl.col("t_close")/1_000_000).cast(pl.Datetime(time_unit="us")).alias("t_close_dt"))
    df = df.with_columns(pl.col("t_close_dt").dt.truncate("1m").alias("t_min"))
    agg = df.group_by("t_min").agg([
        pl.col("o").first().alias("open"),
        pl.col("h").max().alias("high"),
        pl.col("l").min().alias("low"),
        pl.col("c").last().alias("close"),
        pl.col("v").sum().alias("volume"),
    ]).sort("t_min")
    out = agg.to_pandas().rename(columns={"t_min":"t"})
    out["t"] = pd.to_datetime(out["t"], utc=True)
    return out[["t","open","high","low","close","volume"]]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", required=True, help="Comma-separated tickers, e.g., AAPL,AMC")
    ap.add_argument("--dates", required=True, help="Comma-separated dates YYYY-MM-DD")
    ap.add_argument("--vendor", choices=["polygon"], default="polygon")
    ap.add_argument("--our-minute-root", default=None, help="Root to our minute parquet tree")
    ap.add_argument("--our-dib-root", default=None, help="Root to our DIB bars to aggregate into minute")
    ap.add_argument("--price-tol", type=float, default=0.002)
    ap.add_argument("--vol-tol", type=float, default=0.05)
    ap.add_argument("--out", required=True, help="Path to write JSON report")
    args = ap.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    dates = [d.strip() for d in args.dates.split(",") if d.strip()]

    results = {"vendor": args.vendor, "symbols": symbols, "dates": dates,
               "price_tol": args.price_tol, "vol_tol": args.vol_tol, "items": []}

    for sym in symbols:
        for day in dates:
            ref = fetch_polygon_1min(sym, day)
            if args.our-minute-root:
                ours = load_our_minute(args.our-minute-root, sym, day)
            elif args.our-dib-root:
                ours = load_our_from_dib(args.our-dib-root, sym, day)
            else:
                raise RuntimeError("Provide either --our-minute-root or --our-dib-root")

            if ref.empty or ours.empty:
                item = {"symbol": sym, "date": day, "rows_compared": 0, "match_rate": 0.0, "note": "empty ref or ours"}
            else:
                comp = compare_ohlcv(ref, ours, price_tol=args.price_tol, vol_tol=args.vol_tol)
                item = {"symbol": sym, "date": day, **comp}
            results["items"].append(item)

    total_rows = sum(i.get("rows_compared", 0) for i in results["items"])
    mr = [i.get("match_rate", 0.0) * i.get("rows_compared", 0) for i in results["items"]]
    overall = (sum(mr)/total_rows) if total_rows else 0.0
    results["overall_match_rate"] = overall

    pathlib.Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"Wrote report: {args.out}\nOverall match rate: {overall:.4f}")

if __name__ == "__main__":
    main()
