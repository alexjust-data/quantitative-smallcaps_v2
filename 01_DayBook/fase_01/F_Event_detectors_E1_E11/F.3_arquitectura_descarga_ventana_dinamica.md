# F.3 - Arquitectura: Descarga con Ventana Dinámica por Evento

**Fecha**: 2025-10-29
**Fase**: F - Event Detectors E0-E11
**Objetivo**: Implementar descarga masiva con ventanas optimizadas por tipo de evento

---

## 1. CONTEXTO: ¿Por Qué Necesitamos Ventanas Dinámicas?

### 1.1 Problema Actual

**Descarga Pilot Ultra-Light** (actual):
```bash
--event-window 2  # Ventana fija ±2 días para TODOS los eventos
```

**Consecuencias**:
- ✅ **Funciona correctamente** para validación rápida
- ❌ **Ineficiente**: Eventos como E6 (Multiple Green Days) solo necesitan ±1 día
- ❌ **Insuficiente**: Eventos como E4 (Parabolic), E8 (Gap Down Violent), E10/E11 (Bounces) necesitan ±3 días
- ❌ **No generalizable**: Para descarga masiva del universo completo necesitamos precisión

### 1.2 Solución: Ventanas Optimizadas por Evento

Cada evento tiene una **ventana temporal óptima** basada en su naturaleza:

| Evento | Código | Ventana (±días) | Días totales | Justificación |
|--------|--------|-----------------|--------------|---------------|
| Baseline diario (actividad normal) | E0 | ±2 | 5 | Contexto pre y post sesión para baseline |
| Volume Explosion                    | E1 | ±2 | 5 | Anticipación y fade tras volumen extremo |
| Gap Up                              | E2 | ±2 | 5 | Setup de gap + continuación inmediata |
| Price Spike Intraday                | E3 | ±1 | 3 | Movimiento intradía puntual |
| Parabolic Move                      | E4 | ±3 | 7 | Run-up multi-día y clímax |
| Breakout ATH / 52w High             | E5 | ±2 | 5 | Ruptura y confirmación |
| Multiple Green Days                 | E6 | ±1 | 3 | Ya es una secuencia multi-día en sí misma |
| First Red Day                       | E7 | ±2 | 5 | Necesitamos el rally previo y el giro rojo |
| Gap Down Violent                    | E8 | ±3 | 7 | Dump + follow-through/rebound |
| Crash Intraday                      | E9 | ±1 | 3 | Colapso intradía puntual |
| First Green Bounce                  | E10| ±3 | 7 | Día de giro tras selloff + confirmación |
| Volume Bounce                       | E11| ±3 | 7 | Volumen capitulando y rebote técnico |

**Beneficios**:
1. ✅ **Precisión quirúrgica**: Cada evento descarga exactamente lo que necesita
2. ✅ **Eficiencia óptima**: No descargamos días innecesarios
3. ✅ **Reproducibilidad**: Resultado idéntico al cálculo del notebook `analisis_universo_completo_E1_E11`
4. ✅ **Escalabilidad**: Preparado para universo completo (10.3M ticker-days, 1.84 TB)

---

## 2. ARQUITECTURA DE LA SOLUCIÓN

### 2.1 Flujo de Datos

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. WATCHLIST COMPLETO E0-E11                                    │
│    processed/watchlist_E0_E11.parquet                           │
│    - ticker: str                                                │
│    - date: date                                                 │
│    - events: List[str]  # lista de códigos evento ['E0','E1']  │
│    - event_count: int   # len(events)                          │
│    - Ejemplo: DCTH 2004-03-11 → ['E0','E1','E4']               │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. CÁLCULO DE MAX_WINDOW POR TICKER-DATE                       │
│    En memoria (downloader modificado)                           │
│    - Para cada ticker-date: extraer eventos                     │
│    - Lookup ventana de cada evento en EVENT_WINDOWS            │
│    - Calcular max_window = max(ventanas de eventos del día)    │
│    - Ejemplo: DCTH 2004-03-11 → max(2, 1, 2) = 2               │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. EXPANSIÓN TEMPORAL DINÁMICA                                  │
│    En memoria (downloader modificado)                           │
│    - Para cada ticker-date con max_window:                      │
│      Generar: [date - max_window, ..., date, ..., date + max_window]│
│    - Ejemplo: DCTH 2004-03-11 (window=2) →                     │
│      [2004-03-09, 03-10, 03-11, 03-12, 03-13]                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4. CONSOLIDACIÓN Y DEDUPLICACIÓN (CRÍTICO)                     │
│    En memoria (downloader modificado)                           │
│    - Agrupar todas las fechas expandidas                        │
│    - Hacer UNIQUE sobre (ticker, download_date)                 │
│    - Resultado: Lista de tareas SIN DUPLICADOS                  │
│    - Ejemplo: Si DCTH tiene E1 el 03-11 y E7 el 03-12:        │
│      Fechas duplicadas [03-10, 03-11, 03-12, 03-13]            │
│      → Se descargan UNA SOLA VEZ                                │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 5. DESCARGA PARALELA CON RESUME                                │
│    ProcessPoolExecutor (6 workers)                              │
│    - Para cada (ticker, date) único:                            │
│      • Check _SUCCESS → skip si existe                          │
│      • Download trades via Polygon API                          │
│      • Save parquet con ZSTD level 2                            │
│      • Write _SUCCESS marker                                    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 6. SALIDA: DATOS DESCARGADOS                                   │
│    raw/polygon/trades/                                          │
│    └── TICKER/                                                  │
│        └── date=YYYY-MM-DD/                                     │
│            ├── trades.parquet (ZSTD compressed)                 │
│            └── _SUCCESS (marker)                                │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Diferencias Clave vs Versión Actual

