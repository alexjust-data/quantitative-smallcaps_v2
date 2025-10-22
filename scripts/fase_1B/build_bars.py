#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
build_bars.py
Constructor de barras avanzadas desde trades tick-level.

Tipos de barras implementadas:
- DB (Dollar Bars): Cierra barra cuando se acumula X dólares
- VB (Volume Bars): Cierra barra cuando se acumula X volumen
- DIB (Dollar Imbalance Bars): Cierra por desequilibrio de dólares (López de Prado)
- VIB (Volume Imbalance Bars): Cierra por desequilibrio de volumen

Fallback: Si no hay trades disponibles, puede usar 1m aggregates como aproximación.

Uso:
    # Dollar Bars con target 50k USD
    python build_bars.py \
        --trades-root raw/polygon/trades \
        --ticker GPRO \
        --from 2024-01-01 --to 2024-12-31 \
        --outdir processed/bars \
        --mode DB --target 50000

    # Dollar Imbalance Bars con EWMA alpha=0.2
    python build_bars.py \
        --trades-root raw/polygon/trades \
        --ticker GPRO \
        --from 2024-01-01 --to 2024-12-31 \
        --outdir processed/bars \
        --mode DIB --target 50000 --alpha 0.2

    # Fallback desde 1m aggregates
    python build_bars.py \
        --agg1m-root raw/polygon/ohlcv_intraday_1m \
        --ticker GPRO \
        --from 2024-01-01 --to 2024-12-31 \
        --outdir processed/bars \
        --mode VB --target 100000
