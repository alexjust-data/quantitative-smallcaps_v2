# C.5 - Plan de Ejecución E0: Descarga Ticks 2004-2025

**Fecha**: 2025-10-26  
**Versión**: 1.1.0 (actualizado post-error SCD-2)  
**Basado en**: Contrato_E0.md v2.0.0  
**Prerequisito**: C.4 - Descarga OHLCV Daily/Intraday completada (8,620 tickers raw intraday)  
**Ver también**: C.7_ERROR_SCD2_Y_SOLUCION.md para contexto del error crítico y fix aplicado    



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

**Objetivo**: Descargar ticks de Polygon solo para días info-rich identificados

**Status**: COMPLETADO (2025-10-27)
**Tiempo real**: ~1 hora (paralelización eficiente)
**Cobertura**: 92.2% (64,801 / 70,290 días trading)
**Storage**: 16.58 GB (vs 2.6 TB estimado, -99.2%)

**Script**: `download_trades_optimized.py`

**Estrategia**: **Modo watchlists** (lee automáticamente todos los watchlists)

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

**Output esperado**:
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
└── ... (4,898 tickers únicos, 29,555 eventos E0 total)
```

**Schema trades.parquet**:
```
t: Datetime (microseconds)      # sip_timestamp
p: Float64                       # price
s: Int64                         # size
c: List[Utf8]                   # conditions
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

## 2. CRONOGRAMA REAL vs ESTIMADO

| Paso | Tarea | Estimado | Real | Status |
|------|-------|----------|------|--------|
| 0 | ~~SCD-2 market cap~~ | 2 min | 2 min | ❌ DEPRECADO (datos solo 2025-10-19→) |
| 1 | Caché diario 2004-2025 | 6-8h | 4.8h × 2 = 9.6h | ✅ COMPLETADO (2da ejecución OK) |
| 2 | Config umbrales | 1 min | 1 min | ✅ ACTUALIZADO (sin cap_max) |
| 3 | Universo dinámico E0 | 30-45 min | 11 min | ✅ COMPLETADO (5,934 watchlists, 29,555 E0) |
| 4 | Análisis características E0 | 10-15 min | 2 min | ✅ COMPLETADO (simplificado, sin C_v1) |
| 5 | Descarga ticks | 18-24h | TBD | ⏳ PENDIENTE |

**Total real**: ~10-15 horas hasta aquí (incluyendo debugging y re-ejecución)

**Nota**: El paso 5 (descarga ticks) es el cuello de botella. Considerar:
- Ejecutar en servidor/instancia cloud con buena conexión
- Monitorear rate limits de Polygon API
- Usar `--resume` para tolerancia a fallos
- Ejecutar en horario off-peak si es posible

---

## 3. ESTRATEGIA DE VALIDACIÓN (CADA PASO)

### Antes de avanzar al siguiente paso, verificar:

**PASO 0 → PASO 1**:
- ~~SCD-2 market_cap_dim~~ **DEPRECADO** (solo cubre 2025-10-19→)

**PASO 1 → PASO 2**:
- ✅ 8,617+ tickers procesados
- ✅ Tickers con datos tienen >100 días (verificar NO solo 2)
- ✅ `rvol30`, `pctchg_d`, `dollar_vol_d` calculados
- ✅ `market_cap_d` = NULL (aceptable)

**PASO 2 → PASO 3**:
- ✅ `configs/universe_config.yaml` actualizado SIN `cap_max`
- ✅ `min_price: 0.2`, `max_price: 20.0`

**PASO 3 → PASO 4**:
- ✅ 5,934 watchlists generadas (confirmado)
- ✅ ~29,555 eventos E0 identificados
- ✅ Tickers info-rich cumplen TODOS los umbrales
- ✅ Exit code 0 (ejecución exitosa)

**PASO 4 → PASO 5**:
- ✅ Análisis características E0 completado
- ✅ 29,555 eventos E0 identificados (2004-2025)
- ✅ TODOS los eventos cumplen filtros E0
- ✅ Documentación JSON y CSV generada

**PASO 5 → FIN**:
- ✅ >95% ticker-días info-rich con ticks descargados
- ✅ `_SUCCESS` markers presentes
- ✅ Ticks válidos (sample verificado)

---

## 4. GESTIÓN DE ERRORES Y CONTINGENCIAS

### Errores comunes y soluciones:

**SCD-2 con baja cobertura** (<80% market cap):
```bash
# Opción 1: Imputar con shares_outstanding × close_d
python scripts/fase_C_ingesta_tiks/build_market_cap_dim.py \
  --details-root raw/polygon/reference/ticker_details \
  --outdir processed/ref/market_cap_dim \
  --daily-cache processed/daily_cache \
  --impute
```

