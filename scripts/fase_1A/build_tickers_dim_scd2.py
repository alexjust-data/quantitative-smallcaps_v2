#!/usr/bin/env python
# build_tickers_dim_scd2.py
import argparse, datetime as dt
from pathlib import Path
import polars as pl

KEY_COLS = ["ticker"]  # business key
TRACK_COLS = [
  "name","primary_exchange","active","market","locale","type",
  "currency_name","composite_figi","share_class_figi"
]

def log(m): print(f"[{dt.datetime.now():%F %T}] {m}", flush=True)

def load_snapshot(snapdir: Path) -> pl.DataFrame:
    df = pl.read_parquet(snapdir / "tickers.parquet")
    # aseguramos que las columnas existen
    for c in TRACK_COLS:
        if c not in df.columns: df = df.with_columns(pl.lit(None).alias(c))
    return df

def initial_dim(snapshot: pl.DataFrame) -> pl.DataFrame:
    snap_date = snapshot["snapshot_date"][0]
    return (snapshot
        .select(KEY_COLS + TRACK_COLS + ["snapshot_date"])
        .with_columns([
            pl.col("snapshot_date").alias("effective_from"),
            pl.lit(None, dtype=pl.Utf8).alias("effective_to")
        ])
        .drop("snapshot_date")
    )

def scd2_merge(dim: pl.DataFrame, prev_snap: pl.DataFrame, curr_snap: pl.DataFrame) -> pl.DataFrame:
    # join prev vs curr por KEY_COLS
    on = KEY_COLS
    prev = prev_snap.select(KEY_COLS + TRACK_COLS + ["snapshot_date"]).rename({c:f"prev_{c}" for c in TRACK_COLS+["snapshot_date"]})
    curr = curr_snap.select(KEY_COLS + TRACK_COLS + ["snapshot_date"]).rename({c:f"curr_{c}" for c in TRACK_COLS+["snapshot_date"]})
    j = prev.join(curr, on=on, how="outer")

    # filas que nacen en curr pero no estaban en prev → nuevas altas
    new_mask = j["prev_name"].is_null() & j["curr_name"].is_not_null()
    new_rows = (j.filter(new_mask)
                  .select(on + [f"curr_{c}" for c in TRACK_COLS] + ["curr_snapshot_date"])
                  .rename({f"curr_{c}": c for c in TRACK_COLS} | {"curr_snapshot_date":"effective_from"})
                  .with_columns(pl.lit(None, dtype=pl.Utf8).alias("effective_to")))

    # filas que estaban en prev y cambian en curr → cerrar antiguo y abrir nuevo
    change_mask = (~j["prev_name"].is_null()) & (~j["curr_name"].is_not_null())
    changed = j.filter(change_mask)

    # registros con cambio en TRACK_COLS
    changed = changed.with_columns(
        pl.any_horizontal([pl.col(f"prev_{c}") != pl.col(f"curr_{c}") for c in TRACK_COLS]).alias("changed")
    )

    # cerrar antiguos
    to_close = (changed.filter(pl.col("changed"))
                .select(on + ["prev_snapshot_date"])
                .rename({"prev_snapshot_date":"effective_to"}))

    # abrir nuevos
    to_open = (changed.filter(pl.col("changed"))
               .select(on + [f"curr_{c}" for c in TRACK_COLS] + ["curr_snapshot_date"])
               .rename({f"curr_{c}": c for c in TRACK_COLS} | {"curr_snapshot_date":"effective_from"})
               .with_columns(pl.lit(None, dtype=pl.Utf8).alias("effective_to")))

    # aplicar cierre a dim existente (match por key y effective_to is null)
    if to_close.height:
        dim_open = dim.filter(pl.col("effective_to").is_null())
        dim_closed = dim.filter(pl.col("effective_to").is_not_null())
        dim_open = dim_open.join(to_close, on=on, how="left")
        dim_open = dim_open.with_columns(
            pl.when(pl.col("effective_to").is_null() & pl.col("effective_to_right").is_not_null())
              .then(pl.col("effective_to_right"))
              .otherwise(pl.col("effective_to")).alias("effective_to")
        ).drop("effective_to_right")
        dim = pl.concat([dim_closed, dim_open], how="vertical_relaxed")

    # añadir nuevos y nuevas altas
    additions = pl.concat([to_open, new_rows], how="vertical_relaxed") if (to_open.height or new_rows.height) else None
    if additions is not None and additions.height:
        dim = pl.concat([dim, additions], how="vertical_relaxed")

    return dim.sort(on + ["effective_from"])

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dimdir", required=True, help="Salida: processed/ref/tickers_dim")
    ap.add_argument("--prev-snapshot", required=False, help="raw/polygon/reference/tickers_snapshot/snapshot_date=YYYY-MM-DD (opcional la 1ª vez)")
    ap.add_argument("--curr-snapshot", required=True, help="raw/polygon/reference/tickers_snapshot/snapshot_date=YYYY-MM-DD")
    args = ap.parse_args()

    dimdir = Path(args.dimdir); dimdir.mkdir(parents=True, exist_ok=True)

    curr = load_snapshot(Path(args.curr_snapshot))
    if args.prev_snapshot:
        prev = load_snapshot(Path(args.prev_snapshot))
        # cargar dim si existe; si no, iníciala con prev
        dim_path = dimdir / "tickers_dim.parquet"
        if dim_path.exists():
            dim = pl.read_parquet(dim_path)
        else:
            dim = initial_dim(prev)
        dim = scd2_merge(dim, prev, curr)
    else:
        dim = initial_dim(curr)

    out = dimdir / "tickers_dim.parquet"
    dim.write_parquet(out)
    log(f"Escrito: {out} ({dim.height:,} filas)")

if __name__ == "__main__":
    from pathlib import Path
    main()
