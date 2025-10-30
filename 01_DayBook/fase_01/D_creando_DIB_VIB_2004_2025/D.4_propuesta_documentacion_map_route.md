# D.4 - Propuesta Documentación Fase D para map_route_phase1.md

**Fecha**: 2025-10-30
**Objetivo**: Documentar el pipeline completo Fase D (DIB + Labels + Weights + ML Dataset) en el checkpoint map_route_phase1.md

---

## Proposed Documentation Structure for Fase D

Based on the analysis of all D.0-D.3 documents and the structure pattern in [map_route_phase1.md](../../map_route_phase1.md), here's the proposed structure:

---

## **.. / fase_01 / D_creando_DIB_VIB_2004_2025**

### **Fase D: DIB/VIB Construction + ML Dataset Pipeline**

**ASCII Flow Diagram:**
```sh
Flujo:
  raw/polygon/trades/                    (PASO 5 output - 60,825 días)
          │
          ├──[D.1]──> processed/bars/              (Dollar Imbalance Bars)
          │               │
          │               ├──[D.2]──> processed/labels/        (Triple Barrier Labels)
          │               │               │
          │               │               ├──[D.3]──> processed/weights/     (Sample Weights)
          │               │               │               │
          │               │               │               └──[D.4]──> processed/datasets/
          │               │               │                               ├── daily/
          │               │               │                               ├── global/
          │               │               │                               └── splits/
          │               │               │                                    ├── train.parquet (3.49M rows)
          │               │               │                                    └── valid.parquet (872K rows)
```

**Objetivo**: Construir barras informacionales (Dollar Imbalance Bars) desde tick data, aplicar Triple Barrier Labeling, calcular Sample Weights con unicidad temporal, y generar ML Dataset walk-forward listo para entrenamiento supervisado.

**Cobertura**: 2004-2025 (21 años), 4,874 tickers, 64,801 días únicos
**Resultado final**: 4.36M eventos ML-ready con 14 features intraday + labels + weights

---

### **[D.1] Dollar Imbalance Bars (DIB)**

**Explicación detallada**:
- [D.0_Constructor_barras_Dollar_Vol_Imbalance.md](./D.0_Constructor_barras_Dollar_Vol_Imbalance.md)
- [D.1.1_notas_6.1_DIB.md](./D.1.1_notas_6.1_DIB.md) - Parámetros target-usd y ema-window

**Script**: `scripts/fase_D_creando_DIB_VIB/build_bars_from_trades.py`

`INPUT`:
- `raw/polygon/trades/{ticker}/date={YYYY-MM-DD}/trades.parquet` (60,825 archivos, formato NUEVO con t_raw + t_unit)

`TRANSFORMACIÓN`:
```python
# Event-driven sampling (López de Prado 2018)
# Acumula flujo de dólares hasta umbral adaptativo

for cada tick:
    dollar_flow += price × size × tick_sign
    if dollar_flow >= threshold_adaptativo:
        flush_bar(t_open, t_close, OHLC, volume, n_trades, imbalance_score)
        threshold = EMA(threshold, window=50)
```

**Parámetros clave**:
- `--target-usd 300000`: $300k por barra (~1-2% volumen diario small cap)
- `--ema-window 50`: Suavización adaptativa del umbral (memoria ~sesión completa)
- `--parallel 8`: Workers concurrentes

**Fix Crítico Aplicado**:
Timestamps corruptos (año 52XXX) → Solución definitiva en origen (downloader)
- [D.2_actualizacion_timestamp_FIX.md](./D.2_actualizacion_timestamp_FIX.md:34-78)
- Formato NUEVO: `t_raw: Int64` + `t_unit: 'ns'/'us'/'ms'` preserva unidades sin corrupción

`OUTPUT`:
- `processed/bars/{ticker}/date={YYYY-MM-DD}/dollar_imbalance.parquet`
- **64,801 archivos** (100% completitud)
- Schema: `{t_open, t_close, o, h, l, c, v, n, dollar, imbalance_score}`
- Promedio: ~57 barras/día, ~190 KB/archivo

**Métricas ejecución**:
- Tiempo: 55.5 min
- Velocidad: 19.5 archivos/seg
- Errores: 0