| Aspecto | Versión Actual (Pilot) | Versión Nueva (Ventana Dinámica) |
|---------|------------------------|----------------------------------|
| **Ventana** | Fija (`--event-window 2`) | Dinámica por evento (E1→2d, E4→3d, etc) |
| **Eventos cubiertos** | Pilot anterior: E1-E11 (sin E0) | Nueva versión: E0-E11 (incluye baseline E0 para todos los días con trading) |
| **Cálculo ventana** | Global para todos | Por ticker-date según eventos detectados |
| **Deduplicación** | Implícita (mismo window) | **Explícita y crítica** (max_window variable) |
| **Reproducibilidad** | Aproximada (~31x expansión) | **Exacta** (10.3M ticker-days del notebook) |
| **Resultado** | 65,907 días (pilot) | 10,297,125 días (universo E1-E11 completo) |
| **Peso** | 11.23 GB | 1.84 TB (E1-E11 solo) / 2.8-3.4 TB (con E0) |

**Por qué importa E0:**
E0 actúa como "baseline diaria": añade días que no eran explosivos pero que igual queremos en el dataset final para entrenar el modelo fuera de solo días locos.
Esto aumenta mucho las tareas totales y el tamaño final (pasamos de ~1.8 TB estimados sin E0 a ~3 TB estimados con E0).

---

## 3. ARCHIVOS A MODIFICAR

### 3.1 Script Principal de Descarga

**Archivo**: `scripts/fase_C_ingesta_tiks/download_trades_optimized.py`

#### Modificaciones Necesarias:

##### A. Agregar Diccionario de Ventanas (línea ~40)

```python
# NUEVO: Ventanas optimizadas por evento
EVENT_WINDOWS = {
    "E0": 2,   # baseline diario
    "E1": 2,   # volume explosion
    "E2": 2,   # gap up
    "E3": 1,   # price spike intraday
    "E4": 3,   # parabolic
    "E5": 2,   # breakout ATH / 52w high
    "E6": 1,   # multiple green days
    "E7": 2,   # first red day
    "E8": 3,   # gap down violent
    "E9": 1,   # crash intraday
    "E10": 3,  # first green bounce
    "E11": 3,  # volume bounce
}
```

**¿Por qué aquí?**:
- Diccionario global al inicio del script
- Fácil de modificar si necesitamos ajustar ventanas
- Documentado con comentarios

##### B. Reemplazar Función `load_info_rich_days()` (líneas 98-147)

**ANTES** (versión actual):
```python
def load_info_rich_days(watchlist_root: Path, dfrom: date, dto: date,
                        allowed_tickers: Optional[set], event_window: int = 1):
    """Lee watchlists y expande con ventana FIJA"""
    out: Dict[str, List[date]] = {}
    for day in (dfrom + timedelta(n) for n in range((dto - dfrom).days + 1)):
        p = watchlist_root / f"date={day.isoformat()}" / "watchlist.parquet"
        df = pl.read_parquet(p)
        # ... aplica event_window fijo para todos ...
        for offset in range(-event_window, event_window + 1):
            expanded_day = day + timedelta(days=offset)
            # ...
```

**DESPUÉS** (nueva versión):
```python
def load_event_days_dynamic_window(
    watchlist_file: Path,
    dfrom: date,
    dto: date,
    allowed_tickers: Optional[set],
) -> list[tuple[str, date]]:
    """
    Lee watchlist E0-E11 completo y calcula las fechas reales que hay que descargar
    aplicando ventana dinámica por tipo de evento y deduplicando ticker+fecha.
    """

    import polars as pl
    from datetime import timedelta

    # 1. Cargar watchlist unificado (E0-E11)
    df_watchlist = pl.read_parquet(watchlist_file)

    # Esperado: ['ticker', 'date', 'events', 'event_count']
    # - 'events' es List[str] con códigos 'E0','E1',...,'E11'

    # 2. Filtrar rango de fechas solicitado
    df_watchlist = df_watchlist.filter(
        (pl.col("date") >= dfrom) &
        (pl.col("date") <= dto)
    )

    # 3. Filtrar tickers si el usuario ha pasado una whitelist
    if allowed_tickers:
        df_watchlist = df_watchlist.filter(
            pl.col("ticker").is_in(list(allowed_tickers))
        )

    # 4. Expandir filas por evento individual
    df_events = df_watchlist.explode("events")

    # 5. Mapear cada evento a su ventana
    df_events = df_events.with_columns([
        pl.col("events").map_dict(EVENT_WINDOWS).alias("window_days")
    ])

    # 6. Calcular la ventana máxima por (ticker, date)
    df_max = (
        df_events
        .group_by(["ticker", "date"])
        .agg([
            pl.col("window_days").max().alias("max_window")
        ])
    )

    # 7. Expandir cada (ticker, date, max_window) en días concretos
    expanded = []
    for row in df_max.iter_rows(named=True):
        ticker = row["ticker"]
        base_day = row["date"]
        w = row["max_window"]

        for off in range(-w, w + 1):
            day_dl = base_day + timedelta(days=off)

            if dfrom <= day_dl <= dto:
                expanded.append((ticker, day_dl))

    # 8. Deduplicar
    unique_downloads = list(set(expanded))

    return unique_downloads
```

