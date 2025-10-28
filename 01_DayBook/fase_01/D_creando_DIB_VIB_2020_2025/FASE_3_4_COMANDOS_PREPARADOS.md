# Fase 3 y 4: Sample Weights + ML Dataset Builder

**Fecha preparación**: 2025-10-27
**Status anterior**: DIB (100%) + Labels (99.998%) → COMPLETADOS
**Objetivo**: Completar pipeline ML end-to-end

---

## Estado Actual del Pipeline

### ✅ Fase 1: Dollar Imbalance Bars (DIB) - COMPLETADO
- **Archivos**: 64,801 / 64,801 (100%)
- **Tiempo**: 55.5 minutos
- **Output**: `processed/bars/{TICKER}/date={YYYY-MM-DD}/dollar_imbalance.parquet`
- **Marcadores _SUCCESS**: 100%

### ✅ Fase 2: Triple Barrier Labeling - COMPLETADO
- **Archivos**: 64,800 / 64,801 (99.998%)
- **Tiempo**: 25.3 minutos
- **Output**: `processed/labels/{TICKER}/date={YYYY-MM-DD}/labels.parquet`
- **Parámetros**: PT=3σ, SL=2σ, T1=120 barras
- **Validación**: Timestamps correctos, retornos coherentes

---

## Fase 3: Sample Weights

### Objetivo
Calcular pesos de muestra para cada barra etiquetada, considerando:
1. **Unicidad temporal**: Reducir peso de eventos solapados
2. **Magnitud del retorno**: Mayor peso a movimientos significativos
3. **Time-decay**: Datos recientes más relevantes

### Comando Preparado

```bash
cd D:/04_TRADING_SMALLCAPS

python scripts/fase_D_creando_DIB_VIB/make_sample_weights.py \
  --labels-root processed/labels \
  --outdir processed/weights \
  --uniqueness \
  --abs-ret-weight \
  --time-decay-half_life 90 \
  --parallel 8 \
  --resume
```

### Parámetros

| Parámetro | Valor | Descripción |
|-----------|-------|-------------|
| `--labels-root` | `processed/labels` | Directorio con labels generados en Fase 2 |
| `--outdir` | `processed/weights` | Directorio output para weights |
| `--uniqueness` | `true` | Ajusta peso por concurrency (ventanas overlapping) |
| `--abs-ret-weight` | `true` | Peso base = \|ret_at_outcome\| (favorece eventos significativos) |
| `--time-decay-half_life` | `90` | Semivida de 90 días (decay exponencial por antigüedad) |
| `--parallel` | `8` | Workers en paralelo |
| `--resume` | `true` | Idempotencia (skip archivos ya procesados) |

### Fórmula de Pesos

```
weight[i] = (|ret_at_outcome[i]| / concurrency[i]) × decay[i]
```

Donde:
- **concurrency[i]**: Número de ventanas `[anchor_ts, t1]` que contienen el evento `i`
- **decay[i]**: `0.5 ^ (age_days / 90)` (aproximación para eventos dentro del mismo día = 1.0)
- **Normalización**: Pesos se escalan para sumar 1.0 dentro de cada archivo (por ticker-day)

### Output Esperado

```
processed/weights/
├── {TICKER_1}/
│   └── date=2004-04-20/
│       └── weights.parquet  ← Schema: {anchor_ts, weight}
├── {TICKER_2}/
│   └── date=2004-04-21/
│       └── weights.parquet
└── ...
```

**Schema weights.parquet**:
```
{
  'anchor_ts': Datetime (o Int64),  # Join key con labels
  'weight': Float64                  # Peso normalizado (sum=1.0 por archivo)
}
```

### Estimación de Tiempo
- **Archivos a procesar**: ~64,800
- **Velocidad estimada**: ~50 archivos/segundo (basado en Fase 2)
- **Tiempo estimado**: **~20-25 minutos**

---

## Fase 4: ML Dataset Builder

### Objetivo
Consolidar DIB + Labels + Weights en un dataset ML final listo para entrenamiento.

### Comando Preparado

```bash
cd D:/04_TRADING_SMALLCAPS

python scripts/fase_D_creando_DIB_VIB/build_ml_daser.py \
  --bars-root processed/bars \
  --labels-root processed/labels \
  --weights-root processed/weights \
  --outdir processed/datasets \
  --bar-file dollar_imbalance.parquet \
  --parallel 8 \
  --resume \
  --split walk_forward \
  --folds 5 \
  --purge-bars 50
```

### Parámetros

