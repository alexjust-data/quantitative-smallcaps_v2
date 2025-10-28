#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
build_bars_from_trades.py
Crea barras informacionales (Dollar/Volume Imbalance Bars) a partir de trades v3.
Entrada:
  raw/polygon/trades/{ticker}/date=YYYY-MM-DD/trades.parquet  (cols: t,p,s[,c])
Salida:
  processed/bars/{ticker}/date=YYYY-MM-DD/{bar_type}.parquet
Uso:
  python scripts/fase_D_barras/build_bars_from_trades.py \
    --trades-root raw/polygon/trades \
    --outdir processed/bars \
    --bar-type dollar_imbalance --target-usd 300000 \
    --ema-window 50 --parallel 8 --resume
"""
import os, sys, argparse, time
from pathlib import Path
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed
import polars as pl

def log(msg): print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)

def list_day_paths(trades_root: Path):
    # Recorre raw/polygon/trades/*/date=*/trades.parquet
    for tdir in trades_root.iterdir():
        if not tdir.is_dir(): continue
        ticker = tdir.name
        for ddir in tdir.glob("date=*"):
            parquet = ddir / "trades.parquet"
            if parquet.exists():
                yield ticker, ddir.name.split("=",1)[1], parquet

def success_marker(path: Path): (path / "_SUCCESS").touch(exist_ok=True)
def has_success(path: Path) -> bool: return (path / "_SUCCESS").exists()

def build_bars_one_day(in_file: Path, out_dir: Path, bar_type: str,
                       target_usd: float, target_vol: int, ema_window: int):
    df = pl.read_parquet(in_file)
    if df.is_empty():
        out_dir.mkdir(parents=True, exist_ok=True)
        pl.DataFrame(schema={"t":pl.Datetime, "o":pl.Float64, "h":pl.Float64,
                             "l":pl.Float64, "c":pl.Float64, "v":pl.Int64,
                             "n":pl.Int64, "dollar":pl.Float64,
                             "imbalance_score":pl.Float64}).write_parquet(
            out_dir / f"{bar_type}.parquet", compression="zstd", compression_level=2, statistics=False
        )
        success_marker(out_dir); return

    # Orden temporal y columnas mínimas
    cols = df.columns
    need = set(["t","p","s"])
    if not need.issubset(cols):
        raise ValueError(f"Faltan columnas en {in_file}: {need - set(cols)}")

    # FIX: Convert timestamp from nanoseconds to microseconds if needed
    # Polygon API returns nanosecond timestamps, but they may be stored as microseconds in parquet
    # Check if timestamp values are too large (> year 3000 when interpreted as microseconds)
    t_sample = df["t"].head(1).cast(pl.Int64).item()
    if t_sample > 32503680000000000:  # Jan 1, 3000 in microseconds
        # Timestamps are in nanoseconds, convert to microseconds
        df = df.with_columns((pl.col("t").cast(pl.Int64) // 1000).cast(pl.Datetime(time_unit="us")).alias("t"))

    df = df.sort("t")

    # Tick-rule (signo por comparación con precio previo). +1 uptick, -1 downtick, 0 igual
    df = df.with_columns([
        (pl.col("p") - pl.col("p").shift(1)).alias("dp"),
        pl.when(pl.col("p") > pl.col("p").shift(1)).then(1)
          .when(pl.col("p") < pl.col("p").shift(1)).then(-1)
          .otherwise(0).alias("sign")
    ])
    # Dollar flow por trade
    df = df.with_columns((pl.col("p") * pl.col("s")).alias("d"))

    # Umbral de barra
    target = target_usd if bar_type.startswith("dollar") else float(target_vol)

    # Construcción incremental
    bars = []
    acc_vol = 0.0
    acc_dol = 0.0
    acc_n   = 0
    acc_imb = 0.0

    o = h = l = c = None
    t_open = t_close = None

    def flush_bar():
        nonlocal acc_vol, acc_dol, acc_n, acc_imb, o, h, l, c, t_open, t_close
        if acc_n == 0: return
        bars.append({
            "t_open": t_open, "t_close": t_close,
            "o": o, "h": h, "l": l, "c": c,
            "v": int(acc_vol), "n": acc_n,
            "dollar": acc_dol,
            "imbalance_score": acc_imb / max(1, acc_n)  # promedio de signo
        })
        acc_vol = acc_dol = 0.0
        acc_n = 0
        acc_imb = 0.0
        o = h = l = c = None
        t_open = t_close = None

    threshold = 0.0
    # EWMA simple del umbral objetivo para suavizar el ritmo de barras
    alpha = 2.0 / (ema_window + 1.0) if ema_window and ema_window > 1 else 1.0
    ewma = target

    for row in df.iter_rows(named=True):
        t, p, s, d, sign = row["t"], float(row["p"]), int(row["s"]), float(row["d"]), int(row["sign"])
        if o is None:
            o = h = l = c = p
            t_open = t
        else:
            h = max(h, p)
            l = min(l, p)
            c = p
        acc_vol += s
        acc_dol += d
        acc_n   += 1
        acc_imb += sign

        # actualiza umbral suavizado hacia target
        ewma = alpha * target + (1 - alpha) * ewma
        threshold = ewma

        metric = acc_dol if bar_type.startswith("dollar") else acc_vol
        if metric >= threshold:
            t_close = t
            flush_bar()

    # cierra resto
    if acc_n > 0:
        t_close = df.select(pl.col("t").last()).item()
        flush_bar()

    out_dir.mkdir(parents=True, exist_ok=True)
    pl.from_dicts(bars).write_parquet(out_dir / f"{bar_type}.parquet",
                                      compression="zstd", compression_level=2, statistics=False)
    success_marker(out_dir)

def worker(task):
    ticker, day, in_file, outdir, bar_type, target_usd, target_vol, ema_window, resume = task
    out_dir = outdir / ticker / f"date={day}"
    if resume and (out_dir / "_SUCCESS").exists():
        return f"{ticker} {day}: SKIP"
    try:
        build_bars_one_day(in_file, out_dir, bar_type, target_usd, target_vol, ema_window)
        return f"{ticker} {day}: OK"
    except Exception as e:
        return f"{ticker} {day}: ERROR {e}"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trades-root", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--bar-type", choices=["dollar_imbalance","volume_imbalance"], default="dollar_imbalance")
    ap.add_argument("--target-usd", type=float, default=300000.0)
    ap.add_argument("--target-vol", type=int, default=100000)
    ap.add_argument("--ema-window", type=int, default=50)
    ap.add_argument("--parallel", type=int, default=8)
    ap.add_argument("--resume", action="store_true")
    args = ap.parse_args()

    trades_root = Path(args.trades_root)
    outdir = Path(args.outdir)
    tasks = []
    for ticker, day, parquet in list_day_paths(trades_root):
        tasks.append((ticker, day, parquet, outdir, args.bar_type,
                      args.target_usd, args.target_vol, args.ema_window, args.resume))
    log(f"Tareas: {len(tasks):,} | paralelismo={args.parallel} | tipo={args.bar_type}")
    t0 = time.time()
    done = 0
    with ProcessPoolExecutor(max_workers=args.parallel) as ex:
        futs = [ex.submit(worker, t) for t in tasks]
        for f in as_completed(futs):
            msg = f.result()
            done += 1
            if done % 200 == 0: log(f"Progreso: {done}/{len(tasks)}")
            if "ERROR" in msg: log(msg)
    log(f"FIN en {(time.time()-t0)/60:.1f} min")

if __name__ == "__main__":
    from concurrent.futures import ProcessPoolExecutor, as_completed
    main()
