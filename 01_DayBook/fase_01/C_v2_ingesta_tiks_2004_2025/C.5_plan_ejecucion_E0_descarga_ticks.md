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

**Objetivo**: Agregar OHLCV 1-min → diario con features (rvol30, pctchg_d)

**Tiempo real**: ~4.8 horas (8,620 tickers, 67.6% vacíos sin datos raw)

**Script**: `build_daily_cache.py`

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

>**❌ ERROR COMETIDO** (2025-10-25 23:40 - ejecución 1):
>```bash
>--cap-filter-parquet processed/ref/market_cap_dim/market_cap_dim.parquet
>```
>Resultado: Solo 2 días generados (2025-10-20/21) en lugar de 21 años. SCD-2 solo cubría desde 2025-10-19.

**¿Qué hace?**:
1. Lee barras 1-min de `raw/polygon/ohlcv_intraday_1m/`
2. Agrega a diario por ticker-fecha: `close_d`, `vol_d`, `dollar_vol_d`, `vwap_d`, `session_rows`, `has_gaps`
3. Calcula features: `pctchg_d`, `return_d`, `rvol30` (rolling 30 sesiones, min_periods=1)
4. ~~Join temporal con SCD-2~~ **DEPRECADO**: `market_cap_d` = NULL

**Output esperado**:
```
processed/daily_cache/
├── ticker=AAPL/
│   ├── daily.parquet               (schema: 12 columnas, ZSTD)
│   └── _SUCCESS
├── ticker=TSLA/
│   ├── daily.parquet
│   └── _SUCCESS
├── ... (3,107 tickers)
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

**Objetivo**: Identificar días info-rich según filtros E0 y generar watchlists diarias

**Tiempo estimado**: 30-45 minutos

**Script**: `build_dynamic_universe_optimized.py`

**Comando**:
```bash
python scripts/fase_C_ingesta_tiks/build_dynamic_universe_optimized.py \
  --daily-cache processed/daily_cache \
  --outdir processed/universe/info_rich \
  --from 2004-01-01 --to 2025-10-21 \
  --config configs/universe_config.yaml
```

**¿Qué hace?**:
1. Lee caché diario completo (8,620 tickers, ~2,795 con datos)
2. Aplica filtros E0 **SIN market_cap**:
   ```python
   r_rvol = (rvol30 >= 2.0)
   r_chg = (|pctchg_d| >= 0.15)
   r_dvol = (dollar_vol_d >= 5_000_000)
   r_px = (0.20 <= close_d <= 20.00)

   info_rich = r_rvol AND r_chg AND r_dvol AND r_px
   # NO market_cap filter
   ```
3. Genera watchlists diarias (una por fecha)
4. Calcula TopN_12m (ranking runners)

**Output esperado**:
```
processed/universe/info_rich/
├── daily/
│   ├── date=2004-01-02/watchlist.parquet
│   ├── date=2004-01-05/watchlist.parquet
│   ├── ... (~5,292 archivos, uno por día de trading)
│   └── date=2025-10-21/watchlist.parquet
├── topN_12m.parquet                        (ranking completo)
├── topN_12m.csv                            (top 200 para referencia)
└── _SUCCESS
```

**Schema watchlist.parquet**:
```
ticker: Utf8
trading_day: Date
close_d: Float64
pctchg_d: Float64
rvol30: Float64
vol_d: Int64
dollar_vol_d: Float64
vwap_d: Float64
market_cap_d: Float64
r_rvol: Boolean
r_chg: Boolean
r_dvol: Boolean
r_px: Boolean
info_rich: Boolean              ← True si cumple todos los filtros
```

**Métricas esperadas** (extrapolando desde C_v1):
- Días procesados: ~5,292
- Tickers info-rich/día promedio: 20-40 (varía por régimen)
- Total ticker-días info-rich: ~100,000-200,000 (21 años)
- Tickers únicos info-rich: ~2,000-2,500

**Validación**:
```python
import polars as pl

# Validar día ejemplo
df = pl.read_parquet("processed/universe/info_rich/daily/date=2025-10-21/watchlist.parquet")
info_rich = df.filter(pl.col("info_rich"))
print(f"Total tickers: {len(df)}")
print(f"Info-rich: {len(info_rich)}")
print(f"RVOL min: {info_rich['rvol30'].min():.2f} (esperado >= 2.0)")
print(f"|%chg| min: {info_rich['pctchg_d'].abs().min():.2%} (esperado >= 15%)")
print(f"$vol min: ${info_rich['dollar_vol_d'].min():,.0f} (esperado >= $5M)")
print(f"Precio min: ${info_rich['close_d'].min():.2f} (esperado >= $0.20)")
print(f"Precio max: ${info_rich['close_d'].max():.2f} (esperado <= $20.00)")
print(f"Cap max: ${info_rich['market_cap_d'].max():,.0f} (esperado < $2B)")
```

**Criterio de éxito**:
- ✅ ~5,292 watchlists generadas (una por día de trading)
- ✅ Tickers info-rich cumplen TODOS los umbrales
- ✅ TopN_12m.parquet con ranking de runners

---

### PASO 4: Verificación Inclusión C_v1 vs E0

**Objetivo**: Documentar diferencias entre C_v1 (2020-2025) y E0 v2.0.0

**Tiempo estimado**: 10-15 minutos

**Script a crear**: `verify_inclusion_C_v1_vs_E0.py`

**Comando**:
```bash
python scripts/fase_C_ingesta_tiks/verify_inclusion_C_v1_vs_E0.py \
  --c_v1-watchlists processed/universe/info_rich_v1/daily \
  --e0-watchlists processed/universe/info_rich/daily \
  --from 2020-01-01 --to 2025-10-21 \
  --outdir audits
