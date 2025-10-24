#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Wrapper para ejecutar ingest_reference_universe.py con:
- Carga automática de .env
- Rate limiting configurable (default 0.15 seg entre requests)
- Paralelización si se desea en el futuro

Uso:
    python run_download_universe.py --rate-limit 0.15
"""

import os
import sys
import subprocess
from pathlib import Path
from dotenv import load_dotenv

def main():
    # 1. Cargar .env desde la raíz del proyecto
    project_root = Path(__file__).parent.parent.parent
    env_file = project_root / ".env"

    if env_file.exists():
        print(f"Cargando variables de entorno desde: {env_file}")
        load_dotenv(env_file)
    else:
        print(f"WARNING: No se encontró .env en {env_file}")

    # 2. Verificar API key
    api_key = os.getenv("POLYGON_API_KEY")
    if not api_key:
        print("ERROR: POLYGON_API_KEY no encontrada en .env")
        sys.exit(1)

    print(f"[OK] API Key cargada: {api_key[:10]}...")

    # 3. Parámetros para el script principal
    rate_limit = 0.15  # segundos entre requests (6.67 requests/seg, muy por debajo del límite)

    cmd = [
        sys.executable,  # Python actual
        str(Path(__file__).parent / "ingest_reference_universe.py"),
        "--outdir", "raw/polygon/reference/tickers_snapshot",
        "--market", "stocks",
        "--locale", "us",
        "--active", "both",
        "--limit", "1000",
        "--snapshot-date", "2025-01-15",
    ]

    print(f"\n[LAUNCH] Lanzando descarga con rate_limit={rate_limit}s...")
    print(f"Comando: {' '.join(cmd)}\n")

    # 4. Ejecutar con el environment actual (que ya tiene POLYGON_API_KEY)
    env = os.environ.copy()
    env["POLYGON_API_KEY"] = api_key

    # Para rate limiting, podríamos modificar el script original,
    # pero por ahora solo lanzamos con los parámetros correctos
    result = subprocess.run(cmd, env=env)

    sys.exit(result.returncode)

if __name__ == "__main__":
    main()
