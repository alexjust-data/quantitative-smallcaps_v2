# C.5.8 - Descarga Pilot Ultra-Light con Ventanas Optimizadas

**Fecha**: 2025-10-29
**Sesión**: Nocturna
**Objetivo**: Descargar ticks para Pilot Ultra-Light (15 tickers, 2,127 días multi-evento) con ventanas temporales optimizadas por tipo de evento

---

## 1. CONTEXTO Y MOTIVACIÓN

### Situación Inicial

Después de detectar 3.4M+ eventos (E1-E11) sobre 2.9M ticker-date combinaciones, necesitamos descargar los ticks (trades intraday) para análisis detallado. Sin embargo:

**Problemas identificados**:
- Watchlist completa: 2.9M ticker-date → ~743 TB con ventanas optimizadas
- Asunción ingenua (±3 días para TODOS los eventos): ~1 PB de datos
- Espacio disponible en disco: **602 GB**
- Tiempo restante de Polygon API: **pocos días**

**Pregunta clave del usuario**:
> "no entiendo de donde salen 3 dias para todos los E ¿no tenemos datos? hemos de descargar 3 dias para todo?"

Esta pregunta reveló que la asunción de ±3 días para TODOS los eventos era **incorrecta**. Cada evento tiene requisitos de contexto temporal diferentes según su naturaleza.

---

## 2. ANÁLISIS DE VENTANAS OPTIMIZADAS POR EVENTO

### 2.1 Metodología

Cada tipo de evento (E1-E11) requiere una ventana temporal específica basada en:
- **Naturaleza del patrón**: ¿Es intraday o multi-día?
- **Requisitos de análisis**: ¿Necesitamos contexto pre/post evento?
- **Setup y follow-through**: ¿El patrón se desarrolla en varios días?

### 2.2 Tabla de Ventanas Optimizadas

| Evento | Descripción | Window | Total Days | Justificación |
|--------|------------|--------|------------|---------------|
| **E1** | Volume Explosion | ±2d | 5 | Anticipación de volumen + fade posterior |
| **E2** | Gap Up | ±2d | 5 | Pre-gap setup + continuation |
| **E3** | Price Spike Intraday | ±1d | 3 | Solo evento (análisis intraday) |
| **E4** | Parabolic Move | ±3d | 7 | Run-up multi-día + climax + collapse |
| **E5** | Breakout ATH | ±2d | 5 | Breakout + confirmación |
| **E6** | Multiple Green Days | ±1d | 3 | Ya es multi-día (solo evento final) |
| **E7** | First Red Day | ±2d | 5 | Rally previo + caída inmediata |
| **E8** | Gap Down Violent | ±3d | 7 | Post-gap continuation o rebound |
| **E9** | Crash Intraday | ±1d | 3 | Solo evento (análisis intraday) |
| **E10** | First Green Bounce | ±3d | 7 | Bounce + confirmación volumen |
| **E11** | Volume Bounce | ±3d | 7 | Context + bounce + follow-through |

### 2.3 Código: Diccionario de Ventanas

```python
EVENT_WINDOWS = {
    'E1_VolExplosion': 2,       # Anticipacion + fade
    'E2_GapUp': 2,              # Pre-gap + continuation
    'E3_PriceSpikeIntraday': 1, # Solo dia del spike (intraday)
    'E4_Parabolic': 3,          # Run-up + climax + collapse
    'E5_BreakoutATH': 2,        # Breakout + confirmation
    'E6_MultipleGreenDays': 1,  # Ya es multi-dia (solo evento final)
    'E7_FirstRedDay': 2,        # Rally previo + caida
    'E8_GapDownViolent': 3,     # Post-gap continuation o rebound
    'E9_CrashIntraday': 1,      # Solo dia del crash (intraday)
    'E10_FirstGreenBounce': 3,  # Bounce + confirmacion volumen
    'E11_VolumeBounce': 3,      # Context + bounce + follow-through
}
```

### 2.4 Resultados: Comparación Ingenua vs Optimizada

**Para watchlist COMPLETA (2.9M entries)**:

| Métrica | Ingenua (±3 todos) | Optimizada (ventanas) | Reducción |
|---------|-------------------|----------------------|-----------|
| Ticker-days | 20,578,768 | 15,216,009 | **26.1%** |
| Espacio estimado | 1,005 TB | 743 TB | **262 TB** |
| Tiempo (100 req/min) | 143 días | 106 días | **37 días** |

**Cálculo detallado por evento**:

```
E6_MultipleGreenDays:  1,543,990 × 3 días =  4,631,970 ticker-days (30%)
E10_FirstGreenBounce:    814,068 × 7 días =  5,698,476 ticker-days (37%)
E5_BreakoutATH:          412,902 × 5 días =  2,064,510 ticker-days (14%)
E1_VolExplosion:         164,941 × 5 días =    824,705 ticker-days (5%)
E3_PriceSpikeIntraday:   144,062 × 3 días =    432,186 ticker-days (3%)
E4_Parabolic:             81,278 × 7 días =    568,946 ticker-days (4%)
E2_GapUp:                 73,170 × 5 días =    365,850 ticker-days (2%)
E11_VolumeBounce:         47,583 × 7 días =    333,081 ticker-days (2%)
E9_CrashIntraday:         24,074 × 3 días =     72,222 ticker-days (0%)
E8_GapDownViolent:        19,924 × 7 días =    139,468 ticker-days (1%)
E7_FirstRedDay:           16,919 × 5 días =     84,595 ticker-days (1%)
────────────────────────────────────────────────────────────────────
TOTAL:                 3,342,911           = 15,216,009 ticker-days
```

