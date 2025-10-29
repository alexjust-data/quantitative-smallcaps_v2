import argparse, pathlib, random
from _utils import try_import_polars, fail_or_pass

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--sample", type=int, default=200)
    ap.add_argument("--tol", type=float, default=0.001)
    args = ap.parse_args()

    pl = try_import_polars()
    bars_root = pathlib.Path(args.root) / "processed/bars"
    items = []
    for p in bars_root.rglob("date=*/dollar_imbalance.parquet"):
        parts = p.parts
        ticker = parts[-3]
        date = parts[-2].split("=")[1]
        items.append((ticker, date, str(p)))
    random.shuffle(items)
    items = items[:args.sample]

    violations = []
    for ticker, date, bar_file in items:
        trades_file = pathlib.Path(args.root) / f"raw/polygon/trades/{ticker}/date={date}/trades.parquet"
        if not trades_file.exists():
            violations.append({"ticker": ticker, "date": date, "reason":"missing trades"})
            continue
        try:
            dfb = pl.read_parquet(bar_file).select(["t_open","t_close","v","dollar"])
            dft = pl.read_parquet(trades_file).select(["t","p","s"])
            sum_v = dfb["v"].sum()
            sum_d = dfb["dollar"].sum()
            sum_s = dft["s"].sum()
            sum_ps = (dft["p"] * dft["s"]).sum()
            ev = abs(sum_v - sum_s) / max(1, sum_s)
            ed = abs(sum_d - sum_ps) / max(1.0, sum_ps)
            if ev > args.tol or ed > args.tol:
                violations.append({"ticker":ticker,"date":date,"ev":float(ev),"ed":float(ed)})
        except Exception as e:
            violations.append({"ticker":ticker,"date":date,"error":str(e)})

    ok = (len(violations) == 0)
    fail_or_pass(args.out, {"sampled": len(items), "violations": violations}, ok)

if __name__ == "__main__":
    main()
