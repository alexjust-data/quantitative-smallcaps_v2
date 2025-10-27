# C.6 - Roadmap Multi-Evento: Post-PASO 5 (E0 Completado)

**Fecha**: 2025-10-27  
**Versión**: 2.0.0 (Consolidado C.6 + C.7)  
**Estado**: E0 COMPLETADO (67,439 archivos, 16.58 GB, 92.2% cobertura)  
**Siguiente**: Implementar E1, E4, E7, E8 + Prototipo DIB/VIB en paralelo  
**Relacionado**: [C.1](C.1_estrategia_descarga_ticks_eventos.md), [C.5](C.5_plan_ejecucion_E0_descarga_ticks.md)  

---

## SITUACIÓN ACTUAL (POST-PASO 5)

### ✅ COMPLETADO

```
FASE C - INGESTA TICKS E0 (2004-2025)
═════════════════════════════════════
✅ PASO 1: Daily Cache (8,618 tickers procesados)
✅ PASO 2: Config Umbrales E0
✅ PASO 3: Watchlists E0 (5,934 días, 29,555 eventos)
✅ PASO 4: Auditoría E0 (4,898 tickers únicos)
✅ PASO 5: Descarga Ticks E0 (67,439 archivos, 16.58 GB, 92.2% cobertura)
```

**Dataset actual**:
- **Ticks descargados**: 67,439 `_SUCCESS` files
- **Storage**: 16.58 GB
- **Cobertura**: 92.2% (64,801 / 70,290 días trading)
- **Window aplicado**: ±1 día (contexto para labeling)
- **Estructura**: `raw/polygon/trades/TICKER/date=YYYY-MM-DD/trades.parquet`

### ⚠️ LIMITACIONES DE E0

**E0 es GENÉRICO** ("algo está pasando") pero **NO identifica el patrón específico**:

```python
# Con E0 solo sabemos:
ticker_day_E0 = {
    'ticker': 'BCRX',
    'date': '2020-03-16',
    'E0': True,  # ✓ Info-rich (RVOL≥2, |%chg|≥15%, $vol≥$5M)

    # ❌ NO sabemos el patrón específico:
    'is_FRD': ???          # ¿Es First Red Day tras pump?
    'is_parabolic': ???    # ¿Viene de +50% en 5 días?
    'is_gap_down': ???     # ¿Es gap down violento post-dilution?
}
```

**Consecuencia**: DIB/VIB construidas sobre E0 solo tendrían **labeling genérico** → modelo aprende "ruido promediado" en vez de patrones específicos de trading.

---

## DECISIÓN ESTRATÉGICA: HÍBRIDO A+B

### ❌ Opción A Rechazada: "Construir DIB/VIB con E0 Solo"

**Flujo**:
1. Construir DIB/VIB sobre ticks E0
2. Hacer triple barrier labeling genérico
3. Entrenar modelo con E0
4. Descubrir que necesitamos eventos específicos (FRD, Parabolic...)
5. RE-DESCARGAR ticks E1-E13
6. RE-CONSTRUIR DIB/VIB con eventos completos
7. RE-HACER labeling con contexto

**Problema**: Re-trabajo doble (DIB/VIB 2 veces, descarga API 2 veces, labeling 2 veces)

---

### ❌ Opción B Rechazada: "Descargar E1-E13 Sin Validar DIB/VIB"

**Flujo**:
1. Implementar detectores E1-E13
2. Descargar ticks adicionales (+3-4 TB)
3. Luego construir DIB/VIB

**Problema**: Commitment +3 TB sin validar que podemos construir barras informativas

---

### ✅ Opción C APROBADA: Híbrido A+B (Track Paralelo)

**Estrategia**:

```
SEMANA 1-2: INGENIERÍA BASE (PARALELO)
═══════════════════════════════════════
Track A (Eventos)              Track B (Barras)
─────────────────              ────────────────
Implementar detectores →       Prototipo DIB/VIB
E1, E4, E7, E8                en subset pequeño
↓                             (2-3 tickers × 10 días)
Watchlists multi-evento       ↓
con merge inteligente         Validar feature factory
↓                             ↓
AMBOS LISTOS → SEMANA 3
↓
SEMANA 3: DESCARGA INCREMENTAL
═══════════════════════════════
Descargar ticks E1-E13 adicionales
(solo días NUEVOS, resume salta E0)
↓
SEMANA 4-5: DATASET MAESTRO
═══════════════════════════════
Construir DIB/VIB UNA VEZ
sobre conjunto COMPLETO {E0 ∪ E1-E13}
```

**Por qué es óptima**:
- ✅ DIB/VIB una vez (sobre dataset completo)
- ✅ Valida pipeline crítico antes de commitment +3 TB
- ✅ Paraleliza ingenierías (detectores + prototipo = misma semana)
- ✅ Descarga incremental eficiente (resume salta E0)

---

## ARQUITECTURA MULTI-EVENTO (ESPECIFICACIÓN TÉCNICA)

**Referencia completa**: Ver [C.5 Sección 6](C.5_plan_ejecucion_E0_descarga_ticks.md#6-arquitectura-multi-evento-e0--e1-e17-futuros)

### Watchlist Unificado (No Carpetas Separadas)

**Problema con carpetas separadas**: Si `BCRX` tiene E0+E1+E4 el mismo día → 3× `trades.parquet` duplicados

**Solución**: Watchlist unificado + metadata JSON

```
processed/universe/multi_event/daily/date=YYYY-MM-DD/
└── watchlist.parquet
    # Columnas boolean: E0_info_rich, E1_volume_explosion, E4_parabolic, E7_first_red, E8_gap_down
    # event_types: list[str]  (códigos cortos: ["E0", "E4"])
    # max_event_window: int   (ventana individual más grande, ej: E4 ±3 → 7 días)

raw/polygon/trades/TICKER/date=YYYY-MM-DD/
├── trades.parquet  # UN SOLO archivo por ticker-día
├── _SUCCESS
└── events.json     # Metadata: eventos, is_event_day, window_offset
```

### Schema: `events.json` (Crítico para Labeling)

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
  "download_window_applied_days": ["2020-03-13", ..., "2020-03-19"],
  "_success": true
}
```

**Campos clave**:
- `is_event_day`: Distingue día del evento vs contexto pre/post (crítico para triple barrier labeling)
- `window_offset`: Días desde evento (`date - event_day`)
- `event_day`: Día real donde se detectó el evento
- `max_event_window`: Ventana individual más grande (NO unión de ventanas)

### Lógica `--resume` con Merge Inteligente

**Problema**: E4 requiere window ±3, pero E0 ya descargó ±1

**Solución**:
1. Leer `events.json` existente
2. Agregar nuevo evento a `events_context`
3. Recalcular `max_event_window` = max(window_size)
4. Regenerar `download_window_applied_days` (unión de ventanas)
5. Si hay días nuevos no cubiertos → descargar adicionales

**Implementación**: `scripts/fase_C_ingesta_tiks/build_multi_event_watchlists.py`

---

## ROADMAP DETALLADO (3-4 SEMANAS)

### SEMANA 1: Track A - Detectores Multi-Evento (Días 1-3)

**Objetivo**: Implementar detectores de eventos específicos del playbook

**Scripts a crear**:
```
scripts/fase_C_ingesta_tiks/event_detectors/
├── __init__.py
├── e1_volume_explosion.py       # RVOL > 5x (10 líneas, trivial)
├── e4_parabolic_move.py         # +50% en ≤5 días (15 líneas, fácil)
├── e7_first_red_day.py          # 3+ verdes → primer rojo (50 líneas, complejo)
└── e8_gap_down.py               # gap < -15% (10 líneas, trivial)
```

**Script maestro**: `build_multi_event_watchlists.py`
- Lee `daily_cache` completo
- Ejecuta todos los detectores en un solo pass
- Genera watchlist multi-evento con columnas boolean
- Implementa merge inteligente de ventanas
- Marca días ya cubiertos por E0 (no re-descargar)

**Comando**:
```bash
python scripts/fase_C_ingesta_tiks/build_multi_event_watchlists.py \
  --daily-cache processed/daily_cache \
  --events E0,E1,E4,E7,E8 \
  --outdir processed/universe/multi_event \
  --from 2004-01-01 --to 2025-10-21
