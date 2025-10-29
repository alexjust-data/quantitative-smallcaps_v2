import argparse, pathlib
from _utils import try_import_polars, fail_or_pass

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--window_days", type=int, default=10)
    args = ap.parse_args()

    pl = try_import_polars()
    filings_root = pathlib.Path(args.root) / "processed/reference/filings"
    daily_cache = pathlib.Path(args.root) / "processed/universe/daily_cache"

    violations = []; total = 0
    for f in filings_root.rglob("filings.parquet"):
        tkr = f.parent.name
        df = pl.read_parquet(f)
        if not set(["date","form"]).issubset(set(df.columns)):
            violations.append({"ticker": tkr, "reason": "bad schema"}); continue
        forms = df.filter(pl.col("form").is_in(["S-3","424B","ATM","PIPE"])).select(["date","form"]).to_dicts()
        for row in forms:
            total += 1
            date = row["date"]
            dc_dir = daily_cache / tkr
            if not dc_dir.exists():
                violations.append({"ticker": tkr, "date": date, "reason": "no daily_cache dir"}); continue
            dc = dc_dir / f"date={date}" / "daily.parquet"
            if not dc.exists():
                violations.append({"ticker": tkr, "date": date, "reason": "missing daily on filing day", "form": row["form"]})

    ok = (len(violations) == 0)
    fail_or_pass(args.out, {"checked": total, "violations": violations}, ok)

if __name__ == "__main__":
    main()
