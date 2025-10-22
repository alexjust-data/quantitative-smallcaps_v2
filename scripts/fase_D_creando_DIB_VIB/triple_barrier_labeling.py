#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
triple_barrier_labeling.py
Etiqueta eventos por Triple Barrier sobre barras informacionales.
Entrada:
  processed/bars/{ticker}/date=YYYY-MM-DD/{bar_type}.parquet  (cols: t_open,t_close,o,h,l,c, ...)
Salida:
  processed/labels/{ticker}/date=YYYY-MM-DD/labels.parquet
Uso:
  python scripts/fase_F_labeling/triple_barrier_labeling.py \
    --bars-root processed/bars \
    --outdir processed/labels \
    --pt-mul 3.0 --sl-mul 2.0 --t1-bars 120 \
    --vol-est ema --vol-window 50 --parallel 8 --resume
"""
import argparse, time
from datetime import datetime
from pathlib import Path
import polars as pl
from concurrent.futures import ProcessPoolExecutor, as_completed

def log(msg): print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)

def list_bar_files(bars_root: Path):
    for tdir in bars_root.iterdir():
        if not tdir.is_dir(): continue
        ticker = tdir.name
        for ddir in tdir.glob("date=*"):
            day = ddir.name.split("=")[1]
            for f in ddir.glob("*.parquet"):
                yield ticker, day, f

def ema(series: pl.Series, span: int) -> pl.Series:
    if span <= 1: return series
    alpha = 2.0 / (span + 1.0)
    out = []
    v = None
    for x in series:
        if v is None: v = x
        else: v = alpha * x + (1 - alpha) * v
        out.append(v)
    return pl.Series(out)

def label_day(in_file: Path, out_file: Path, pt_mul: float, sl_mul: float,
              t1_bars: int, vol_est: str, vol_window: int):
    df = pl.read_parquet(in_file)
    if df.is_empty():
        out_file.parent.mkdir(parents=True, exist_ok=True)
        pl.DataFrame(schema={"anchor_ts":pl.Datetime,"t1":pl.Datetime,"pt_hit":pl.Boolean,
                             "sl_hit":pl.Boolean,"label":pl.Int8,"ret_at_outcome":pl.Float64,
                             "vol_at_anchor":pl.Float64}).write_parquet(out_file, compression="zstd", compression_level=2)
        return

    # Usamos c (close) y t_close como timestamp de barra.
    df = df.sort("t_close")
    if not {"t_close","c","h","l"}.issubset(set(df.columns)):
        raise ValueError(f"Faltan columnas minimas en {in_file}")

    # Retornos y vol
    df = df.with_columns(pl.col("c").log().diff().alias("r"))
    # Estimador de vol:
    if vol_est == "ema":
        vol = ema(df["r"].abs().fill_null(0), vol_window).fill_null(strategy="forward")
    else:
        vol = df["r"].abs().rolling_mean(vol_window, min_periods=1)
    df = df.with_columns(pl.Series(name="vol", values=vol).fill_null(0.0))

    rows = df.to_dicts()
    labels = []

    n = len(rows)
    for i in range(n):
        anchor_ts = rows[i]["t_close"]
        px0 = rows[i]["c"]
        vol0 = max(1e-8, rows[i]["vol"])
        pt = px0 * (1 + pt_mul * vol0)   # aproximación: usa σ de retornos log como magnitud
        sl = px0 * (1 - sl_mul * vol0)

        j_last = min(n-1, i + t1_bars)
        pt_hit = False
        sl_hit = False
        ret_out = 0.0
        t1 = rows[j_last]["t_close"]

        for j in range(i+1, j_last+1):
            high = rows[j]["h"]; low = rows[j]["l"]; close = rows[j]["c"]
            if high >= pt:
                pt_hit = True; t1 = rows[j]["t_close"]; ret_out = (close/px0 - 1.0); break
            if low <= sl:
                sl_hit = True; t1 = rows[j]["t_close"]; ret_out = (close/px0 - 1.0); break

        if not pt_hit and not sl_hit:
            # vertical barrier
            close = rows[j_last]["c"]; ret_out = (close/px0 - 1.0)

        label = 1 if pt_hit and not sl_hit else (-1 if sl_hit and not pt_hit else 0)
        labels.append({
            "anchor_ts": anchor_ts,
            "t1": t1,
            "pt_hit": pt_hit,
            "sl_hit": sl_hit,
            "label": label,
            "ret_at_outcome": ret_out,
            "vol_at_anchor": float(vol0),
        })

    out_file.parent.mkdir(parents=True, exist_ok=True)
    pl.from_dicts(labels).write_parquet(out_file, compression="zstd", compression_level=2)

def worker(task):
    ticker, day, fpath, outdir, pt, sl, t1, vol_est, vol_win, resume = task
    out = outdir / ticker / f"date={day}" / "labels.parquet"
    if resume and out.exists(): return f"{ticker} {day}: SKIP"
    try:
        label_day(fpath, out, pt, sl, t1, vol_est, vol_win); return f"{ticker} {day}: OK"
    except Exception as e:
        return f"{ticker} {day}: ERROR {e}"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bars-root", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--pt-mul", type=float, default=3.0)
    ap.add_argument("--sl-mul", type=float, default=2.0)
    ap.add_argument("--t1-bars", type=int, default=120)
    ap.add_argument("--vol-est", choices=["ema","sma"], default="ema")
    ap.add_argument("--vol-window", type=int, default=50)
    ap.add_argument("--parallel", type=int, default=8)
    ap.add_argument("--resume", action="store_true")
    args = ap.parse_args()

    bars_root = Path(args.bars_root)
    outdir = Path(args.outdir)
    tasks = []
    for ticker, day, f in list_bar_files(bars_root):
        tasks.append((ticker, day, f, outdir, args.pt_mul, args.sl_mul,
                      args.t1_bars, args.vol_est, args.vol_window, args.resume))

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