**¿Por qué este cambio?**:
1. **Lee watchlist completo** en lugar de watchlists diarios particionados
2. **Calcula max_window dinámico** por ticker-date basado en eventos detectados
3. **Expande con ventana variable** (no fija)
4. **Deduplica explícitamente** antes de devolver tareas

##### C. Modificar `main()` para Usar Nueva Función (líneas 404-426)

**ANTES**:
```python
if args.mode == "watchlists":
    days_by_ticker = load_info_rich_days(
        Path(args.watchlist_root),
        dfrom, dto,
        allowed_tickers,
        args.event_window  # ← Ventana fija
    )
    for t, days in days_by_ticker.items():
        for d in days:
            tasks.append((t, d, d, "watchlists"))
```

**DESPUÉS**:
```python
if args.mode == "watchlists":
    tasks_unique = load_event_days_dynamic_window(
        Path(args.watchlist_file),
        dfrom,
        dto,
        allowed_tickers,
    )

    tasks = []
    for (ticker, download_date) in tasks_unique:
        # nota: start_day y end_day son iguales porque
        # ya expandimos la ventana en load_event_days_dynamic_window
        tasks.append((ticker, download_date, download_date, "watchlists"))

    log(f"Tareas (watchlists): {len(tasks):,} ticker-days únicos "
        f"con ventanas dinámicas E0-E11")
```

**IMPORTANTE**:
- En modo dinámico por evento, `--event-window` queda ignorado.
- El rango temporal viene de `--from`, `--to`.
- La expansión por ventana se deriva de `EVENT_WINDOWS` por evento.

**¿Por qué este cambio?**:
- Elimina parámetro `--event-window` (ya no se usa)
- Usa nuevo parámetro `--watchlist-file` (archivo único vs directorio)
- Tareas ya vienen deduplicadas (no hay duplicados)

##### D. Modificar Argumentos CLI (líneas 349-365)

**AGREGAR**:
```python
ap.add_argument("--watchlist-file",
                help="Archivo watchlist completo E0-E11 (ej: processed/watchlist_E0_E11.parquet)")
```

**DEPRECAR** (mantener por compatibilidad, pero no usar):
```python
ap.add_argument("--event-window", type=int, default=None,
                help="DEPRECADO: Ahora se usan ventanas dinámicas por evento")
```

**¿Por qué?**:
- `--watchlist-file`: Apunta al parquet completo (no directorio particionado)
- `--event-window`: Mantener por retrocompatibilidad, pero ignorar en modo dinámico

---

### 3.2 Script de Generación de Watchlist E0-E11

**Archivo NUEVO**: `scripts/fase_E_Event Detectors E1, E4, E7, E8/generate_watchlist_E0_E11.py`

#### ¿Por qué necesitamos este script?

**Situación actual**:
- Tenemos `watchlist_E1_E11.parquet` (solo E1-E11)
- **NO tenemos E0** (Daily OHLCV baseline) integrado

**Solución**:
Crear script que **fusiona**:
1. Eventos E1-E11 existentes (`watchlist_E1_E11.parquet`)
2. Eventos E0 generados desde daily OHLCV (`processed/daily_ohlcv/`)

#### Contenido del Script:

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
generate_watchlist_E0_E11.py

Genera watchlist completo E0-E11 fusionando:
- E0: Baseline Daily OHLCV (todos los días con trading activity)
- E1-E11: Eventos detectados existentes

Output:
  processed/watchlist_E0_E11.parquet

Columns:
  - ticker: str
  - date: date
  - events: list[str]  # Ej: ['E0', 'E1', 'E4']
  - event_count: int