```

**Output esperado**:
```
processed/universe/multi_event/daily/
├── date=2020-03-16/watchlist.parquet
└── ... (~10K-15K días con eventos)

Estadísticas:
- Total días con eventos: ~15,000
- Días nuevos (no E0): ~30,000-40,000
- Días ya cubiertos por E0: 64,801
```

**Tiempo**: 2-3 días implementación

---

### SEMANA 1: Track B - Prototipo DIB/VIB (Días 1-3, PARALELO)

**Objetivo**: **VALIDAR que podemos construir barras informativas** antes de commitment +3 TB

**Por qué es OBLIGATORIO**:
> Track B valida que nuestra **feature factory intradía funciona**. Sin Track B, descargar más datos es **fe sin pruebas**.

**Script prototipo**: `scripts/fase_D_barras/prototype_dib_vib.py`

**Qué valida**:
- ✅ Podemos leer ticks descargados (no corruptos)
- ✅ Timestamps coherentes (no "year 57676" bugs)
- ✅ Imbalance calculation funciona (DIB/VIB correctas)
- ✅ Features de microestructura calculables
- ✅ Pipeline no crashea (gaps, halts, días vacíos)

**Input**: Subset pequeño (2-3 tickers × 10 días E0 ya descargados)

**Algoritmo DIB básico**:
```python
def build_dollar_imbalance_bars(df_ticks: pl.DataFrame, threshold_usd: float = 250_000.0):
    """
    Dollar Imbalance Bars según López de Prado (2018) Cap 2.4

    1. Inferir dirección de trade con tick rule (buy=+1, sell=-1)
    2. Acumular imbalance = sum(direction × dollar_volume)
    3. Cuando |imbalance| >= threshold → crear nueva barra
    """
    # Ver implementación completa en prototype_dib_vib.py
```

**Comando**:
```bash
python scripts/fase_D_barras/prototype_dib_vib.py \
  --ticks-root raw/polygon/trades \
  --sample-tickers BCRX,GERN,VXRT \
  --sample-days 10 \
  --outdir temp_prototype_bars
```

**Criterio de éxito**:
- ✅ Procesa 30 ticker-días sin errores
- ✅ Genera barras coherentes (timestamps, features, orden)
- ✅ Code ready para escalar a ~300K ticker-días

**Tiempo**: 2-3 días implementación

---

### SEMANA 2-3: Descarga Incremental E1-E13 (Días 4-8)

**Prerequisito**:
- ✅ Track A completo (watchlists multi-evento listos)
- ✅ Track B validado (DIB/VIB funciona)

**Script**: Reutilizar `download_trades_optimized.py` con watchlists multi-evento

**Comando**:
```bash
python scripts/fase_C_ingesta_tiks/download_trades_optimized.py \
  --watchlist-root processed/universe/multi_event/daily \
  --outdir raw/polygon/trades \
  --mode watchlists \
  --resume \
  --workers 8 \
  --rate-limit 0.15 \
  --page-limit 50000
