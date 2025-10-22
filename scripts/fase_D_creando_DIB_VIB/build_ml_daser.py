#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
build_ml_daser.py
Crea dataset de ML uniendo barras informacionales (DIB/VIB) + labels (Triple Barrier) + sample weights.
Genera features intradía sencillas desde barras, ensambla dataset diario y global, y hace split walk-forward
con purged gap.

Entradas esperadas (ya generadas en tu Fase D):
  processed/bars/{ticker}/date=YYYY-MM-DD/dollar_imbalance.parquet
  processed/labels/{ticker}/date=YYYY-MM-DD/labels.parquet
  processed/weights/{ticker}/date=YYYY-MM-DD/weights.parquet

Salidas:
  processed/datasets/daily/{ticker}/date=YYYY-MM-DD/dataset.parquet
  processed/datasets/global/dataset.parquet
  processed/datasets/splits/train.parquet
  processed/datasets/splits/valid.parquet
  processed/datasets/meta.json

Uso típico:
  python scripts/fase_H_dataset/build_ml_daser.py \
    --bars-root processed/bars \
    --labels-root processed/labels \
    --weights-root processed/weights \
    --outdir processed/datasets \
    --bar-file dollar_imbalance.parquet \
    --parallel 8 --resume \
    --split walk_forward --folds 5 --purge-bars 50
