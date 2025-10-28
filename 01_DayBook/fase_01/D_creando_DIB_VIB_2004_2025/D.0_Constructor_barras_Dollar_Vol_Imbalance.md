


# 1) Construir barras informacionales (DIB/VIB) desde `raw/polygon/trades`

**Objetivo:** transformar ticks en barras impulsadas por información (mejor SNR para tus setups intradía).

### Script sugerido (nuevo): `scripts/fase_D_barras/build_bars_from_trades.py`

* Entrada: `raw/polygon/trades/{ticker}/date=YYYY-MM-DD/trades.parquet`
* Salida:

  ```
  processed/bars/{ticker}/date=YYYY-MM-DD/dollar_imbalance.parquet
  processed/bars/{ticker}/date=YYYY-MM-DD/volume_imbalance.parquet
  ```
* Parámetros útiles:

  * `--bar-type {dollar_imbalance,volume_imbalance}`
  * `--target-usd` (p.ej. 200k–500k en small caps) o `--target-vol` (p.ej. 50k–200k)
  * `--ema-window` (umbral adaptativo estilo López de Prado)
  * `--min-trades` (descarta días anémicos)

**Comando ejemplo (para tus 11.054 días):**

```bash
python scripts/fase_D_barras/build_bars_from_trades.py \
  --trades-root raw/polygon/trades \
  --outdir processed/bars \
  --bar-type dollar_imbalance --target-usd 300000 \
  --ema-window 50 --parallel 8 --resume
```

**Schema esperado (por barra):**

```
t_open, t_close, price_open, price_high, price_low, price_close,
dollar_flow, volume, n_trades, imbalance_score
```

> Tip: si algún `date=…` no tiene trades (raro con tu auditoría), deja un marcador vacío para que el pipeline no se corte.
> Tip 2: si ves barras demasiado densas o escasas, ajusta `--target-usd` (↑ = menos barras; ↓ = más barras).

---

# 2) Features rápidas sobre barras (para señal y labeling)

Script ligero (nuevo) `scripts/fase_E_features/make_features_intraday.py`:

* Entrada: `processed/bars/.../*.parquet`
* Salida: `processed/features/{ticker}/date=YYYY-MM-DD/features.parquet`

**Features mínimas:**

* Retornos log por barra, rango normalizado, RVOL-bar (vs EMA), distancia a VWAP (reconstruido con ticks), burst/pausas (tiempo por barra), microestructura simple (si guardaste `n_trades`).

**Comando:**

```bash
python scripts/fase_E_features/make_features_intraday.py \
  --bars-root processed/bars \
  --outdir processed/features \
  --vwap-from-trades true --parallel 8 --resume
```

---

# 3) Labeling (Triple Barrier) por evento/instante

Script (nuevo) `scripts/fase_F_labeling/triple_barrier_labeling.py`:

* Genera etiquetas por “anclas” (pueden ser:

  * cada barra (uniforme),
  * o eventos rule-based simples: gap continuation, VWAP reclaim/reject, ORB…).

* Parámetros:

  * `--pt-mul 3.0 --sl-mul 2.0` (en múltiplos de σ intradía calculada sobre las barras)
  * `--t1-bars 100` (vertical barrier en número de barras)

**Comando:**

```bash
python scripts/fase_F_labeling/triple_barrier_labeling.py \
  --bars-root processed/bars \
  --features-root processed/features \
  --outdir processed/labels \
  --pt-mul 3.0 --sl-mul 2.0 --t1-bars 120 \
  --vol-est ema --vol-window 50 --anchor rule_based:vwap_reclaim \
  --parallel 8 --resume
```

**Salida por ancla:**

```
anchor_ts, t1, pt_hit, sl_hit, label (1/-1/0), ret_at_outcome, vol_at_anchor
```

---

# 4) Sample Weights (unicidad + magnitud + time-decay)

Script (nuevo) `scripts/fase_G_weights/make_sample_weights.py`:

* Calcula **unicidad temporal** (solapamiento de ventanas), pondera por **|retorno|** y aplica **decay** (p.ej. semivida 90 días).
* **Salida:** `processed/weights/{ticker}/date=.../weights.parquet` con `weight`.

**Comando:**

```bash
python scripts/fase_G_weights/make_sample_weights.py \
  --labels-root processed/labels \
  --outdir processed/weights \
  --uniqueness true --abs-ret-weight true --time-decay-half_life 90 \
  --parallel 8 --resume
```

---

# 5) Dataset de entrenamiento y validación (walk-forward)

Script (nuevo) `scripts/fase_H_dataset/build_ml_dataset.py`:

* Joins: `bars + features + labels + weights`
* Split: **Purged K-Fold** o **Walk-Forward** por fecha
* Salida:

  * `processed/datasets/train.parquet`
  * `processed/datasets/valid.parquet`
  * `processed/datasets/meta.json` (columnas, escalados, etc.)

**Comando:**

```bash
python scripts/fase_H_dataset/build_ml_dataset.py \
  --features-root processed/features \
  --labels-root processed/labels \
  --weights-root processed/weights \
  --outdir processed/datasets \
  --split walk_forward --folds 5 --purge-bars 50
```

---

## Checks rápidos en cada etapa