```

**Lógica descarga incremental**:
- `--resume` salta días con `_SUCCESS` existente
- Solo descarga:
  - Días E1-E13 NO cubiertos por E0
  - Ventanas adicionales (E4 necesita ±3, E0 ya tiene ±1 → descarga solo ±2 y ±3)
- Actualiza `events.json` con merge inteligente

**Storage estimado adicional**: +3-4 TB (small caps tienen 100x-1000x menos volumen que large caps)

**Metadata generada**: `events.json` por ticker-día con:
- Lista de eventos aplicables
- `is_event_day` flag
- `window_offset` para cada evento
- `download_window_applied_days` (auditoría)

**Tiempo estimado**: 20-30 horas (paralelo con 8 workers)

---

### SEMANA 4-5: Dataset Maestro DIB/VIB (Días 9-14)

**Objetivo**: Construir **UNA SOLA VEZ** las barras informativas sobre conjunto completo {E0 ∪ E1-E13}

**Script final**: `scripts/fase_D_barras/build_info_bars.py`

**Input**:
- Ticks: `raw/polygon/trades/<TICKER>/date=*/trades.parquet`
- Metadata: `raw/polygon/trades/<TICKER>/date=*/events.json`
- Watchlists: `processed/universe/multi_event/daily/date=*/watchlist.parquet`

**Output**:
```
processed/bars/<TICKER>/date=YYYY-MM-DD/
├── dib.parquet           # Dollar Imbalance Bars
├── vib.parquet           # Volume Imbalance Bars
├── features.parquet      # Features microestructura
└── metadata.json         # Eventos aplicables, contexto diario
```

**Features por barra**:
- Timestamp (bar_start, bar_end)
- Price (open, high, low, close, vwap)
- Volume (total, buy_volume, sell_volume)
- Imbalance (dollar_imbalance, volume_imbalance)
- Microestructura (spread_pct, order_flow_imbalance)
- Contexto diario (rvol30, pctchg_d, eventos: ["E0", "E4"])
- Event context (is_event_day, window_offset)

**Comando**:
```bash
python scripts/fase_D_barras/build_info_bars.py \
  --ticks-root raw/polygon/trades \
  --events-metadata processed/universe/multi_event \
  --outdir processed/bars \
  --bar-types dib,vib \
  --parallel 8