"""
import argparse, json, math, os, sys, time
from pathlib import Path
from datetime import datetime
from typing import List, Tuple
from concurrent.futures import ProcessPoolExecutor, as_completed
import polars as pl

def log(m): print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {m}", flush=True)

# --------------------------
# Utils para listar archivos
# --------------------------
def list_label_days(labels_root: Path) -> List[Tuple[str, str, Path]]:
    tasks = []
    for tdir in labels_root.iterdir():
        if not tdir.is_dir(): continue
        tkr = tdir.name
        for ddir in tdir.glob("date=*"):
            day = ddir.name.split("=",1)[1]
            f = ddir / "labels.parquet"
            if f.exists(): tasks.append((tkr, day, f))
    return tasks

def expected_paths(bars_root: Path, weights_root: Path, ticker: str, day: str, bar_file: str):
    bar_path    = bars_root / ticker / f"date={day}" / bar_file
    weight_path = weights_root / ticker / f"date={day}" / "weights.parquet"
    return bar_path, weight_path

# --------------------------
# Feature engineering simple
# --------------------------
def make_features_from_bars(bars: pl.DataFrame) -> pl.DataFrame:
    """
    Entrada barras: t_open,t_close,o,h,l,c,v,n,dollar,imbalance_score
    Devuelve un DF indexado por t_close con features rodantes sencillas.
    """
    df = bars.sort("t_close")
    # returns / rangos
    df = df.with_columns([
        pl.col("c").log().diff().alias("ret_1"),
        ((pl.col("h") - pl.col("l")) / (pl.col("c").shift(1).abs() + 1e-12)).alias("range_norm"),
        pl.col("v").cast(pl.Float64).alias("vol_f"),
        pl.col("dollar").alias("dollar_f"),
        pl.col("imbalance_score").alias("imb_f"),
    ])
    # EMA manual (rápida) para pocas col.
    def ema(series: pl.Series, span: int):
        if span <= 1: return series
        a = 2.0/(span+1.0); out=[]; v=None
        for x in series:
            if v is None: v = float(x) if x is not None else 0.0
            else: v = a*float(x if x is not None else 0.0) + (1-a)*v
            out.append(v)
        return pl.Series(out)

    # Ventanas típicas (ajustables)
    for col, span in [("ret_1", 10), ("ret_1", 30), ("range_norm", 20),
                      ("vol_f", 20), ("dollar_f", 20), ("imb_f", 20)]:
        name = f"{col}_ema{span}"
        df = df.with_columns(pl.Series(name=name, values=ema(df[col].fill_null(0), span)))

    # Z-scores simples (contra EMA y desvío rolling)
    df = df.with_columns([
        pl.when(pl.col("vol_f").rolling_std(20).fill_null(0) > 0)
          .then( (pl.col("vol_f") - pl.col("vol_f").rolling_mean(20).fill_null(0)) / (pl.col("vol_f").rolling_std(20)+1e-12) )
          .otherwise(0.0).alias("vol_z20"),
        pl.when(pl.col("dollar_f").rolling_std(20).fill_null(0) > 0)
          .then( (pl.col("dollar_f") - pl.col("dollar_f").rolling_mean(20).fill_null(0)) / (pl.col("dollar_f").rolling_std(20)+1e-12) )
          .otherwise(0.0).alias("dollar_z20"),
    ])
    # Selección de columnas de features
    keep = [
        "t_close","c","ret_1","range_norm","vol_f","dollar_f","imb_f",
        "ret_1_ema10","ret_1_ema30","range_norm_ema20",
        "vol_f_ema20","dollar_f_ema20","imb_f_ema20",
        "vol_z20","dollar_z20","n"
    ]
    return df.select([k for k in keep if k in df.columns])

# --------------------------
# Ensamblado día (ticker,day)
# --------------------------
def build_day_dataset(bars_path: Path, labels_path: Path, weights_path: Path) -> pl.DataFrame:
    bars = pl.read_parquet(bars_path)
    labels = pl.read_parquet(labels_path)
    if bars.is_empty() or labels.is_empty():
        return pl.DataFrame()

    feats = make_features_from_bars(bars)
    # Join labels ↔ barras por timestamp: anchor_ts == t_close
    # (Tus labels fueron ancladas en t_close de la barra)
    df = labels.join(feats, left_on="anchor_ts", right_on="t_close", how="inner")

    # Añade pesos si existen
    if weights_path.exists():
        w = pl.read_parquet(weights_path)
        if not w.is_empty():
            df = df.join(w, on="anchor_ts", how="left")
    if "weight" not in df.columns:
        df = df.with_columns(pl.lit(1.0).alias("weight"))

    # Limpieza mínima
    # Quita NaNs infinitos en features
    clean_cols = [c for c in df.columns if c not in ("anchor_ts","t1","pt_hit","sl_hit","label","weight","t_close")]
    df = df.with_columns([pl.col(c).fill_nan(0).fill_null(0) for c in clean_cols])

    # Orden por tiempo
    df = df.sort("anchor_ts")

    return df

def worker(task):
    ticker, day, bar_path, label_path, weight_path, daily_outdir, bar_file, resume = task
    out = daily_outdir / ticker / f"date={day}" / "dataset.parquet"
    if resume and out.exists(): return f"{ticker} {day}: SKIP"
    try:
        ds = build_day_dataset(bar_path, label_path, weight_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        if ds.is_empty():
            pl.DataFrame(schema={"anchor_ts":pl.Datetime,"label":pl.Int8,"weight":pl.Float64}).write_parquet(out)
        else:
            ds.write_parquet(out, compression="zstd", compression_level=2)
        return f"{ticker} {day}: OK"
    except Exception as e:
        return f"{ticker} {day}: ERROR {e}"

# --------------------------
# Agregado global + splits
# --------------------------
def concat_daily_to_global(daily_root: Path, out_path: Path) -> Tuple[int,int]:
    files = []
    for tdir in daily_root.iterdir():
        if not tdir.is_dir(): continue
        for ddir in tdir.glob("date=*"):
            f = ddir / "dataset.parquet"
            if f.exists(): files.append(f)
    if not files:
        pl.DataFrame().write_parquet(out_path)
        return 0, 0
    dfs = [pl.read_parquet(f) for f in files]
    df = pl.concat(dfs, how="vertical_relaxed")
    # Campos mínimos asegurados
    base_cols = ["anchor_ts","label","weight"]
    for c in base_cols:
        if c not in df.columns:
            df = df.with_columns(pl.lit(None).alias(c))
    # Sanity: quitar nulos extremos en label/weight
    df = df.with_columns([
        pl.col("label").cast(pl.Int8).fill_null(0),
        pl.col("weight").cast(pl.Float64).fill_null(1.0)
    ])
    df = df.sort("anchor_ts")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(out_path, compression="zstd", compression_level=2)
    return len(files), df.height

def walk_forward_split(df: pl.DataFrame, folds: int, purge_bars: int) -> Tuple[pl.DataFrame, pl.DataFrame]:
    """
    Split por tiempo: divide el timeline total en 'folds' segmentos.
    Usa folds-1 para entrenamiento y el último segmento como validación,
    con 'purge_bars' de hueco entre train y valid para evitar leakage.
    """
    if df.is_empty(): return df, df
    df = df.sort("anchor_ts")
    n = df.height
    # índices de corte uniformes
    idx = [0]
    for k in range(1, folds):
        idx.append(int(n * k / folds))
    idx.append(n)
    # Train = [0 : idx[-2]-purge), Valid = [idx[-2] : n)
    train_end = max(idx[-2] - purge_bars, 0)
    train = df.slice(0, train_end)
    valid = df.slice(idx[-2], n - idx[-2])
    return train, valid

# --------------------------
# main
# --------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bars-root", required=True)
    ap.add_argument("--labels-root", required=True)
    ap.add_argument("--weights-root", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--bar-file", default="dollar_imbalance.parquet",
                    help="Nombre del parquet de barras dentro de cada date=YYYY-MM-DD/")
    ap.add_argument("--parallel", type=int, default=8)
    ap.add_argument("--resume", action="store_true")

    # Split
    ap.add_argument("--split", choices=["none","walk_forward"], default="walk_forward")
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--purge-bars", type=int, default=50)

    args = ap.parse_args()

    bars_root    = Path(args.bars_root)
    labels_root  = Path(args.labels_root)
    weights_root = Path(args.weights_root)
    outdir       = Path(args.outdir)

    daily_outdir  = outdir / "daily"
    global_outdir = outdir / "global"
    splits_outdir = outdir / "splits"
    meta_path     = outdir / "meta.json"

    # Tareas: derivadas de labels (es el driver)
    tasks = []
    label_days = list_label_days(labels_root)
    for (tkr, day, labels_path) in label_days:
        bar_path, weight_path = expected_paths(bars_root, weights_root, tkr, day, args.bar_file)
        if not bar_path.exists():
            # si faltan barras, saltar
            continue
        tasks.append((tkr, day, bar_path, labels_path, weight_path, daily_outdir, args.bar_file, args.resume))

    log(f"Tareas diarias: {len(tasks):,} | paralelismo={args.parallel}")
    t0 = time.time()
    done=0; err=0
    with ProcessPoolExecutor(max_workers=args.parallel) as ex:
        futs = [ex.submit(worker, t) for t in tasks]
        for f in as_completed(futs):
            msg = f.result(); done += 1
            if "ERROR" in msg: err += 1; log(msg)
            if done % 200 == 0: log(f"Progreso: {done}/{len(tasks)}")

    log(f"Daily datasets OK: {done-err}, errores: {err}. Tiempo {(time.time()-t0)/60:.1f} min")

    # Concatenar a global
    global_path = global_outdir / "dataset.parquet"
    files_cnt, rows_cnt = concat_daily_to_global(daily_outdir, global_path)
    log(f"Global dataset: archivos={files_cnt}, filas={rows_cnt} -> {global_path}")

    # Splits
    train_rows = valid_rows = 0
    if args.split == "walk_forward":
        df = pl.read_parquet(global_path)
        train, valid = walk_forward_split(df, args.folds, args.purge_bars)
        splits_outdir.mkdir(parents=True, exist_ok=True)
        train.write_parquet(splits_outdir / "train.parquet", compression="zstd", compression_level=2)
        valid.write_parquet(splits_outdir / "valid.parquet", compression="zstd", compression_level=2)
        train_rows, valid_rows = train.height, valid.height
        log(f"Split walk-forward: folds={args.folds}, purge={args.purge_bars} -> "
            f"train={train_rows}, valid={valid_rows}")

    # Meta
    meta = {
        "created_at": datetime.utcnow().isoformat(),
        "bars_root": str(bars_root),
        "labels_root": str(labels_root),
        "weights_root": str(weights_root),
        "outdir": str(outdir),
        "bar_file": args.bar_file,
        "tasks": len(tasks),
        "daily_files": files_cnt,
        "global_rows": rows_cnt,
        "split": args.split,
        "folds": args.folds,
        "purge_bars": args.purge_bars,
        "train_rows": train_rows,
        "valid_rows": valid_rows,
        "feature_columns_example": [
            "ret_1","range_norm","vol_f","dollar_f","imb_f",
            "ret_1_ema10","ret_1_ema30","range_norm_ema20",
            "vol_f_ema20","dollar_f_ema20","imb_f_ema20",
            "vol_z20","dollar_z20","n"
        ],
        "label_column": "label",
        "weight_column": "weight",
        "time_index": "anchor_ts"
    }
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(meta, indent=2))
    log(f"Meta escrito en {meta_path}")

if __name__ == "__main__":
    main()