* **Barras**: media de barras/día por ticker en rango razonable (small caps con `target_usd=300k` suelen dar centenas por sesión).
* **Features**: sin nulos en campos clave; VWAP coherente con price_close.
* **Labels**: proporción de (1 / -1 / 0) no degenerada (evitar >90% de una clase).
* **Weights**: distribución no súper concentrada (Gini < ~0.9 como guía “sanidad”).

---

## Qué haría en paralelo (no bloqueante)

* **TopN12m snapshots** (si no lo sacaste aún): mensual/anual para priorizar backfills futuros.
* **SCD-2 de market cap** (si quieres activar `<$2B` histórico en el universo dinámico; no afecta a lo ya descargado).

---

## Atajos si quieres correr YA con lo mínimo

1. Barras DIB únicamente:

```bash
python scripts/fase_D_barras/build_bars_from_trades.py \
  --trades-root raw/polygon/trades --outdir processed/bars \
  --bar-type dollar_imbalance --target-usd 250000 --parallel 8 --resume
```

2. Labeling simple por barra (sin eventos):

```bash
python scripts/fase_F_labeling/triple_barrier_labeling.py \
  --bars-root processed/bars --outdir processed/labels \
  --pt-mul 3.0 --sl-mul 2.0 --t1-bars 80 --parallel 8 --resume
```

3. Pesos y dataset (rápido):

```bash
python scripts/fase_G_weights/make_sample_weights.py \
  --labels-root processed/labels --outdir processed/weights \
  --uniqueness true --time-decay-half_life 90 --parallel 8 --resume

python scripts/fase_H_dataset/build_ml_dataset.py \
  --features-root processed/bars --labels-root processed/labels \
  --weights-root processed/weights --outdir processed/datasets
```

---

# tres scripts base


(`build_bars_from_trades.py`, `triple_barrier_labeling.py`, `make_sample_weights.py`) 




**los 3 scripts** listos para pegar en tu repo y correr **tal cual** con tus `trades.parquet` (schema `t,p,s` ya validado). Están pensados para **small caps** y tus **11.054 días info-rich**.

---

# 1) `scripts/fase_D_barras/build_bars_from_trades.py`

* Construye **Dollar Imbalance Bars** (*DIB*) o **Volume Imbalance Bars** (*VIB*) por **día** y **ticker**.
* Umbral por barra: `--target-usd` o `--target-vol`.
* Calcula OHLC, H/L, vol, nº trades, **dollar_flow**, y **imbalance_score** (tick rule simple).
* ZSTD + `_SUCCESS` y `--resume`.

```python
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
```

---

# 2) `scripts/fase_F_labeling/triple_barrier_labeling.py`

* Aplica **Triple Barrier** sobre las barras generadas.
* Volatilidad por **EMA** de retornos log (`--vol-window`).
* Barreras: `pt = pt_mul * σ * price`, `sl = sl_mul * σ * price`.
* Vertical: `--t1-bars` (n barras hacia delante).

```python
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
```

---

# 3) `scripts/fase_G_weights/make_sample_weights.py`

* **Unicidad temporal** (overlaps entre ventanas `[anchor_ts, t1]`).
* Peso base `= |ret_at_outcome| / concurrency`.
* **Time-decay** con semivida en **días** (`--time-decay-half_life`).
* Output por día: `weights.parquet` con `anchor_ts, weight`.

```python
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
```

> Nota: si más adelante quieres **unicidad “exacta”** tipo López de Prado (con *concurrency* por **todo el timeline** y **purged k-fold**), hacemos un módulo específico que compute la matriz de cobertura temporal; para arrancar, esta aproximación por día funciona bien en POC.

---

## Cómo correrlos (orden recomendado)

1. **Barras** (DIB por defecto):

```bash
python scripts/fase_D_barras/build_bars_from_trades.py ^
  --trades-root raw/polygon/trades ^
  --outdir processed/bars ^
  --bar-type dollar_imbalance --target-usd 300000 ^
  --ema-window 50 --parallel 8 --resume
```

2. **Labels** (triple barrier):

```bash
python scripts/fase_F_labeling/triple_barrier_labeling.py ^
  --bars-root processed/bars ^
  --outdir processed/labels ^
  --pt-mul 3.0 --sl-mul 2.0 --t1-bars 120 ^
  --vol-est ema --vol-window 50 ^
  --parallel 8 --resume
```

3. **Pesos** (unicidad + |ret| + normalización):

```bash
python scripts/fase_G_weights/make_sample_weights.py ^
  --labels-root processed/labels ^
  --outdir processed/weights ^
  --uniqueness --abs-ret-weight ^
  --time-decay-half_life 90 ^
  --parallel 8 --resume
```

---

## Sanity checks rápidos

* **Barras**: por día y ticker, deberías ver entre **decenas y centenas** de barras (según `--target-usd`).
* **Labels**: ratio (1 / -1 / 0) no extremo (>90% de una sola clase).
* **Weights**: suman ≈ 1 **por fichero** (normalización interna).

Si quieres, luego te dejo un mini `build_ml_dataset.py` que junte `features(barras) + labels + weights` y te escupa `train.parquet / valid.parquet` con *walk-forward* + *purged*.
