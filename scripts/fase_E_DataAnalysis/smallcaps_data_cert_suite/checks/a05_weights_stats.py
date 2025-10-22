import argparse, pathlib
from _utils import try_import_polars, fail_or_pass

def gini(arr):
    import numpy as np
    x = np.array(arr, dtype=float).flatten()
    if x.size == 0: return 0.0
    if (x < 0).any(): return 1.0
    x += 1e-18
    x = np.sort(x)
    n = x.size
    index = np.arange(1, n+1)
    return (np.sum((2*index - n - 1) * x) / (n * np.sum(x)))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--gini_max", type=float, default=0.9)
    ap.add_argument("--eps_sum", type=float, default=1e-6)
    args = ap.parse_args()

    pl = try_import_polars()
    weights_root = pathlib.Path(args.root) / "processed/weights"
    gini_vals = []; bad_norm = 0; files = 0

    for p in weights_root.rglob("weights.parquet"):
        df = pl.read_parquet(p).select(["weight"])
        s = float(df["weight"].sum())
        if abs(s - 1.0) > args.eps_sum: bad_norm += 1
        g = gini(df["weight"].to_numpy())
        gini_vals.append(g); files += 1

    avg_gini = float(sum(gini_vals)/max(1,len(gini_vals)))
    metrics = {"files": files, "bad_normalization_files": bad_norm, "avg_gini": avg_gini, "gini_max": args.gini_max}
    ok = (bad_norm == 0 and avg_gini <= args.gini_max)
    fail_or_pass(args.out, metrics, ok)

if __name__ == "__main__":
    main()