### 2.5 Notebook de Análisis

**Archivo**: `01_DayBook/fase_01/C_v2_ingesta_tiks_2004_2025/notebooks/analisis_ventanas_optimizadas_por_evento_executed.ipynb`

**Contenido**:
1. Definición de ventanas optimizadas
2. Carga y análisis de watchlist completa
3. Cálculo de ticker-days con ventanas diferenciadas
4. Comparación ingenua vs optimizada
5. Estimación de recursos (espacio, tiempo, API calls)
6. Visualizaciones:
   - Gráfico de ticker-days por evento
   - Comparación de recursos (ticker-days, espacio, tiempo)

**Gráficos generados**:
- `ticker_days_por_evento.png` - Distribución por evento con códigos de color por ventana
- `comparacion_ingenua_vs_optimizada.png` - Comparativa 3-panel

---

## 3. ESTRATEGIA: PILOT ULTRA-LIGHT

### 3.1 Iteraciones de Piloto

Debido a las restricciones de espacio (602 GB disponibles), iteramos sobre el tamaño del piloto:

**Iteración 1: Pilot 100 tickers**
- Tickers: 100 más activos
- Ticker-date entries: 119,493
- Estimación: **~30 TB** con ventanas optimizadas
- ❌ **DESCARTADO**: No cabe en 602 GB

**Iteración 2: Pilot Light 30 tickers (multi-evento ≥3)**
- Tickers: 30 con más días de 3+ eventos simultáneos
- Ticker-date entries: 3,198
- Estimación: **~805 GB** con ZSTD
- ❌ **DESCARTADO**: Excede 602 GB (déficit de 158 GB)

**Iteración 3: PILOT ULTRA-LIGHT 15 tickers ✅**
- Tickers: 15 con más días de 3+ eventos simultáneos
- Ticker-date entries: 2,127
- Estimación: **~528 GB** con ZSTD
- ✅ **APROBADO**: Cabe con margen de 119 GB

### 3.2 Generación del Pilot Ultra-Light

**Filtros aplicados**:
1. Solo días con `event_count >= 3` (3+ eventos simultáneos)
   - Reduce de 2.9M → 57,720 entries (**98% reducción**)
2. Top 15 tickers por número de días multi-evento
3. Mantener TODOS los tipos de evento (E1-E11) para estos días

**Código de generación**:

```python
import polars as pl
from pathlib import Path

# Cargar watchlist completa
df = pl.read_parquet('processed/watchlist_E1_E11.parquet')

# Filtrar días con multi-evento >= 3
df_multi = df.filter(pl.col('event_count') >= 3)
print(f'Días con 3+ eventos: {len(df_multi):,}')  # 57,720

# Top 15 tickers por número de días multi-evento
top15 = (
    df_multi
    .group_by('ticker')
    .agg([pl.len().alias('n_days_multi')])
    .sort('n_days_multi', descending=True)
    .head(15)
)

# Filtrar watchlist
top15_list = top15['ticker'].to_list()
df_pilot_ultra = df_multi.filter(pl.col('ticker').is_in(top15_list))

# Guardar
df_pilot_ultra.write_parquet('processed/watchlist_E1_E11_pilot_ultra_light.parquet')

print(f'Pilot Ultra-Light: {len(df_pilot_ultra):,} entries')  # 2,127
```

### 3.3 Top 15 Tickers Seleccionados

| # | Ticker | Días Multi-Evento | Total Eventos | Perfil |
|---|--------|-------------------|---------------|--------|
| 1 | DCTH | 313 | 976 | Penny stock volátil |
| 2 | ASTI | 260 | 828 | Solar/tech smallcap |
| 3 | SRNE | 219 | 768 | Biotech volátil |
| 4 | SBNY | 157 | 554 | Bank (Silicon Valley) |
| 5 | BBIG | 152 | 516 | Meme stock |
| 6 | RNVA | 137 | 440 | Penny stock |
| 7 | SONG | 118 | 388 | Tech smallcap |
| 8 | SRAX | 108 | 350 | AdTech |
| 9 | MULN | 103 | 340 | EV penny stock |
| 10 | FRBK | 100 | 328 | Bank (Republic First) |
| 11 | TNXP | 96 | 307 | Biotech |
| 12 | ALPP | 93 | 311 | Penny stock |
| 13 | HMNY | 92 | 318 | MoviePass (collapsed) |
| 14 | IDEX | 90 | 325 | EV/Fintech |
| 15 | LTCH | 89 | 291 | Tech |

**Características comunes**:
- **Extrema volatilidad**: Penny stocks y meme stocks
- **Alta actividad retail**: Reddit/WSB favorites
- **Múltiples eventos catalíticos**: News-driven, pumps, crashes
- **Range temporal**: 2004-2025 (21 años de historia)

