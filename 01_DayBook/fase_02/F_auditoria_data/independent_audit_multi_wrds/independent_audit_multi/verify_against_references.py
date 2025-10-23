import argparse, pathlib, json, pandas as pd, polars as pl
from utils.compare_minute import compare_ohlcv

def load_our_minute(our_minute_root: str, symbol: str, date: str) -> pd.DataFrame:
    p = pathlib.Path(our_minute_root) / symbol / f"date={date}" / "minute.parquet"
    if not p.exists(): return pd.DataFrame(columns=["t","open","high","low","close","volume"])
    df = pl.read_parquet(p).to_pandas()
    if "t" in df.columns: t = pd.to_datetime(df["t"], unit="us", utc=True, errors="coerce")
    elif "t_close" in df.columns: t = pd.to_datetime(df["t_close"], unit="us", utc=True, errors="coerce")
    else: raise RuntimeError("minute.parquet must contain 't' or 't_close' (µs).")
    cols={"o":"open","h":"high","l":"low","c":"close","v":"volume"}
    for src,dst in cols.items():
        if src in df.columns and dst not in df.columns: df[dst]=df[src]
    out = pd.DataFrame({"t":t,"open":df.get("open"),"high":df.get("high"),"low":df.get("low"),"close":df.get("close"),"volume":df.get("volume")}).dropna()
    return out

def load_our_from_dib(our_dib_root: str, symbol: str, date: str) -> pd.DataFrame:
    p = pathlib.Path(our_dib_root) / symbol / f"date={date}" / "dollar_imbalance.parquet"
    if not p.exists(): return pd.DataFrame(columns=["t","open","high","low","close","volume"])
    df = pl.read_parquet(p)
    df = df.with_columns((pl.col("t_close")/1_000_000).cast(pl.Datetime(time_unit="us")).alias("t_close_dt"))
    df = df.with_columns(pl.col("t_close_dt").dt.truncate("1m").alias("t_min"))
    agg = df.group_by("t_min").agg([pl.col("o").first().alias("open"),pl.col("h").max().alias("high"),pl.col("l").min().alias("low"),pl.col("c").last().alias("close"),pl.col("v").sum().alias("volume")]).sort("t_min")
    out = agg.to_pandas().rename(columns={"t_min":"t"}); out["t"]=pd.to_datetime(out["t"], utc=True)
    return out[["t","open","high","low","close","volume"]]

def load_vendor_frame(vendor: str, symbol: str, date: str, csv_root: str=None, wrds_root: str=None, wrds_include: str=None, wrds_exclude: str=None):
    if vendor=="polygon":
        from vendors.polygon_client import fetch_polygon_1min; return fetch_polygon_1min(symbol, date)
    if vendor=="iex":
        from vendors.iex_client import fetch_iex_1min; return fetch_iex_1min(symbol, date)
    if vendor=="finnhub":
        from vendors.finnhub_client import fetch_finnhub_1min; return fetch_finnhub_1min(symbol, date)
    if vendor=="csv":
        from vendors.csv_client import load_csv_minute
        if not csv_root: raise RuntimeError("--csv-root required for vendor=csv")
        return load_csv_minute(csv_root, symbol, date)
    raise RuntimeError(f"Unknown vendor: {vendor}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", required=True)
    ap.add_argument("--dates", required=True)
    ap.add_argument("--vendors", required=True, help="comma list: polygon,iex,finnhub,csv,wrds")
    ap.add_argument("--csv-root", default=None)
    ap.add_argument("--wrds-root", default=None)
    ap.add_argument("--wrds-include", default="@", help="Comma list of sale-condition codes to include (e.g., @)")
    ap.add_argument("--wrds-exclude", default="", help="Comma list of sale-condition codes to exclude")
    ap.add_argument("--our-minute-root", default=None)
    ap.add_argument("--our-dib-root", default=None)
    ap.add_argument("--price-tol", type=float, default=0.002)
    ap.add_argument("--vol-tol", type=float, default=0.05)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    symbols=[s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    dates=[d.strip() for d in args.dates.split(",") if d.strip()]
    vendors=[v.strip().lower() for v in args.vendors.split(",") if v.strip()]

    results={"vendors":vendors,"symbols":symbols,"dates":dates,"price_tol":args.price_tol,"vol_tol":args.vol_tol,"items":[]}

    for sym in symbols:
        for day in dates:
            if args.our-minute-root: ours = load_our_minute(args.our-minute-root, sym, day)
            elif args.our-dib-root:  ours = load_our_from_dib(args.our-dib-root, sym, day)
            else: raise RuntimeError("Provide either --our-minute-root or --our-dib-root")
            item={"symbol":sym,"date":day,"vendors":{}}
            for v in vendors:
                try:
                    ref = load_vendor_frame(v, sym, day, csv_root=args.csv_root, wrds_root=args.wrds_root, wrds_include=args.wrds_include, wrds_exclude=args.wrds_exclude)
                    if ref.empty or ours.empty:
                        comp={"rows_compared":0,"match_rate":0.0,"breaks":[],"stats":{}}
                    else:
                        comp=compare_ohlcv(ref, ours, price_tol=args.price_tol, vol_tol=args.vol_tol)
                    item["vendors"][v]=comp
                except Exception as e:
                    item["vendors"][v]={"error":str(e),"rows_compared":0,"match_rate":0.0}
            results["items"].append(item)

    overall={}
    for v in vendors:
        rows=sum(i["vendors"].get(v,{}).get("rows_compared",0) for i in results["items"])
        mr=sum(i["vendors"].get(v,{}).get("match_rate",0.0)*i["vendors"].get(v,{}).get("rows_compared",0) for i in results["items"])
        overall[v]=(mr/rows) if rows else 0.0
    results["overall_match_rate"]=overall

    pathlib.Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(args.out).write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Wrote report:", args.out); print("Overall:", overall)

if __name__=="__main__":
    main()
