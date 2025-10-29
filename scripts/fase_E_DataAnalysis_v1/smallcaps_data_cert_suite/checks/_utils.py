import json, sys, time, hashlib, os, argparse, pathlib, math
from typing import Dict, Any, List, Tuple

def save_json(path, obj):
    pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def fail_or_pass(report_path: str, metrics: dict, ok: bool):
    metrics["status"] = "PASS" if ok else "FAIL"
    save_json(report_path, metrics)
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    sys.exit(0 if ok else 1)

def try_import_polars():
    try:
        import polars as pl
        return pl
    except Exception as e:
        print("Polars no disponible. Instala con: pip install polars pyarrow", file=sys.stderr)
        raise

def list_parquet_files(base: str, filename: str):
    base_p = pathlib.Path(base)
    return [str(p) for p in base_p.rglob(filename)]

def hxxh64_file(path, chunk_size=1<<20):
    h = hashlib.blake2b(digest_size=16)
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk_size)
            if not b:
                break
            h.update(b)
    return h.hexdigest()

def human(x):
    for unit in ['B','KB','MB','GB','TB']:
        if x < 1024.0:
            return f"{x:3.1f} {unit}"
        x /= 1024.0
    return f"{x:.1f} PB"
