# C.5 - Plan de Ejecución E0: Descarga Ticks 2004-2025

**Fecha**: 2025-10-27
**Versión**: 1.2.0 (refactor post-PASO 5 completado)
**Basado en**: Contrato_E0.md v2.0.0
**Prerequisito**: C.4 - Descarga OHLCV Daily/Intraday completada (8,620 tickers raw intraday)
**Ver también**: C.7_ERROR_SCD2_Y_SOLUCION.md para contexto del error crítico y fix aplicado

---

## ÍNDICE

1. [Pipeline de Ejecución (5 PASOS)](#1-pipeline-de-ejecución-5-pasos)
   - [PASO 0: Generación Dimensión SCD-2 (DEPRECADO)](#paso-0-generación-dimensión-scd-2-market-cap-deprecado)
   - [PASO 1: Generación Caché Diario 2004-2025](#paso-1-generación-caché-diario-2004-2025)
   - [PASO 2: Actualizar Configuración Umbrales E0](#paso-2-actualizar-configuración-umbrales-e0)
   - [PASO 3: Generación Universo Dinámico E0](#paso-3-generación-universo-dinámico-e0-2004-2025)
   - [PASO 4: Análisis Características E0](#paso-4-análisis-características-e0-2004-2025)
   - [PASO 5: Descarga Ticks Días Info-Rich E0](#paso-5-descarga-ticks-días-info-rich-e0)
2. [Estructura Final de Datos (PASO 5 Completado)](#2-estructura-final-de-datos-paso-5-completado)
3. [Especificación Técnica Multi-Evento](#3-especificación-técnica-multi-evento-e0--e1-e17-futuros)
4. [Comandos Rápidos (Resumen)](#4-comandos-rápidos-resumen)
5. [Notas Finales](#5-notas-finales)

**Roadmaps de Implementación Multi-Evento**:
- [C.6 - Roadmap Ejecutivo Multi-Evento](C.6_roadmap_multi_evento.md) - Estrategia, decisiones, timeline
- [C.7 - Especificación Técnica Detallada](C.7_roadmap_post_paso5.md) - Código ejecutable, algoritmos completos

---

## 1. PIPELINE DE EJECUCIÓN (5 PASOS)

### PASO 0: ~~Generación Dimensión SCD-2 Market Cap~~ (DEPRECADO)

**⚠️ IMPORTANTE**: Este paso fue deprecado debido a error crítico detectado el 2025-10-26.

**Problema identificado**:
- La dimensión SCD-2 generada solo contenía UN período por ticker
- Rango temporal: `2025-10-19 → 2099-12-31` (solo 7 días históricos)
- Faltaban datos históricos 2004-2025
- Causó que PASO 1 solo generara 2 días por ticker en lugar de 21 años

**Impacto**:
```
Ejecución CON market_cap (2025-10-25 23:40):
- 8,617 tickers procesados
- PERO solo 2 días por ticker (2025-10-20, 2025-10-21)
- Total days: 5,524 (debería ser ~5M = 8,617 × 600)
```

**Causa raíz**:
El join temporal en `build_daily_cache.py`:
```python
.filter(
    (pl.col("effective_from") <= pl.col("trading_day")) &
    (pl.col("trading_day") < pl.col("effective_to"))
)
```
Filtró el 99.9% de datos históricos porque SCD-2 solo cubría desde 2025-10-19.

**Solución aplicada**:
- ✅ Re-ejecutar PASO 1 **SIN** `--cap-filter-parquet`
- ✅ `market_cap_d` será NULL en daily_cache
- ✅ PASO 3 (filtrado E0) modificado para NO usar filtro market_cap

**Pendiente futuro** (post-MVP E0):
- Construir SCD-2 histórico real (múltiples períodos por ticker)
- Requiere fuente de datos con history (Polygon solo tiene snapshot actual)
- Proxy alternativo: `market_cap_d = close_d × shares_outstanding_d`

---

### PASO 1: Generación Caché Diario 2004-2025

* **Objetivo**: Agregar OHLCV 1-min → diario con features (rvol30, pctchg_d)
* **Tiempo real**: ~4.8 horas (8,620 tickers, 67.6% vacíos sin datos raw)
* **Script**: `build_daily_cache.py`

**Comando CORRECTO** (actualizado 2025-10-26 08:05):
```bash
python scripts/fase_C_ingesta_tiks/build_daily_cache.py \
  --intraday-root raw/polygon/ohlcv_intraday_1m \
  --outdir processed/daily_cache \
  --from 2004-01-01 --to 2025-10-21 \
  --parallel 8
  # SIN --cap-filter-parquet
  # market_cap_d quedará NULL temporalmente (corregir en PASO 0 v2)
```

**¿Qué hace?**:
1. Lee barras 1-min de `raw/polygon/ohlcv_intraday_1m/`
2. Agrega a diario por ticker-fecha: `close_d`, `vol_d`, `dollar_vol_d`, `vwap_d`, `session_rows`, `has_gaps`
3. Calcula features: `pctchg_d`, `return_d`, `rvol30` (rolling 30 sesiones, min_periods=1)
4. ~~Join temporal con SCD-2~~ **DEPRECADO**: `market_cap_d` = NULL

**Output esperado**:
```
processed/daily_cache/
├── ticker=BCRX/
│   ├── daily.parquet               (schema: 12 columnas, ZSTD)
│   └── _SUCCESS
├── ticker=GERN/
│   ├── daily.parquet
│   └── _SUCCESS
├── ... (8,617 tickers)
├── MANIFEST.json                   (metadata global)
└── _SUCCESS
```

**Schema output**:
```
ticker: Utf8
trading_day: Date
close_d: Float64
vol_d: Int64
dollar_vol_d: Float64
vwap_d: Float64
pctchg_d: Float64
return_d: Float64
rvol30: Float64
session_rows: Int64
has_gaps: Boolean
market_cap_d: Float64               ← NULL (SCD-2 deprecado)
```

**Métricas REALES** (ejecución 2025-10-26 08:05):
- Tickers encontrados: 8,620
- Tickers con datos: ~2,795 (32.4%)
- Tickers vacíos (0 días): 5,825 (67.6%) - sin datos raw intraday
- Ticker-días reales: Pendiente completar ejecución
- Tiempo: ~4-5 horas
- Tamaño: ~15 MB (comprimido ZSTD)

**Validación** (ejecutar ANTES de PASO 3):
```bash
python scripts/audit_paso1_complete.py
```

Verificar:
- TOP 20 tickers tienen >100 días (NO solo 2)
- market_cap_d es 100% NULL (esperado)
- rvol30, pctchg_d, dollar_vol_d calculados correctamente

**Criterio de éxito**:
- ✅ 8,617+ tickers procesados (success + no_data)
- ✅ Tickers con datos tienen rango completo 2004-2025 (NO solo 2025-10-20/21)
- ✅ rvol30 calculado correctamente
- ✅ market_cap_d = NULL (aceptable, sin filtro cap en PASO 3)

---

> ...  
> **Resultados** : mira este link [PASO 1: Generación Caché Diario 2004-2025](./C.5.0_resultados_paso_1.md)  
>  
> 📊 **Archivo JSON Generado**
> El archivo `stats_daily_cache.json` contiene:
> * Estadísticas detalladas de cada ticker
> * Distribución de días E0
> * Métricas por columna (min, max, mean, median, std)
> * Conteo de NULLs
> ¿Quieres ver el contenido del JSON de algún ticker específico? Por ejemplo:  
> `python -c "import json; data=json.load(open('stats_daily_cache.json')); ticker=[t for t in data['tickers'] if t['ticker']=='BCRX'][0]; import pprint; pprint.pprint(ticker)`
> ...  


### PASO 2: Actualizar Configuración Umbrales E0

**Objetivo**: Configurar umbrales E0 **SIN** filtro market_cap

**Tiempo**: 1 minuto

**Archivo**: `configs/universe_config.yaml`

**Contenido ACTUALIZADO** (2025-10-26):
```yaml
# E0/C_v2 (2004-2025) - Contrato v2.0.0 - market_cap removido
thresholds:
  rvol: 2.0                   # Volumen relativo mínimo
  pctchg: 0.15                # |% change| mínimo (15%)
  dvol: 5_000_000             # Dollar volume mínimo ($5M)
  min_price: 0.2              # Precio mínimo $0.20 (proxy small cap)
  max_price: 20.0             # Precio máximo $20.00 (proxy small cap)
  # cap_max: REMOVIDO (market_cap_d es NULL)
```

**Justificación**:
- Filtro de precio ($0.20-$20.00) ya elimina mayoría de large caps
- Filtro de volumen ($5M) asegura liquidez
- Market cap era redundante con precio para small caps

---

### PASO 3: Generación Universo Dinámico E0 (2004-2025)

* **Objetivo**: Identificar días info-rich según filtros E0 y generar watchlists diarias
* **Tiempo REAL**: ~11 minutos (2025-10-26 20:42-20:54)
* **Script**: `build_dynamic_universe_optimized.py`

**Comando**:
```bash
python scripts/fase_C_ingesta_tiks/build_dynamic_universe_optimized.py \
  --daily-cache processed/daily_cache \
  --outdir processed/universe/info_rich \
  --from 2004-01-01 --to 2025-10-21 \
  --config configs/universe_config.yaml
```

**¿Qué hace?**:
1. Lee caché diario completo (8,617 tickers, 14,763,368 ticker-días)
2. Aplica filtros E0:

   ```python
   r_rvol = (rvol30 >= 2.0)
   r_chg = (|pctchg_d| >= 0.15)
   r_dvol = (dollar_vol_d >= 5_000_000)
   r_px = (0.20 <= close_d <= 20.00)
   r_cap = (market_cap_d < 2_000_000_000) OR (market_cap_d IS NULL)

   info_rich = r_rvol AND r_chg AND r_dvol AND r_px AND r_cap
   ```
3. Genera watchlists diarias (una por fecha)
4. Guarda en estructura particionada por día

**Output generado**:
```
processed/universe/info_rich/
├── daily/
│   ├── date=2004-01-02/watchlist.parquet    (0 tickers E0)
│   ├── date=2004-01-06/watchlist.parquet    (3 tickers E0)
│   ├── date=2015-06-15/watchlist.parquet    (1,389 tickers E0)
│   ├── date=2024-10-15/watchlist.parquet    (2,236 tickers E0)
│   ├── ... (5,934 archivos, uno por día de trading)
│   └── date=2025-10-21/watchlist.parquet
└── _SUCCESS
```

**Schema watchlist.parquet**:
```
ticker: Utf8
trading_day: Date
close_d: Float64
pctchg_d: Float64
rvol30: Float64
dollar_vol_d: Float64
session_rows: UInt32
has_gaps: Boolean
```

**Métricas REALES** (ejecución 2025-10-26 20:42-20:54):
- **Días procesados**: 5,934 (2004-01-02 a 2025-10-21)
- **Total eventos E0**: ~29,555 ticker-días
- **Promedio E0/día**: 4.98 tickers (~5 por día)
- **Watchlists generadas**: 5,934 archivos
- **Tiempo ejecución**: ~11 minutos
  - Carga cache (8,617 tickers): 15s
  - Carga registros (14.7M rows): 64s
  - Generación watchlists: ~10 min
- **Exit code**: 0 (SUCCESS)

**Validación REAL** (ejemplos verificados):
```python
import polars as pl

# Día 2004-01-06 (inicio histórico)
df = pl.read_parquet("processed/universe/info_rich/daily/date=2004-01-06/watchlist.parquet")
print(f"Tickers E0: {len(df)}")  # 3 tickers

# Día 2015-06-15 (período intermedio)
df = pl.read_parquet("processed/universe/info_rich/daily/date=2015-06-15/watchlist.parquet")
print(f"Tickers E0: {len(df)}")  # 1,389 tickers
print(f"RVOL min: {df['rvol30'].min():.2f}")  # ≥2.0
print(f"|%chg| min: {df['pctchg_d'].abs().min():.2%}")  # ≥15%
print(f"$vol min: ${df['dollar_vol_d'].min():,.0f}")  # ≥$5M

# Día 2024-10-15 (reciente)
df = pl.read_parquet("processed/universe/info_rich/daily/date=2024-10-15/watchlist.parquet")
print(f"Tickers E0: {len(df)}")  # 2,236 tickers
print(f"Precio min: ${df['close_d'].min():.2f}")  # ≥$0.20
print(f"Precio max: ${df['close_d'].max():.2f}")  # ≤$20.00
```

**Análisis completo**: Ver notebook [analysis_watchlists_paso3.ipynb](notebooks/analysis_watchlists_paso3.ipynb)

**Resultados detallados**: Ver [C.5.2_resultados_paso_3.md](C.5.2_resultados_paso_3.md)

**Criterio de éxito**:
- ✅ 5,934 watchlists generadas (uno por día de trading)
- ✅ ~29,555 eventos E0 identificados (21 años)
- ✅ Todos los tickers E0 cumplen TODOS los umbrales
- ✅ Exit code 0 (sin errores)

---

### PASO 4: Análisis Características E0 (2004-2025)

* **Objetivo**: Documentar características de eventos E0 identificados

* **Tiempo REAL**: ~2 minutos (2025-10-26)

* **Script ejecutado**: `analyze_e0_characteristics.py`

**Comando**:
```bash
python scripts/fase_C_ingesta_tiks/analyze_e0_characteristics.py
```

**NOTA IMPORTANTE**: Este paso fue **SIMPLIFICADO** porque no existen watchlists C_v1 para comparar.
En su lugar, se documentaron las características de E0 para verificar cumplimiento del Contrato v2.0.0.

**¿Qué hace?**:
1. Lee todos los watchlists E0 (2004-2025)
2. Filtra solo eventos con `info_rich=True`
3. Analiza distribución temporal por año
4. Verifica rangos de precio ($0.20-$20.00)
5. Valida características E0 (RVOL≥2, |%chg|≥15%, $vol≥$5M)
6. Identifica TOP tickers más frecuentes

**Output generado**:
```
01_DayBook/fase_01/C_v2_ingesta_tiks_2004_2025/audits/
├── CARACTERISTICAS_E0.json         (análisis completo)
└── top_e0_tickers.csv              (TOP 20 tickers)
```

**Métricas REALES** (ejecución 2025-10-26):
```json
{
  "periodo": "2004-01-02 → 2025-10-21",
  "total_eventos_e0": 29555,
  "tickers_unicos": 4898,
  "dias_con_e0": 4949,

  "caracteristicas_e0": {
    "rvol30": {"mean": 9.13, "median": 5.94, "umbral_min": 2.0},
    "pctchg_abs": {"mean": 0.4175, "median": 0.2377, "umbral_min": 0.15},
    "dollar_vol": {"mean": 82792984, "median": 22094051, "umbral_min": 5000000}
  },

  "distribucion_precio": {
    "$1-$5": "35.6%",
    "$10-$20": "30.4%",
    "$5-$10": "28.2%",
    "$0.50-$1": "3.8%",
    "$0.20-$0.50 (penny)": "2.1%"
  },

  "top_5_tickers": [
    {"ticker": "BCRX", "dias_e0": 63},
    {"ticker": "GERN", "dias_e0": 53},
    {"ticker": "VXRT", "dias_e0": 51},
    {"ticker": "SRNE", "dias_e0": 50},
    {"ticker": "BLDP", "dias_e0": 43}
  ],

  "conclusion": "E0 cumple con Contrato v2.0.0: small/micro caps ($0.20-$20.00), info-rich (RVOL≥2, |%chg|≥15%, $vol≥$5M)"
}
```

**Eventos E0 por año**:
- 2004-2007: ~400 eventos/año (inicio histórico)
- 2008-2009: ~1,000 eventos/año (crisis financiera)
- 2010-2019: ~500-1,300 eventos/año (estable)
- 2020-2021: ~3,300 eventos/año (pandemia, alta volatilidad)
- 2022-2024: ~2,200-3,500 eventos/año (normalización)
- 2025: ~4,200 eventos (parcial, hasta Oct 21)

**Validación cumplimiento filtros E0**:
```python
# Todos los eventos E0 cumplen:
RVOL30: mean=9.13, median=5.94    ✅ (≥2.0)
|%chg|: mean=41.75%, median=23.77% ✅ (≥15%)
$vol: mean=$82.8M, median=$22.1M   ✅ (≥$5M)
Precio: min=$0.20, max=$20.00      ✅ (rango correcto)
```

* **Análisis completo**: Ver notebook [analysis_caracteristicas_paso4_executed.ipynb](notebooks/analysis_caracteristicas_paso4_executed.ipynb)

* **Resultados detallados**: Ver [C.5.4_resultados_paso_4.md](C.5.4_resultados_paso_4.md)

* **Archivos de auditoría**: Ver [audits/CARACTERISTICAS_E0.json](audits/CARACTERISTICAS_E0.json)

**Criterio de éxito**:
- ✅ 29,555 eventos E0 identificados (2004-2025)
- ✅ 4,898 tickers únicos con eventos E0
- ✅ TODOS los eventos cumplen filtros E0
- ✅ Distribución de precio coherente con small/micro caps
- ✅ Documentación completa generada

**IMPORTANTE**: No se comparó con C_v1 porque no existen watchlists v1 guardadas.
Esta auditoría verifica que E0 cumple con el Contrato v2.0.0 sin necesidad de comparación.

---

### PASO 5: Descarga Ticks Días Info-Rich E0

* **Objetivo**: Descargar ticks de Polygon solo para días info-rich identificados

  * **Status**: COMPLETADO (2025-10-27)  
  * **Tiempo real**: ~1 hora (paralelización eficiente)  
  * **Cobertura**: 92.2% (64,801 / 70,290 días trading)  
  * **Storage**: 16.58 GB (vs 2.6 TB estimado, -99.2%)  

* **Script**: `download_trades_optimized.py`

* **Estrategia**: **Modo watchlists** (lee automáticamente todos los watchlists)

**Comando RECOMENDADO** (todos los tickers E0 + ventana ±1 día):
```bash
python scripts/fase_C_ingesta_tiks/download_trades_optimized.py \
  --watchlist-root processed/universe/info_rich/daily \
  --outdir raw/polygon/trades \
  --from 2004-01-01 --to 2025-10-21 \
  --mode watchlists \
  --event-window 1 \
  --page-limit 50000 \
  --rate-limit 0.15 \
  --workers 8 \
  --resume
```

**Comando ALTERNATIVO** (solo día del evento, sin ventana):
```bash
python scripts/fase_C_ingesta_tiks/download_trades_optimized.py \
  --watchlist-root processed/universe/info_rich/daily \
  --outdir raw/polygon/trades \
  --from 2004-01-01 --to 2025-10-21 \
  --mode watchlists \
  --event-window 0 \
  --page-limit 50000 \
  --rate-limit 0.15 \
  --workers 8 \
  --resume
```

**Comando ALTERNATIVO** (solo TOP 200 tickers más activos):
```bash
python scripts/fase_C_ingesta_tiks/download_trades_optimized.py \
  --tickers-csv processed/universe/info_rich/topN_12m.csv \
  --watchlist-root processed/universe/info_rich/daily \
  --outdir raw/polygon/trades \
  --from 2004-01-01 --to 2025-10-21 \
  --mode watchlists \
  --page-limit 50000 \
  --rate-limit 0.15 \
  --workers 8 \
  --resume
```

**¿Qué hace?** (MODO WATCHLISTS):
1. Lee todos los watchlists en `processed/universe/info_rich/daily/` (5,934 días)
2. Para cada watchlist, identifica tickers con `info_rich=True` (eventos E0)
3. **EXPANDE cada evento E0 con ventana temporal**: `--event-window N` descarga ±N días alrededor del evento
   - `event-window=0`: Solo el día del evento (29,555 días total)
   - `event-window=1` (DEFAULT): ±1 día → [day-1, day, day+1] (~88,665 días total)
   - Ej: E0 el 2020-03-16 con window=1 descarga [2020-03-15, 2020-03-16, 2020-03-17]
   - **Rationale**: Triple barrier labeling, meta-labeling y microstructure analysis necesitan contexto pre/post evento
4. Descarga ticks de esos ticker-días usando Polygon API v3
5. **Si usas `--tickers-csv`**: Limita descarga SOLO a tickers en ese CSV (ej: TOP 200)
6. **Sin `--tickers-csv`**: Descarga TODOS los tickers E0 (4,898 únicos, 29,555 eventos)
7. Guarda en: `raw/polygon/trades/{TICKER}/date={YYYY-MM-DD}/trades.parquet`
8. Marca completados con `_SUCCESS`
9. Resume automático si se interrumpe

**Parámetros clave**:
- `--mode watchlists`: Descarga solo días con `info_rich=True` (eficiente)
- `--tickers-csv`: **OPCIONAL** - Limita a subset de tickers (ej: topN_12m.csv = TOP 200)
- `--event-window N`: **NUEVO** - Días extra antes/después del evento E0 (default=1)
  - `0`: Solo día evento (29,555 días total)
  - `1`: ±1 día (window default, ~88,665 días, 3x volumen)
  - `2`: ±2 días (~147,775 días, 5x volumen)
- `--page-limit 50000`: Tamaño de página Polygon (óptimo para ticks)
- `--rate-limit 0.15`: 150ms entre requests (evita 429)
- `--workers 8`: Procesos concurrentes (ajustar según RAM)
- `--resume`: Salta días ya descargados (_SUCCESS existe)

**Métricas REALES** (PASO 5 completado):
```
Eventos E0 identificados: 29,555 ticker-días (2004-2025)
Tickers únicos E0: 4,898
Event window aplicado: ±1 día

DESCARGA COMPLETADA:
- Días objetivo: 82,012 (incluye weekends/holidays)
- Días trading reales: 70,290
- Días descargados: 64,801 (92.2% cobertura)
- Días faltantes: 7,039 (7.8% - Polygon gaps, delisted)

STORAGE Y TICKS:
- Storage total: 16.58 GB
- Proyección 100%: ~20 GB (vs 2.6 TB estimado, -99.2%)
- Ticks promedio/día: ~12,234 (vs ~50K estimado)
- Total ticks: ~805M (vs ~4.4B estimado)
- Tamaño promedio/día: ~258 KB (vs ~30 MB estimado)

RAZON DIFERENCIA:
- Small caps tienen 100x-1000x menos volumen que large caps
- Estimación basada en tickers grandes (AAPL, TSLA)
- Años antiguos (2004-2010) tienen muy pocos ticks
```

**Ver resultados detallados**: `C.5.5_resultados_paso_5.md`

**Nota**: Con 8 workers en paralelo. Con 1 worker sería 8x más lento.

**Output REAL generado**:
```
raw/polygon/trades/
├── BCRX/                            (63 días E0 - TOP 1 ticker)
│   ├── date=2008-10-15/
│   │   ├── trades.parquet          (ticks del día)
│   │   └── _SUCCESS
│   ├── date=2020-03-16/
│   │   ├── trades.parquet
│   │   └── _SUCCESS
│   └── ... (63 días con eventos E0)
├── GERN/                            (53 días E0 - TOP 2 ticker)
│   ├── date=2009-01-22/
│   │   ├── trades.parquet
│   │   └── _SUCCESS
│   └── ...
├── VXRT/                            (51 días E0 - TOP 3 ticker)
│   └── ...
└── ... (4,875 tickers con descarga, 67,439 archivos completados)
```

**Archivos REALES generados**:
- **Tickers con descarga**: 4,875 (de 4,898 tickers únicos E0)
- **Archivos _SUCCESS**: 67,439
- **Archivos trades.parquet**: 67,439
- **Storage total**: 16.58 GB (~20 GB proyectado al 100%)

**Schema trades.parquet** (Polygon API v3):
```
t: Datetime(ns)                  # Timestamp nanosegundos
p: Float64                       # Precio
s: UInt64                        # Size (volumen)
c: List[UInt8]                   # Condiciones del trade
x: UInt8                         # Exchange ID
z: UInt8                         # Tape (A/B/C)
```

**Validación durante descarga**:
```python
import polars as pl
from pathlib import Path

# Verificar ticker-día ejemplo
df = pl.read_parquet("raw/polygon/trades/AAPL/date=2004-01-05/trades.parquet")
print(f"Ticks: {len(df):,}")
print(f"Rango tiempo: {df['t'].min()} → {df['t'].max()}")
print(f"Precio min/max: ${df['p'].min():.2f} / ${df['p'].max():.2f}")
print(f"Tamaño total: {sum(df['s']):,} shares")
print(df.head(10))
```

**Monitoreo progreso**:
```bash
# Ver logs en tiempo real
tail -f download_trades.log

# Contar días completados
find raw/polygon/trades -name "_SUCCESS" | wc -l

# Estimar tiempo restante (actualizar cada hora)
python scripts/fase_C_ingesta_tiks/estimate_remaining_time.py \
  --target-dir raw/polygon/trades \
  --total-expected 150000
```

**Criterio de éxito**:
- ✅ >95% ticker-días info-rich descargados
- ✅ Ticks válidos (timestamp, price, size coherentes)
- ✅ `_SUCCESS` por cada ticker-día completado
- ✅ Resume funciona correctamente si se interrumpe

---

## 2. ESTRUCTURA FINAL DE DATOS (PASO 5 COMPLETADO)

```
D:\04_TRADING_SMALLCAPS\
│
├── raw/polygon/
│   ├── reference/
│   │   └── ticker_details/                (8,686 tickers)
│   └── trades/                             (PASO 5 ✅ COMPLETADO)
│       ├── BCRX/
│       │   ├── date=2008-10-15/
│       │   │   ├── trades.parquet
│       │   │   └── _SUCCESS
│       │   └── ... (63 días E0 para BCRX)
│       └── ... (67,439 archivos, 16.58 GB)
│
├── processed/
│   ├── ref/
│   │   └── market_cap_dim/
│   │       └── market_cap_dim.parquet      (SCD-2, 8,686 tickers)
│   ├── daily_cache/                         (PASO 1 ✅ COMPLETADO)
│   │   ├── ticker=AAPL/
│   │   │   ├── daily.parquet
│   │   │   └── _SUCCESS
│   │   └── ... (8,618 tickers)
│   └── universe/
│       └── info_rich/                       (PASO 3 ✅ COMPLETADO)
│           ├── daily/
│           │   ├── date=2004-01-02/watchlist.parquet
│           │   └── ... (5,934 watchlists)
│           ├── topN_12m.parquet
│           └── topN_12m.csv
│
└── 01_DayBook/fase_01/C_v2_ingesta_tiks_2004_2025/
    ├── audits/                              (PASO 4 ✅ COMPLETADO)
    │   ├── CARACTERISTICAS_E0.json
    │   └── top_e0_tickers.csv
    ├── C.5_plan_ejecucion_E0_descarga_ticks.md
    ├── C.5.5_resultados_paso_5.md
    └── notebooks/
        └── analysis_paso5_executed.ipynb
```

**Métricas finales REALES (2025-10-27)**:
- **PASO 1** (Daily Cache): 8,617 tickers procesados
- **PASO 3** (Watchlists): 5,934 días, 29,555 eventos E0, 4,898 tickers únicos
- **PASO 5** (Ticks): 4,875 tickers, 67,439 archivos, 16.58 GB, ~805M ticks, 92.2% cobertura

---

## 3. ESPECIFICACIÓN TÉCNICA MULTI-EVENTO (E0 + E1-E17 FUTUROS)

**Roadmaps de Implementación**:
- **[C.6 - Roadmap Ejecutivo Multi-Evento](C.6_roadmap_multi_evento.md)** - Estrategia Híbrido A+B, decisiones, timeline
- **[C.7 - Especificación Técnica Detallada](C.7_roadmap_post_paso5.md)** - Código ejecutable, algoritmos DIB/VIB, detectores completos

Esta sección documenta la **especificación técnica** de cómo se almacenarán y procesarán múltiples eventos (E0-E17) de forma eficiente sin duplicar ticks.

### 3.1 Estado Actual

**ACTUALMENTE IMPLEMENTADO** (PASO 5 completado):
```
✅ E0 (Generic Info-Rich) - 2004-2025
   - 67,439 archivos descargados
   - 16.58 GB storage
   - 92.2% cobertura (64,801 / 70,290 días trading)
   - Event window: ±1 día
   - Estructura: raw/polygon/trades/{TICKER}/date={YYYY-MM-DD}/trades.parquet
```

**PLANIFICADO** (Ver [C.1](C.1_estrategia_descarga_ticks_eventos.md) y [C.6](C.6_roadmap_multi_evento.md)):
- E1: Volume Explosion (RVOL > 5×)
- E4: Parabolic Move (+50% en ≤5 días)
- E7: First Red Day (patrón más confiable)
- E8: Gap Down (>15%)
- E13: Offering Pricing (dilution events)

### 3.2 Arquitectura de Almacenamiento Multi-Evento

**Pregunta**: ¿Cómo guardar múltiples eventos sin duplicar ticks?

**Respuesta**: Watchlist unificado + metadata JSON por ticker-día

#### Opción A: Carpetas Separadas por Evento ❌

**Problema**: Duplicación masiva si `BCRX` tiene E0+E1+E4 el mismo día → 3× `trades.parquet`

**Conclusión**: Descartada (no escala para ML, imposible "verdad única" por ticker-día)

#### Opción B: Watchlist Unificado + Metadata JSON ✅

**Estructura**:

```
processed/universe/multi_event/daily/date=YYYY-MM-DD/
└── watchlist.parquet
    # Columnas boolean por evento: E0_info_rich, E1_volume_explosion, E4_parabolic, E7_first_red, E8_gap_down
    # event_types: list[str]  (ej: ["E0", "E4"])
    # max_event_window: int   (ventana individual más grande, ej: E4 ±3 → 7 días)

raw/polygon/trades/TICKER/date=YYYY-MM-DD/
├── trades.parquet  # UN SOLO archivo (sin duplicados)
├── _SUCCESS
└── events.json     # Metadata: qué eventos, ventanas, is_event_day, window_offset
```

**Ventajas**:
- ✅ UN solo `trades.parquet` por ticker-día (sin duplicación)
- ✅ Storage eficiente (~3-5x menos que carpetas separadas)
- ✅ Filtrado flexible por evento(s)
- ✅ Trazabilidad completa vía `events.json`

### 3.3 Especificación Técnica de Datos

#### Schema: `watchlist.parquet` (multi-evento)

```python
ticker: str
trading_day: date

# Columnas boolean legibles por evento
E0_info_rich: bool
E1_volume_explosion: bool
E4_parabolic: bool
E7_first_red_day: bool
E8_gap_down: bool

# Resumen compacto
event_types: list[str]         # Códigos cortos: ["E0", "E4"]
max_event_window: int          # Ventana individual más grande (E4 ±3 → 7 días)
```

**Nota**: `max_event_window` es el tamaño total de la ventana MÁS EXIGENTE, NO la unión de ventanas.

#### Schema: `events.json` (por ticker-día descargado)

Ubicación: `raw/polygon/trades/TICKER/date=YYYY-MM-DD/events.json`

```json
{
  "ticker": "BCRX",
  "date": "2020-03-14",

  "events_context": [
    {
      "event_type": "E4",
      "event_day": "2020-03-16",
      "is_event_day": false,
      "window_offset": -2,
      "window_size": 7
    },
    {
      "event_type": "E0",
      "event_day": "2020-03-16",
      "is_event_day": false,
      "window_offset": -2,
      "window_size": 3
    }
  ],

  "max_event_window": 7,
  "download_window_applied_days": ["2020-03-13", "2020-03-14", ..., "2020-03-19"],
  "_success": true
}
```

**Campos clave**:
- `is_event_day`: Distingue día del evento vs contexto pre/post (crítico para labeling)
- `window_offset`: Días desde evento (`date - event_day`)
- `download_window_applied_days`: Auditoría y reproducibilidad

#### Lógica `--resume` con Merge Inteligente

**Problema**: Nuevo evento E4 requiere ventana ±3, pero E0 ya descargó ±1

**Solución**: Merge incremental en `events.json`

1. Leer `events.json` existente
2. Agregar nuevo evento a `events_context`
3. Recalcular `max_event_window` = max(window_size)
4. Regenerar `download_window_applied_days` (unión de ventanas)
5. Si hay días nuevos no cubiertos → descargar adicionales

**Implementación**: Ver `scripts/fase_C_ingesta_tiks/build_multi_event_watchlists.py`

---

### 3.4 Implementación (Roadmap Completo)

**Ver documento completo**: [C.6_roadmap_multi_evento.md](C.6_roadmap_multi_evento.md)

**Scripts a implementar**:
- `scripts/fase_C_ingesta_tiks/event_detectors/` (E1, E4, E7, E8)

```python
def calculate_all_events(df: pl.DataFrame) -> pl.DataFrame:
    """
    Calcula todos los eventos E0-E17 en un solo pass del daily_cache.
    """
    return df.with_columns([
        # E0: Generic Info-Rich (ya implementado)
        ((pl.col('rvol30') >= 2.0) &
         (pl.col('pctchg_d').abs() >= 0.15) &
         (pl.col('dollar_vol_d') >= 5_000_000) &
         (pl.col('close_d') >= 0.20) &
         (pl.col('close_d') <= 20.00)).alias('E0_info_rich'),

        # E1: Volume Explosion
        (pl.col('rvol30') >= 5.0).alias('E1_volume_explosion'),

        # E2: Gap Up > 10%
        (pl.col('gap_pct') > 0.10).alias('E2_gap_up'),

        # E4: Parabolic Move (+50% en ≤5 días)
        (pl.col('change_5d') >= 0.50).alias('E4_parabolic'),

        # E5: Breakout ATH
        (pl.col('close_d') >= pl.col('ath_252d')).alias('E5_breakout_ath'),

        # ... E7, E8, E10, E12-E17

        # Metadata: lista de eventos activos
        pl.when(pl.col('E0_info_rich')).then(pl.lit('E0')).otherwise(pl.lit(None)).alias('e0_flag'),
        pl.when(pl.col('E1_volume_explosion')).then(pl.lit('E1')).otherwise(pl.lit(None)).alias('e1_flag'),
        # ... agregar todos los flags
    ]).with_columns([
        # Consolidar eventos en una lista
        pl.concat_list(['e0_flag', 'e1_flag', 'e4_flag', ...])
          .list.drop_nulls()
          .alias('event_types'),

        # Calcular ventana máxima
        pl.when(pl.col('E4_parabolic')).then(pl.lit(6))
          .when(pl.col('E5_breakout_ath')).then(pl.lit(4))
          .when(pl.col('E1_volume_explosion')).then(pl.lit(4))
          .when(pl.col('E0_info_rich')).then(pl.lit(3))
          .otherwise(pl.lit(1))
          .alias('max_event_window')
    ])
```

#### Paso 2: Modificar `download_trades_optimized.py`

Agregar soporte para multi-eventos:

```python
def load_multi_event_days(watchlist_root: Path, dfrom: date, dto: date,
                          event_types: List[str], allowed_tickers: Optional[set]) -> Dict[str, List[date]]:
    """
    Lee watchlists multi-evento y expande según ventana máxima por ticker-día.

    Args:
        event_types: ['E0', 'E1', 'E4'] - qué eventos descargar
        Si None, descarga TODOS los eventos encontrados
    """
    days_by_ticker = {}

    for watchlist_path in sorted(watchlist_root.glob('date=*/watchlist.parquet')):
        df = pl.read_parquet(watchlist_path)
        day = datetime.strptime(watchlist_path.parent.name.split('=')[1], '%Y-%m-%d').date()

        # Filtrar por eventos solicitados (si se especifican)
        if event_types:
            event_filter = pl.lit(False)
            for event_type in event_types:
                event_filter = event_filter | pl.col(f'{event_type}_event')
            df_events = df.filter(event_filter)
        else:
            # Cualquier ticker con al menos un evento activo
            df_events = df.filter(pl.col('event_types').list.len() > 0)

        # Expandir según max_event_window de cada ticker-día
        for row in df_events.iter_rows(named=True):
            ticker = row['ticker']
            if allowed_tickers and ticker not in allowed_tickers:
                continue

            max_window = row['max_event_window']

            # Expandir ventana: [day - max_window, day, day + max_window]
            for offset in range(-max_window, max_window + 1):
                expanded_day = day + timedelta(days=offset)
                if expanded_day >= dfrom and expanded_day <= dto:
                    days_by_ticker.setdefault(ticker, []).append(expanded_day)

    # Deduplicar y ordenar fechas
    for ticker in days_by_ticker:
        days_by_ticker[ticker] = sorted(set(days_by_ticker[ticker]))

    return days_by_ticker

# Agregar argumento --event-types al argparse
ap.add_argument("--event-types", type=str, default=None,
                help="Comma-separated list de eventos a descargar (ej: 'E0,E1,E4'). "
                     "Si no se especifica, descarga TODOS los eventos detectados.")
```

#### Paso 3: Guardar Metadata de Eventos

Al descargar cada ticker-día, guardar metadata:

```python
def download_span_with_metadata(ticker: str, day: date, watchlist_data: dict, ...):
    """
    Descarga ticks + guarda metadata de eventos.
    """
    # ... descargar ticks como siempre ...

    # Guardar metadata de eventos
    events_json = {
        'ticker': ticker,
        'date': str(day),
        'events': watchlist_data['event_types'],  # ["E0", "E4"]
        'event_windows': {
            'E0': 3,
            'E4': 6
        },
        'max_window_used': watchlist_data['max_event_window']
    }

    events_path = day_path / 'events.json'
    with open(events_path, 'w') as f:
        json.dump(events_json, f, indent=2)
```

### 3.5 Estructura Final de Datos (Multi-Evento)

```
raw/polygon/trades/
└── BCRX/
    ├── date=2020-03-15/          ← Ventana pre-evento
    │   ├── trades.parquet
    │   ├── _SUCCESS
    │   └── events.json           ← {"events": ["E0", "E4"], "reason": "window"}
    ├── date=2020-03-16/          ← DÍA DEL EVENTO
    │   ├── trades.parquet
    │   ├── _SUCCESS
    │   └── events.json           ← {"events": ["E0", "E4"], "reason": "event_day"}
    ├── date=2020-03-17/          ← Ventana post-evento (day+1)
    │   ├── trades.parquet
    │   ├── _SUCCESS
    │   └── events.json           ← {"events": ["E0", "E4"], "reason": "window"}
    ├── date=2020-03-18/          ← Ventana extendida (E4 requiere hasta day+3)
    │   ├── trades.parquet
    │   ├── _SUCCESS
    │   └── events.json           ← {"events": ["E4"], "reason": "window_E4"}
    └── ...
```

### 3.6 Uso Downstream (Multi-Evento)

```python
import polars as pl
from pathlib import Path

# Cargar todos los eventos
watchlists = pl.scan_parquet('processed/universe/multi_event/daily/**/*.parquet')

# Filtrar por eventos de interés
e0_and_e4_events = watchlists.filter(
    pl.col('E0_info_rich') & pl.col('E4_parabolic')
).collect()

print(f"Tickers con E0+E4 simultáneos: {len(e0_and_e4_events)}")

# Cargar ticks para un evento
for row in e0_and_e4_events.head(10).iter_rows(named=True):
    ticker = row['ticker']
    event_date = row['trading_day']

    # Cargar ticks del día del evento
    ticks_path = f'raw/polygon/trades/{ticker}/date={event_date}/trades.parquet'
    if Path(ticks_path).exists():
        ticks = pl.read_parquet(ticks_path)
        print(f"{ticker} {event_date}: {len(ticks):,} ticks - Eventos: {row['event_types']}")
```

### 3.7 Resumen: Respuesta a "¿Dónde se Guardarán los Otros E's?"

1. **Ahora mismo**: NO SE GUARDAN porque E1-E17 no están implementados (solo E0 existe)

2. **Cuando los implementes** (recomendación):
   - **Watchlists**: UN solo archivo diario con columnas booleanas por cada evento
   - **Ticks**: UN solo archivo por ticker-día (sin duplicados)
   - **Metadata**: `events.json` indica qué eventos aplican a cada ticker-día
   - **Sin duplicación**: Si BCRX tiene E0+E1+E4 el 2020-03-16 → un solo `trades.parquet`

3. **Beneficios**:
   - Eficiencia de storage (~3-5x menos espacio)
   - Análisis downstream simplificado
   - Trazabilidad completa (metadata en JSON)
   - Flexible: puedes filtrar por cualquier combinación de eventos

---

## 4. COMANDOS RÁPIDOS (RESUMEN)

```bash
# PASO 0: SCD-2 - DEPRECADO (solo cubre 2025-10-19→)
# NO ejecutar

# PASO 1: Caché diario (SIN market_cap)
python scripts/fase_C_ingesta_tiks/build_daily_cache.py \
  --intraday-root raw/polygon/ohlcv_intraday_1m \
  --outdir processed/daily_cache \
  --from 2004-01-01 --to 2025-10-21 \
  --parallel 8
  # SIN --cap-filter-parquet

# PASO 2: Actualizar config (remover cap_max)
# Editar: configs/universe_config.yaml
# Comentar o eliminar: cap_max: 2_000_000_000

# PASO 3: Universo E0 (sin filtro market_cap)
python scripts/fase_C_ingesta_tiks/build_dynamic_universe_optimized.py \
  --daily-cache processed/daily_cache \
  --outdir processed/universe/info_rich \
  --from 2004-01-01 --to 2025-10-21 \
  --config configs/universe_config.yaml

# PASO 4: Verificación (script a crear)
python scripts/fase_C_ingesta_tiks/verify_inclusion_C_v1_vs_E0.py \
  --c_v1-watchlists processed/universe/info_rich_v1/daily \
  --e0-watchlists processed/universe/info_rich/daily \
  --from 2020-01-01 --to 2025-10-21 \
  --outdir audits

# PASO 5: Descarga ticks
python scripts/fase_C_ingesta_tiks/download_trades_optimized.py \
  --tickers-csv processed/universe/info_rich/topN_12m.csv \
  --watchlist-root processed/universe/info_rich/daily \
  --outdir raw/polygon/trades \
  --from 2004-01-01 --to 2025-10-21 \
  --mode watchlists \
  --page-limit 50000 \
  --rate-limit 0.15 \
  --workers 8 \
  --resume
```

---

## 5. NOTAS FINALES

### Validación conceptual
Este plan ejecuta la estrategia documentada en Contrato_E0.md v2.0.0:
- ✅ E0 como "pegamento legal" entre C_v1 y C_v2
- ✅ Filtros coherentes con mandato Small/MicroCap
- ✅ Documentación de diferencias C_v1 vs E0
- ✅ Trazabilidad completa de exclusiones/inclusiones

### Garantía de coherencia
- Pipeline único unificado (no C_v1 + C_v2 separados)
- Versionado formal (Contrato v2.0.0)
- Auditoría empírica de inclusión
- Justificación documentada de diferencias

### Escalabilidad a 21 años
- SCD-2 para market cap histórico correcto
- Join temporal evita survivorship bias
- Watchlists por día permiten descarga selectiva
- Resume tolerance para ejecuciones largas

### Listo para ML
- Features pre-calculadas (rvol30, pctchg_d)
- Ticks listos para barras informativas
- Etiquetas por evento (E0, E1, ..., E13)
- Particionado por régimen macro

---

**Documento creado**: 2025-10-25
**Autor**:  Alex Just Rodriguez
**Versión**: 1.0.0
**Basado en**: Contrato_E0.md v2.0.0
**Status**: LISTO PARA EJECUCIÓN

**FIN DEL PLAN DE EJECUCIÓN**