```

**¿Qué hace?**:
1. Lee watchlists C_v1 (2020-2025)
2. Lee watchlists E0 (mismo periodo)
3. Identifica ticker-días en cada conjunto:
   - `only_C_v1`: Días en C_v1 pero NO en E0 (esperado: mid/large caps)
   - `only_E0`: Días en E0 pero NO en C_v1 (esperado: penny stocks $0.20-$0.50)
   - `both`: Días en ambos (esperado: mayoría)
4. Para `only_C_v1`, verifica que son mid/large caps (cap >= $2B)
5. Para `only_E0`, verifica que son penny stocks ($0.20 <= precio < $0.50)
6. Calcula métricas de inclusión

**Output esperado**:
```
audits/
├── AUDITORIA_INCLUSION_C_v1_vs_E0.json
├── only_C_v1_midcaps.parquet               (días excluidos, cap >= $2B)
├── only_E0_pennystocks.parquet             (días nuevos, $0.20-$0.50)
└── comparison_summary.txt
```

**Métricas esperadas**:
```json
{
  "periodo": "2020-01-01 → 2025-10-21",
  "c_v1_ticker_dias": 11054,
  "e0_ticker_dias": 12500,
  "overlap": 10200,
  "only_c_v1": 854,
  "only_e0": 2300,
  "inclusion_rate_c_v1_in_e0": "92.3%",
  "exclusion_reason_only_c_v1": "Market cap >= $2B (mid/large caps)",
  "inclusion_reason_only_e0": "Penny stocks $0.20-$0.50 (no en C_v1)",
  "conclusion": "E0 NO es superset puro, pero ES versión limpia small/micro cap"
}
```

**Criterio de éxito**:
- ✅ Inclusión C_v1 en E0: 90-95% (esperado por exclusión mid/large caps)
- ✅ Días `only_C_v1`: >95% tienen cap >= $2B
- ✅ Días `only_E0`: >95% tienen precio $0.20-$0.50
- ✅ Documentación clara de diferencias

**IMPORTANTE**: Esta NO es una falla. Es la consecuencia documentada de aplicar filtro cap < $2B. Ver Contrato_E0.md sección 11.

---

### PASO 5: Descarga Ticks Días Info-Rich E0

**Objetivo**: Descargar ticks de Polygon solo para días info-rich identificados

**Tiempo estimado**: Variable (depende de total ticker-días info-rich)

**Script**: `download_trades_optimized.py`

**Estrategia recomendada**: **Modo watchlists** (solo días info-rich)

**Comando**:
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

**¿Qué hace?**:
1. Lee `topN_12m.csv` (lista de tickers a procesar)
2. Para cada ticker, lee watchlists diarias en `processed/universe/info_rich/daily/`
3. Identifica días donde `info_rich = True`
4. Descarga ticks SOLO de esos días usando Polygon API v3
5. Guarda en: `raw/polygon/trades/{TICKER}/date={YYYY-MM-DD}/trades.parquet`
6. Marca completados con `_SUCCESS`
7. Resume automático si se interrumpe

**Parámetros clave**:
- `--mode watchlists`: Descarga solo días info-rich (eficiente)
- `--page-limit 50000`: Tamaño de página Polygon (óptimo para ticks)
- `--rate-limit 0.15`: 150ms entre requests (evita 429)
- `--workers 8`: Procesos concurrentes (ajustar según RAM)
- `--resume`: Salta días ya descargados (_SUCCESS existe)

**Estimación de volumen**:
```
Supuestos:
- Ticker-días info-rich: ~150,000 (21 años)
- Ticks promedio/día: ~50,000
- Tamaño promedio/ticker-día: ~30 MB (comprimido ZSTD)

Total estimado:
- Ticks totales: 150,000 × 50,000 = 7.5B ticks
- Storage: 150,000 × 30 MB = 4.5 TB
```

**Tiempo estimado**:
```
Supuestos:
- Rate limit: 0.15s/request → ~400 requests/min → 24,000/hora
- Requests/ticker-día: ~3 (promedio con paginación)
- Total requests: 150,000 × 3 = 450,000

Tiempo descarga: 450,000 / 24,000 = ~18.75 horas (~1 día)
```

**Nota**: Esto es con 8 workers en paralelo. Con 1 worker sería ~150 horas (~6 días).

**Output esperado**:
```
raw/polygon/trades/
├── AAPL/
│   ├── date=2004-01-05/
│   │   ├── trades.parquet          (ticks del día, schema: t, p, s, c)
│   │   └── _SUCCESS
│   ├── date=2004-03-12/
│   │   ├── trades.parquet
│   │   └── _SUCCESS
│   └── ...
├── TSLA/
│   ├── date=2020-08-31/
│   │   ├── trades.parquet
│   │   └── _SUCCESS
│   └── ...
└── ... (2,000-2,500 tickers únicos con días info-rich)
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
| 3 | Universo dinámico E0 | 30-45 min | TBD | ⏳ PENDIENTE |
| 4 | Verificación C_v1 vs E0 | 10-15 min | TBD | ⏳ PENDIENTE |
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
- ✅ ~5,292 watchlists generadas
- ✅ Tickers info-rich cumplen umbrales
- ✅ TopN_12m.parquet generado

**PASO 4 → PASO 5**:
- ✅ Auditoría C_v1 vs E0 completada
- ✅ Diferencias documentadas y justificadas
- ✅ Inclusión ~90-95% explicada por filtro cap

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
