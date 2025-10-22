import argparse, pathlib
from _utils import try_import_polars, fail_or_pass

SCHEMAS = {
  "trades": {"path": "raw/polygon/trades", "file": "trades.parquet",
             "required": {"t":"i64", "p":"f64", "s":"i64"}},
  "bars": {"path": "processed/bars", "file": "dollar_imbalance.parquet",
           "required": {"t_open":"i64","t_close":"i64","o":"f64","h":"f64","l":"f64","c":"f64","v":"i64","n":"i64","dollar":"f64","imbalance_score":"f64"}},
  "labels": {"path": "processed/labels", "file": "labels.parquet",
             "required": {"anchor_ts":"i64","t1":"i64","pt_hit":"bool","sl_hit":"bool","label":"i64","ret_at_outcome":"f64","vol_at_anchor":"f64"}},
  "weights": {"path": "processed/weights", "file": "weights.parquet",
              "required": {"anchor_ts":"i64","weight":"f64"}},
  "dataset": {"path": "processed/datasets/daily", "file": "dataset.parquet",
              "required": {"anchor_ts":"i64","label":"i64","weight":"f64","c":"f64","n":"i64"}}
}

def check_dir(pl, base, sub, filename, required):
    base = pathlib.Path(base) / sub
    n_files = 0; null_viol = 0; type_viol = 0; sample = []
    for p in base.rglob(filename):
        n_files += 1
        try:
            df = pl.read_parquet(p)
            for col in required.keys():
                if col not in df.columns:
                    type_viol += 1; break
            for col in required.keys():
                if df.get_column(col).null_count() > 0:
                    null_viol += 1; break
        except Exception as e:
            type_viol += 1
            sample.append({"file": str(p), "error": str(e)})
            if len(sample) >= 5: break
        if len(sample) < 3: sample.append({"file": str(p)})
        if n_files > 2000: break
    return dict(n_files=n_files, null_viol=null_viol, type_viol=type_viol, sample=sample)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    pl = try_import_polars()
    metrics = {"root": args.root, "results": {}}
    ok = True

    for k, meta in SCHEMAS.items():
        r = check_dir(pl, args.root, meta["path"], meta["file"], meta["required"])
        metrics["results"][k] = r
        ok &= (r["type_viol"] == 0 and r["null_viol"] == 0 and r["n_files"] > 0)

    fail_or_pass(args.out, metrics, ok)

if __name__ == "__main__":
    main()
