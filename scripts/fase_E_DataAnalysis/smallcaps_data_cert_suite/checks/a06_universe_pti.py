import argparse, pathlib
from _utils import try_import_polars, fail_or_pass

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--mc_max", type=float, default=2e9)
    ap.add_argument("--float_max", type=float, default=1e8)
    ap.add_argument("--pmin", type=float, default=0.5)
    ap.add_argument("--pmax", type=float, default=20.0)
    ap.add_argument("--volmin", type=float, default=5e5)
    ap.add_argument("--chgmin", type=float, default=0.15)
    args = ap.parse_args()

    pl = try_import_polars()
    daily_cache = pathlib.Path(args.root) / "processed/universe/daily_cache"
    watchlists = pathlib.Path(args.root) / "processed/universe/dynamic"

    violations = []; ok_count = 0; total = 0
    for wl in watchlists.rglob("watchlist.parquet"):
        day = [q for q in wl.parts if q.startswith("date=")][0].split("=")[1]
        dfw = pl.read_parquet(wl)  # expect ticker column
        for tkr in dfw["ticker"].unique().to_list():
            total += 1
            dc = daily_cache / tkr / f"date={day}" / "daily.parquet"
            if not dc.exists():
                violations.append({"ticker": tkr, "date": day, "reason": "missing daily_cache"}); continue
            d = pl.read_parquet(dc)
            row = d.select(["close","volume","rvol","pct_chg","shares_out","float_est","exchange"]).to_dicts()
            if not row:
                violations.append({"ticker": tkr, "date": day, "reason": "empty daily_cache"}); continue
            r = row[0]
            market_cap = float((r.get("close") or 0.0) * (r.get("shares_out") or 0.0))
            conds = [
                market_cap <= args.mc_max,
                (r.get("float_est") or 0.0) <= args.float_max,
                args.pmin <= (r.get("close") or 0.0) <= args.pmax,
                (r.get("volume") or 0.0) >= args.volmin,
                abs(r.get("pct_chg") or 0.0) >= args.chgmin,
                (r.get("exchange") or "") in ("NASDAQ","NYSE","NYSE MKT","AMEX")
            ]
            if not all(conds):
                violations.append({"ticker": tkr, "date": day, "market_cap": market_cap, "row": r})
            else:
                ok_count += 1

    ok = (len(violations) == 0 and total > 0)
    fail_or_pass(args.out, {"checked": total, "pass": ok_count, "violations": violations}, ok)

if __name__ == "__main__":
    main()
