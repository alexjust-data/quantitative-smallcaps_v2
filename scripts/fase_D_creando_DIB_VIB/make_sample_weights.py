#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
make_sample_weights.py
Calcula pesos de muestra: unicidad temporal + |ret| + time-decay.
Entrada:
  processed/labels/{ticker}/date=YYYY-MM-DD/labels.parquet
Salida:
  processed/weights/{ticker}/date=YYYY-MM-DD/weights.parquet
Uso:
  python scripts/fase_G_weights/make_sample_weights.py \
    --labels-root processed/labels \
    --outdir processed/weights \
    --uniqueness true --abs-ret-weight true \
    --time-decay-half_life 90 --parallel 8 --resume
"""
import argparse, time, math
from datetime import datetime
from pathlib import Path
import polars as pl
from concurrent.futures import ProcessPoolExecutor, as_completed

def log(msg): print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)

def list_label_files(labels_root: Path):
    for tdir in labels_root.iterdir():
        if not tdir.is_dir(): continue
        ticker = tdir.name
        for ddir in tdir.glob("date=*"):
            day = ddir.name.split("=")[1]
            f = ddir / "labels.parquet"
            if f.exists():
                yield ticker, day, f

def compute_weights(df: pl.DataFrame, use_uniqueness: bool, abs_ret: bool,
                    half_life_days: int) -> pl.DataFrame:
    if df.is_empty():
        return pl.DataFrame({"anchor_ts": [], "weight": []})

    df = df.sort("anchor_ts")
    # Base weight: |ret| o 1
    base = df["ret_at_outcome"].abs() if abs_ret else pl.Series([1.0]*df.height)

    # Unicidad temporal: prox con conteo de eventos que cubren cada anchor_ts (ventanas [anchor,t1])
    # Aproximación: para cada i, concurrency = nº de ventanas que incluyen anchor_ts[i]
    anchors = df["anchor_ts"]
    t1s = df["t1"]
    # Convert to python lists for speed in small batches
    a = anchors.to_list(); b = t1s.to_list()
    n = len(a)
    conc = []
    for i in range(n):
        ai = a[i]; cnt = 0
        for j in range(n):
            if a[j] <= ai <= b[j]:
                cnt += 1
        conc.append(max(1, cnt))
    conc_s = pl.Series(conc)

    w = base / conc_s if use_uniqueness else base

    # Time decay (por días): decay = 0.5 ** (age_days / half_life)
    if half_life_days and half_life_days > 0:
        # Suponemos los labels de un mismo day => age_days ~ 0; si mezclas días, ajustar cálculo por fecha
        decay = pl.Series([1.0]*n)
        w = w * decay

    # Normaliza (opcional): escala para que sumen 1 dentro del fichero
    w = w / max(1e-12, w.sum())
    return pl.DataFrame({"anchor_ts": anchors, "weight": w})

def worker(task):
    ticker, day, fpath, outdir, use_uni, abs_ret, half_life, resume = task
    out = outdir / ticker / f"date={day}" / "weights.parquet"
    if resume and out.exists(): return f"{ticker} {day}: SKIP"
    try:
        df = pl.read_parquet(fpath)
        out.parent.mkdir(parents=True, exist_ok=True)
        compute_weights(df, use_uni, abs_ret, half_life).write_parquet(out, compression="zstd", compression_level=2)
        return f"{ticker} {day}: OK"
    except Exception as e:
        return f"{ticker} {day}: ERROR {e}"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels-root", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--uniqueness", action="store_true")
    ap.add_argument("--abs-ret-weight", action="store_true")
    ap.add_argument("--time-decay-half_life", type=int, default=90)
    ap.add_argument("--parallel", type=int, default=8)
    ap.add_argument("--resume", action="store_true")
    args = ap.parse_args()

    labels_root = Path(args.labels_root)
    outdir = Path(args.outdir)
    tasks = [(t, d, f, outdir, args.uniqueness, args.abs_ret_weight, args.time_decay_half_life, args.resume)
             for (t, d, f) in list_label_files(labels_root)]

    log(f"Tareas: {len(tasks):,} | paralelismo={args.parallel}")
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=args.parallel) as ex:
        futs = [ex.submit(worker, t) for t in tasks]
        done = 0
        for f in as_completed(futs):
            msg = f.result(); done += 1
            if done % 200 == 0: log(f"Progreso: {done}/{len(tasks)}")
            if "ERROR" in msg: log(msg)
    log(f"FIN en {(time.time()-t0)/60:.1f} min")

if __name__ == "__main__":
    main()
