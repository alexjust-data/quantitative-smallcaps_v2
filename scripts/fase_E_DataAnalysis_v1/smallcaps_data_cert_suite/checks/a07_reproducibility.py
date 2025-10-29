import argparse, pathlib
from _utils import hxxh64_file, fail_or_pass

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    root = pathlib.Path(args.root)
    dirs = [
        "processed/bars",
        "processed/labels",
        "processed/weights",
        "processed/datasets/daily",
        "processed/datasets/global",
        "processed/datasets/splits",
    ]

    hashes = {}
    for d in dirs:
        droot = root / d
        if not droot.exists(): continue
        for p in droot.rglob("*.parquet"):
            hashes[str(p.relative_to(root))] = hxxh64_file(p)

    fail_or_pass(args.out, {"files_hashed": len(hashes), "hashes": hashes}, True)

if __name__ == "__main__":
    main()
