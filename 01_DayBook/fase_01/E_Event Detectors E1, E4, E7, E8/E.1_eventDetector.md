# Track A: Event Detectors E1, E4, E7, E8 - Daily OHLCV Pipeline

**Fase**: E - Event Detection
**Objetivo**: Construir daily OHLCV desde 1m bars para alimentar detectores de eventos E1/E4/E7/E8
**Status**: 🔄 EN PROGRESO - Agregando 1m → Daily OHLCV (8,620 tickers)

---

## Menú de Navegación

### Documentación
- [← C.7 Roadmap Post Paso 5](../C_v2_ingesta_tiks_2004_2025/C.7_roadmap_post_paso5.md) - Estrategia Multi-Evento
- [D.3 Resumen Pipeline](../D_creando_DIB_VIB_2004_2025/D.3_resumen_pipeline.md) - Pipeline DIB/VIB completado

### 🔧 Scripts
- [build_daily_ohlcv_from_1m.py](../../../scripts/fase_E_Event%20Detectors%20E1,%20E4,%20E7,%20E8/build_daily_ohlcv_from_1m.py) - ⚙️ Agregador 1m → Daily (EN EJECUCIÓN)
- [event_detectors.py](../../../scripts/fase_E_Event%20Detectors%20E1,%20E4,%20E7,%20E8/event_detectors.py) - 🎯 Detectores E1/E4/E7/E8