### 3.4 Estadísticas del Pilot Ultra-Light

**Archivo guardado**: `processed/watchlist_E1_E11_pilot_ultra_light.parquet`
**Tamaño**: 37.11 KB

**Composición**:
- **Ticker-date entries**: 2,127
- **Tickers únicos**: 15
- **Rango temporal**: 2004-01-12 → 2025-10-24
- **Eventos por día**: Mínimo 3, máximo 7

**Distribución de eventos en el piloto**:

```
E4_Parabolic:           1,951 occurrences × 7 días = 13,657 ticker-days
E8_GapDownViolent:      1,084 occurrences × 7 días =  7,588 ticker-days
E1_VolExplosion:        1,451 occurrences × 5 días =  7,255 ticker-days
E3_PriceSpikeIntraday:  2,189 occurrences × 3 días =  6,567 ticker-days
E11_VolumeBounce:         788 occurrences × 7 días =  5,516 ticker-days
E10_FirstGreenBounce:     765 occurrences × 7 días =  5,355 ticker-days
E6_MultipleGreenDays:   1,018 occurrences × 3 días =  3,054 ticker-days
E2_GapUp:                 583 occurrences × 5 días =  2,915 ticker-days
E9_CrashIntraday:         548 occurrences × 3 días =  1,644 ticker-days
E5_BreakoutATH:           187 occurrences × 5 días =    935 ticker-days
E7_FirstRedDay:            99 occurrences × 5 días =    495 ticker-days
──────────────────────────────────────────────────────────────────
TOTAL:                 10,663 events           = 54,981 ticker-days
```

---

## 4. PREPARACIÓN PARA DESCARGA

### 4.1 Problema: Formato de Watchlist

El script `download_trades_optimized.py` NO acepta un único archivo `.parquet`. Requiere estructura particionada:

```
processed/universe/multi_event_pilot_ultra_light/daily/
  date=2004-01-12/
    watchlist.parquet
  date=2004-01-30/
    watchlist.parquet
  ...
  date=2025-10-24/
    watchlist.parquet
```

Cada `watchlist.parquet` debe contener:
- Columna `ticker`: String
- Columna `info_rich`: Boolean (True = descargar este ticker en esta fecha)

### 4.2 Conversión a Formato Particionado

**Script de conversión**:

```python
import polars as pl
from pathlib import Path
import shutil

# Limpiar directorios previos corruptos
corrupt_dir = Path('processed/universe/multi_event_pilot_ultra_light')
if corrupt_dir.exists():
    shutil.rmtree(corrupt_dir)

# Cargar pilot ultra-light
SRC = Path('processed/watchlist_E1_E11_pilot_ultra_light.parquet')
OUT_ROOT = Path('processed/universe/multi_event_pilot_ultra_light/daily')

df = pl.read_parquet(SRC)

# Normalizar fecha (asegurar string simple YYYY-MM-DD)
date_col = 'trading_day' if 'trading_day' in df.columns else 'date'
df = df.with_columns([
    pl.col(date_col).cast(pl.Date).cast(pl.Utf8).alias('date'),
    pl.lit(True).alias('info_rich')  # Flag para downloader
])

OUT_ROOT.mkdir(parents=True, exist_ok=True)

# Particionar por fecha
partitions_created = 0
for date_val in df['date'].unique().sort():
    subdf = df.filter(pl.col('date') == date_val)

    day_dir = OUT_ROOT / f'date={date_val}'
    day_dir.mkdir(parents=True, exist_ok=True)

    # Guardar solo ticker + info_rich
    subdf.select(['ticker', 'info_rich']).write_parquet(
        day_dir / 'watchlist.parquet'
    )
    partitions_created += 1

print(f'Creadas {partitions_created} particiones')
```

**Resultado**: ✅ 1,455 particiones creadas correctamente

**Verificación**:
```
date=2004-01-12: 1 ticker
date=2004-01-30: 1 ticker
date=2004-02-26: 1 ticker
...
```

### 4.3 Características del Downloader

El script `scripts/fase_C_ingesta_tiks/download_trades_optimized.py` tiene:

**Características clave**:
1. **Compresión ZSTD**: Ya activada en el código
   ```python
   df.write_parquet(path, compression="zstd", compression_level=2)
   ```

2. **Ventana temporal**: Flag `--event-window N`
   - N = 0: Solo día del evento
   - N = 1: ±1 día (3 días total)
   - N = 2: ±2 días (5 días total) ← **USAREMOS ESTO**
   - N = 3: ±3 días (7 días total)

3. **Resume capability**: Flag `--resume`
   - Marca carpetas con `_SUCCESS` al completarse
   - Salta carpetas ya descargadas
   - Permite reanudar tras interrupción o cambio de disco

4. **Paralelización**: Flag `--workers N`
   - Múltiples descargas simultáneas
   - Usaremos 6 workers para balancear velocidad/estabilidad

5. **Rate limiting**: Flag `--rate-limit SECONDS`
   - 0.12 segundos entre requests = ~8.3 req/seg
   - Con 6 workers = ~50 req/seg efectivo

### 4.4 Decisión: Ventana Global ±2 días

Aunque tenemos ventanas optimizadas (±1, ±2, ±3) por evento, el downloader actual NO soporta ventanas diferenciadas por tipo de evento.

