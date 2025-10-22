import argparse, pathlib
from _utils import try_import_polars, fail_or_pass

REQUIRED = {"event_type","anchor_ts","start_ts","end_ts","score","source"}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    pl = try_import_polars()
    events_root = pathlib.Path(args.root) / "processed/events"

    n=0; bad=0; samples=[]
    for p in events_root.rglob("events.parquet"):
        n+=1
        try:
            df = pl.read_parquet(p)
            if not REQUIRED.issubset(set(df.columns)):
                bad += 1; samples.append({"file": str(p), "reason": "missing columns"}); continue
            if (df["start_ts"] > df["anchor_ts"]).any() or (df["anchor_ts"] > df["end_ts"]).any():
                bad += 1; samples.append({"file": str(p), "reason": "temporal order"})
        except Exception as e:
            bad += 1; samples.append({"file": str(p), "error": str(e)})
    ok = (bad == 0)
    fail_or_pass(args.out, {"files": n, "bad": bad, "samples": samples[:5]}, ok)

if __name__ == "__main__":
    main()
