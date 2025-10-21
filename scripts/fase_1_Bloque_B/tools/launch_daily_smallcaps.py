#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
launch_daily_smallcaps.py

Launcher para descargar OHLCV diario desde Polygon con múltiples procesos (shards).
Cada shard invoca ingest_ohlcv_daily.py con sus propios workers. Gestiona logs,
PIDs, status/stop y resume (excluye tickers ya iniciados).

Uso:
  export POLYGON_API_KEY=xxx

  python tools/launch_daily_smallcaps.py start \
    --tickers-csv processed/universe/cs_xnas_xnys_under2b.csv \
    --outdir raw/polygon/ohlcv_daily \
    --from 2004-01-01 --to 2025-10-20 \
    --shards 12 --per-shard-workers 4 \
    --workdir runs/daily_2025-10-20 \
    --ingest-script scripts/fase_1_Bloque_B/ingest_ohlcv_daily.py \
    --resume

  python tools/launch_daily_smallcaps.py status --workdir runs/daily_2025-10-20
  python tools/launch_daily_smallcaps.py stop   --workdir runs/daily_2025-10-20
"""
from __future__ import annotations
import os
import sys
import signal
import time
import argparse
import datetime as dt
from pathlib import Path
import subprocess as sp
from typing import List, Tuple
import polars as pl

# ---------- utils ----------
def log(msg: str) -> None:
    print(f"[{dt.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)

def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def read_tickers(csv_path: Path) -> List[str]:
    df = pl.read_csv(csv_path)
    if "ticker" not in df.columns:
        raise SystemExit("El CSV debe contener columna 'ticker'.")
    return df["ticker"].drop_nulls().unique().to_list()

def existing_tickers_daily(outdir: Path) -> set[str]:
    """Resume básico: si hay carpeta del ticker en outdir, lo consideramos ya iniciado."""
    if not outdir.exists():
        return set()
    return {p.name for p in outdir.iterdir() if p.is_dir()}

def shard_list(items: List[str], k: int) -> List[List[str]]:
    k = max(1, k)
    n = len(items)
    base = n // k
    rem  = n % k
    shards = []
    start = 0
    for i in range(k):
        size = base + (1 if i < rem else 0)
        shards.append(items[start:start+size])
        start += size
    return shards

def write_shards(shards: List[List[str]], workdir: Path) -> List[Path]:
    shard_paths = []
    for i, lst in enumerate(shards):
        p = workdir / "shards" / f"tickers_shard_{i:02d}.csv"
        ensure_dir(p.parent)
        pl.DataFrame({"ticker": lst}).write_csv(p)
        shard_paths.append(p)
    return shard_paths

def pid_file(workdir: Path, i: int) -> Path:
    return workdir / "pids" / f"worker_{i:02d}.pid"

def log_file(workdir: Path, i: int) -> Path:
    return workdir / "logs" / f"worker_{i:02d}.log"

def is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except Exception:
        return False

def tail_file(path: Path, n: int = 10) -> List[str]:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        return lines[-n:] if lines else []
    except Exception:
        return []

# ---------- commands ----------
def cmd_start(args) -> None:
    workdir = Path(args.workdir)
    ensure_dir(workdir / "logs")
    ensure_dir(workdir / "pids")
    ensure_dir(workdir / "shards")

    tickers = read_tickers(Path(args.tickers_csv))
    log(f"Tickers originales: {len(tickers):,}")

    if args.resume:
        done = existing_tickers_daily(Path(args.outdir))
        if done:
            tickers = [t for t in tickers if t not in done]
            log(f"Resume: excluidos {len(done):,} tickers con carpeta existente en outdir.")
            log(f"Quedan por descargar: {len(tickers):,}")

    if not tickers:
        log("No hay tickers que procesar. ¿Ya está todo descargado?")
        return

    shards = shard_list(tickers, args.shards)
    shard_paths = write_shards(shards, workdir)

    # Verificar API key
    env = os.environ.copy()
    if not env.get("POLYGON_API_KEY"):
        log("WARNING: POLYGON_API_KEY no está en el entorno.")

    # Mostrar configuración
    log(f"\n{'='*80}")
    log(f"CONFIGURACIÓN DIARIA:")
    log(f"  Date range:    {args.date_from} → {args.date_to}")
    log(f"  Shards:        {args.shards}")
    log(f"  Workers/shard: {args.per_shard_workers}")
    log(f"  Workdir:       {workdir}")
    log(f"  Outdir:        {args.outdir}")
    log(f"{'='*80}\n")

    procs: List[Tuple[int, sp.Popen]] = []

    for i, shard_csv in enumerate(shard_paths):
        cmd = [
            sys.executable, args.ingest_script,
            "--tickers-csv", str(shard_csv),
            "--outdir", args.outdir,
            "--from", args.date_from,
            "--to", args.date_to,
            "--max-workers", str(args.per_shard_workers),
        ]
        lf = open(log_file(workdir, i), "a", encoding="utf-8")
        log(f"Lanzando worker {i:02d}: shard con {len(shards[i]):,} tickers")
        p = sp.Popen(cmd, stdout=lf, stderr=lf, cwd=Path.cwd(), env=env)
        with open(pid_file(workdir, i), "w", encoding="utf-8") as f:
            f.write(str(p.pid))
        procs.append((i, p))

    log(f"\n{'='*80}")
    log(f"Workers lanzados: {len(procs)}")
    log(f"  Logs:   {workdir/'logs'}")
    log(f"  PIDs:   {workdir/'pids'}")
    log(f"  Shards: {workdir/'shards'}")
    log(f"\nMONITOREO:")
    log(f"  python {sys.argv[0]} status --workdir {workdir}")
    log(f"\nDETENER:")
    log(f"  python {sys.argv[0]} stop --workdir {workdir}")
    log(f"{'='*80}\n")

def cmd_status(args) -> None:
    workdir = Path(args.workdir)
    piddir = workdir / "pids"
    if not piddir.exists():
        log("No hay pids (¿ejecutaste start?).")
        return

    total = 0
    running = 0
    for pf in sorted(piddir.glob("worker_*.pid")):
        total += 1
        try:
            pid = int(pf.read_text().strip())
            alive = is_alive(pid)
            running += 1 if alive else 0
            status = "RUNNING" if alive else "STOPPED"
            print(f"{pf.name}: PID {pid:6d}  [{status}]")
        except Exception as e:
            print(f"{pf.name}: ERROR leyendo PID ({e})")

    print(f"\n{'='*80}")
    print(f"Workers totales: {total} | RUNNING: {running} | STOPPED: {total - running}")
    print(f"{'='*80}\n")

    # Tail de logs
    logdir = workdir / "logs"
    if logdir.exists():
        print("--- Últimas líneas de cada log ---\n")
        for lf in sorted(logdir.glob("worker_*.log")):
            tail = tail_file(lf, n=3)
            if tail:
                print(f"[{lf.name}]")
                for line in tail:
                    print(f"  {line.rstrip()}")
                print()

def cmd_stop(args) -> None:
    workdir = Path(args.workdir)
    piddir = workdir / "pids"
    if not piddir.exists():
        log("No hay pids (¿ejecutaste start?).")
        return

    pids = []
    for pf in sorted(piddir.glob("worker_*.pid")):
        try:
            pid = int(pf.read_text().strip())
            if is_alive(pid):
                pids.append(pid)
        except Exception:
            pass

    if not pids:
        log("No se encontraron PIDs vivos.")
        return

    log(f"Enviando SIGTERM a {len(pids)} procesos…")
    for pid in pids:
        try:
            if sys.platform == "win32":
                sp.run(["taskkill", "/PID", str(pid), "/T"],
                      capture_output=True, timeout=5)
            else:
                os.kill(pid, signal.SIGTERM)
        except Exception as e:
            log(f"Error terminando PID {pid}: {e}")

    time.sleep(3.0)
    still = [pid for pid in pids if is_alive(pid)]
    if still:
        log(f"Aún vivos {len(still)} → enviando SIGKILL")
        for pid in still:
            try:
                if sys.platform == "win32":
                    sp.run(["taskkill", "/PID", str(pid), "/F", "/T"],
                          capture_output=True, timeout=5)
                else:
                    os.kill(pid, signal.SIGKILL)
            except Exception as e:
                log(f"Error matando PID {pid}: {e}")

    log("STOP completado.")

# ---------- CLI ----------
def parse_args():
    ap = argparse.ArgumentParser(
        description="Launcher OHLCV diario (multi-proceso) para Polygon",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    # START command
    aps = sub.add_parser("start", help="Iniciar descarga OHLCV diario")
    aps.add_argument("--tickers-csv", required=True,
                    help="CSV con columna 'ticker' (universo final)")
    aps.add_argument("--outdir", required=True,
                    help="raw/polygon/ohlcv_daily")
    aps.add_argument("--from", dest="date_from", required=True,
                    help="Fecha inicio YYYY-MM-DD")
    aps.add_argument("--to", dest="date_to", required=True,
                    help="Fecha fin YYYY-MM-DD")
    aps.add_argument("--shards", type=int, default=12,
                    help="Nº de procesos (shards)")
    aps.add_argument("--per-shard-workers", type=int, default=4,
                    help="Hilos por proceso → --max-workers del ingester")
    aps.add_argument("--workdir", required=True,
                    help="Carpeta de corrida (logs/, pids/, shards/)")
    aps.add_argument("--ingest-script", required=True,
                    help="Ruta a scripts/fase_1_Bloque_B/ingest_ohlcv_daily.py")
    aps.add_argument("--resume", action="store_true",
                    help="Excluir tickers con carpeta ya creada en outdir")

    # STATUS command
    aps_status = sub.add_parser("status", help="Ver estado de workers")
    aps_status.add_argument("--workdir", required=True,
                           help="Directorio de corrida")

    # STOP command
    aps_stop = sub.add_parser("stop", help="Detener workers")
    aps_stop.add_argument("--workdir", required=True,
                         help="Directorio de corrida")

    return ap.parse_args()

def main():
    args = parse_args()
    if args.cmd == "start":
        cmd_start(args)
    elif args.cmd == "status":
        cmd_status(args)
    elif args.cmd == "stop":
        cmd_stop(args)
    else:
        raise SystemExit("Comando desconocido.")

if __name__ == "__main__":
    main()