**Caché diario lento**:
- Aumentar `--parallel` (si tienes más cores)
- Ejecutar en instancia con más CPU/RAM
- Usar `--incremental` para procesar solo nuevos

**Descarga ticks interrumpida**:
- Usar `--resume` (automático)
- Verificar API key de Polygon activa
- Verificar rate limits no excedidos
- Ajustar `--rate-limit` si ves muchos 429

**Polygon API 429 (Too Many Requests)**:
- Aumentar `--rate-limit` (0.15 → 0.20 → 0.25)
- Reducir `--workers` (8 → 4 → 2)
- Pausar y reintentar más tarde

**Storage lleno durante descarga ticks**:
- Estimar antes: ~4.5 TB para 21 años
- Considerar descarga por ventanas (2004-2010, 2011-2015, etc.)
- Comprimir con ZSTD level 3-5 (más agresivo)

---

## 5. ESTRUCTURA FINAL DE DATOS

```
D:\04_TRADING_SMALLCAPS\
│
├── raw/polygon/
│   ├── reference/ticker_details/          (snapshots market cap)
│   └── trades/                             (ticks E0)
│       ├── AAPL/date=2004-01-05/trades.parquet
│       └── ... (~150,000 ticker-días)
│
├── processed/
│   ├── ref/market_cap_dim/
│   │   └── market_cap_dim.parquet         (SCD-2 temporal)
│   ├── daily_cache/                        (caché diario agregado)
│   │   ├── ticker=AAPL/daily.parquet
│   │   └── ... (3,107 tickers)
│   └── universe/info_rich/
│       ├── daily/                          (watchlists E0)
│       │   ├── date=2004-01-02/watchlist.parquet
│       │   └── ... (~5,292 días)
│       ├── topN_12m.parquet
│       └── topN_12m.csv
│
├── audits/
│   ├── AUDITORIA_INCLUSION_C_v1_vs_E0.json
│   ├── only_C_v1_midcaps.parquet
│   └── only_E0_pennystocks.parquet
│
└── 01_DayBook/fase_01/C_v2_ingesta_tiks_2004_2025/
    ├── Contrato_E0.md                      (contrato inmutable v2.0.0)
    ├── C.4_anotacion_descarga_tiks_daily.md
    └── C.5_plan_ejecucion_E0_descarga_ticks.md  (este documento)
```

---

## 6. PRÓXIMOS PASOS POST-DESCARGA

Una vez completada la descarga de ticks E0:

1. **Construcción de Barras Informativas** (DIB/VIB):
   - Dollar Imbalance Bars
   - Volume Imbalance Bars
   - Tick Imbalance Bars

2. **Triple Barrier Labeling**:
   - Profit target / stop loss
   - Time-based exit
   - Meta-labeling

3. **Feature Engineering**:
   - Microestructura (spread, VWAP deviation, order flow)
   - Volume Profile
   - Tick-level features

4. **Sample Weighting**:
   - Bootstrap weights
   - Sequential bootstrap
   - Time decay

5. **Incorporación eventos E1-E13**:
   - Parabolic (E4)
   - First Red Day (E7)
   - Dilution (E9)
   - etc.

6. **Dataset Maestro 2004-2025**:
   - Unificación E0 ∪ E1 ∪ ... ∪ E13
   - Particionado por régimen
   - Versionado para ML

---

## 6. EVENTOS FUTUROS E1-E17 (NO IMPLEMENTADOS AÚN)

### 6.1 Estado Actual vs. Futuro

**ACTUALMENTE IMPLEMENTADO** (C_v2 Fase 1 - PASO 5 en ejecución):
```
✅ E0 (Generic Info-Rich)
   - RVOL ≥ 2.0
   - |%chg| ≥ 15%
   - $vol ≥ $5M
   - Precio $0.20-$20
   - Event window: ±1 día (3 días total)
   - Status: DESCARGANDO AHORA
   - Archivos: raw/polygon/trades/{TICKER}/date={YYYY-MM-DD}/
```

**PLANIFICADO PARA FUTURO** (C_v2 Fases 2-N):

Según [C.1_estrategia_descarga_ticks_eventos.md](C.1_estrategia_descarga_ticks_eventos.md):

| Evento | Descripción | Ventana | Días/Evento | Status |
|--------|-------------|---------|-------------|--------|
| E1 | Volume Explosion (RVOL > 5×) | −1 → +2 | 4 días | ⏳ Pendiente |
| E2 | Gap Up > 10% | −1 → +1 | 3 días | ⏳ Pendiente |
| E3 | Spike Intraday | mismo día | 1 día | ⏳ Pendiente |
| E4 | Parabolic Move (+50% en ≤5 días) | −2 → +3 | 6 días | ⏳ Pendiente |
| E5 | Breakout ATH | −1 → +2 | 4 días | ⏳ Pendiente |
| E7 | First Red Day (FRD) | −1 → +2 | 4 días | ⏳ Pendiente |
| E8 | Gap Down > 15% | −1 → +1 | 3 días | ⏳ Pendiente |
| E10 | First Green Bounce | −1 → +1 | 3 días | ⏳ Pendiente |
| E12-E14 | Dilution events | −2 → +2 | 5 días | ⏳ Pendiente |
| E15-E17 | Halts, SSR, spread | mismo día | 1 día | ⏳ Pendiente |