"""
import argparse
import datetime as dt
from pathlib import Path
from typing import Literal, Optional, List, Tuple

import polars as pl
import numpy as np

def log(m):
    print(f"[{dt.datetime.now():%Y-%m-%d %H:%M:%S}] {m}", flush=True)

# ========== Helpers ==========

def compute_sign(ret: np.ndarray) -> np.ndarray:
    """Computa signo del retorno: +1 (up), -1 (down), 0 (flat)"""
    return np.sign(ret)

def ewma(x: np.ndarray, alpha: float) -> np.ndarray:
    """EWMA (Exponentially Weighted Moving Average) manual"""
    out = np.empty_like(x, dtype=float)
    w = 0.0
    for i, v in enumerate(x):
        if i == 0:
            w = v
        else:
            w = alpha * v + (1 - alpha) * w
        out[i] = w
    return out

# ========== Core: Bar Construction ==========

def build_dollar_bars(trades: pl.DataFrame, bar_usd_target: float) -> pl.DataFrame:
    """
    Dollar Bars: Cierra barra cuando se acumula bar_usd_target dólares.

    Args:
        trades: DataFrame con columnas ['sip_ts', 'price', 'size'] ordenado por sip_ts
        bar_usd_target: USD objetivo por barra (ej: 50,000)

    Returns:
        DataFrame con barras OHLCV
    """
    if trades.height == 0:
        return pl.DataFrame({
            "t": [], "open": [], "high": [], "low": [],
            "close": [], "v": [], "dollar": []
        })

    df = trades.select([
        pl.col("sip_ts").alias("t"),
        pl.col("price").alias("p"),
        pl.col("size").alias("q"),
        (pl.col("price") * pl.col("size")).alias("pq")  # dólares por trade
    ]).sort("t")

    # Acumular hasta exceder target -> nueva barra
    cuts: List[Tuple[int, int]] = []
    acc_d = 0.0
    last_idx = 0
    t_dict = df.to_dict(as_series=False)

    for i in range(len(t_dict["pq"])):
        acc_d += float(t_dict["pq"][i])
        if acc_d >= bar_usd_target:
            cuts.append((last_idx, i))
            last_idx = i + 1
            acc_d = 0.0

    # Cola (último fragmento)
    if last_idx < len(t_dict["pq"]):
        cuts.append((last_idx, len(t_dict["pq"]) - 1))

    # Construir barras OHLCV
    bars = []
    for (a, b) in cuts:
        if a > b:
            continue
        seg = df.slice(a, b - a + 1)
        open_ = seg["p"][0]
        close = seg["p"][-1]
        high = seg["p"].max()
        low = seg["p"].min()
        vol = seg["q"].sum()
        dollar = seg["pq"].sum()
        ts = int(seg["t"][0])  # timestamp apertura barra
        bars.append((ts, float(open_), float(high), float(low),
                    float(close), float(vol), float(dollar)))

    return pl.DataFrame(bars, schema=["t", "open", "high", "low", "close", "v", "dollar"])

def build_volume_bars(trades: pl.DataFrame, bar_vol_target: float) -> pl.DataFrame:
    """
    Volume Bars: Cierra barra cuando se acumula bar_vol_target volumen.

    Args:
        trades: DataFrame con columnas ['sip_ts', 'price', 'size']
        bar_vol_target: Volumen objetivo por barra

    Returns:
        DataFrame con barras OHLCV
    """
    if trades.height == 0:
        return pl.DataFrame({
            "t": [], "open": [], "high": [], "low": [],
            "close": [], "v": [], "dollar": []
        })

    df = trades.select([
        pl.col("sip_ts").alias("t"),
        pl.col("price").alias("p"),
        pl.col("size").alias("q"),
        (pl.col("price") * pl.col("size")).alias("pq")
    ]).sort("t")

    cuts: List[Tuple[int, int]] = []
    acc_q = 0.0
    last_idx = 0
    t_dict = df.to_dict(as_series=False)

    for i in range(len(t_dict["q"])):
        acc_q += float(t_dict["q"][i])
        if acc_q >= bar_vol_target:
            cuts.append((last_idx, i))
            last_idx = i + 1
            acc_q = 0.0

    if last_idx < len(t_dict["q"]):
        cuts.append((last_idx, len(t_dict["q"]) - 1))

    bars = []
    for (a, b) in cuts:
        if a > b:
            continue
        seg = df.slice(a, b - a + 1)
        open_, close = seg["p"][0], seg["p"][-1]
        high, low = seg["p"].max(), seg["p"].min()
        vol = seg["q"].sum()
        dollar = seg["pq"].sum()
        ts = int(seg["t"][0])
        bars.append((ts, float(open_), float(high), float(low),
                    float(close), float(vol), float(dollar)))

    return pl.DataFrame(bars, schema=["t", "open", "high", "low", "close", "v", "dollar"])

def build_imbalance_bars(trades: pl.DataFrame,
                        kind: Literal["dollar", "volume"] = "dollar",
                        target: float = 50_000,
                        alpha: float = 0.2) -> pl.DataFrame:
    """
    Imbalance Bars (López de Prado): Cierra barra cuando el desequilibrio acumulado
    excede umbral dinámico basado en EWMA.

    Args:
        trades: DataFrame con columnas ['sip_ts', 'price', 'size']
        kind: "dollar" usa p*q, "volume" usa q
        target: Magnitud base objetivo
        alpha: Factor EWMA para umbral dinámico

    Returns:
        DataFrame con barras OHLCV
    """
    if trades.height == 0:
        return pl.DataFrame({
            "t": [], "open": [], "high": [], "low": [],
            "close": [], "v": [], "dollar": []
        })

    df = trades.select([
        pl.col("sip_ts").alias("t"),
        pl.col("price").alias("p"),
        pl.col("size").alias("q")
    ]).sort("t")

    # Signo del retorno por trade (proxy de buy/sell pressure)
    p = df["p"].to_numpy()
    ret = np.diff(p, prepend=p[0])
    sgn = np.sign(ret)  # -1, 0, +1

    # EWMA del desequilibrio "esperado"
    sgn_abs_ewma = ewma(np.abs(sgn).astype(float), alpha=alpha)

    # Magnitud por trade
    if kind == "dollar":
        mag = (df["p"] * df["q"]).to_numpy()
    else:
        mag = df["q"].to_numpy()

    bars = []
    acc_imb = 0.0
    acc_mag = 0.0
    last_idx = 0

    for i in range(len(mag)):
        # Desequilibrio firmado (buy vs sell proxy por signo del cambio de precio)
        imb_i = float(sgn[i]) * float(mag[i])
        acc_imb += imb_i
        acc_mag += float(mag[i])

        threshold = sgn_abs_ewma[i] * target  # umbral dinámico

        # Cerrar barra si:
        # 1. Desequilibrio acumulado excede umbral, O
        # 2. Magnitud acumulada excede target
        if abs(acc_imb) >= max(1.0, threshold) or acc_mag >= target:
            seg = df.slice(last_idx, i - last_idx + 1)
            open_, close = seg["p"][0], seg["p"][-1]
            high, low = seg["p"].max(), seg["p"].min()
            vol = seg["q"].sum()
            dollar = (seg["p"] * seg["q"]).sum()
            ts = int(seg["t"][0])
            bars.append((ts, float(open_), float(high), float(low),
                        float(close), float(vol), float(dollar)))
            last_idx = i + 1
            acc_imb = 0.0
            acc_mag = 0.0

    # Cola (último fragmento)
    if last_idx < len(mag):
        seg = df.slice(last_idx, len(mag) - last_idx)
        if seg.height > 0:
            open_, close = seg["p"][0], seg["p"][-1]
            high, low = seg["p"].max(), seg["p"].min()
            vol = seg["q"].sum()
            dollar = (seg["p"] * seg["q"]).sum()
            ts = int(seg["t"][0])
            bars.append((ts, float(open_), float(high), float(low),
                        float(close), float(vol), float(dollar)))

    return pl.DataFrame(bars, schema=["t", "open", "high", "low", "close", "v", "dollar"])

# ========== I/O ==========

def read_trades_folder(trades_root: Path, ticker: str, date_from: str, date_to: str) -> pl.DataFrame:
    """
    Lee todos los días [from,to] del layout: ticker/year=YYYY/month=MM/day=YYYY-MM-DD/trades.parquet
    """
    y0, y1 = int(date_from[:4]), int(date_to[:4])
    dfs = []

    for y in range(y0, y1 + 1):
        yy = f"year={y}"
        ydir = trades_root / ticker / yy
        if not ydir.exists():
            continue

        for mdir in ydir.iterdir():
            if not mdir.is_dir():
                continue

            for ddir in mdir.iterdir():
                if not ddir.is_dir():
                    continue

                day = ddir.name.replace("day=", "")
                if day < date_from or day > date_to:
                    continue

                f = ddir / "trades.parquet"
                if f.exists():
                    dfs.append(pl.read_parquet(f))

    if not dfs:
        return pl.DataFrame({"sip_ts": [], "price": [], "size": []})

    df = pl.concat(dfs, how="vertical_relaxed").sort("sip_ts")
    return df

def read_agg1m_fallback(agg1m_root: Path, ticker: str, date_from: str, date_to: str) -> pl.DataFrame:
    """
    Fallback: Lee 1m aggregates y los convierte a pseudo-trades.
    Menos preciso que trades reales, pero útil cuando trades no están disponibles.
    """
    root = Path(agg1m_root) / ticker
    dfs = []

    if root.exists():
        for ydir in root.iterdir():
            if not ydir.is_dir():
                continue
            for mdir in ydir.iterdir():
                if not mdir.is_dir():
                    continue
                f = mdir / "minute.parquet"
                if f.exists():
                    df = pl.read_parquet(f).select([
                        pl.col("t").alias("sip_ts"),
                        pl.col("c").alias("price"),
                        pl.col("v").alias("size")
                    ])
                    dfs.append(df)

    if not dfs:
        return pl.DataFrame({"sip_ts": [], "price": [], "size": []})

    trades = pl.concat(dfs, how="vertical_relaxed").filter(
        (pl.from_epoch(pl.col("sip_ts") / 1000, time_unit="ms").dt.strftime("%Y-%m-%d") >= date_from) &
        (pl.from_epoch(pl.col("sip_ts") / 1000, time_unit="ms").dt.strftime("%Y-%m-%d") <= date_to)
    ).sort("sip_ts")

    return trades

def write_bars(df: pl.DataFrame, outdir: Path, ticker: str, bar_kind: str,
              date_from: str, date_to: str) -> None:
    """Escribe barras particionadas por año"""
    if df.height == 0:
        out = outdir / ticker / bar_kind / "empty.parquet"
        out.parent.mkdir(parents=True, exist_ok=True)
        df.write_parquet(out)
        return

    # Particiona por año
    df = df.with_columns(
        pl.from_epoch(pl.col("t") / 1_000_000_000, time_unit="ns")\
          .dt.strftime("%Y").alias("year")
    )

    for year, part in df.group_by("year"):
        y = year[0]
        out = outdir / ticker / bar_kind / f"year={y}" / "bars.parquet"
        out.parent.mkdir(parents=True, exist_ok=True)

        if out.exists():
            # Merge idempotente
            old = pl.read_parquet(out)
            merged = pl.concat([old, part.drop("year")], how="vertical_relaxed")\
                      .unique(subset=["t"], keep="last").sort("t")
            merged.write_parquet(out)
        else:
            part.drop("year").sort("t").write_parquet(out)

# ========== CLI ==========

def main():
    ap = argparse.ArgumentParser(
        description="Bar Construction (Dollar/Volume/Imbalance) desde TRADES o fallback 1m",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--trades-root", required=False,
                    help="Root de trades parquet")
    ap.add_argument("--agg1m-root", required=False,
                    help="Root de intraday_1m parquet (fallback)")
    ap.add_argument("--ticker", required=True,
                    help="Ticker a procesar")
    ap.add_argument("--from", dest="date_from", required=True,
                    help="Fecha inicio YYYY-MM-DD")
    ap.add_argument("--to", dest="date_to", required=True,
                    help="Fecha fin YYYY-MM-DD")
    ap.add_argument("--outdir", required=True,
                    help="Directorio de salida (ej: processed/bars)")
    ap.add_argument("--mode", required=True, choices=["DB", "VB", "DIB", "VIB"],
                    help="Tipo de barra: DB=Dollar, VB=Volume, DIB=Dollar Imbalance, VIB=Volume Imbalance")
    ap.add_argument("--target", type=float, default=50_000.0,
                    help="USD objetivo (DB/DIB) o VOL objetivo (VB/VIB) - Default: 50,000")
    ap.add_argument("--alpha", type=float, default=0.2,
                    help="EWMA alpha para Imbalance Bars - Default: 0.2")
    args = ap.parse_args()

    # 1) Cargar trades o fallback 1m
    if args.trades_root:
        log(f"Cargando trades desde {args.trades_root}...")
        trades = read_trades_folder(Path(args.trades_root), args.ticker,
                                   args.date_from, args.date_to)
        trades = trades.rename({"sip_ts": "sip_ts", "price": "price", "size": "size"})
    else:
        if not args.agg1m_root:
            raise SystemExit("ERROR: Proveer --trades-root o --agg1m-root")
        log(f"Cargando 1m aggregates (fallback) desde {args.agg1m_root}...")
        trades = read_agg1m_fallback(Path(args.agg1m_root), args.ticker,
                                    args.date_from, args.date_to)

    log(f"Total trades/ticks: {trades.height:,}")

    # 2) Construir barras
    if args.mode == "DB":
        log(f"Construyendo Dollar Bars (target: ${args.target:,.0f})...")
        bars = build_dollar_bars(trades, bar_usd_target=args.target)
        kind = "dollar"
    elif args.mode == "VB":
        log(f"Construyendo Volume Bars (target: {args.target:,.0f} shares)...")
        bars = build_volume_bars(trades, bar_vol_target=args.target)
        kind = "volume"
    elif args.mode == "DIB":
        log(f"Construyendo Dollar Imbalance Bars (target: ${args.target:,.0f}, alpha: {args.alpha})...")
        bars = build_imbalance_bars(trades, kind="dollar", target=args.target, alpha=args.alpha)
        kind = "dollar_imbalance"
    else:  # VIB
        log(f"Construyendo Volume Imbalance Bars (target: {args.target:,.0f}, alpha: {args.alpha})...")
        bars = build_imbalance_bars(trades, kind="volume", target=args.target, alpha=args.alpha)
        kind = "volume_imbalance"

    # 3) Guardar
    write_bars(bars, Path(args.outdir), args.ticker, kind, args.date_from, args.date_to)
    log(f"✓ {args.ticker} {args.mode}: {bars.height:,} barras generadas")

if __name__ == "__main__":
    main()
