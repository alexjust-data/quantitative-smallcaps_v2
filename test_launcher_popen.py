import subprocess as sp
import sys
from pathlib import Path

# Reproducir exactamente lo que hace el launcher
cmd = [
    sys.executable, "scripts/fase_1_Bloque_B/ingest_ohlcv_intraday_minute.py",
    "--tickers-csv", "runs/intraday_streaming_fixed/shards/2004-01-01_2010-12-31_shard_00.csv",
    "--outdir", "raw/polygon/ohlcv_intraday_1m",
    "--from", "2004-01-01",
    "--to", "2010-12-31",
    "--max-workers", "1",
    "--rate-limit", "0.2",
]

print(f"Comando: {' '.join(cmd)}")

with open("test_popen.log", "w", encoding="utf-8") as lf:
    p = sp.Popen(cmd, stdout=lf, stderr=lf, cwd=Path.cwd())
    print(f"PID: {p.pid}")
    p.wait()
    print(f"Exit code: {p.returncode}")

print("\n--- Log output ---")
with open("test_popen.log", "r", encoding="utf-8") as f:
    print(f.read())