**Promedio ponderado** (según frecuencia): ~3–5 días por evento

### 6.2 Pregunta Clave: ¿Dónde se Guardarán los Otros E's?

**Respuesta**: Cuando implementes E1-E17, tienes **DOS opciones arquitectónicas**:

#### Opción A: Watchlists Separados por Tipo de Evento (NO RECOMENDADA)

```
processed/universe/
├── E0_generic_info_rich/
│   └── daily/
│       └── date=2020-03-16/
│           └── watchlist.parquet (info_rich=True)
│
├── E1_volume_explosion/
│   └── daily/
│       └── date=2020-03-16/
│           └── watchlist.parquet (volume_explosion=True, RVOL>5.0)
│
├── E2_gap_up/
│   └── daily/...
│
└── E4_parabolic/
    └── daily/...

raw/polygon/trades/
├── E0/
│   └── BCRX/date=2020-03-16/trades.parquet  ← Duplica ticks
├── E1/
│   └── BCRX/date=2020-03-16/trades.parquet  ← Duplica ticks
└── E4/
    └── BCRX/date=2020-03-16/trades.parquet  ← Duplica ticks
```

**Ventajas**:
- Separación clara por tipo de evento
- Fácil auditar cada evento independientemente

**Desventajas**:
- ❌ **Duplicación de ticks**: Un ticker-día con E0+E1+E4 → 3× storage
- ❌ Ineficiente en disco (un ticker puede tener múltiples eventos simultáneos)
- ❌ Confuso para downstream analysis

#### Opción B: Columnas Multi-Evento en UN SOLO Watchlist (✅ RECOMENDADA)

```
processed/universe/multi_event/
└── daily/
    └── date=2020-03-16/
        └── watchlist.parquet
            Columnas:
            - ticker
            - trading_day
            - E0_info_rich: bool
            - E1_volume_explosion: bool
            - E2_gap_up: bool
            - E4_parabolic: bool
            - E5_breakout_ath: bool
            - E7_first_red: bool
            - E8_gap_down: bool
            - E10_first_green: bool
            - E12_dilution: bool
            - E15_halt: bool
            - event_types: List[str]  ← ["E0", "E4"] para multi-events
            - max_event_window: int   ← Max(ventana E0, E4) = max(3, 6) = 6

raw/polygon/trades/
└── BCRX/
    └── date=2020-03-16/
        ├── trades.parquet    ← UN solo archivo (sin duplicados)
        ├── _SUCCESS
        └── events.json       ← Metadata: {"events": ["E0", "E4"], "windows": {"E0": 3, "E4": 6}}
```

**Ejemplo de fila en watchlist**:
```python
{
  'ticker': 'BCRX',
  'trading_day': '2020-03-16',
  'E0_info_rich': True,          # ✓ Cumple E0 (RVOL≥2.0, |%chg|≥15%)
  'E1_volume_explosion': False,
  'E2_gap_up': False,
  'E4_parabolic': True,          # ✓ Cumple E4 (+50% en ≤5 días)
  'E5_breakout_ath': False,
  'event_types': ['E0', 'E4'],   # Multi-evento simultáneo
  'max_event_window': 6          # Max de (E0=3, E4=6) = 6 días
}
```

**Ventajas**:
- ✅ **UN solo archivo de ticks por ticker-día** (sin duplicados)
- ✅ Eficiente en storage (~3-5x menos espacio vs Opción A)
- ✅ Puedes filtrar por cualquier combinación de eventos
- ✅ Downstream analysis más fácil (un ticker-día = un archivo)
- ✅ Metadata clara sobre qué eventos aplican

**Desventaja**:
- Watchlist más complejo (13+ columnas booleanas)

### 6.3 Implementación Futura Recomendada

Cuando implementes E1-E17, sigue estos pasos:

#### Paso 1: Modificar `build_dynamic_universe_optimized.py`

Agregar cálculo de TODAS las E's en un solo pass:

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

### 6.4 Estructura Final de Datos (Multi-Evento)

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

### 6.5 Uso Downstream (Multi-Evento)

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

### 6.6 Resumen: Respuesta a "¿Dónde se Guardarán los Otros E's?"

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

## 7. COMANDOS RÁPIDOS (RESUMEN)

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

## 8. NOTAS FINALES

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