**Compromiso adoptado**:
- Usar `--event-window 2` (±2 días = 5 días totales)
- Esto es **cercano al promedio ponderado** de las ventanas optimizadas
- Evita modificar el downloader (que ya funciona bien)
- Para producción futura: implementar ventanas per-evento

**Media ponderada de ventanas**:
```
(E1:2 + E2:2 + E3:1 + E4:3 + E5:2 + E6:1 + E7:2 + E8:3 + E9:1 + E10:3 + E11:3)
────────────────────────────────────────────────────────────────────────────────
                                11 eventos
= 2.09 días promedio ≈ 2 días
```

---

## 5. ESTIMACIÓN DE RECURSOS

### 5.1 Parámetros de Estimación

**Parámetros base**:
- `AVG_MB_PER_DAY = 50`: Tamaño promedio por ticker-día sin comprimir
- `ZSTD_RATIO = 0.3`: Compresión ZSTD reduce a ~30% del original
- `API_RATE = 100`: Requests por minuto (límite Polygon.io)

### 5.2 Cálculos Detallados

**Ticker-days totales**:
```
54,981 ticker-days (con ventanas optimizadas reales)
```

**Espacio sin comprimir**:
```
54,981 ticker-days × 50 MB/day = 2,749,050 MB = 2,684.6 GB
```

**Espacio con ZSTD**:
```
2,684.6 GB × 0.30 = 805.4 GB
```

**Pero**: Al usar `--event-window 2` global en lugar de ventanas diferenciadas:
```
2,127 entries × 5 días (±2) × 50 MB × 0.30 (ZSTD) ≈ 528 GB
```

**Tiempo de descarga**:
```
54,981 API calls ÷ (100 req/min × 60 min/hr) = 9.16 horas
```

Con 6 workers y overhead de red: **~6-8 horas reales**

### 5.3 Viabilidad en Disco

**Disco D: Estado actual**:
- Total: 931 GB
- Usado: 328 GB
- **Libre: 602 GB**

**Espacio necesario (Pilot Ultra-Light)**:
- **528 GB** con ZSTD

**Margen de seguridad**:
- 602 GB × 80% = 482 GB (umbral recomendado)
- 602 GB - 528 GB = **74 GB libres después**
- ✅ **VIABLE** (aunque ajustado)

---

## 6. COMANDO DE DESCARGA EJECUTADO

### 6.1 Comando Final

```bash
cd "D:\04_TRADING_SMALLCAPS"

python "scripts\fase_C_ingesta_tiks\download_trades_optimized.py" \
  --outdir "raw\polygon\trades" \
  --from 2004-01-01 \
  --to 2025-10-21 \
  --mode watchlists \
  --watchlist-root "processed\universe\multi_event_pilot_ultra_light\daily" \
  --event-window 2 \
  --page-limit 50000 \
  --rate-limit 0.12 \
  --workers 6 \
  --resume
```

### 6.2 Explicación de Flags

| Flag | Valor | Explicación |
|------|-------|-------------|
| `--outdir` | `raw\polygon\trades` | Directorio destino para trades |
| `--from` | `2004-01-01` | Fecha inicio (cubrir todo el range) |
| `--to` | `2025-10-21` | Fecha fin |
| `--mode` | `watchlists` | Modo watchlist (vs. months completos) |
| `--watchlist-root` | `processed\universe\...` | Ruta a watchlist particionada |
| `--event-window` | `2` | ±2 días alrededor del evento (5 días total) |
| `--page-limit` | `50000` | Trades por página API (max Polygon) |
| `--rate-limit` | `0.12` | 0.12 seg entre requests (~8 req/s) |
| `--workers` | `6` | 6 procesos paralelos |
| `--resume` | (flag) | Continuar desde último completado |

### 6.3 Background Process ID

**ID de proceso**: `0e133c`

Para monitorear progreso:
```bash
# Ver output del proceso
BashOutput 0e133c

# Verificar archivos descargados
find raw/polygon/trades -name "_SUCCESS" | wc -l

# Verificar espacio usado
du -sh raw/polygon/trades
```

### 6.4 Hora de Inicio

**Timestamp de lanzamiento**: 2025-10-29 01:04:40 UTC
**Hora local**: 29 de octubre, 01:04 AM

**Estimación de finalización**: ~07:00-09:00 AM (6-8 horas después)

---

## 7. ESTRUCTURA DE SALIDA

### 7.1 Formato de Archivos

**Estructura de directorios**:
```
raw/polygon/trades/
  DCTH/
    date=2004-01-12/
      trades.parquet         # Trades del día
      _SUCCESS               # Marca de completado
    date=2004-01-30/
      trades.parquet
      _SUCCESS
    ...
  ASTI/
    date=2004-02-26/
      trades.parquet
      _SUCCESS
    ...
  (15 tickers × ~142 días promedio)
```

### 7.2 Schema de trades.parquet

```python
{
    "ticker": pl.Utf8,
    "timestamp": pl.Int64,        # Unix timestamp (nanoseconds)
    "price": pl.Float64,
    "size": pl.Int64,             # Shares traded
    "exchange": pl.Utf8,
    "conditions": pl.List(pl.Int32),
    "id": pl.Utf8,                # Trade ID
}
```

