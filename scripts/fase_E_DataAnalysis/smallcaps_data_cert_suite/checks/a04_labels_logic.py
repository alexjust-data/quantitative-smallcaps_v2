import argparse, pathlib
from _utils import try_import_polars, fail_or_pass

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max_zero_share", type=float, default=0.9)
    args = ap.parse_args()

    pl = try_import_polars()
    labels_root = pathlib.Path(args.root) / "processed/labels"
    total = 0; bad = 0; cnt = {-1:0, 0:0, 1:0}

    for p in labels_root.rglob("labels.parquet"):
        df = pl.read_parquet(p).select(["anchor_ts","t1","pt_hit","sl_hit","label"])
        total += len(df)
        both = (df["pt_hit"] & df["sl_hit"]).sum()
        if both > 0: bad += int(both)
        bad += int((df["t1"] < df["anchor_ts"]).sum())
        for k in cnt.keys():
            cnt[k] += int((df["label"] == k).sum())

    total_labels = sum(cnt.values())
    max_share = max(cnt.values()) / max(1, total_labels)
    metrics = {"total_rows": total_labels, "label_counts": cnt, "bad_rows": bad, "max_label_share": max_share}
    ok = (bad == 0 and max_share <= args.max_zero_share)
    fail_or_pass(args.out, metrics, ok)

if __name__ == "__main__":
    main()
