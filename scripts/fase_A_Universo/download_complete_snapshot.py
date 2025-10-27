"""
Descargar snapshot COMPLETO de tickers (activos + inactivos) desde Polygon API
Incluye paginación automática y manejo de rate limits
"""
import polars as pl
import requests
from pathlib import Path
import time
from datetime import datetime

# Configuración
import os
API_KEY = os.getenv("POLYGON_API_KEY")
if not API_KEY:
    raise ValueError("POLYGON_API_KEY environment variable not set. Please set it before running.")
output_dir = Path("raw/polygon/reference/tickers_snapshot")
snapshot_date = datetime.now().strftime("%Y-%m-%d")

print("=" * 100)
print("DESCARGA SNAPSHOT COMPLETO - POLYGON TICKERS (ACTIVOS + INACTIVOS)")
print("=" * 100)
print()

def download_tickers(active=True):
    """Descargar tickers con paginación"""
    base_url = "https://api.polygon.io/v3/reference/tickers"

    params = {
        "market": "stocks",
        "active": str(active).lower(),
        "limit": 1000,
        "apiKey": API_KEY
    }

    all_results = []
    page = 1
    next_url = None

    status = "ACTIVOS" if active else "INACTIVOS"
    print(f"Descargando tickers {status}...")

    while True:
        try:
            if next_url:
                url = next_url + f"&apiKey={API_KEY}"
                response = requests.get(url, timeout=30)
            else:
                response = requests.get(base_url, params=params, timeout=30)

            if response.status_code != 200:
                print(f"❌ Error {response.status_code}: {response.text}")
                break

            data = response.json()

            if "results" in data and data["results"]:
                batch_size = len(data["results"])
                all_results.extend(data["results"])
                print(f"   Página {page:>3}: +{batch_size:>4} tickers | Total: {len(all_results):>7,}")
            else:
                break

            # Verificar next_url
            if "next_url" in data and data["next_url"]:
                next_url = data["next_url"]
                page += 1
                time.sleep(0.15)  # Rate limit
            else:
                break

        except Exception as e:
            print(f"❌ Error en página {page}: {e}")
            break

    print(f"Descarga completa: {len(all_results):,} tickers {status}")
    return all_results

# Descargar ACTIVOS
print("\nFASE 1: TICKERS ACTIVOS")
print("-" * 100)
active_data = download_tickers(active=True)

# Descargar INACTIVOS
print("\nFASE 2: TICKERS INACTIVOS")
print("-" * 100)
inactive_data = download_tickers(active=False)

# Procesar y guardar
print("\nFASE 3: PROCESAR Y GUARDAR")
print("-" * 100)

# Agregar snapshot_date
for item in active_data:
    item["snapshot_date"] = snapshot_date

for item in inactive_data:
    item["snapshot_date"] = snapshot_date

# Crear DataFrames
df_active = pl.DataFrame(active_data)
df_inactive = pl.DataFrame(inactive_data)

# Concatenar con how="diagonal" para permitir diferentes esquemas
# Esto rellena con null las columnas faltantes automáticamente
df_all = pl.concat([df_active, df_inactive], how="diagonal")

print(f"Tickers activos:   {len(df_active):>7,}")
print(f"Tickers inactivos: {len(df_inactive):>7,}")
print(f"Total combinado:   {len(df_all):>7,}")
print()

# Crear directorios
output_path = output_dir / f"snapshot_date={snapshot_date}"
output_path.mkdir(parents=True, exist_ok=True)

# Guardar archivos
file_all = output_path / "tickers_all.parquet"
file_active = output_path / "tickers_active.parquet"
file_inactive = output_path / "tickers_inactive.parquet"

print(f"Guardando snapshot completo:    {file_all}")
df_all.write_parquet(file_all, compression="zstd", compression_level=3)

print(f"Guardando solo activos:         {file_active}")
df_active.write_parquet(file_active, compression="zstd", compression_level=3)

print(f"Guardando solo inactivos:       {file_inactive}")
df_inactive.write_parquet(file_inactive, compression="zstd", compression_level=3)

# Guardar CSV de conteo
count_data = pl.DataFrame({
    "active": [True, False],
    "count": [len(df_active), len(df_inactive)],
    "percentage": [
        len(df_active) / len(df_all) * 100,
        len(df_inactive) / len(df_all) * 100
    ]
})

csv_file = Path("temp_active_counts_complete.csv")
count_data.write_csv(csv_file)
print(f"Guardando resumen CSV:          {csv_file}")

print()
print("=" * 100)
print("DESCARGA COMPLETADA")
print("=" * 100)
print(f"""
Archivos generados:
   - Completo (activos + inactivos): {file_all}
   - Solo activos:                   {file_active}
   - Solo inactivos:                 {file_inactive}
   - Resumen CSV:                    {csv_file}

Resumen:
   - Activos:   {len(df_active):>7,} ({len(df_active)/len(df_all)*100:>5.1f}%)
   - Inactivos: {len(df_inactive):>7,} ({len(df_inactive)/len(df_all)*100:>5.1f}%)
   - Total:     {len(df_all):>7,}
""")
