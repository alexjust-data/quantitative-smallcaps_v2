import argparse, pathlib
from _utils import try_import_polars, fail_or_pass

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    pl = try_import_polars()
    events_root = pathlib.Path(args.root) / "processed/events"
    bars_root = pathlib.Path(args.root) / "processed/bars"

    bad = 0; total=0; samples=[]
    for ev in events_root.rglob("events.parquet"):
        parts = ev.parts
        ticker = parts[-3]
        date = parts[-2].split("=")[1]
        bars_file = bars_root / ticker / f"date={date}" / "dollar_imbalance.parquet"
        if not bars_file.exists():
            bad += 1; samples.append({"file": str(ev), "reason":"missing bars"}); continue
        dfb = pl.read_parquet(bars_file).select(["t_open","t_close"])
        dfe = pl.read_parquet(ev).select(["anchor_ts"])
        total += len(dfe)
        j = dfe.join(dfb, left_on="anchor_ts", right_on="t_close", how="left")
        miss = int(j["t_open"].null_count())
        bad += miss
        if miss: samples.append({"file": str(ev), "missing_anchors": miss})
    ok = (bad == 0 and total>0)
    fail_or_pass(args.out, {"events_checked": total, "missing_anchors": bad, "samples": samples[:5]}, ok)

if __name__ == "__main__":
    main()
