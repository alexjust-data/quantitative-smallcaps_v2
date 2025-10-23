#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Descarga FINRA Reg SHO Daily Short Sale Volume (Query API)
- Dataset: group=otcmarket, name=regShoDaily
- Docs límites/paginación FINRA: máx 5,000 registros por request y ~3MB payload (usar limit/offset). 
- Campos típicos: Date/tradeDate, Symbol/issueSymbol, ShortVolume, ShortExemptVolume, TotalVolume, Market.

Uso:
  python download_finra_short_volume_api.py \
    --outdir raw/finra/regsho_daily \
    --from 2020-01-01 --to 2025-10-21 \
    --tickers-csv processed/universe/info_rich/info_rich_tickers_20251015_20251021.csv \
    --batch-days 7 --limit 5000 --parallel 6 --resume

  # Sin tickers (descarga universo completo para el rango):
  python download_finra_short_volume_api.py --outdir raw/finra/regsho_daily --from 2025-10-01 --to 2025-10-21

Salida (particionada):
  raw/finra/regsho_daily/
    date=YYYY-MM-DD/
      regsho.parquet
      _SUCCESS
"""

from __future__ import annotations
import argparse, os, sys, time, json, math
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests
import polars as pl

FINRA_BASE = "https://api.finra.org"
FINRA_AUTH_URL = "https://ews.fip.finra.org/fip/rest/ews/oauth2/access_token"
DATASET_PATH = "/data/group/OTCMarket/name/regShoDaily"  # dataset (Reg SHO daily)
META_PATH   = "/metadata/group/OTCMarket/name/regShoDaily"

# Límites/plataforma (ver FINRA docs)
HARD_LIMIT_MAX = 5000  # máx registros por request síncrono
DEFAULT_LIMIT  = 5000
TIMEOUT = 30
RETRIES = 4

# OAuth 2.0 - Obtener access token
def get_access_token(client_id: str, client_secret: str) -> str:
    """
    Obtiene access token usando OAuth 2.0 Client Credentials flow.
    """
    try:
        response = requests.post(
            FINRA_AUTH_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=TIMEOUT
        )
        response.raise_for_status()
        token_data = response.json()
        return token_data.get("access_token", "")
    except Exception as e:
        print(f"[ERROR] Failed to get OAuth token: {e}", flush=True)
        sys.exit(1)

# Sesión HTTP
def build_session(access_token: Optional[str] = None) -> requests.Session:
    s = requests.Session()
    # Conexiones pequeñas pero estables
    adapter = requests.adapters.HTTPAdapter(pool_connections=2, pool_maxsize=4, max_retries=0)
    s.mount("https://", adapter)
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    s.headers.update(headers)
    return s

def backoff_sleep(k: int) -> None:
    # backoff moderado y tope
    delay = min(20.0, 1.5 ** (k + 1))
    time.sleep(delay)

@dataclass
class FieldsMap:
    date_col: str
    symbol_col: str

def get_fields_map(session: requests.Session) -> FieldsMap:
    """
    Interroga metadata para detectar los nombres de columnas.
    Fallback razonables si el metadata falla.
    """
    try:
        r = session.get(FINRA_BASE + META_PATH, timeout=TIMEOUT)
        r.raise_for_status()
        meta = r.json()
        # meta["fields"] puede listar objetos con "name"
        names = { (f.get("name") or "").lower(): f.get("name") for f in meta.get("fields", []) }
        # candidatos
        date_candidates   = ["tradereportdate", "tradedate", "date"]
        symbol_candidates = ["securitiesinformationprocessorsymbolidentifier", "symbol", "issuesymbol"]
        date_col = None
        for c in date_candidates:
            if c in names:
                date_col = names[c]; break
        if not date_col:
            date_col = "tradeReportDate"  # fallback from docs

        symbol_col = None
        for c in symbol_candidates:
            if c in names:
                symbol_col = names[c]; break
        if not symbol_col:
            symbol_col = "securitiesInformationProcessorSymbolIdentifier"  # fallback from docs

        return FieldsMap(date_col=date_col, symbol_col=symbol_col)
    except Exception:
        # Fallback robusto from official docs
        return FieldsMap(date_col="tradeReportDate", symbol_col="securitiesInformationProcessorSymbolIdentifier")

def build_post_payload(date_col: str, start: str, end: str,
                       symbol_col: Optional[str] = None,
                       tickers: Optional[List[str]] = None,
                       limit: int = DEFAULT_LIMIT,
                       offset: int = 0,
                       fields: Optional[List[str]] = None) -> Dict:
    """
    Construye el body POST (Query API) con filtros por rango de fechas y tickers (si se pasan).
    Query API acepta compareFilters (EQUAL, BETWEEN, GREATER, LESS) y domainFilters.
    """
    compare_filters = [
        {
            "compareType": "BETWEEN",
            "fieldName": date_col,
            "fieldValue": f"{start}~{end}"  # formato BETWEEN: "start~end"
        }
    ]

    domain_filters = []
    if tickers and symbol_col:
        # Domain filter: IN (lista de símbolos)
        domain_filters.append({
            "fieldName": symbol_col,
            "values": tickers
        })

    payload = {
        "limit": limit,
        "offset": offset,
        "compareFilters": compare_filters
    }
    if domain_filters:
        payload["domainFilters"] = domain_filters

    if fields:
        payload["fields"] = fields

    return payload

def chunk_list(lst: List[str], size: int) -> List[List[str]]:
    return [lst[i:i+size] for i in range(0, len(lst), size)]

def daterange_chunks(date_from: str, date_to: str, batch_days: int) -> List[Tuple[str, str]]:
    """
    Divide el rango [date_from, date_to] en ventanas de batch_days (inclusive).
    """
    start = datetime.fromisoformat(date_from)
    end   = datetime.fromisoformat(date_to)
    out = []
    cur = start
    one_day = timedelta(days=1)
    while cur <= end:
        stop = min(cur + timedelta(days=batch_days-1), end)
        out.append((cur.date().isoformat(), stop.date().isoformat()))
        cur = stop + one_day
    return out

def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)

def has_success_flag(dir_date: Path) -> bool:
    return (dir_date / "_SUCCESS").exists()

def write_success_flag(dir_date: Path) -> None:
    (dir_date / "_SUCCESS").write_text("")

def fetch_page(session: requests.Session, url: str, payload: Dict) -> List[Dict]:
    """
    POST síncrono con reintentos moderados.
    """
    body = json.dumps(payload)
    for k in range(RETRIES):
        try:
            r = session.post(url, data=body, timeout=TIMEOUT)
            # FINRA a veces devuelve 200 con [] para "no data"
            if r.status_code == 200:
                return r.json() if r.content else []
            # Para límites, errores 4xx/5xx reintentables
            if r.status_code in (429, 500, 502, 503, 504):
                backoff_sleep(k)
                continue
            r.raise_for_status()
            return r.json() if r.content else []
        except Exception:
            backoff_sleep(k)
    # Último intento fuera del loop
    r = session.post(url, data=body, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json() if r.content else []

def save_parquet_partition(df: pl.DataFrame, outdir: Path, date_str: str) -> None:
    """
    Guarda un único parquet por fecha (partición date=YYYY-MM-DD).
    """
    dir_date = outdir / f"date={date_str}"
    ensure_dir(dir_date)
    out_file = dir_date / "regsho.parquet"
    # Merge incremental (si existe, append y unique por (date, symbol, market))
    if out_file.exists():
        prev = pl.read_parquet(out_file)
        df = pl.concat([prev, df], how="vertical_relaxed").unique(
            subset=[c for c in df.columns if c.lower() in ("date", "tradedate", "symbol", "issuesymbol", "market")],
            keep="last"
        )
    df.write_parquet(out_file, compression="zstd", compression_level=3)
    write_success_flag(dir_date)

def normalize_datestr(s: str) -> str:
    """
    FINRA puede devolver fechas como 'YYYY-MM-DD' o 'YYYYMMDD'. Normalizamos a YYYY-MM-DD.
    """
    s = str(s)
    if len(s) == 8 and s.isdigit():
        return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
    return s

def main():
    ap = argparse.ArgumentParser(description="Descarga FINRA Reg SHO Daily Short Sale Volume (Query API)")
    ap.add_argument("--outdir", required=True, help="Directorio salida (particionado por fecha)")
    ap.add_argument("--from", dest="date_from", required=True, help="YYYY-MM-DD")
    ap.add_argument("--to", dest="date_to", required=True, help="YYYY-MM-DD")
    ap.add_argument("--tickers-csv", help="CSV con columna 'ticker' (opcional)")
    ap.add_argument("--tickers-col", default="ticker", help="Nombre de la columna de tickers en el CSV")
    ap.add_argument("--batch-days", type=int, default=7, help="Ventana de días por batch (default: 7)")
    ap.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="Registros por request (<=5000)")
    ap.add_argument("--parallel", type=int, default=1, help="(Opcional) Paralelismo por procesos (no implementado aquí)")
    ap.add_argument("--resume", action="store_true", help="Saltar fechas con _SUCCESS")
    args = ap.parse_args()

    if args.limit > HARD_LIMIT_MAX:
        print(f"[WARN] --limit {args.limit} > {HARD_LIMIT_MAX}. Ajustando a {HARD_LIMIT_MAX}.", flush=True)
        args.limit = HARD_LIMIT_MAX

    outdir = Path(args.outdir)
    ensure_dir(outdir)

    # Tickers (opcional)
    tickers: Optional[List[str]] = None
    if args.tickers_csv:
        df_t = pl.read_csv(args.tickers_csv, infer_schema_length=10000)
        if args.tickers_col not in df_t.columns:
            sys.exit(f"ERROR: La columna '{args.tickers_col}' no está en {args.tickers_csv}")
        tickers = sorted([t for t in df_t[args.tickers_col].unique().to_list() if isinstance(t, str) and t.strip()])

    # FINRA regShoDaily is a PUBLIC dataset - no authentication required
    print("[INFO] Using FINRA public API (no authentication required)", flush=True)
    session = build_session(access_token=None)
    fields_map = get_fields_map(session)
    date_col   = fields_map.date_col
    symbol_col = fields_map.symbol_col

    print(f"[INFO] Campos detectados - date_col='{date_col}' symbol_col='{symbol_col}'", flush=True)
    print(f"[INFO] Rango fechas - {args.date_from} a {args.date_to}", flush=True)
    if tickers:
        print(f"[INFO] Tickers objetivo - {len(tickers)} simbolos (ej: {tickers[:8]})", flush=True)
    else:
        print(f"[INFO] Tickers objetivo - [TODOS] (sin filtro de simbolo)", flush=True)

    url = FINRA_BASE + DATASET_PATH

    # Recorremos por ventanas de fechas (batch_days)
    date_windows = daterange_chunks(args.date_from, args.date_to, args.batch_days)
    total_rows = 0
    total_dates = 0

    for start, end in date_windows:
        # Para escritura particionada por día, descargamos la ventana y luego separamos por fecha
        print(f"[BATCH] {start} ~ {end}", flush=True)

        # Descarga por páginas (offset)
        offset = 0
        batch_rows = 0
        collected: List[Dict] = []
        k = 0
        while True:
            payload = build_post_payload(
                date_col=date_col,
                start=start,
                end=end,
                symbol_col=symbol_col if tickers else None,
                tickers=tickers if tickers else None,
                limit=args.limit,
                offset=offset,
                fields=None  # traer todo y filtrar luego si se quiere
            )
            data = fetch_page(session, url, payload)
            n = len(data) if isinstance(data, list) else 0
            if n == 0:
                break
            collected.extend(data)
            batch_rows += n
            offset += args.limit
            # Si trae menos de limit, ya no hay más
            if n < args.limit:
                break
            # Pequeña pausa para no golpear el payload limit
            time.sleep(0.25)
            k += 1
            if k % 10 == 0:
                print(f"  [..] Paginando: {batch_rows} filas acumuladas...", flush=True)

        if batch_rows == 0:
            print(f"  [.] Sin datos", flush=True)
            continue

        # Pasar a Polars y normalizar fecha
        df = pl.from_dicts(collected)
        # normalizar fecha a YYYY-MM-DD en una nueva columna 'date_norm'
        if date_col in df.columns:
            df = df.with_columns(
                pl.col(date_col).map_elements(normalize_datestr).alias("date_norm")
            )
        elif "Date" in df.columns:
            df = df.with_columns(
                pl.col("Date").map_elements(normalize_datestr).alias("date_norm")
            )
        else:
            # si no hay fecha → abortar este batch
            print("  [WARN] Columna de fecha no encontrada en respuesta. Saltando batch.", flush=True)
            continue

        # Split por día y escribir particiones
        for d, sub in df.group_by("date_norm"):
            date_str = d  # ya normalizado
            dir_date = outdir / f"date={date_str}"
            if args.resume and has_success_flag(dir_date):
                # ya existe: saltar
                continue
            # Guardar parquet
            # Estabilizar nombres de columnas comunes
            sub2 = sub.rename({date_col: "tradeDate"} if date_col in sub.columns else {}) \
                     .rename({symbol_col: "symbol"} if symbol_col in sub.columns else {})
            # Columnas en minúscula para consistencia
            sub2 = sub2.rename({c: c for c in sub2.columns})
            # Eliminar 'date_norm' en escritura
            sub2 = sub2.drop("date_norm")
            save_parquet_partition(sub2, outdir, date_str)
            total_rows += sub2.height
            total_dates += 1

        print(f"  [OK] Guardado: {total_dates} fechas acumuladas, {total_rows} filas totales", flush=True)

    print(f"\n[FIN] Completado. Fechas: {total_dates} | Filas: {total_rows}", flush=True)
    print(f"[OUT] {outdir}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[STOP] Interrumpido por el usuario.", flush=True)
        sys.exit(130)
