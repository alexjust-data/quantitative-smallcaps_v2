#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
launch_intraday_smallcaps.py

Launcher para descargar intradía 1m de Polygon con múltiple procesos (workers),
sharding de tickers, control de ritmo (rate-limit) por worker, logs, PIDs,
status y stop. Inspirado en 'launch_accelerated_0125s.py'.

Uso típico:
  export POLYGON_API_KEY=xxx

  python tools/launch_intraday_smallcaps.py start \
    --tickers-csv processed/universe/cs_xnas_xnys_under2b.csv \
    --outdir raw/polygon/ohlcv_intraday_1m \
    --from 2004-01-01 --to 2025-10-20 \
    --shards 12 --per-shard-workers 4 \
    --rate-limit 0.125 \
    --workdir runs/intraday_1m_2025-10-20 \
    --ingest-script scripts/fase_1_Bloque_B/ingest_ohlcv_intraday_minute.py \
    --resume

Comandos:
  start  : crea shards, lanza N workers, guarda logs y PIDs
  status : muestra estado de los workers (vivos, logs resumen)
  stop   : termina los workers (SIGTERM -> SIGKILL)
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
import polars as pl
from typing import List, Tuple

# ---------------------- utils ----------------------
def log(msg: str) -> None:
    print(f"[{dt.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)

def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def read_tickers(csv_path: Path) -> List[str]:
    df = pl.read_csv(csv_path)
    if "ticker" not in df.columns:
        raise SystemExit("El CSV debe contener columna 'ticker'.")
    return df["ticker"].drop_nulls().unique().to_list()

def existing_tickers(outdir: Path) -> set[str]:
    """Resume simple: si existe carpeta del ticker en outdir, lo consideramos 'ya iniciado'."""
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

# ---------------------- commands ----------------------
def cmd_start(args) -> None:
    workdir = Path(args.workdir)
    ensure_dir(workdir / "logs")
    ensure_dir(workdir / "pids")
    ensure_dir(workdir / "shards")

    tickers = read_tickers(Path(args.tickers_csv))
    log(f"Tickers originales: {len(tickers):,}")

    if args.resume:
        done = existing_tickers(Path(args.outdir))
        if done:
            tickers = [t for t in tickers if t not in done]
            log(f"Resume: excluidos {len(done):,} tickers que ya tienen carpeta en outdir.")
            log(f"Quedan por descargar: {len(tickers):,}")

    if len(tickers) == 0:
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
    log(f"CONFIGURACIÓN:")
    log(f"  Date range:   {args.date_from} → {args.date_to}")
    log(f"  Shards:       {args.shards}")
    log(f"  Workers/shard: {args.per_shard_workers}")
    log(f"  Rate limit:   {args.rate_limit}s/page")
    log(f"  Workdir:      {workdir}")
    log(f"  Outdir:       {args.outdir}")
    log(f"{'='*80}\n")

    # Lanzar un proceso por shard
    procs: List[Tuple[int, sp.Popen]] = []

    for i, shard_csv in enumerate(shard_paths):
        # Cada worker invoca el ingest con su shard
        cmd = [
            sys.executable, args.ingest_script,
            "--tickers-csv", str(shard_csv),
            "--outdir", args.outdir,
            "--from", args.date_from,
            "--to", args.date_to,
            "--max-workers", str(args.per_shard_workers),
            "--rate-limit", str(args.rate_limit),
        ]
        lf = open(log_file(workdir, i), "a", encoding="utf-8")
        log(f"Lanzando worker {i:02d}: shard con {len(shards[i]):,} tickers")
        p = sp.Popen(cmd, stdout=lf, stderr=lf, cwd=Path.cwd(), env=env)
        ensure_dir((workdir / "pids"))
        pid_path = pid_file(workdir, i)
        with open(pid_path, "w", encoding="utf-8") as f:
            f.write(str(p.pid))
        procs.append((i, p))

    log(f"\n{'='*80}")
    log(f"Workers lanzados: {len(procs)}")
    log(f"  Logs: {workdir/'logs'}")
    log(f"  PIDs: {workdir/'pids'}")
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

    # Resumen rápido desde logs (líneas finales)
    logdir = workdir / "logs"
    if logdir.exists():
        print("--- Últimas líneas de cada log ---\n")
        for lf in sorted(logdir.glob("worker_*.log")):
            try:
                tail = tail_file(lf, n=3)
                print(f"[{lf.name}]")
                for line in tail:
                    print(f"  {line.rstrip()}")
                print()
            except Exception:
                pass

def tail_file(path: Path, n: int = 10) -> List[str]:
    """Tail simple: leer últimas n líneas"""
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
    return lines[-n:] if lines else []

def cmd_stop(args) -> None:
    workdir = Path(args.workdir)
    piddir = workdir / "pids"
    if not piddir.exists():
        log("No hay pids (¿ejecutaste start?).")
        return

    # Leer todos los PIDs
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
                # Windows: usar taskkill
                sp.run(["taskkill", "/PID", str(pid), "/T"],
                      capture_output=True, timeout=5)
            else:
                os.kill(pid, signal.SIGTERM)
        except Exception as e:
            log(f"Error terminando PID {pid}: {e}")

    time.sleep(3.0)

    # Verificar cuáles siguen vivos
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

# ---------------------- CLI ----------------------
def parse_args():
    ap = argparse.ArgumentParser(
        description="Launcher intradía 1m (multi-proceso) para Polygon",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    # START command
    aps = sub.add_parser("start", help="Iniciar descarga intraday")
    aps.add_argument("--tickers-csv", required=True,
                    help="CSV con columna 'ticker' (universo final)")
    aps.add_argument("--outdir", required=True,
                    help="Salida base intradía 1m (raw/polygon/ohlcv_intraday_1m)")
    aps.add_argument("--from", dest="date_from", required=True,
                    help="Fecha inicio YYYY-MM-DD")
    aps.add_argument("--to", dest="date_to", required=True,
                    help="Fecha fin YYYY-MM-DD")
    aps.add_argument("--shards", type=int, default=12,
                    help="Nº de procesos (workers)")
    aps.add_argument("--per-shard-workers", type=int, default=4,
                    help="Hilos internos por proceso (pasa a --max-workers del ingest)")
    aps.add_argument("--rate-limit", type=float, default=0.125,
                    help="Segundos entre páginas por worker")
    aps.add_argument("--workdir", required=True,
                    help="Directorio de corrida (guardará logs/, pids/, shards/)")
    aps.add_argument("--ingest-script", required=True,
                    help="Ruta a scripts/fase_1_Bloque_B/ingest_ohlcv_intraday_minute.py")
    aps.add_argument("--resume", action="store_true",
                    help="Excluir tickers que ya tienen carpeta en outdir")

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
