import argparse, pathlib, collections
from _utils import try_import_polars, fail_or_pass

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max_overlap_ratio", type=float, default=0.8)
    args = ap.parse_args()

    pl = try_import_polars()
    events_root = pathlib.Path(args.root) / "processed/events"

    counts = collections.Counter(); overlaps = 0; files = 0
    for ev in events_root.rglob("events.parquet"):
        files += 1
        df = pl.read_parquet(ev).select(["event_type","start_ts","end_ts"])
        for et, grp in df.group_by("event_type"):
            counts[et] += len(grp)
            grp_sorted = grp.sort(["start_ts","end_ts"])
            same = int(((grp_sorted["start_ts"].shift(1) == grp_sorted["start_ts"]) & 
                        (grp_sorted["end_ts"].shift(1) == grp_sorted["end_ts"])).sum())
            if len(grp_sorted) > 0 and same / max(1, len(grp_sorted)) > args.max_overlap_ratio:
                overlaps += 1

    ok = (overlaps == 0)
    fail_or_pass(args.out, {"files": files, "event_counts": dict(counts), "overlap_flags": overlaps}, ok)

if __name__ == "__main__":
    main()