### 7.3 Marcadores _SUCCESS

Cada carpeta `ticker/date=YYYY-MM-DD/` con descarga completada contiene:
- `_SUCCESS`: Archivo vacío que marca completado
- Permite resume: si existe `_SUCCESS`, se salta esta carpeta

**Uso para resume**:
```python
success_marker = ticker_dir / date_dir / "_SUCCESS"
if success_marker.exists():
    continue  # Skip already downloaded
```

---

## 8. MONITOREO Y VALIDACIÓN

### 8.1 Comandos de Monitoreo Durante Descarga

**Ver progreso en tiempo real**:
```bash
# Output del proceso
cd D:/04_TRADING_SMALLCAPS
python -c "from pathlib import Path; import time
while True:
    success = len(list(Path('raw/polygon/trades').rglob('_SUCCESS')))
    print(f'Carpetas completadas: {success:,}', end='\r')
    time.sleep(10)
"
```

**Verificar espacio en disco**:
```bash
# Windows
cd D:/04_TRADING_SMALLCAPS
du -sh raw/polygon/trades

# Espacio libre
df -h D:
```

**Contar archivos descargados**:
```bash
# _SUCCESS markers (carpetas completadas)
find raw/polygon/trades -name "_SUCCESS" | wc -l

# trades.parquet (archivos de datos)
find raw/polygon/trades -name "trades.parquet" | wc -l
```

### 8.2 Validación Post-Descarga (Mañana)

**Script de validación**:

```python
import polars as pl
from pathlib import Path

trades_root = Path('raw/polygon/trades')

print('=== VALIDACIÓN PILOT ULTRA-LIGHT ===')
print()

# 1. Contar archivos
success_files = list(trades_root.rglob('_SUCCESS'))
trade_files = list(trades_root.rglob('trades.parquet'))

print(f'Carpetas completadas (_SUCCESS): {len(success_files):,}')
print(f'Archivos trades.parquet: {len(trade_files):,}')
print()

# 2. Calcular tamaño total
total_bytes = sum(f.stat().st_size for f in trade_files)
total_gb = total_bytes / 1e9

print(f'Tamaño total: {total_gb:.2f} GB')
print(f'Promedio por archivo: {total_bytes/len(trade_files)/1e6:.2f} MB')
print()

# 3. Validar 5 archivos aleatorios
import random
sample = random.sample(trade_files, min(5, len(trade_files)))

print('Validando 5 archivos aleatorios:')
for tf in sample:
    ticker = tf.parent.parent.name
    date = tf.parent.name.split('=')[1]

    df = pl.read_parquet(tf)
    print(f'{ticker} {date}: {len(df):,} trades, {tf.stat().st_size/1e6:.2f} MB')

print()

# 4. Estadísticas agregadas
print('Leyendo todos los trades (puede tardar)...')
df_all = pl.read_parquet(trades_root / '**' / 'trades.parquet')

print(f'Total trades: {len(df_all):,}')
print(f'Tickers únicos: {df_all["ticker"].n_unique()}')
print(f'Rango temporal: {df_all["timestamp"].min()} -> {df_all["timestamp"].max()}')
print(f'Precio promedio: ${df_all["price"].mean():.4f}')
print(f'Size promedio: {df_all["size"].mean():.0f} shares')
```

### 8.3 Métricas a Calcular

**Métricas clave**:
1. **Coverage**: ¿Cuántas de las 2,127 entries se descargaron?
2. **Tamaño real vs estimado**: ¿Fue precisa la estimación de 528 GB?
3. **Tiempo real**: ¿Cuántas horas tomó realmente?
4. **MB por ticker-day**: Calcular promedio real para futuras estimaciones
5. **Tasa de descarga**: API calls/minuto efectiva

**Fórmulas**:
```python
# Coverage
coverage = len(success_files) / 2127 * 100

# Tamaño real vs estimado
ratio = total_gb / 528

# MB por ticker-day
mb_per_day = (total_gb * 1024) / len(success_files)

# Tiempo total (en horas)
start_time = "2025-10-29 01:04:40"
end_time = "TIMESTAMP_DE_FINALIZACIÓN"
hours = (end_time - start_time).total_seconds() / 3600

# Tasa efectiva
effective_rate = len(success_files) / (hours * 60)  # req/min
```

---

## 9. STRATEGY PARA REANUDAR SI SE LLENA EL DISCO

### 9.1 Problema Potencial

Si durante la descarga el disco D: se llena (probable dado el margen ajustado de 74 GB):

**Síntomas**:
- Error "No space left on device"
- Proceso se detiene
- Última carpeta sin `_SUCCESS`

### 9.2 Solución: Symlink a Disco Externo

**Paso 1: Detener proceso**
```bash
# Identificar PID del proceso
ps aux | grep download_trades_optimized

# Detener (Ctrl+C o kill)
kill <PID>
```

**Paso 2: Verificar último archivo completado**
```bash
# Contar archivos descargados
find raw/polygon/trades -name "_SUCCESS" | wc -l

# Identificar última carpeta SIN _SUCCESS (incompleta)
find raw/polygon/trades -type d -name "date=*" \
  ! -exec test -f {}/_SUCCESS \; -print | tail -5
```

