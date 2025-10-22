import argparse, pathlib
from _utils import try_import_polars, fail_or_pass

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--train_rows", type=int, default=1297816)
    ap.add_argument("--valid_rows", type=int, default=324467)
    ap.add_argument("--purge", type=int, default=50)
    args = ap.parse_args()

    pl = try_import_polars()
    split_root = pathlib.Path(args.root) / "processed/datasets/splits"
    train = pl.read_parquet(split_root / "train.parquet")
    valid = pl.read_parquet(split_root / "valid.parquet")

    ok = (len(train) == args.train_rows and len(valid) == args.valid_rows)
    t_train_max = int(train["anchor_ts"].max())
    t_valid_min = int(valid["anchor_ts"].min())
    ok = ok and (t_train_max + args.purge <= t_valid_min)

    fail_or_pass(args.out, {
        "train_rows": int(len(train)),
        "valid_rows": int(len(valid)),
        "t_train_max": t_train_max,
        "t_valid_min": t_valid_min,
        "purge": args.purge
    }, ok)

if __name__ == "__main__":
    main()