> EVIDENCIA de resultados: [D.1_Ejecucion_Pipeline_DIB_Labels_Weights.md](./D.1_Ejecucion_Pipeline_DIB_Labels_Weights.md#1-dollar-imbalance-bars-dib)

---

### **[D.2] Triple Barrier Labeling**

**Explicación detallada**:
- [D.1.2_notas_6.1_tripleBarrierLabeling.md](./D.1.2_notas_6.1_tripleBarrierLabeling.md)

**Script**: `scripts/fase_D_creando_DIB_VIB/triple_barrier_labeling.py`

`INPUT`:
- `processed/bars/{ticker}/date={YYYY-MM-DD}/dollar_imbalance.parquet`

`TRANSFORMACIÓN`:
```python
# Triple Barrier Method (López de Prado Ch.3)
# Para cada barra como "anchor":

σ = EMA(|log_returns|, span=50)  # Volatilidad adaptativa

# Barreras horizontales:
PT = price_anchor × (1 + 3.0 × σ)  → label = +1 si toca primero
SL = price_anchor × (1 - 2.0 × σ)  → label = -1 si toca primero

# Barrera vertical:
t1 = anchor_ts + 120 barras (~medio día)  → label = 0 si expira sin tocar PT/SL

# Asimétrico: PT=3σ vs SL=2σ favorece captura de momentum (pumps explosivos)
```

**Parámetros clave**:
- `--pt-mul 3.0`: Profit target = 3 × σ (significancia estadística)
- `--sl-mul 2.0`: Stop loss = 2 × σ (asimétrico, stop más cercano)
- `--t1-bars 120`: Vertical barrier ~2-3 horas trading
- `--vol-est ema --vol-window 50`: Estimación volatilidad adaptativa

`OUTPUT`:
- `processed/labels/{ticker}/date={YYYY-MM-DD}/labels.parquet`
- **64,800 archivos** (99.998% completitud, 1 archivo faltante)
- Schema: `{anchor_ts, t1, pt_hit, sl_hit, label, ret_at_outcome, vol_at_anchor}`

**Métricas ejecución**:
- Tiempo: 25.3 min
- Velocidad: 42.7 archivos/seg
- Errores: 0

> EVIDENCIA de resultados: [D.1_Ejecucion_Pipeline_DIB_Labels_Weights.md](./D.1_Ejecucion_Pipeline_DIB_Labels_Weights.md#2-triple-barrier-labeling)

---

### **[D.3] Sample Weights (Uniqueness + Magnitude + Time-Decay)**

**Explicación detallada**:
- [D.1.3_notas_6.1_SampleWeights.md](./D.1.3_notas_6.1_SampleWeights.md)

**Script**: `scripts/fase_D_creando_DIB_VIB/make_sample_weights.py`

`INPUT`:
- `processed/labels/{ticker}/date={YYYY-MM-DD}/labels.parquet`

`TRANSFORMACIÓN`:
```python
# Fórmula (López de Prado Ch.4):
weight[i] = (|ret_at_outcome[i]| / concurrency[i]) × decay[i]

# Componentes:
# 1. |ret_at_outcome|: Peso base por magnitud (eventos +80% > +0.3%)
# 2. concurrency[i]: #ventanas [anchor_ts, t1] que contienen evento i
#    → Reduce peso de eventos solapados (no independientes)
# 3. decay[i]: 0.5 ^ (age_days / 90) - Prioriza recencia
#    (actualmente stub=1.0 intra-día, activable cross-day futuro)

# Normalización: ∑weights = 1.0 por ticker-day
```

**Parámetros clave**:
- `--uniqueness`: Ajusta por concurrency (evita overfit a racimos temporales)
- `--abs-ret-weight`: Peso base = |ret| (prioriza eventos significativos)
- `--time-decay-half_life 90`: Semivida 90 días (hook preparado para cross-day)

`OUTPUT`:
- `processed/weights/{ticker}/date={YYYY-MM-DD}/weights.parquet`
- **64,801 archivos** (100% completitud)
- Schema: `{anchor_ts, weight}`

**Métricas ejecución**:
- Tiempo: 24.9 min
- Velocidad: 43.4 archivos/seg
- Errores: 0

> EVIDENCIA de resultados: [D.1_Ejecucion_Pipeline_DIB_Labels_Weights.md](./D.1_Ejecucion_Pipeline_DIB_Labels_Weights.md#3-sample-weights-unicidad--retorno--time-decay)

---

### **[D.4] ML Dataset Builder (Features + Walk-Forward Split)**

**Script**: `scripts/fase_D_creando_DIB_VIB/build_ml_daser.py`

`INPUT`:
- `processed/bars/{ticker}/date={day}/dollar_imbalance.parquet`
- `processed/labels/{ticker}/date={day}/labels.parquet`
- `processed/weights/{ticker}/date={day}/weights.parquet`

`TRANSFORMACIÓN`:
```python
# 1. Feature Engineering (14 columnas intraday):
ret_1 = log(c / c_prev)
range_norm = (h - l) / |c_prev|
vol_f, dollar_f, imb_f = volume/dollar/imbalance fractional changes
ret_1_ema10, ret_1_ema30, range_norm_ema20, ...
vol_z20, dollar_z20 = z-scores volumen/dólar (20-bar window)

# 2. Join componentes:
dataset = bars.join(labels, left_on="t_close", right_on="anchor_ts")
              .join(weights, on="anchor_ts")

# 3. Walk-Forward Split (no aleatorio):
timeline = sorted(anchor_ts)
train = primeros 80% días - purge_bars=50
valid = últimos 20% días

# Purged K-Fold: gap 50 barras entre train/valid (evita leakage temporal)
```

**Parámetros clave**:
- `--split walk_forward`: Split temporal (no random)
- `--folds 5`: Divide timeline en 5 folds
- `--purge-bars 50`: Embargo period entre train/valid
- `--parallel 12`: Workers concurrentes

`OUTPUT`:
- `processed/datasets/daily/{ticker}/date={day}/dataset.parquet` (**64,801 archivos**)
- `processed/datasets/global/dataset.parquet` (**4,359,730 rows**)
- `processed/datasets/splits/train.parquet` (**3,487,734 rows, 80.0%**)
- `processed/datasets/splits/valid.parquet` (**871,946 rows, 20.0%**)
- `processed/datasets/meta.json` (metadata: features, folds, purge, stats)

**Features generadas (14)**:
```
ret_1, range_norm, vol_f, dollar_f, imb_f,
ret_1_ema10, ret_1_ema30, range_norm_ema20,
vol_f_ema20, dollar_f_ema20, imb_f_ema20,
vol_z20, dollar_z20, n
```

**Métricas ejecución**:
- Tiempo: 50.9 min (daily: 26.8 min, concat: 24.1 min)
- Velocidad: 40.2 archivos/seg (daily phase)
- Errores: 0

> EVIDENCIA de resultados: [D.1_Ejecucion_Pipeline_DIB_Labels_Weights.md](./D.1_Ejecucion_Pipeline_DIB_Labels_Weights.md#4-ml-dataset-builder-bonus)

---

## **RESUMEN EJECUTIVO Fase D**

**Pipeline completo ejecutado**: 2025-10-28

| Etapa | Tiempo | Archivos | Tasa Éxito | Output |
|-------|--------|----------|------------|--------|
| D.1 DIB Bars | 55.5 min | 64,801 | 100% | processed/bars/ |
| D.2 Labels | 25.3 min | 64,800 | 99.998% | processed/labels/ |
| D.3 Weights | 24.9 min | 64,801 | 100% | processed/weights/ |
| D.4 ML Dataset | 50.9 min | 64,801 | 100% | processed/datasets/ |
| **TOTAL** | **156.6 min** | **64,801** | **99.998%** | **4.36M rows ML-ready** |

**Dataset final características**:
- **Cobertura temporal**: 2004-2025 (21 años)
- **Tickers únicos**: 4,874 (info-rich universe E0)
- **Total eventos**: 4,359,730 barras con labels + features + weights
- **Train/Valid split**: 3.49M / 872K (80% / 20%) walk-forward
- **Storage**: ~2.8 GB (ZSTD compressed)
- **Formato**: Parquet con schema validado, timestamps corregidos

**Próximo paso**: Entrenamiento modelo supervisado (LightGBM/XGBoost) con sample weights y Purged K-Fold CV

> **EVIDENCIA completa**: [D.3_resumen_pipeline.md](./D.3_resumen_pipeline.md)

---

## **Estructura de Documentación**

Esta propuesta sigue el mismo patrón que Fases A, B, C:

1. **Flujo ASCII visual**: Muestra el pipeline de datos claramente
2. **Secciones por PASO** (D.1-D.4): Cada fase documentada individualmente
3. **INPUT → TRANSFORMACIÓN → OUTPUT**: Claramente definidos
4. **Parámetros clave documentados**: Con explicación de cada uno
5. **Métricas de ejecución**: Tiempo, velocidad, errores
6. **Enlaces a documentación detallada**: Para deep-dive
7. **Resumen ejecutivo final**: Tabla de tiempos y resultados

---

## **Referencias Cruzadas**

### Documentos de Deep-Dive:
- [D.0_Constructor_barras_Dollar_Vol_Imbalance.md](./D.0_Constructor_barras_Dollar_Vol_Imbalance.md) - Overview pipeline y scripts
- [D.1_Ejecucion_Pipeline_DIB_Labels_Weights.md](./D.1_Ejecucion_Pipeline_DIB_Labels_Weights.md) - Ejecución completa
- [D.1.1_notas_6.1_DIB.md](./D.1.1_notas_6.1_DIB.md) - Parámetros DIB
- [D.1.2_notas_6.1_tripleBarrierLabeling.md](./D.1.2_notas_6.1_tripleBarrierLabeling.md) - Parámetros Triple Barrier
- [D.1.3_notas_6.1_SampleWeights.md](./D.1.3_notas_6.1_SampleWeights.md) - Parámetros Sample Weights
- [D.2_actualizacion_timestamp_FIX.md](./D.2_actualizacion_timestamp_FIX.md) - Fix crítico timestamps
- [D.3_resumen_pipeline.md](./D.3_resumen_pipeline.md) - Resumen ejecutivo

### Conexión con Fase C:
- INPUT de Fase D viene de OUTPUT de [PASO 5](../C_v2_ingesta_tiks_2004_2025/) (60,825 días ticks descargados)
- Utiliza eventos E0 detectados en [PASO 1-4](../C_v2_ingesta_tiks_2004_2025/)

---

## **Próximos Pasos**

1. ✅ Propuesta documentación creada (este archivo)
2. ⏭️ Revisión y aprobación por usuario
3. ⏭️ Integración en [map_route_phase1.md](../../map_route_phase1.md)
4. ⏭️ Fase E: Entrenamiento modelo ML (LightGBM/XGBoost)

---