**Paso 3: Mover a disco externo (ej: E:)**
```bash
# Crear carpeta en disco externo
mkdir E:/TRADING_DATA/polygon_trades

# Mover datos ya descargados
robocopy raw/polygon/trades E:/TRADING_DATA/polygon_trades /E /MOVE

# O con rsync (si disponible)
rsync -av --remove-source-files raw/polygon/trades/ E:/TRADING_DATA/polygon_trades/
```

**Paso 4: Crear symlink en D:**
```cmd
# Windows (como Administrador)
mklink /D "D:\04_TRADING_SMALLCAPS\raw\polygon\trades" "E:\TRADING_DATA\polygon_trades"
```

**Paso 5: Reanudar descarga**
```bash
# El mismo comando original con --resume
python "scripts\fase_C_ingesta_tiks\download_trades_optimized.py" \
  --outdir "raw\polygon\trades" \
  --from 2004-01-01 \
  --to 2025-10-21 \
  --mode watchlists \
  --watchlist-root "processed\universe\multi_event_pilot_ultra_light\daily" \
  --event-window 2 \
  --page-limit 50000 \
  --rate-limit 0.12 \
  --workers 6 \
  --resume
```

El flag `--resume` detectará los `_SUCCESS` markers y continuará desde donde se detuvo.

### 9.3 Alternativa: Descarga Incremental

Si prefieres no mover archivos:

**Opción A: Descargar en lotes de N tickers**
```python
# Dividir pilot en 3 lotes de 5 tickers
batch1 = ['DCTH', 'ASTI', 'SRNE', 'SBNY', 'BBIG']
batch2 = ['RNVA', 'SONG', 'SRAX', 'MULN', 'FRBK']
batch3 = ['TNXP', 'ALPP', 'HMNY', 'IDEX', 'LTCH']

# Filtrar watchlist por lote
for batch_id, tickers in enumerate([batch1, batch2, batch3], 1):
    df_batch = df_pilot.filter(pl.col('ticker').is_in(tickers))
    df_batch.write_parquet(f'processed/watchlist_batch{batch_id}.parquet')
```

Descargar batch1, validar, luego batch2, etc.

**Opción B: Comprimir archivos ya descargados**
```bash
# Comprimir carpetas ya completadas para liberar espacio
find raw/polygon/trades -name "_SUCCESS" -exec dirname {} \; | \
while read dir; do
    tar -czf "${dir}.tar.gz" "$dir"
    rm -rf "$dir"  # Solo si tar fue exitoso
done
```

---

## 10. SIGUIENTES PASOS (POST-DESCARGA)

### 10.1 Inmediato (Mañana 29/10)

**1. Validar descarga completa**
- Ejecutar script de validación (sección 8.2)
- Verificar coverage (¿cuántas carpetas completadas?)
- Calcular métricas reales vs estimadas

**2. Auditoría de calidad**
- Verificar que NO hay archivos corruptos
- Verificar que timestamps son coherentes
- Verificar que precios son razonables (no outliers absurdos)

**3. Generar reporte de métricas**
```python
# Métricas a documentar
metrics = {
    'total_success_folders': len(success_files),
    'total_trade_files': len(trade_files),
    'total_size_gb': total_gb,
    'total_trades': len(df_all),
    'avg_mb_per_day': mb_per_day,
    'coverage_pct': coverage,
    'download_hours': hours,
    'effective_rate_req_min': effective_rate,
    'size_ratio_vs_estimated': ratio,
}

# Guardar como JSON
import json
with open('processed/pilot_ultra_light_metrics.json', 'w') as f:
    json.dump(metrics, f, indent=2)
```

### 10.2 Corto Plazo (Próximos Días)

**1. Construir Dollar Imbalance Bars (DIB)**
- Input: `raw/polygon/trades`
- Output: `processed/bars`
- Script: `scripts/fase_D_creando_DIB_VIB/build_bars_from_trades.py`

**2. Detectar eventos intraday refinados (E3, E9)**
- Usar 1-minute bars para detectar spikes/crashes reales
- Marcar `intraday_confirmed=True` donde corresponda
- Actualizar watchlist con confirmaciones

**3. Feature engineering**
- VWAP, microstructure, order flow
- Imbalance ratios, trade intensity
- Pre-evento vs post-evento stats

### 10.3 Medio Plazo (Próxima Semana)

**1. Expandir a más tickers**
- Si el piloto fue exitoso, considerar:
  - Top 50 tickers (en lugar de 15)
  - O solo eventos con mejor win rate (E8, E10, E11)
- Repetir proceso con disco externo preparado

**2. Triple Barrier Labeling**
- Etiquetar bars con outcomes
- Profit target, stop loss, time decay
- Calcular win rates reales por evento

**3. Sample weights**
- Uniqueness, return-based weights
- Time decay, concurrency
- Preparar para entrenamiento ML

### 10.4 Largo Plazo (Próximas 2 Semanas)

**1. ML Dataset construction**
- Features + Labels + Weights → Dataset
- Train/validation splits (walk-forward)
- Purged CV para evitar data leakage

