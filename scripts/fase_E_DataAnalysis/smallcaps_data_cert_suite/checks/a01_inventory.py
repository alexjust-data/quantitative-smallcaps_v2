import argparse, pathlib, re
from _utils import save_json, fail_or_pass

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, help="Proyecto raíz (ej. D:/04_TRADING_SMALLCAPS)")
    ap.add_argument("--out", required=True, help="Archivo JSON de salida")
    ap.add_argument("--min_date", default="2020-01-03")
    ap.add_argument("--max_date", default="2025-10-21")
    args = ap.parse_args()

    root = pathlib.Path(args.root)
    metrics = {"root": str(root), "checks": []}

    expected_per_day = {
        "raw/polygon/trades": ["trades.parquet", "_SUCCESS"],
        "processed/bars": ["dollar_imbalance.parquet", "_SUCCESS"],
        "processed/labels": ["labels.parquet"],
        "processed/weights": ["weights.parquet"],
        "processed/datasets/daily": ["dataset.parquet"],
    }

    total_ok = True
    date_pat = re.compile(r"date=(\d{4}-\d{2}-\d{2})")
    all_days = set()

    for sub, files in expected_per_day.items():
        subroot = root / sub
        found = 0
        missing = 0
        per_day_counts = {}
        for day_dir in subroot.rglob("date=*"):
            m = date_pat.search(str(day_dir))
            if not m: 
                continue
            day = m.group(1)
            all_days.add(day)
            expected = set(files)
            present = set([p.name for p in day_dir.glob("*") if p.is_file()])
            miss = sorted(list(expected - present))
            per_day_counts[day] = {"present": sorted(list(present & expected)), "missing": miss}
            if miss:
                missing += 1
            else:
                found += 1

        metrics["checks"].append({
            "subdir": sub,
            "days_ok": found,
            "days_missing": missing,
            "sample": {k:v for k,v in list(per_day_counts.items())[:3]}
        })
        total_ok &= (missing == 0)

    metrics["date_range"] = {
        "min_requested": args.min_date, "max_requested": args.max_date,
        "observed_total_days": len(all_days)
    }
    fail_or_pass(args.out, metrics, total_ok)

if __name__ == "__main__":
    main()