### Datos
- **Input**: `raw/polygon/ohlcv_intraday_1m/<TICKER>/year=*/month=*/minute.parquet`
- **Output**: `processed/daily_ohlcv/<TICKER>/daily.parquet`
- **Schema**: [Ver Schema Output](#schema-output-daily-ohlcv)

### Notebooks
- [Validación Track A](notebooks/) - 📈 Validación completa de detectores (PENDIENTE)

---

## Contexto y Motivación

### ✅ Lo Que Ya Tenemos

**Event Detectors Implementados** → [event_detectors.py](../../../scripts/fase_E_Event%20Detectors%20E1,%20E4,%20E7,%20E8/event_detectors.py)

| Detector | Función | Descripción |
|----------|---------|-------------|
| **E1** | `detect_e1_volume_explosion()` | RVOL > 5x (20-day average) |
| **E4** | `detect_e4_parabolic_move()` | +50% en ≤5 días consecutivos |
| **E7** | `detect_e7_first_red_day()` | Primer día rojo tras run verde **CRÍTICO** |
| **E8** | `detect_e8_gap_down_violent()` | Gap down >15% |

### ❌ Lo Que Nos Falta: OHLCV Diario Completo

Los detectores **requieren OHLCV diario completo**, no solo `close_d` y `vol_d`:

| Campo | Descripción | Necesario Para |
|-------|-------------|----------------|
| `o` | Open del día (primer minuto) | **E8**: Gap Down → `open_today` vs `close_prev` |
| `h` | High del día (máximo intradía) | **E4**: Parabolic → detectar pico vs inicio run |
| `l` | Low del día (mínimo intradía) | **E7**: FRD → extensión intradía |
| `c` | Close del día (último minuto) | **E7**: FRD → detectar "red day" (`c < c_prev`) |
| `v` | Volume del día (suma total) | **E1**: Volume Explosion → RVOL > 5x |

**Problema Actual**:
`processed/daily_cache` solo tiene:
- `close_d`, `vol_d`, `return_d`
- **NO** tiene `open`, `high`, `low`

**✅ Solución**:
Generar `processed/daily_ohlcv` desde `raw/polygon/ohlcv_intraday_1m`

---

## Arquitectura: Por Qué Daily OHLCV Primero

### Flujo de Datos Correcto

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Daily OHLCV (resolución día)                             │
│    → Detectar días interesantes (E1/E4/E7/E8)               │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Descargar Ticks (solo días detectados ±1, ±3, ±5)       │
│    → Bajar al intradía SOLO para días relevantes            │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Construir DIB/VIB (intraday bars)                        │
│    → Dollar Imbalance Bars (~$300k threshold)               │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. Triple Barrier Labeling + Weights                        │
│    → PT=3σ, SL=2σ, T1=120 bars                              │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. Dataset ML Intraday                                       │
│    → Entrenar modelos de trading intradía                   │
└─────────────────────────────────────────────────────────────┘
```

## Script: `build_daily_ohlcv_from_1m.py`

### Especificación del Script

**Ubicación**: [scripts/fase_E_Event Detectors E1, E4, E7, E8/build_daily_ohlcv_from_1m.py](../../../scripts/fase_E_Event%20Detectors%20E1,%20E4,%20E7,%20E8/build_daily_ohlcv_from_1m.py)

**CLI**:
```bash
python build_daily_ohlcv_from_1m.py \
    --intraday-root raw/polygon/ohlcv_intraday_1m \
    --outdir processed/daily_ohlcv \
    --parallel 8 \
    --resume
```

### 🔄 Lógica Por Ticker

Para cada ticker en `raw/polygon/ohlcv_intraday_1m/<TICKER>`:

1. **Buscar** todos los `minute.parquet` (estructura: `year=*/month=*/minute.parquet`)
2. **Leer y concatenar** todos los archivos del ticker
3. **Agrupar por `date`** y calcular:

| Métrica | Cálculo | Descripción |
|---------|---------|-------------|
| `o` | `o` de la fila con **mínimo `t`** | Open del primer minuto |
| `h` | `max(h)` | High máximo del día |
| `l` | `min(l)` | Low mínimo del día |
| `c` | `c` de la fila con **máximo `t`** | Close del último minuto |
| `v` | `sum(v)` | Volumen total del día |
| `n` | `sum(n)` | Número de trades del día |
| `dollar` | `sum(v * c)` | Dollar volume del día |

4. **Ordenar por `date`**
5. **Escribir** `processed/daily_ohlcv/<TICKER>/daily.parquet`
6. **Marcar éxito** con `_SUCCESS` file

### ⚠️ Notas Técnicas Críticas

#### Orden por Timestamp Correcto

```python
# INCORRECTO: confiar en orden de lectura
df_daily = df.group_by("date").agg([
    pl.col("o").first(),  # ⚠️ Puede no ser el primer minuto!
])

# CORRECTO: ordenar por timestamp primero
df_daily = (
    df
    .sort(["date", "t"])  # Orden crítico!
    .group_by("date")
    .agg([
        pl.col("o").first(),  # Ahora sí es el primer minuto
        pl.col("c").last(),   # Último minuto
    ])
)
```

#### Resume Mode

Si `--resume` está activo:
- Saltar tickers con `processed/daily_ohlcv/<TICKER>/_SUCCESS`
- Permite reiniciar tras errores sin reprocesar

#### 🚀 Paralelización

- `ProcessPoolExecutor` con N workers
- Cada ticker procesado independientemente
- Igual que `build_bars_from_trades.py`, `triple_barrier_labeling.py`, etc.

---

## Schema Output: Daily OHLCV

### Estructura de Archivos

```
processed/daily_ohlcv/
├── AAPL/
│   ├── daily.parquet       # Todas las fechas del ticker
│   └── _SUCCESS
├── TSLA/
│   ├── daily.parquet
│   └── _SUCCESS
└── ...                     # 8,620 tickers
```

### Schema `daily.parquet`

| Columna | Tipo | Descripción | Ejemplo |
|---------|------|-------------|---------|
| `ticker` | `String` | Ticker symbol | "AAPL" |
| `date` | `Date` | Trading day | 2024-01-15 |
| `o` | `Float64` | Open (primer minuto) | 185.23 |
| `h` | `Float64` | High (máximo día) | 187.45 |
| `l` | `Float64` | Low (mínimo día) | 184.10 |
| `c` | `Float64` | Close (último minuto) | 186.78 |
| `v` | `Float64` | Volume (suma total) | 52341267.0 |
| `n` | `Int64` | Trades (suma total) | 412563 |
| `dollar` | `Float64` | Dollar volume (sum v*c) | 9756234521.34 |

**Orden**: Filas ordenadas por `date` ascendente

---

## Uso: Event Detectors

### Pipeline Completo

Una vez generado `processed/daily_ohlcv`, ejecutar detectores:

```bash
python event_detectors.py \
    --daily-root processed/daily_ohlcv \
    --outdir processed/events_raw \
    --events E1,E4,E7,E8
```

### Detectores Individuales

#### E1: Volume Explosion
```python
detector.detect_e1_volume_explosion(df_daily, rvol_threshold=5.0)
```
**Output**: Días con `volumen / media_20d > 5.0`

#### E4: Parabolic Move
```python
detector.detect_e4_parabolic_move(df_daily, min_gain_pct=0.50, max_days=5)
```
**Output**: Rampas de +50% en ≤5 días consecutivos

#### E7: First Red Day (CRÍTICO)
```python
detector.detect_e7_first_red_day(df_daily, min_run_days=3, min_extension_pct=0.50)
```
**Output**: Primer día rojo tras ≥3 días verdes con extensión ≥50%

#### E8: Gap Down Violent
```python
detector.detect_e8_gap_down_violent(df_daily, gap_threshold=-0.15)
```
**Output**: Gaps down >15% (`open < close_prev * 0.85`)

---

## 🔗 Multi-Event Fuser (Siguiente Paso)

Después de generar eventos individuales, crear **watchlist multi-evento**:

### Fuser Logic

```python
# Outer join por (ticker, date)
df_fused = (
    e1_events
    .join(e4_events, on=["ticker", "date"], how="outer")
    .join(e7_events, on=["ticker", "date"], how="outer")
    .join(e8_events, on=["ticker", "date"], how="outer")
)

# Columnas boolean por evento
df_fused = df_fused.with_columns([
    pl.col("E1_volume_explosion").fill_null(False),
    pl.col("E4_parabolic").fill_null(False),
    pl.col("E7_first_red_day").fill_null(False),
    pl.col("E8_gap_down").fill_null(False),
])

# Columna event_types: lista de códigos presentes
df_fused = df_fused.with_columns([
    pl.concat_str([...]).alias("event_types")
])

# Columna max_event_window para descarga ticks
df_fused = df_fused.with_columns([
    pl.max([E1_window, E4_window, E7_window, E8_window]).alias("max_event_window")
])
```

### Output: Watchlist Multi-Evento

```
processed/multi_event_watchlist.parquet
```

| ticker | date | E1 | E4 | E7 | E8 | event_types | max_window |
|--------|------|----|----|----|----|-------------|------------|
| AAPL | 2024-01-15 | T | F | T | F | "E1,E7" | 5 |
| TSLA | 2024-02-08 | F | T | F | T | "E4,E8" | 7 |

**Consumidor**: `download_trades_optimized.py` descarga ticks para `(ticker, date ± max_window)`

---

## Status Actual

### Proceso En Ejecución

**Script**: [build_daily_ohlcv_from_1m.py](../../../scripts/fase_E_Event%20Detectors%20E1,%20E4,%20E7,%20E8/build_daily_ohlcv_from_1m.py)
**Shell ID**: `a7afa4`
**Progreso**: ~8/8,620 tickers (iniciando)
**ETA**: ~30-40 minutos

**Comando**:
```bash
cd D:/04_TRADING_SMALLCAPS && python "scripts/fase_E_Event Detectors E1, E4, E7, E8/build_daily_ohlcv_from_1m.py" \
    --intraday-root raw/polygon/ohlcv_intraday_1m \
    --outdir processed/daily_ohlcv \
    --parallel 8 \
    --resume
```

### ✅ Siguientes Pasos (Track A)

1. **Esperar completado** de `build_daily_ohlcv_from_1m.py` (~30-40 min)
2. **Testear event detectors** E1, E4, E7, E8 en sample data
3. **Crear multi-event fuser** → `processed/multi_event_watchlist.parquet`
4. **Validar con notebook** → `notebooks/validacion_track_a.ipynb`

---

## Referencias

### Documentación Relacionada
- [C.1 Definición Eventos E1-E13](../C_v2_ingesta_tiks_2004_2025/C.1_definicion_eventos.md)
- [C.7 Roadmap Multi-Evento](../C_v2_ingesta_tiks_2004_2025/C.7_roadmap_post_paso5.md)
- [D.3 Resumen Pipeline DIB/VIB](../D_creando_DIB_VIB_2004_2025/D.3_resumen_pipeline.md)

### Scripts Relacionados
- [build_bars_from_trades.py](../../../scripts/fase_D_creando_DIB_VIB/build_bars_from_trades.py) - Dollar Imbalance Bars
- [triple_barrier_labeling.py](../../../scripts/fase_D_creando_DIB_VIB/triple_barrier_labeling.py) - Triple Barrier Labels
- [build_ml_dataset.py](../../../scripts/fase_D_creando_DIB_VIB/build_ml_dataset.py) - ML Dataset Builder

---

**Última Actualización**: 2025-10-28  
**Autor**: Track A Event Detection Pipeline  
**Status**: 🔄 EN PROGRESO - Daily OHLCV Generation  