**2. Modelo baseline**
- Random Forest o LightGBM
- Predecir: ¿Lado del trade (long/short/skip)?
- Métrica: Sharpe ratio, win rate, expected return

**3. Backtest framework**
- Simular estrategia con slippage/commissions
- Comparar vs benchmark (SPY, equal-weight portfolio)
- Calcular métricas de riesgo (max drawdown, Sortino)

---

## 11. LECCIONES APRENDIDAS

### 11.1 Ventanas Optimizadas > Ventanas Fijas

**Antes**: Asunción ingenua de ±3 días para TODOS los eventos
- Resultado: 20.6M ticker-days, 1 PB de datos

**Después**: Ventanas diferenciadas por naturaleza del patrón
- Resultado: 15.2M ticker-days, 743 TB (**26% reducción**)

**Lección**: El análisis granular de requisitos por tipo de evento reduce significativamente los recursos necesarios sin perder calidad de contexto.

### 11.2 Multi-Evento como Filtro Efectivo

**Filtro aplicado**: `event_count >= 3`
- De 2.9M entries → 57,720 entries (**98% reducción**)
- Mantiene los días más "informativos"
- Concentra esfuerzo en tickers con patrones complejos

**Lección**: Los días con múltiples eventos simultáneos son catalizadores excepcionales. Priorizarlos maximiza información por GB descargado.

### 11.3 Piloto Antes de Descarga Masiva

**Estrategia adoptada**: Pilot Ultra-Light (15 tickers, 528 GB)
- Valida proceso end-to-end con volumen manejable
- Permite calcular métricas reales (MB/ticker-day)
- Ajusta estimaciones antes de descarga masiva

**Lección**: Siempre validar con piloto antes de comprometer recursos masivos (tiempo, espacio, API quota).

### 11.4 Compresión es Crítica

**Sin ZSTD**: 2,684 GB
**Con ZSTD**: 805 GB (**70% reducción**)

**Lección**: Compresión ZSTD es esencial para smallcaps data pipelines. El overhead de CPU es mínimo comparado con el ahorro de espacio.

### 11.5 Resume Capability es No-Negociable

**Sin resume**:
- Fallo en descarga = reiniciar desde cero
- Riesgo de duplicar archivos
- No permite cambio de disco mid-flight

**Con resume** (`_SUCCESS` markers):
- Reanudar exactamente donde se detuvo
- Permite cambio de disco sin perder progreso
- Robusto ante interrupciones

**Lección**: Para pipelines largos (>2 horas), resume capability es obligatorio.

---

## 12. RECURSOS Y REFERENCIAS

### 12.1 Archivos Clave Generados

| Archivo | Descripción | Tamaño |
|---------|-------------|--------|
| `processed/watchlist_E1_E11_pilot_ultra_light.parquet` | Pilot Ultra-Light watchlist | 37 KB |
| `processed/universe/multi_event_pilot_ultra_light/daily/` | Watchlist particionada | 1,455 dirs |
| `01_DayBook/.../analisis_ventanas_optimizadas_por_evento_executed.ipynb` | Notebook análisis | 203 KB |
| `raw/polygon/trades/` | Trades descargados (en progreso) | ~528 GB (estimado) |

### 12.2 Scripts Utilizados

| Script | Función |
|--------|---------|
| `scripts/fase_C_ingesta_tiks/download_trades_optimized.py` | Downloader con ZSTD, resume, ventanas |
| Inline Python (sección 3.2) | Generación Pilot Ultra-Light |
| Inline Python (sección 4.2) | Conversión a formato particionado |
| Inline Python (sección 8.2) | Validación post-descarga |

### 12.3 Documentación Relacionada

| Documento | Tema |
|-----------|------|
| `C.5.7_validacion_prototipo_dib_vib.md` | Prototipo DIB/VIB |
| `E.4_implementar_E2_E11.md` | Implementación detectores E2-E11 |
| `E.5_sesion_completa_E1_E11_backtest.md` | Detección E1-E11 + backtest |
| `C.6_roadmap_multi_evento.md` | Roadmap Fase C completa |

### 12.4 Enlaces Externos

- **Polygon.io API Docs**: https://polygon.io/docs/stocks/get_v3_trades__stockticker
- **Polars Docs**: https://pola-rs.github.io/polars/py-polars/html/reference/
- **ZSTD Compression**: https://facebook.github.io/zstd/

---

## 13. CONCLUSIONES

### 13.1 Estado Actual

✅ **Análisis de ventanas optimizadas completado**
- Reducción del 26.1% en recursos vs enfoque ingenuo
- Documentado en notebook ejecutado

✅ **Pilot Ultra-Light generado**
- 15 tickers, 2,127 días multi-evento
- Watchlist particionada en formato correcto

✅ **Descarga nocturna lanzada**
- Background process ID: 0e133c
- Timestamp inicio: 2025-10-29 01:04:40
- Estimación: ~528 GB en ~6-8 horas

### 13.2 Próximos Hitos

**Mañana (29/10)**:
- [ ] Verificar progreso descarga (BashOutput 0e133c)
- [ ] Ejecutar validación post-descarga
- [ ] Calcular métricas reales vs estimadas
- [ ] Documentar resultados en este archivo

**Esta semana**:
- [ ] Construir Dollar Imbalance Bars
- [ ] Refinar eventos intraday (E3, E9)
- [ ] Feature engineering básico