| Parámetro | Valor | Descripción |
|-----------|-------|-------------|
| `--bars-root` | `processed/bars` | Directorio con barras DIB |
| `--labels-root` | `processed/labels` | Directorio con labels |
| `--weights-root` | `processed/weights` | Directorio con weights |
| `--outdir` | `processed/datasets` | Directorio output |
| `--bar-file` | `dollar_imbalance.parquet` | Nombre archivo barras |
| `--parallel` | `8` | Workers paralelos |
| `--resume` | `true` | Idempotencia |
| `--split` | `walk_forward` | Tipo de split temporal |
| `--folds` | `5` | Número de folds para validación |
| `--purge-bars` | `50` | Gap de purging entre train/valid (evita leakage) |

### Proceso

1. **Feature Engineering** por ticker-day:
   - Retornos log: `ret_1`
   - Rango normalizado: `range_norm = (H-L) / |C_prev|`
   - Volume/Dollar/Imbalance features: `vol_f`, `dollar_f`, `imb_f`
   - EMAs: `ret_1_ema10`, `ret_1_ema30`, `range_norm_ema20`, `vol_f_ema20`, `dollar_f_ema20`, `imb_f_ema20`
   - Z-scores: `vol_z20`, `dollar_z20`

2. **Join de componentes**:
   ```python
   dataset = bars.join(labels, left_on="t_close", right_on="anchor_ts")
                 .join(weights, on="anchor_ts")
   ```

3. **Datasets diarios**: 64,800 archivos `processed/datasets/daily/{ticker}/date={day}/dataset.parquet`

4. **Dataset global**: Concatenación de todos los daily datasets

5. **Walk-Forward Split**:
   - Divide timeline en 5 folds
   - Train = primeros 4 folds (con purge de 50 barras al final)
   - Valid = último fold

### Output Esperado

```
processed/datasets/
├── daily/
│   └── {ticker}/date={day}/dataset.parquet  (64,800 archivos)
├── global/
│   └── dataset.parquet  (~1.5M+ rows)
├── splits/
│   ├── train.parquet  (~1.2M rows, ~80%)
│   └── valid.parquet  (~300K rows, ~20%)
└── meta.json  (metadata del dataset)
```

### Features Generadas (14 columnas)

```python
[
    "ret_1", "range_norm", "vol_f", "dollar_f", "imb_f",
    "ret_1_ema10", "ret_1_ema30", "range_norm_ema20",
    "vol_f_ema20", "dollar_f_ema20", "imb_f_ema20",
    "vol_z20", "dollar_z20", "n"
]
```

### Columnas Adicionales

- `label`: -1 (SL), 0 (Vertical), +1 (PT)
- `weight`: Peso de muestra (sum=1.0 por ticker-day, luego global)
- `anchor_ts`: Timestamp de referencia
- OHLCV original: `o`, `h`, `l`, `c`, `v`
- `dollar`: Dollar volume por barra
- `imbalance_score`: Tick rule indicator

### Estimación de Tiempo
- **Fase daily datasets**: ~5-10 minutos (feature engineering paralelo)
- **Fase concat global**: ~3-5 minutos (concatenación + ordenamiento)
- **Fase split**: ~2-3 minutos (walk-forward + purging)
- **Tiempo total estimado**: **~10-18 minutos**

---

## Ejecución Secuencial Propuesta

### Opción A: Ejecutar Fase 3 + Fase 4 en secuencia

```bash
# Fase 3: Sample Weights
cd D:/04_TRADING_SMALLCAPS
python scripts/fase_D_creando_DIB_VIB/make_sample_weights.py \
  --labels-root processed/labels \
  --outdir processed/weights \
  --uniqueness \
  --abs-ret-weight \
  --time-decay-half_life 90 \
  --parallel 8 \
  --resume

# Auditoría Fase 3
echo "=== AUDITORÍA FASE 3: SAMPLE WEIGHTS ==="
find processed/weights -name "weights.parquet" | wc -l

# Fase 4: ML Dataset Builder
python scripts/fase_D_creando_DIB_VIB/build_ml_daser.py \
  --bars-root processed/bars \
  --labels-root processed/labels \
  --weights-root processed/weights \
  --outdir processed/datasets \
  --bar-file dollar_imbalance.parquet \
  --parallel 8 \
  --resume \
  --split walk_forward \
  --folds 5 \
  --purge-bars 50

# Auditoría Fase 4
echo "=== AUDITORÍA FASE 4: ML DATASET ==="
echo "Daily files:"
find processed/datasets/daily -name "dataset.parquet" | wc -l
echo "Global dataset:"
ls -lh processed/datasets/global/dataset.parquet
echo "Train/Valid splits:"
ls -lh processed/datasets/splits/
```

