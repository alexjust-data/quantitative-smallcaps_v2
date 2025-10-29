#!/usr/bin/env python
"""
monitor_dib_build.py
Monitorea el progreso de construcción de DIB bars para Pilot50.
"""
import sys
from pathlib import Path
from datetime import datetime
import time

def log(msg):
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)

def count_files(root: Path, pattern: str = "*.parquet"):
    """Cuenta archivos recursivamente."""
    if not root.exists():
        return 0
    return sum(1 for _ in root.rglob(pattern))

def main():
    # Paths
    trades_root = Path("raw/polygon/trades_pilot50_validation")
    dib_root = Path("processed/dib_bars/pilot50_validation")

    # Total esperado
    total_expected = count_files(trades_root, "trades.parquet")
    log(f"Total trades files (expected): {total_expected:,}")

    if total_expected == 0:
        log("[ERROR] No se encontraron trades files")
        return

    # Monitorear construcción
    log("Iniciando monitoreo de construcción de DIB bars...")
    log("Presiona Ctrl+C para salir")

    last_count = 0
    start_time = time.time()

    try:
        while True:
            # Contar DIB bars construidos
            dib_count = count_files(dib_root, "_SUCCESS")

            if dib_count > last_count:
                elapsed = time.time() - start_time
                progress_pct = (dib_count / total_expected) * 100
                rate = dib_count / elapsed if elapsed > 0 else 0
                remaining = (total_expected - dib_count) / rate if rate > 0 else 0

                log(f"Progreso: {dib_count:,}/{total_expected:,} ({progress_pct:.1f}%) | "
                    f"Rate: {rate:.1f} files/sec | "
                    f"ETA: {remaining/60:.1f} min")

                last_count = dib_count

            # Si completó, salir
            if dib_count >= total_expected:
                log(f"[✓] COMPLETADO: {dib_count:,} DIB bars construidos en {elapsed/60:.1f} min")
                break

            time.sleep(10)  # Check cada 10 segundos

    except KeyboardInterrupt:
        log("\n[!] Monitoreo interrumpido por usuario")
        elapsed = time.time() - start_time
        log(f"Progreso final: {dib_count:,}/{total_expected:,} en {elapsed/60:.1f} min")

if __name__ == "__main__":
    main()