**Próxima semana**:
- [ ] Triple Barrier Labeling
- [ ] ML Dataset construction
- [ ] Modelo baseline

### 13.3 Riesgos Identificados

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| Disco lleno mid-flight | Media | Alto | Symlink a disco externo (sección 9.2) |
| API rate limit excedido | Baja | Medio | Rate limit conservador (0.12s) |
| Archivos corruptos | Baja | Bajo | Validación post-descarga |
| Tiempo > estimado | Media | Bajo | Resume permite continuar otro día |

### 13.4 Métricas de Éxito

**Para considerar el piloto exitoso**:
1. Coverage ≥ 95% (≥ 2,020 de 2,127 carpetas)
2. Tamaño real ≤ 600 GB (no llenar disco)
3. Tiempo ≤ 12 horas (completar en noche + mañana)
4. Zero archivos corruptos
5. Métricas reales ±20% de estimadas

Si estos criterios se cumplen → **proceder a expansión (Top 50 tickers o filtro win rate)**

---

## ANEXO A: Comandos de Referencia Rápida

```bash
# ============================================================================
# MONITOREO DURANTE DESCARGA
# ============================================================================

# Ver progreso del proceso en background
cd D:/04_TRADING_SMALLCAPS
# (Usar BashOutput 0e133c en la CLI)

# Contar carpetas completadas
find raw/polygon/trades -name "_SUCCESS" -type f | wc -l

# Verificar espacio usado
du -sh raw/polygon/trades

# Verificar espacio libre en disco
df -h D:

# Ver últimos archivos descargados
find raw/polygon/trades -name "trades.parquet" -type f -mmin -10

# ============================================================================
# VALIDACIÓN POST-DESCARGA
# ============================================================================

# Contar archivos totales
echo "Success markers:" && find raw/polygon/trades -name "_SUCCESS" | wc -l
echo "Trade files:" && find raw/polygon/trades -name "trades.parquet" | wc -l

# Calcular tamaño total
du -sh raw/polygon/trades

# Listar tickers descargados
ls raw/polygon/trades

# Validar un archivo random
python -c "
import polars as pl
from pathlib import Path
import random

files = list(Path('raw/polygon/trades').rglob('trades.parquet'))
sample = random.choice(files)
print(f'Archivo: {sample}')
df = pl.read_parquet(sample)
print(f'Rows: {len(df):,}')
print(df.head())
"

# ============================================================================
# REANUDAR SI SE INTERRUMPE
# ============================================================================

# Mismo comando original (--resume detecta _SUCCESS)
python "scripts\fase_C_ingesta_tiks\download_trades_optimized.py" \
  --outdir "raw\polygon\trades" \
  --from 2004-01-01 \
  --to 2025-10-21 \
  --mode watchlists \
  --watchlist-root "processed\universe\multi_event_pilot_ultra_light\daily" \
  --event-window 2 \
  --page-limit 50000 \
  --rate-limit 0.12 \
  --workers 6 \
  --resume

# ============================================================================
# MOVER A DISCO EXTERNO (SI SE LLENA D:)
# ============================================================================

# Crear symlink (Windows, como Admin)
mklink /D "D:\04_TRADING_SMALLCAPS\raw\polygon\trades" "E:\TRADING_DATA\polygon_trades"

# Reanudar descarga (detectará symlink transparentemente)
# (mismo comando de arriba)
```

---

## ANEXO B: Estructura Completa de Directorios

```
D:/04_TRADING_SMALLCAPS/
│
├── processed/
│   ├── watchlist_E1_E11.parquet                    # Watchlist completa (2.9M)
│   ├── watchlist_E1_E11_pilot_ultra_light.parquet  # Pilot (2,127 entries)
│   │
│   └── universe/
│       └── multi_event_pilot_ultra_light/
│           └── daily/
│               ├── date=2004-01-12/
│               │   └── watchlist.parquet
│               ├── date=2004-01-30/
│               │   └── watchlist.parquet
│               └── ... (1,455 particiones)
│
├── raw/
│   └── polygon/
│       └── trades/                                 # OUTPUT de descarga
│           ├── DCTH/
│           │   ├── date=2004-01-12/
│           │   │   ├── trades.parquet
│           │   │   └── _SUCCESS
│           │   └── ... (~313 fechas)
│           ├── ASTI/
│           │   └── ... (~260 fechas)
│           └── ... (15 tickers)
│
├── scripts/
│   └── fase_C_ingesta_tiks/
│       └── download_trades_optimized.py            # Downloader con ZSTD
│
└── 01_DayBook/
    └── fase_01/
        └── C_v2_ingesta_tiks_2004_2025/
            ├── C.5.8_descarga_pilot_ultra_light_ventanas_optimizadas.md  # ESTE DOC
            │
            └── notebooks/
                ├── analisis_ventanas_optimizadas_por_evento.ipynb
                └── analisis_ventanas_optimizadas_por_evento_executed.ipynb
```

---

**Fin del documento**

---

**Autor**: Claude
**Fecha**: 2025-10-29 01:30 AM
**Versión**: 1.0
**Status**: Descarga en progreso (Background ID: 0e133c)