```

**Tiempo estimado**: 5-7 días (procesamiento en paralelo)

---

## SIGUIENTE FASE: ML PIPELINE (POST-SEMANA 5)

### PASO 7: Triple Barrier Labeling

**Por tipo de evento** (usando `is_event_day` y `event_type` de `events.json`):
- **E7 (FRD)**: Short setup → profit_target=-10%, stop_loss=+5%
- **E4 (Parabolic)**: Momentum long → profit_target=+15%, stop_loss=-5%
- **E8 (GapDown)**: Fade long → profit_target=+8%, stop_loss=-3%
- **E1 (Vol Explosion)**: Scalp → profit_target=+5%, stop_loss=-2%

**Script**: `scripts/fase_E_ml/triple_barrier_labeling.py`

### PASO 8: Sample Weighting

**Considerando**:
- Overlap temporal entre eventos (unicidad)
- Importancia económica (dollar_vol_d)
- Time decay (eventos recientes más relevantes)

**Script**: `scripts/fase_E_ml/sample_weighting.py`

### PASO 9: Dataset Maestro ML

**Unificar**:
- Barras (DIB/VIB)
- Features (microestructura)
- Labels (triple barrier)
- Weights (bootstrap)
- Metadata (eventos, régimen macro)

**Script**: `scripts/fase_E_ml/build_master_dataset.py`

---

## MÉTRICAS DE ÉXITO

### Semana 1-2 (Ingeniería Base)
- ✅ Detectores E1, E4, E7, E8 implementados
- ✅ Watchlists multi-evento generadas (~15K días)
- ✅ Prototipo DIB/VIB validado (30 ticker-días sin errores)
- ✅ Merge inteligente de ventanas funciona

### Semana 3 (Descarga Incremental)
- ✅ Ticks E1-E13 descargados (~30K-40K días nuevos)
- ✅ Storage final: ~20-22 GB (E0: 16.58 GB + E1-E13: ~4-6 GB)
- ✅ Metadata `events.json` por ticker-día con `is_event_day`
- ✅ Resume tolerance validado

### Semana 4-5 (Dataset Maestro)
- ✅ DIB/VIB construidos sobre ~300K ticker-días
- ✅ Features microestructura calculadas
- ✅ Contexto eventos adjuntado
- ✅ Dataset listo para triple barrier labeling

---

## EVENTOS ESPECÍFICOS (PRIORIDAD MVP)

Según [C.1](C.1_estrategia_descarga_ticks_eventos.md) y [EduTrades Playbook](../../A_Universo/2_estrategia_operativa_small_caps.md):

| Evento | Descripción | Window | Complejidad | Prioridad |
|--------|-------------|--------|-------------|-----------|
| **E1** | Volume Explosion (RVOL > 5×) | ±2 días | Trivial (10 líneas) | Alta |
| **E4** | Parabolic Move (+50% ≤5d) | ±3 días | Fácil (15 líneas) | **MUY ALTA** |
| **E7** | First Red Day (FRD) | ±2 días | Complejo (50 líneas) | **CRÍTICO** |
| **E8** | Gap Down (>15%) | ±1 día | Trivial (10 líneas) | Alta |
| E13 | Offering Pricing | ±2 días | Externo (SEC) | Media |

**Nota**: E13 requiere SEC filings externos → dejarlo fuera de MVP o usar dataset manual

---

## POR QUÉ ESTA ESTRATEGIA ES CORRECTA

### Minimiza Re-trabajo

**Opción B (rechazada)**: DIB/VIB 2 veces (E0 → luego E0+E1-E13)
**Opción C (aprobada)**: DIB/VIV 1 vez (sobre conjunto completo)

### Valida Pipeline Crítico

Track B (prototipo DIB/VIB) valida:
- Ticks son legibles y coherentes
- Imbalance calculation funciona
- Features de microestructura calculables
- Pipeline no crashea con casos edge

### Eficiencia Temporal

**Con Opción B**: ~15-20 días (secuencial)
**Con Opción C**: ~10-12 días (paralelo Track A+B)

### Dataset Completo para ML

DIB/VIB informados por:
- Eventos específicos (E0, E1, E4, E7, E8)
- `is_event_day` flag (día evento vs contexto)
- `window_offset` (pre/post evento)
- Metadata completa (auditoría y reproducibilidad)

---

## REFERENCIAS TÉCNICAS

### López de Prado (2018) - Advances in Financial Machine Learning

- **Cap 2.3-2.4**: Information-Driven Bars (DIB/VIB)
- **Cap 3**: Triple Barrier Labeling
- **Cap 4**: Sample Weighting (bootstrap, time decay)

### EduTrades Playbook

- **E7 (FRD)**: Patrón más confiable (short setup)
- **E4 (Parabolic)**: Momentum riding (long setup)
- **E8 (GapDown)**: Dilution fade (long setup)

### Documentos Proyecto

- [C.1](C.1_estrategia_descarga_ticks_eventos.md): Estrategia completa 17+ eventos
- [C.5](C.5_plan_ejecucion_E0_descarga_ticks.md): Plan ejecución E0 (PASOS 0-5)
- [C.5 Sección 6](C.5_plan_ejecucion_E0_descarga_ticks.md#6-arquitectura-multi-evento-e0--e1-e17-futuros): Especificación técnica multi-evento

---

## PRÓXIMO PASO INMEDIATO

**SEMANA 1 - DÍA 1**:

1. Crear directorios:
```bash
mkdir -p scripts/fase_C_ingesta_tiks/event_detectors
mkdir -p scripts/fase_D_barras
mkdir -p temp_prototype_bars
```

2. Implementar detectores (Track A):
   - `event_detectors/e1_volume_explosion.py`
   - `event_detectors/e4_parabolic_move.py`
   - `event_detectors/e7_first_red_day.py`
   - `event_detectors/e8_gap_down.py`

3. Implementar prototipo DIB/VIV (Track B, en paralelo):
   - `prototype_dib_vib.py`

**Criterio para avanzar a SEMANA 2**:
- ✅ Detectores funcionan y generan watchlists multi-evento
- ✅ Prototipo DIB/VIB procesa 30 ticker-días sin errores

---

**Documento creado**: 2025-10-27
**Autor**: Alex Just Rodriguez + Claude (Anthropic)
**Versión**: 2.0.0 (Consolidado C.6 + C.7 + Especificación Técnica Aprobada)
**Status**: ROADMAP OFICIAL - LISTO PARA EJECUCIÓN

**FIN DE C.6**