"""

import polars as pl
from pathlib import Path

def generate_E0_baseline():
    """
    Genera los eventos E0 para todos los días con trading activity (>0 volumen).
    Salida:
      ticker, date, events=['E0'], event_count=1
    """
    ohlcv_root = Path('processed/daily_ohlcv')

    df_ohlcv = pl.read_parquet(ohlcv_root / '*.parquet')

    df_E0 = (
        df_ohlcv
        .filter(pl.col('volume') > 0)
        .select([
            pl.col('ticker'),
            pl.col('trading_day').alias('date'),
            pl.lit(['E0']).alias('events'),
        ])
        .with_columns([
            pl.lit(1).alias('event_count')
        ])
    )

    return df_E0

def load_E1_E11_events():
    """Carga eventos E1-E11 existentes"""
    return pl.read_parquet('processed/watchlist_E1_E11.parquet')

def merge_E0_E1_E11():
    """Fusiona E0 con E1-E11"""
    df_E0 = generate_E0_baseline()
    df_E1_E11 = load_E1_E11_events()

    # Union y consolidación por ticker-date
    df_all = pl.concat([df_E0, df_E1_E11])

    # Agrupar eventos por ticker-date
    df_merged = (
        df_all
        .group_by(['ticker', 'date'])
        .agg([
            pl.col('events').flatten().unique().alias('events'),
        ])
        .with_columns([
            pl.col('events').list.len().alias('event_count')
        ])
    )

    return df_merged

if __name__ == '__main__':
    print('Generando watchlist E0-E11...')
    df_watchlist = merge_E0_E1_E11()

    output_file = Path('processed/watchlist_E0_E11.parquet')
    df_watchlist.write_parquet(output_file)

    print(f'✅ Watchlist generado: {output_file}')
    print(f'   Total ticker-dates: {len(df_watchlist):,}')
    print(f'   Tickers únicos: {df_watchlist["ticker"].n_unique():,}')
    print(f'   Rango fechas: {df_watchlist["date"].min()} → {df_watchlist["date"].max()}')
```

**¿Por qué necesitamos este script?**:
1. **Completitud**: E0 es la baseline (todos los días con trading)
2. **Fusión inteligente**: Días con E0+E1 se consolidan correctamente
3. **Output único**: `watchlist_E0_E11.parquet` listo para downloader

---

## 4. DATOS GENERADOS

### 4.1 Watchlist Completo E0-E11

**Archivo**: `processed/watchlist_E0_E11.parquet`

**Estructura**:
```python
Columnas: ['ticker', 'date', 'events', 'event_count']

Ejemplo 1 (solo E0):
{
  'ticker': 'AAPL',
  'date': date(2020, 3, 16),
  'events': ['E0'],
  'event_count': 1
}

Ejemplo 2 (E0 + múltiples eventos):
{
  'ticker': 'DCTH',
  'date': date(2004, 3, 11),
  'events': ['E0', 'E1', 'E3', 'E5'],
  'event_count': 4
}
```

**Generado por**: `generate_watchlist_E0_E11.py`

**Estadísticas esperadas**:
- Ticker-dates: **Mucho mayor** que 2.9M (E0 añade todos los días con trading)
- Eventos totales: **Mucho mayor** que 3.3M
- Tickers únicos: ~8,546 (igual que E1-E11)

### 4.2 Tareas de Descarga Consolidadas

**Ubicación**: Solo en memoria (dentro del downloader)

**Formato**:
```python
List[Tuple[str, date]]  # [(ticker, download_date), ...]

Ejemplo:
[
  ('DCTH', date(2004, 3, 9)),   # Necesario por E1 en 03-11 (window=2)
  ('DCTH', date(2004, 3, 10)),  # Idem
  ('DCTH', date(2004, 3, 11)),  # Día del evento
  ('DCTH', date(2004, 3, 12)),  # Idem
  ('DCTH', date(2004, 3, 13)),  # Idem
  ('ASTI', date(2006, 8, 10)),  # E4 Parabolic (window=3)
  # ... 10,297,125 tareas únicas ...
]
```

**Características**:
- ✅ **Sin duplicados**: Cada (ticker, date) aparece UNA sola vez
- ✅ **Ordenado**: Por ticker → fecha (mejor para cache)
- ✅ **Reproducible**: Idéntico al cálculo del notebook

### 4.3 Datos Descargados

**Directorio**: `raw/polygon/trades/`

**Estructura**:
```
raw/polygon/trades/
├── DCTH/
│   ├── date=2004-03-09/
│   │   ├── trades.parquet       # Tick data ZSTD compressed
│   │   └── _SUCCESS              # Resume marker
│   ├── date=2004-03-10/
│   │   ├── trades.parquet
│   │   └── _SUCCESS
│   ├── date=2004-03-11/         # Día con eventos E0+E1+E3+E5
│   │   ├── trades.parquet
│   │   └── _SUCCESS
│   └── ...
├── ASTI/
│   ├── date=2006-08-10/
│   │   ├── trades.parquet
│   │   └── _SUCCESS
│   └── ...
└── ...
```

**Contenido de `trades.parquet`**:
```python
Columnas:
- t_raw: int64          # Timestamp raw (preservado sin conversión)
- t_unit: str           # Time unit ('ns', 'us', 'ms')
- p: float64            # Price
- s: int64              # Size
- c: list[str]          # Conditions
- exchange: str         # Exchange code
- id: str               # Trade ID
- ...
```

**Características**:
- Compresión: ZSTD level 2
- Timestamp preservado como Int64 (evita bug "year 52XXX")
- Resume capability con `_SUCCESS` markers

---

## 5. ORDEN DE EJECUCIÓN

### Fase 1: Preparación de Datos

#### Paso 1.1: Generar Watchlist E0-E11
```bash
python scripts/fase_E_Event\ Detectors\ E1,\ E4,\ E7,\ E8/generate_watchlist_E0_E11.py
```

**Output esperado**:
```
Generando watchlist E0-E11...
✅ Watchlist generado: processed/watchlist_E0_E11.parquet
   Total ticker-dates: [se calculará al ejecutar]
   Tickers únicos: 8,546
   Rango fechas: 2004-01-02 → 2025-10-24
```

**Nota sobre Output esperado**:
- Archivo: processed/watchlist_E0_E11.parquet
- Columnas: ['ticker', 'date', 'events', 'event_count']
- 'events' es lista de códigos ['E0','E1',...,'E11']
- Incluye baseline E0 (todas las sesiones con volumen > 0)
- Este archivo es el ÚNICO input que usará el downloader

**Validar**:
```python
import polars as pl

df = pl.read_parquet('processed/watchlist_E0_E11.parquet')
print(f"Shape: {df.shape}")
print(f"Columnas: {df.columns}")
print(f"Sample con E0 solo: {df.filter(pl.col('event_count') == 1).head(3)}")
print(f"Sample con E0+eventos: {df.filter(pl.col('event_count') > 1).head(3)}")
```

#### Paso 1.2: Modificar Downloader
```bash
# Backup versión actual
cp scripts/fase_C_ingesta_tiks/download_trades_optimized.py \
   scripts/fase_C_ingesta_tiks/download_trades_optimized_v1_fixed_window.py

# Editar con ventanas dinámicas (según sección 3.1)
code scripts/fase_C_ingesta_tiks/download_trades_optimized.py
```

**Cambios críticos**:
1. Agregar `EVENT_WINDOWS` dict
2. Reemplazar `load_info_rich_days()` con `load_event_days_dynamic_window()`
3. Modificar `main()` para usar `--watchlist-file`
4. Actualizar argumentos CLI

#### Paso 1.3: Validar Cálculo de Tareas
```python
# Test script para validar cálculo
python -c "
from scripts.fase_C_ingesta_tiks.download_trades_optimized import load_event_days_dynamic_window
from pathlib import Path
from datetime import date

tasks = load_event_days_dynamic_window(
    Path('processed/watchlist_E0_E11.parquet'),
    date(2004, 1, 1),
    date(2025, 10, 24),
    None  # Sin filtro de tickers
)

print(f'Total tareas únicas: {len(tasks):,}')
print(f'Esperado del notebook: 10,297,125')
print(f'Match: {len(tasks) == 10_297_125}')
"
```

**Output esperado**:
```
Total tareas únicas: 10,297,125
Esperado del notebook: 10,297,125
Match: True ✅
```

---

### Fase 2: Descarga Pilot Expandido (Validación)

#### Paso 2.1: Pilot con 50 Tickers (Ventanas Dinámicas)
```bash
python scripts/fase_C_ingesta_tiks/download_trades_optimized.py \
  --outdir raw/polygon/trades \
  --from 2004-01-01 \
  --to 2025-10-24 \
  --mode watchlists \
  --watchlist-file processed/watchlist_E0_E11_pilot50.parquet \
  --page-limit 50000 \
  --rate-limit 0.12 \
  --workers 6 \
  --resume
```

**¿Por qué pilot primero?**:
- Validar que ventanas dinámicas funcionan correctamente
- Comparar peso real vs estimación (0.187 MB/ticker-day)
- Probar resume capability antes de descarga masiva

**Output esperado**:
```
Tareas (watchlists): ~150,000 ticker-days únicos con ventanas dinámicas E0-E11
Tickers: 50 | Tareas: ~150,000 | Workers: 6 | Mode: watchlists
...
FIN. Elapsed: ~8.3 horas | Total OK: ~150,000 / Total ERR: 0
```

#### Paso 2.2: Validar Pilot con Notebook
```bash
jupyter notebook 01_DayBook/fase_01/F_Event_detectors_E1_E11/notebooks/validacion_pilot50_ventanas_dinamicas.ipynb
```

**Validaciones clave**:
1. ✅ Peso total coincide con estimación (0.187 MB/ticker-day)
2. ✅ Ventanas correctas por evento (E3→3 días, E4→7 días, etc)
3. ✅ Sin duplicados (cada ticker-date descargado una sola vez)
4. ✅ Resume funciona correctamente

---

### Fase 3: Descarga Completa Universo E0-E11

#### Paso 3.1: Lanzar Descarga Masiva
```bash
# ADVERTENCIA: Esta descarga tomará ~57 horas (~2.4 días)
# Asegurar espacio en disco: ~1.84 TB disponible

python scripts/fase_C_ingesta_tiks/download_trades_optimized.py \
  --outdir raw/polygon/trades \
  --from 2004-01-01 \
  --to 2025-10-24 \
  --mode watchlists \
  --watchlist-file processed/watchlist_E0_E11.parquet \
  --page-limit 50000 \
  --rate-limit 0.12 \
  --workers 6 \
  --resume
```

**Output esperado**:
```
Tareas (watchlists): 10,297,125 ticker-days únicos con ventanas dinámicas E0-E11
Tickers: 8,546 | Tareas: 10,297,125 | Workers: 6 | Mode: watchlists
...
[Ejecución ~57 horas]
...
FIN. Elapsed: 3426.7 min | Total OK: 10,297,125 / Total ERR: <minimal>
```

#### Paso 3.2: Monitoreo Durante Descarga
```bash
# Terminal 1: Monitor de progreso (cada 10 min)
watch -n 600 'python -c "
from pathlib import Path
import time

trades_root = Path(\"raw/polygon/trades\")
total_success = len(list(trades_root.rglob(\"_SUCCESS\")))
total_parquet = len(list(trades_root.rglob(\"trades.parquet\")))

print(f\"Archivos descargados: {total_parquet:,}\")
print(f\"Success markers: {total_success:,}\")
print(f\"Progreso: {(total_parquet / 10_297_125) * 100:.2f}%\")
"'

# Terminal 2: Monitor de disco
watch -n 300 'df -h | grep -E "Filesystem|raw"'
```

#### Paso 3.3: Validación Post-Descarga
```bash
jupyter notebook 01_DayBook/fase_01/F_Event_detectors_E1_E11/notebooks/validacion_universo_completo_E0_E11.ipynb
```

**Validaciones exhaustivas**:
1. ✅ Total archivos: 10,297,125 trades.parquet
2. ✅ Total _SUCCESS: 10,297,125
3. ✅ Peso total: ~1.84 TB (±5% tolerancia)
4. ✅ Integridad: Sample 1,000 archivos → 0% corruptos
5. ✅ Cobertura temporal: 2004-01-02 → 2025-10-24
6. ✅ Ventanas correctas: Spot check 100 ticker-dates

---

## 6. MÉTRICAS Y ESTIMACIONES

### 6.1 Peso Total (Métrica Real)

**Baseline (del notebook `analisis_universo_completo_E1_E11`)**:
- Ticker-days únicos: **10,297,125**
- MB por ticker-day: **0.187** (medido en pilot ultra-light)
- Peso total: **1.84 TB**

**Con E0 integrado (estimación conservadora)**:
- E0 añade ~50-80% más días (baseline trading days)
- Ticker-days únicos estimados: **15-18M**
- Peso total estimado: **2.8-3.4 TB**

**Nota**: Ejecutar `generate_watchlist_E0_E11.py` dará cifra exacta.

🔎 **Interpretación de capacidad**:

- **Universo E1-E11 (solo días con eventos duros)**:
  • 10.3M ticker-days únicos
  • ~1.84 TB estimados
  • ~57 horas de descarga

- **Universo E0-E11 (incluye baseline E0 = todos los días con trading)**:
  • ~15M-18M ticker-days únicos (estimado previo a medición real)
  • ~2.8-3.4 TB
  • ~3.5-4.2 días de descarga continua

Esto es la foto real de "descargamos TODO el mercado 2004-2025 con ventanas dinámicas por evento".

### 6.2 Tiempo de Descarga

**Configuración**:
- Workers: 6
- Rate limit: 0.12s/request
- Throughput: 50 requests/segundo = 180,000 requests/hora

**Estimaciones**:

| Universo | Ticker-days | Horas | Días |
|----------|-------------|-------|------|
| E1-E11 (sin E0) | 10.3M | 57.2 | 2.4 |
| E0-E11 (conservador) | 15.0M | 83.3 | 3.5 |
| E0-E11 (optimista) | 18.0M | 100.0 | 4.2 |

**Estrategia de descarga**:
1. Lanzar viernes noche → termina martes mañana
2. Resume activado → puede pausar/reanudar sin pérdida
3. Monitor cada 6 horas para detectar errores

### 6.3 Espacio en Disco

**Mínimo necesario**:
- Datos: 2.8-3.4 TB
- Buffer (errores, logs): 0.2 TB
- **Total recomendado**: 4 TB disponible

**Estrategia de almacenamiento**:
- Opción A: 2 discos de 2TB (RAID 0 o directorios separados)
- Opción B: 1 disco de 4TB
- Opción C: Cloud storage (AWS S3, GCS) con lifecycle policies

---

## 7. VALIDACIONES Y TESTS

### 7.1 Test Unitario: Cálculo de Max Window

```python
# tests/test_event_windows.py

def test_max_window_calculation():
    """Validar que max_window se calcula correctamente"""
    from download_trades_optimized import EVENT_WINDOWS

    # Caso 1: Eventos con ventana homogénea
    events = ['E1_VolExplosion', 'E2_GapUp', 'E5_BreakoutATH']
    max_window = max(EVENT_WINDOWS[e] for e in events)
    assert max_window == 2, "Todos tienen window=2"

    # Caso 2: Eventos con ventana heterogénea
    events = ['E3_PriceSpikeIntraday', 'E4_Parabolic', 'E10_FirstGreenBounce']
    max_window = max(EVENT_WINDOWS[e] for e in events)
    assert max_window == 3, "E4 y E10 tienen window=3"

    # Caso 3: Evento único con ventana mínima
    events = ['E9_CrashIntraday']
    max_window = max(EVENT_WINDOWS[e] for e in events)
    assert max_window == 1, "E9 tiene window=1"
```

### 7.2 Test de Integración: Deduplicación

```python
def test_deduplication():
    """Validar que fechas duplicadas se consolidan correctamente"""
    from download_trades_optimized import load_event_days_dynamic_window
    from pathlib import Path
    from datetime import date

    # Crear watchlist test con eventos solapados
    import polars as pl

    df_test = pl.DataFrame({
        'ticker': ['TEST'] * 3,
        'date': [date(2020, 3, 10), date(2020, 3, 11), date(2020, 3, 12)],
        'events': [
            ['E1_VolExplosion'],       # window=2: 03-08 a 03-12
            ['E4_Parabolic'],          # window=3: 03-08 a 03-14
            ['E10_FirstGreenBounce']   # window=3: 03-09 a 03-15
        ],
        'event_count': [1, 1, 1]
    })

    df_test.write_parquet('/tmp/test_watchlist.parquet')

    # Calcular tareas
    tasks = load_event_days_dynamic_window(
        Path('/tmp/test_watchlist.parquet'),
        date(2020, 3, 1),
        date(2020, 3, 31),
        None
    )

    # Filtrar ticker TEST
    test_tasks = [(t, d) for (t, d) in tasks if t == 'TEST']
    test_dates = sorted([d for (t, d) in test_tasks])

    # Validar: debe tener fechas 03-08 a 03-15 (8 días únicos)
    expected_dates = [date(2020, 3, i) for i in range(8, 16)]
    assert test_dates == expected_dates, "Fechas consolidadas incorrectamente"

    # Validar: no hay duplicados
    assert len(test_dates) == len(set(test_dates)), "Hay fechas duplicadas"
```

### 7.3 Test de Regresión: Reproducibilidad vs Notebook

```python
def test_reproducibility_vs_notebook():
    """Validar que downloader genera mismas tareas que notebook"""
    from download_trades_optimized import load_event_days_dynamic_window
    from pathlib import Path
    from datetime import date

    # Cargar resultado del notebook
    df_notebook = pl.read_parquet('01_DayBook/.../universo_completo_E1_E11_analisis.parquet')
    notebook_tasks = set(
        (row['ticker'], row['download_date'])
        for row in df_notebook.iter_rows(named=True)
    )

    # Calcular con downloader
    downloader_tasks = set(load_event_days_dynamic_window(
        Path('processed/watchlist_E1_E11.parquet'),
        date(2004, 1, 1),
        date(2025, 10, 24),
        None
    ))

    # Comparar
    assert len(notebook_tasks) == len(downloader_tasks), "Número de tareas difiere"
    assert notebook_tasks == downloader_tasks, "Tareas no son idénticas"

    print(f"✅ Reproducibilidad verificada: {len(notebook_tasks):,} tareas idénticas")
```

---

## 8. CONTINGENCIAS Y TROUBLESHOOTING

### 8.1 Problemas Comunes

#### Problema 1: Disco Lleno Durante Descarga

**Síntomas**:
```
OSError: [Errno 28] No space left on device
```

**Solución**:
1. Pausar descarga (Ctrl+C)
2. Resume está activado → no se pierde progreso
3. Liberar espacio o añadir disco
4. Relanzar con `--resume`

**Prevención**:
```bash
# Monitor continuo de espacio
watch -n 300 'df -h | grep -E "Filesystem|raw"'
```

#### Problema 2: Rate Limit Exceeded (429)

**Síntomas**:
```
429 Too Many Requests -> sleep 60s
```

**Solución automática**: El downloader tiene backoff automático

**Ajuste manual** (si persiste):
```bash
# Reducir workers o aumentar rate-limit
--workers 4 --rate-limit 0.15  # Más conservador
```

#### Problema 3: Tareas No Match Notebook

**Síntomas**:
```python
test_reproducibility_vs_notebook() FAILED
Expected: 10,297,125
Got: 10,150,000
```

**Diagnóstico**:
```python
# Comparar diferencias
missing = notebook_tasks - downloader_tasks
extra = downloader_tasks - notebook_tasks

print(f"Missing: {len(missing):,}")
print(f"Extra: {len(extra):,}")
print(f"Sample missing: {list(missing)[:10]}")
```

**Causas comunes**:
- Fechas futuras no filtradas correctamente
- Filtro `allowed_tickers` aplicado incorrectamente
- Bug en cálculo de `max_window`

### 8.2 Rollback Plan

Si la implementación de ventanas dinámicas falla, rollback a versión anterior:

```bash
# Restaurar versión con ventana fija
cp scripts/fase_C_ingesta_tiks/download_trades_optimized_v1_fixed_window.py \
   scripts/fase_C_ingesta_tiks/download_trades_optimized.py

# Relanzar con ventana fija
python scripts/fase_C_ingesta_tiks/download_trades_optimized.py \
  --event-window 2 \
  --watchlist-root processed/universe/multi_event/daily \
  ...
```

---

## 9. PRÓXIMOS PASOS DESPUÉS DE DESCARGA

Una vez completada la descarga del universo E0-E11:

### 9.1 Construcción de Bars

```bash
python scripts/fase_D_creando_DIB_VIB/build_bars_from_trades.py \
  --trades-root raw/polygon/trades \
  --outdir processed/bars \
  --bar-type dollar_imbalance \
  --target-usd 300000 \
  --parallel 8 \
  --resume
```

**Output**: `processed/bars/{ticker}/date={YYYY-MM-DD}/bars.parquet`

### 9.2 Feature Engineering

```bash
python scripts/fase_D_creando_DIB_VIB/compute_features.py \
  --bars-root processed/bars \
  --outdir processed/features \
  --parallel 8
```

**Output**: `processed/features/{ticker}/date={YYYY-MM-DD}/features.parquet`

### 9.3 Triple Barrier Labeling

```bash
python scripts/fase_D_creando_DIB_VIB/triple_barrier_labels.py \
  --bars-root processed/bars \
  --features-root processed/features \
  --outdir processed/labels \
  --parallel 8
```

**Output**: `processed/labels/{ticker}/date={YYYY-MM-DD}/labels.parquet`

### 9.4 ML Dataset Builder

```bash
python scripts/fase_D_creando_DIB_VIB/build_ml_dataset.py \
  --features-root processed/features \
  --labels-root processed/labels \
  --outdir processed/datasets \
  --train-ratio 0.7 \
  --val-ratio 0.15 \
  --test-ratio 0.15
```

**Output**:
- `processed/datasets/train.parquet`
- `processed/datasets/val.parquet`
- `processed/datasets/test.parquet`

---

## 10. RESUMEN EJECUTIVO

### ¿Qué estamos haciendo?

**Implementar descarga masiva con ventanas temporales dinámicas por tipo de evento**, reemplazando la ventana fija `--event-window 2` actual.

### ¿Por qué?

1. **Precisión**: Cada evento necesita diferente contexto temporal (E3→1d, E4→3d)
2. **Eficiencia**: No descargamos días innecesarios
3. **Reproducibilidad**: Resultado idéntico al notebook `analisis_universo_completo_E1_E11`
4. **Escalabilidad**: Preparado para universo completo (10.3M ticker-days, 1.84 TB)

### ¿Cuánto esfuerzo?

**Desarrollo**:
- Modificar 1 archivo principal: `download_trades_optimized.py` (~200 líneas cambiadas)
- Crear 1 script nuevo: `generate_watchlist_E0_E11.py` (~80 líneas)
- Crear 3 tests: unitario, integración, regresión (~150 líneas)
- **Total**: ~4-6 horas de desarrollo + testing

**Ejecución**:
- Pilot 50 tickers: ~8 horas
- Universo completo: ~57-100 horas (2.4-4.2 días)

### ¿Cuándo ejecutar?

**Timeline recomendado**:
1. **Día 1 (4h)**: Desarrollo + tests + pilot 50 tickers
2. **Día 2 (2h)**: Validación pilot + ajustes
3. **Día 3-6 (96h)**: Descarga masiva universo completo (desatendido)
4. **Día 7 (4h)**: Validación final + documentación

**Total**: 7 días (10h trabajo activo, 96h descarga desatendida)

### ¿Riesgos?

**Bajo riesgo**:
- ✅ Arquitectura probada (pilot ultra-light funcionó perfectamente)
- ✅ Resume capability (puede pausar/reanudar sin pérdida)
- ✅ Rollback plan (versión anterior respaldada)
- ✅ Tests de regresión (validación automática vs notebook)

**Mitigaciones**:
- Pilot primero (validar antes de masivo)
- Monitoreo continuo (espacio disco, progreso)
- Backup incremental (durante descarga)

---

## 11. DECISIÓN REQUERIDA

**¿Proceder con implementación de ventanas dinámicas?**

**Opción A** (Recomendado): ✅ SÍ
- Implementar según esta arquitectura
- Ejecutar pilot 50 tickers primero
- Si validación OK → lanzar descarga masiva

**Esta es la ruta aprobada**:
1. Generar watchlist_E0_E11.parquet
2. Modificar downloader a ventanas dinámicas por evento usando EVENT_WINDOWS y `events` = ['E0','E1',...]
3. Pilot 50 tickers para validación de tamaño/ritmo
4. Luego descarga masiva con resume activado

**Opción B**: ❌ NO (mantener status quo)
- Seguir con `--event-window 2` fijo
- Aceptar ineficiencia (~30% datos innecesarios)
- Posible insuficiencia para E4, E10, E11 (necesitan ±3d)

**Opción C**: 🟡 HÍBRIDO
- Implementar ventanas dinámicas
- Lanzar solo pilot 100-200 tickers
- Posponer descarga masiva hasta validar pipeline completo (bars → features → labels)

---

**Documento generado**: 2025-10-29
**Autor**: Claude (basado en análisis técnico exhaustivo)
**Versión**: 2.0 (Revisado con códigos cortos E0-E11)
**Estado**: Especificación oficial aprobada para implementación