### Opción B: Ejecutar solo Fase 3 (esperar validación)

```bash
cd D:/04_TRADING_SMALLCAPS
python scripts/fase_D_creando_DIB_VIB/make_sample_weights.py \
  --labels-root processed/labels \
  --outdir processed/weights \
  --uniqueness \
  --abs-ret-weight \
  --time-decay-half_life 90 \
  --parallel 8 \
  --resume
```

Luego validar, y ejecutar Fase 4 por separado.

---

## Validación Post-Ejecución

### Fase 3: Sample Weights

**Checklist**:
- [ ] Número de archivos weights.parquet == número de archivos labels.parquet
- [ ] Schema correcto: `{anchor_ts, weight}`
- [ ] Weights sum = 1.0 por archivo
- [ ] Weights > 0 para todas las barras
- [ ] No NaN o Inf en weights

**Comando validación**:
```python
import polars as pl
from pathlib import Path

weight_files = list(Path('processed/weights').rglob('weights.parquet'))
print(f"Total archivos weights: {len(weight_files)}")

# Sample validation
sample = weight_files[0]
df = pl.read_parquet(sample)
print(f"\nSchema: {df.schema}")
print(f"Sum weights: {df['weight'].sum()}")
print(f"Min weight: {df['weight'].min()}")
print(f"Max weight: {df['weight'].max()}")
print(f"NaN count: {df['weight'].is_null().sum()}")
```

### Fase 4: ML Dataset

**Checklist**:
- [ ] Daily files generados (~64,800)
- [ ] Global dataset consolidado (>1M rows)
- [ ] Train/Valid splits creados
- [ ] 14 features presentes
- [ ] Labels + Weights incluidos
- [ ] No NaN en features críticos
- [ ] Walk-forward gap verificado (purge-bars=50)

**Comando validación**:
```python
import polars as pl

# Global dataset
df = pl.read_parquet('processed/datasets/global/dataset.parquet')
print(f"Global rows: {len(df):,}")
print(f"Columns: {df.columns}")
print(f"Date range: {df['anchor_ts'].min()} → {df['anchor_ts'].max()}")

# Train/Valid splits
train = pl.read_parquet('processed/datasets/splits/train.parquet')
valid = pl.read_parquet('processed/datasets/splits/valid.parquet')
print(f"\nTrain rows: {len(train):,} ({len(train)/len(df)*100:.1f}%)")
print(f"Valid rows: {len(valid):,} ({len(valid)/len(df)*100:.1f}%)")

# Label distribution
print(f"\nLabel distribution (train):")
print(train['label'].value_counts().sort('label'))
```

---

## Próximos Pasos (Post Fase 4)

Una vez completado el dataset ML:

1. **Exploración de Features**:
   - Correlaciones entre features
   - Importancia de features (permutation, SHAP)
   - Distribuciones por label

2. **Baseline Model**:
   - LightGBM con hiperparámetros default
   - Validación walk-forward
   - Métricas: Accuracy, F1, AUC, Sharpe ratio simulado

3. **Hyperparameter Tuning**:
   - Optuna para búsqueda bayesiana
   - Cross-validation con purging

4. **Backtesting**:
   - Simulación de trading con señales del modelo
   - Costos de transacción
   - Position sizing
   - Métricas de riesgo: Sharpe, Sortino, Max DD

---

## Notas Técnicas

### Optimizaciones Aplicadas
- **Paralelismo agresivo**: 8 workers en todas las fases
- **Resume-safe**: Todos los scripts soportan `--resume`
- **ZSTD compression**: Level 2 para balance velocidad/tamaño
- **Polars**: DataFrames de alto rendimiento vs pandas

### Lecciones Aprendidas (Fases 1-2)
- Timestamps en nanosegundos requieren conversión explícita
- Validación empírica crítica antes de proceder
- Paralelismo I/O-bound escala bien hasta 8-12 workers
- Resume markers evitan reprocesamiento en caso de fallo

### Advertencias
1. **Memory**: Fase 4 (concatenación global) puede requerir ~4-8 GB RAM
2. **Disk I/O**: ~150-200 MB output total (comprimido)
3. **CPU**: 8 cores recomendados para mantener velocidad
4. **Labels requeridos**: Fase 3 depende de Fase 2 (labels)
5. **Weights requeridos**: Fase 4 depende de Fase 3 (weights)

---

**Preparado por**: Claude Code
**Fecha**: 2025-10-27
**Validación previa**: DIB (100%) + Labels (99.998%)
**Status**: ✅ LISTO PARA EJECUTAR FASE 3
