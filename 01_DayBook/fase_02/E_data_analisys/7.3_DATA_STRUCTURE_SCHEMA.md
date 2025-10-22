# Esquema Exhaustivo de Datos - Trading Smallcaps ML Pipeline

**Generado:** 2025-10-22
**Alcance temporal:** 2020-01-03 a 2025-10-21 (5.8 años)
**Universo:** 1,906 tickers únicos (info-rich events)
**Total ticker-days:** 11,054

---

## Resumen Ejecutivo

| Métrica | Valor |
|---------|-------|
| **Total tickers únicos** | 1,906 |
| **Total ticker-days** | 11,054 |
| **Total eventos (barras)** | ~1,193,095 |
| **Total rows dataset ML** | 1,622,333 |
| **Tamaño total datos raw** | ~2.6 GB (trades.parquet) |
| **Tamaño total datos processed** | ~360 MB |
| **Train rows** | 1,297,816 (79.9%) |
| **Valid rows** | 324,467 (20.1%) |

---

## 1. RAW DATA: Tick-Level Trades

### Ubicación
```
raw/polygon/trades/{ticker}/date=YYYY-MM-DD/
├── trades.parquet
└── _SUCCESS
```

### Métricas
- **Tickers:** 1,906
- **Ticker-days:** 11,054
- **Archivos `trades.parquet`:** 11,054
- **Archivos `_SUCCESS`:** 11,054

### Schema: `trades.parquet`

| Columna | Tipo | Descripción | Ejemplo |
|---------|------|-------------|---------|
| `t` | `Datetime(us)` | Timestamp del trade (nanosegundos convertidos a μs) | 2024-10-18 09:30:00.041734 |
| `p` | `Float64` | Precio del trade | 15.23 |
| `s` | `Int64` | Tamaño (shares) | 100 |
| `c` | `List(Int64)` | Condiciones del trade (flags Polygon) | [12, 37] |
| `exchange` | `Int64` | ID del exchange | 4 |
| `id` | `String` | Trade ID único | "12345" |
| `participant_timestamp` | `Int64` | Timestamp del participante (ns) | 1729238400041734650 |
| `sequence_number` | `Int64` | Número de secuencia | 98765 |
| `tape` | `Int64` | Tape (A/B/C) | 1 |
| `trf_id` | `Int64` | TRF ID | 1 |
| `trf_timestamp` | `Int64` | TRF timestamp (ns) | 1729238400041734650 |

### Ejemplo de archivo
- **Ticker:** BAER
- **Fecha:** 2024-10-18
- **Rows:** 13,032 trades
- **Tamaño:** 0.24 MB
- **Ruta:** `raw/polygon/trades/BAER/date=2024-10-18/trades.parquet`

### Origen
- **API:** Polygon.io v3 Trades Endpoint
- **Descarga:** Scripts `fase_C_ingesta_tiks`
- **Filtro:** Solo días info-rich (RVOL≥2.0, |%chg|≥15%, $vol≥$5M)

---

## 2. PROCESSED: Dollar Imbalance Bars (DIB)

### Ubicación
```
processed/bars/{ticker}/date=YYYY-MM-DD/
├── dollar_imbalance.parquet
└── _SUCCESS
```

### Métricas
- **Tickers:** 1,906
- **Ticker-days:** 11,054
- **Archivos `dollar_imbalance.parquet`:** 11,054
- **Archivos `_SUCCESS`:** 11,054
- **Total barras generadas:** ~1,193,095 (~108 barras/ticker-day)
- **Tamaño promedio/archivo:** 0.007 MB (~7 KB)

### Schema: `dollar_imbalance.parquet`

| Columna | Tipo | Descripción | Fórmula/Notas |
|---------|------|-------------|---------------|
| `t_open` | `Int64` | Timestamp apertura barra (μs) | Primer trade en la barra |
| `t_close` | `Int64` | Timestamp cierre barra (μs) | Último trade en la barra |
| `o` | `Float64` | Open price | Precio del primer trade |
| `h` | `Float64` | High price | max(p) en la barra |
| `l` | `Float64` | Low price | min(p) en la barra |
| `c` | `Float64` | Close price | Precio del último trade |
| `v` | `Int64` | Volume (shares) | sum(s) en la barra |
| `n` | `Int64` | Number of trades | count(trades) en la barra |
| `dollar` | `Float64` | Dollar flow acumulado | sum(p × s) |
| `imbalance_score` | `Float64` | Promedio de tick signs | mean(sign) donde sign ∈ {-1, 0, +1} |

### Parámetros de construcción
- **Tipo:** Dollar Imbalance Bars
- **Umbral:** $300,000 USD por barra (adaptativo con EMA)
- **EMA window:** 50 barras
- **Tick rule:** `sign = +1` si p > p_prev, `-1` si p < p_prev, `0` si igual

### Ejemplo de archivo
- **Ticker:** BAER
- **Fecha:** 2024-10-18
- **Rows:** 541 barras
- **Tamaño:** 0.026 MB
- **Ruta:** `processed/bars/BAER/date=2024-10-18/dollar_imbalance.parquet`

---

## 3. PROCESSED: Triple Barrier Labels

### Ubicación
```
processed/labels/{ticker}/date=YYYY-MM-DD/
└── labels.parquet
```

### Métricas
- **Tickers:** 1,906
- **Ticker-days:** 11,054
- **Archivos `labels.parquet`:** 11,054
- **Tamaño promedio/archivo:** 0.015 MB (~15 KB)

### Schema: `labels.parquet`

| Columna | Tipo | Descripción | Valores posibles |
|---------|------|-------------|------------------|
| `anchor_ts` | `Int64` | Timestamp del evento ancla (μs) | = `t_close` de la barra ancla |
| `t1` | `Int64` | Timestamp cuando se tocó barrera (μs) | Timestamp del outcome |
| `pt_hit` | `Boolean` | ¿Se tocó profit-target? | true/false |
| `sl_hit` | `Boolean` | ¿Se tocó stop-loss? | true/false |
| `label` | `Int64` | Etiqueta del evento | +1 (PT), -1 (SL), 0 (vertical) |
| `ret_at_outcome` | `Float64` | Retorno real al momento del outcome | (close_t1 / close_anchor) - 1 |
| `vol_at_anchor` | `Float64` | Volatilidad estimada en anchor | EMA(\|log_returns\|, 50) |

### Lógica Triple Barrier
- **Profit Target (PT):** `price_anchor × (1 + 3.0 × σ)`
- **Stop Loss (SL):** `price_anchor × (1 - 2.0 × σ)`
- **Vertical Barrier (T1):** 120 barras hacia adelante
- **Volatilidad (σ):** EMA de retornos absolutos, ventana 50
- **Label:**
  - `+1` si PT se toca primero
  - `-1` si SL se toca primero
  - `0` si ninguno se toca en 120 barras (vertical barrier)

### Ejemplo de archivo
- **Ticker:** BAER
- **Fecha:** 2024-10-18
- **Rows:** 541 labels (1 por barra)
- **Tamaño:** 0.015 MB
- **Ruta:** `processed/labels/BAER/date=2024-10-18/labels.parquet`

---

## 4. PROCESSED: Sample Weights

### Ubicación
```
processed/weights/{ticker}/date=YYYY-MM-DD/
└── weights.parquet
```

### Métricas
- **Tickers:** 1,906
- **Ticker-days:** 11,054
- **Archivos `weights.parquet`:** 11,054
- **Tamaño promedio/archivo:** 0.001 MB (~1 KB)

### Schema: `weights.parquet`

| Columna | Tipo | Descripción | Fórmula |
|---------|------|-------------|---------|
| `anchor_ts` | `Datetime(us)` | Timestamp del evento (para join con labels) | = `anchor_ts` de labels |
| `weight` | `Float64` | Peso normalizado del sample | `(|ret| / concurrency) × decay` |

### Cálculo de pesos
```
weight[i] = (|ret_at_outcome[i]| / concurrency[i]) × decay[i]

Donde:
- concurrency[i] = # de ventanas [anchor_ts, t1] que contienen evento i
- decay[i] = 0.5 ^ (age_days / 90)  [time-decay con half-life 90 días]
- Normalización: sum(weights) = 1.0 dentro de cada archivo (por ticker-day)
```

### Ejemplo de archivo
- **Ticker:** GRI
- **Fecha:** 2023-05-12
- **Rows:** 20 weights
- **Tamaño:** 0.001 MB
- **Ruta:** `processed/weights/GRI/date=2023-05-12/weights.parquet`

---

## 5. PROCESSED: ML Dataset (Daily)

### Ubicación
```
processed/datasets/daily/{ticker}/date=YYYY-MM-DD/
└── dataset.parquet
```

### Métricas
- **Tickers:** 1,906
- **Ticker-days:** 11,054
- **Archivos `dataset.parquet`:** 11,054
- **Tamaño promedio/archivo:** 0.074 MB (~74 KB)

### Schema: `dataset.parquet` (23 columnas)

#### Columnas de Labels (de `labels.parquet`)
| Columna | Tipo | Descripción |
|---------|------|-------------|
| `anchor_ts` | `Int64` | Timestamp del evento |
| `t1` | `Int64` | Timestamp del outcome |
| `pt_hit` | `Boolean` | ¿Tocó profit-target? |
| `sl_hit` | `Boolean` | ¿Tocó stop-loss? |
| `label` | `Int64` | +1 (PT), -1 (SL), 0 (vertical) |
| `ret_at_outcome` | `Float64` | Retorno real |
| `vol_at_anchor` | `Float64` | Volatilidad estimada |

#### Columnas de Features (engineered desde barras)
| Columna | Tipo | Descripción | Fórmula |
|---------|------|-------------|---------|
| `c` | `Float64` | Close price de la barra | De `dollar_imbalance.parquet` |
| `ret_1` | `Float64` | Retorno log 1-bar | log(c / c_prev) |
| `range_norm` | `Float64` | Rango normalizado | (H - L) / \|C_prev\| |
| `vol_f` | `Float64` | Volume (shares) | Alias de `v` |
| `dollar_f` | `Float64` | Dollar flow | Alias de `dollar` |
| `imb_f` | `Float64` | Imbalance score | Alias de `imbalance_score` |
| `ret_1_ema10` | `Float64` | EMA(10) de ret_1 | Suavizado exponencial |
| `ret_1_ema30` | `Float64` | EMA(30) de ret_1 | Suavizado exponencial |
| `range_norm_ema20` | `Float64` | EMA(20) de range_norm | Suavizado exponencial |
| `vol_f_ema20` | `Float64` | EMA(20) de volume | Suavizado exponencial |
| `dollar_f_ema20` | `Float64` | EMA(20) de dollar flow | Suavizado exponencial |
| `imb_f_ema20` | `Float64` | EMA(20) de imbalance | Suavizado exponencial |
| `vol_z20` | `Float64` | Z-score del volume (ventana 20) | (vol - mean) / std |
| `dollar_z20` | `Float64` | Z-score del dollar flow (ventana 20) | (dollar - mean) / std |
| `n` | `Int64` | Number of trades en la barra | De `dollar_imbalance.parquet` |

#### Columna de Weight
| Columna | Tipo | Descripción |
|---------|------|-------------|
| `weight` | `Float64` | Sample weight (de `weights.parquet`) |

### Join Logic
```python
dataset = bars.join(labels, left_on="t_close", right_on="anchor_ts")
              .with_features(...)  # Feature engineering
              .join(weights, on="anchor_ts")
```

### Ejemplo de archivo
- **Ticker:** BAER
- **Fecha:** 2024-10-18
- **Rows:** 541 eventos
- **Tamaño:** 0.074 MB
- **Ruta:** `processed/datasets/daily/BAER/date=2024-10-18/dataset.parquet`

---

## 6. PROCESSED: ML Dataset (Global)

### Ubicación
```
processed/datasets/global/
└── dataset.parquet
```

### Métricas
- **Archivo único:** `dataset.parquet`
- **Total rows:** 1,622,333 eventos
- **Tamaño:** 183.2 MB

### Schema
- **Idéntico al daily dataset** (23 columnas)
- Concatenación vertical de todos los 11,054 daily datasets
- Ordenado cronológicamente por `anchor_ts`

### Rango temporal
- **Primer evento:** 2020-01-03
- **Último evento:** 2025-10-21

### Distribución temporal
- **Total tickers:** 1,906
- **Promedio eventos/ticker-day:** 146.8 eventos
- **Mediana eventos/ticker-day:** ~108 eventos

---

## 7. PROCESSED: ML Dataset (Train/Valid Splits)

### Ubicación
```
processed/datasets/splits/
├── train.parquet
└── valid.parquet
```

### Parámetros del Split
- **Método:** Walk-forward (temporal)
- **Folds:** 5
- **Purge gap:** 50 barras entre train/valid
- **Train:** Primeros 4 folds (80% - purge)
- **Valid:** Último fold (20%)

### Schema: `train.parquet`
- **Columnas:** Idénticas al global dataset (23 columnas)
- **Rows:** 1,297,816 (79.9%)
- **Tamaño:** 146.9 MB
- **Rango temporal:** 2020-01-03 a ~2024-06-30 (aprox)

### Schema: `valid.parquet`
- **Columnas:** Idénticas al global dataset (23 columnas)
- **Rows:** 324,467 (20.1%)
- **Tamaño:** 36.0 MB
- **Rango temporal:** ~2024-07-01 a 2025-10-21 (aprox)

### Walk-Forward Split Logic
```python
# Divide timeline en 5 segmentos temporales uniformes
n_rows = 1,622,333
segment_size = n_rows / 5 = 324,467

# Train = segmentos 1-4, minus purge
train_end = (4 * segment_size) - 50  # Purge de 50 barras
train = dataset[0 : train_end]       # 1,297,816 rows

# Valid = segmento 5
valid_start = 4 * segment_size
valid = dataset[valid_start : ]      # 324,467 rows
```

---

## 8. METADATA

### Ubicación
```
processed/datasets/
└── meta.json
```

### Contenido: `meta.json`
```json
{
  "created_at": "2025-10-22T20:02:06",
  "bars_root": "processed/bars",
  "labels_root": "processed/labels",
  "weights_root": "processed/weights",
  "outdir": "processed/datasets",
  "bar_file": "dollar_imbalance.parquet",
  "tasks": 11054,
  "daily_files": 11054,
  "global_rows": 1622333,
  "split": "walk_forward",
  "folds": 5,
  "purge_bars": 50,
  "train_rows": 1297816,
  "valid_rows": 324467,
  "feature_columns_example": [
    "ret_1", "range_norm", "vol_f", "dollar_f", "imb_f",
    "ret_1_ema10", "ret_1_ema30", "range_norm_ema20",
    "vol_f_ema20", "dollar_f_ema20", "imb_f_ema20",
    "vol_z20", "dollar_z20", "n"
  ],
  "label_column": "label",
  "weight_column": "weight",
  "time_index": "anchor_ts"
}
```

---

## 9. Árbol Completo de Directorios

```
D:/04_TRADING_SMALLCAPS/
│
├── raw/polygon/trades/                    [11,054 ticker-days × 2 archivos = 22,108 archivos]
│   ├── BAER/
│   │   ├── date=2024-10-18/
│   │   │   ├── trades.parquet             (13,032 rows, 0.24 MB)
│   │   │   └── _SUCCESS
│   │   └── date=2024-10-25/
│   │       ├── trades.parquet
│   │       └── _SUCCESS
│   ├── CLPT/
│   │   └── date=.../
│   ├── CVRX/
│   ├── ... [1,906 tickers]
│   └── ZYXI/
│
├── processed/bars/                        [11,054 ticker-days × 2 archivos = 22,108 archivos]
│   ├── BAER/
│   │   ├── date=2024-10-18/
│   │   │   ├── dollar_imbalance.parquet   (541 rows, 0.026 MB)
│   │   │   └── _SUCCESS
│   │   └── date=2024-10-25/
│   │       ├── dollar_imbalance.parquet
│   │       └── _SUCCESS
│   ├── GRI/
│   ├── ... [1,906 tickers]
│   └── ZYXI/
│
├── processed/labels/                      [11,054 archivos]
│   ├── BAER/
│   │   ├── date=2024-10-18/
│   │   │   └── labels.parquet             (541 rows, 0.015 MB)
│   │   └── date=2024-10-25/
│   │       └── labels.parquet
│   ├── GRI/
│   ├── ... [1,906 tickers]
│   └── ZYXI/
│
├── processed/weights/                     [11,054 archivos]
│   ├── BAER/
│   │   ├── date=2024-10-18/
│   │   │   └── weights.parquet            (variable rows, ~0.001 MB)
│   │   └── date=2024-10-25/
│   │       └── weights.parquet
│   ├── GRI/
│   ├── ... [1,906 tickers]
│   └── ZYXI/
│
└── processed/datasets/                    [11,054 + 3 archivos = 11,057 archivos]
    ├── daily/                             [11,054 archivos]
    │   ├── BAER/
    │   │   ├── date=2024-10-18/
    │   │   │   └── dataset.parquet        (541 rows, 0.074 MB, 23 cols)
    │   │   └── date=2024-10-25/
    │   │       └── dataset.parquet
    │   ├── GRI/
    │   ├── ... [1,906 tickers]
    │   └── ZYXI/
    ├── global/                            [1 archivo]
    │   └── dataset.parquet                (1,622,333 rows, 183.2 MB, 23 cols)
    ├── splits/                            [2 archivos]
    │   ├── train.parquet                  (1,297,816 rows, 146.9 MB, 23 cols)
    │   └── valid.parquet                  (324,467 rows, 36.0 MB, 23 cols)
    └── meta.json                          [1 archivo]
```

---

## 10. Conteo Total de Archivos

| Directorio | Archivos por ticker-day | Total archivos |
|------------|-------------------------|----------------|
| `raw/polygon/trades` | 2 (trades.parquet + _SUCCESS) | 22,108 |
| `processed/bars` | 2 (dollar_imbalance.parquet + _SUCCESS) | 22,108 |
| `processed/labels` | 1 (labels.parquet) | 11,054 |
| `processed/weights` | 1 (weights.parquet) | 11,054 |
| `processed/datasets/daily` | 1 (dataset.parquet) | 11,054 |
| `processed/datasets/global` | - | 1 |
| `processed/datasets/splits` | - | 2 |
| `processed/datasets/meta` | - | 1 |
| **TOTAL** | | **77,382 archivos** |

---

## 11. Tamaños de Datos

| Directorio | Tamaño promedio/archivo | Tamaño total estimado |
|------------|-------------------------|----------------------|
| `raw/polygon/trades` | ~0.24 MB | ~2.6 GB |
| `processed/bars` | ~0.007 MB | ~77 MB |
| `processed/labels` | ~0.015 MB | ~166 MB |
| `processed/weights` | ~0.001 MB | ~11 MB |
| `processed/datasets/daily` | ~0.074 MB | ~818 MB |
| `processed/datasets/global` | - | 183 MB |
| `processed/datasets/splits` | - | 183 MB (train+valid) |
| **TOTAL** | | **~4.0 GB** |

---

## 12. Relaciones y Keys para BBDD

### Primary Keys
- **raw/polygon/trades:** `(ticker, date, t)` - Uniqueness por trade timestamp
- **processed/bars:** `(ticker, date, t_close)` - Uniqueness por barra
- **processed/labels:** `(ticker, date, anchor_ts)` - Uniqueness por evento
- **processed/weights:** `(ticker, date, anchor_ts)` - 1:1 con labels
- **processed/datasets/daily:** `(ticker, date, anchor_ts)` - Join de bars+labels+weights

### Foreign Keys / Joins
```sql
-- Barras → Trades (relación many-to-many implícita)
bars.t_open <= trades.t <= bars.t_close

-- Labels → Barras (1:1 por anchor_ts)
labels.anchor_ts = bars.t_close

-- Weights → Labels (1:1 por anchor_ts)
weights.anchor_ts = labels.anchor_ts

-- Dataset → Barras + Labels + Weights (inner join)
dataset.anchor_ts = bars.t_close = labels.anchor_ts = weights.anchor_ts
```

### Temporal Indices
- **Orden cronológico:** `anchor_ts` en todos los datasets
- **Partición:** `(ticker, date)` en daily datasets
- **Walk-forward split:** Temporal partition en `anchor_ts`

---

## 13. Formatos y Compresión

### Formato de archivo
- **Todos los datos:** Apache Parquet
- **Compresión:** ZSTD level 2
- **Statistics:** Disabled (para velocidad de escritura)

### Ventajas Parquet
- Columnar storage (queries eficientes)
- Schema integrado (autodocumentación)
- Compresión ZSTD (~5-10x vs CSV)
- Compatible con Polars, Pandas, DuckDB, Spark

---

## 14. Nomenclatura y Convenciones

### Particionamiento Hive-style
```
{dataset}/{ticker}/date=YYYY-MM-DD/{filename}.parquet
```

### Columnas temporales
- **Timestamp format:** Microsegundos desde epoch (Int64)
- **Conversión:** `datetime.fromtimestamp(ts / 1_000_000)`
- **Timezone:** UTC (implícito)

### Marcadores de éxito
- **`_SUCCESS`:** Archivo vacío que indica procesamiento completo
- **Idempotencia:** Scripts verifican `_SUCCESS` antes de reprocesar

---

## 15. Esquema SQL Recomendado (para migración a BBDD)

### Tabla: `raw_trades`
```sql
CREATE TABLE raw_trades (
    ticker VARCHAR(10) NOT NULL,
    date DATE NOT NULL,
    t TIMESTAMP(6) NOT NULL,  -- Microsegundos
    p DECIMAL(18, 6) NOT NULL,
    s BIGINT NOT NULL,
    c INTEGER[],  -- Array de condiciones
    exchange INTEGER,
    trade_id VARCHAR(50),
    participant_timestamp BIGINT,
    sequence_number BIGINT,
    tape INTEGER,
    trf_id INTEGER,
    trf_timestamp BIGINT,
    PRIMARY KEY (ticker, date, t),
    INDEX idx_ticker_date (ticker, date),
    INDEX idx_timestamp (t)
) PARTITION BY LIST (ticker);
```

### Tabla: `bars_dollar_imbalance`
```sql
CREATE TABLE bars_dollar_imbalance (
    ticker VARCHAR(10) NOT NULL,
    date DATE NOT NULL,
    t_open TIMESTAMP(6) NOT NULL,
    t_close TIMESTAMP(6) NOT NULL,
    o DECIMAL(18, 6),
    h DECIMAL(18, 6),
    l DECIMAL(18, 6),
    c DECIMAL(18, 6),
    v BIGINT,
    n INTEGER,
    dollar DECIMAL(24, 6),
    imbalance_score DECIMAL(8, 6),
    PRIMARY KEY (ticker, date, t_close),
    INDEX idx_ticker_date (ticker, date),
    INDEX idx_t_close (t_close)
) PARTITION BY RANGE (date);
```

### Tabla: `labels_triple_barrier`
```sql
CREATE TABLE labels_triple_barrier (
    ticker VARCHAR(10) NOT NULL,
    date DATE NOT NULL,
    anchor_ts TIMESTAMP(6) NOT NULL,
    t1 TIMESTAMP(6),
    pt_hit BOOLEAN,
    sl_hit BOOLEAN,
    label SMALLINT CHECK (label IN (-1, 0, 1)),
    ret_at_outcome DECIMAL(12, 8),
    vol_at_anchor DECIMAL(12, 8),
    PRIMARY KEY (ticker, date, anchor_ts),
    FOREIGN KEY (ticker, date, anchor_ts)
        REFERENCES bars_dollar_imbalance(ticker, date, t_close),
    INDEX idx_label (label),
    INDEX idx_anchor_ts (anchor_ts)
) PARTITION BY RANGE (date);
```

### Tabla: `sample_weights`
```sql
CREATE TABLE sample_weights (
    ticker VARCHAR(10) NOT NULL,
    date DATE NOT NULL,
    anchor_ts TIMESTAMP(6) NOT NULL,
    weight DECIMAL(18, 12),
    PRIMARY KEY (ticker, date, anchor_ts),
    FOREIGN KEY (ticker, date, anchor_ts)
        REFERENCES labels_triple_barrier(ticker, date, anchor_ts)
) PARTITION BY RANGE (date);
```

### Tabla: `ml_dataset_daily`
```sql
CREATE TABLE ml_dataset_daily (
    ticker VARCHAR(10) NOT NULL,
    date DATE NOT NULL,
    anchor_ts TIMESTAMP(6) NOT NULL,
    t1 TIMESTAMP(6),
    pt_hit BOOLEAN,
    sl_hit BOOLEAN,
    label SMALLINT,
    ret_at_outcome DECIMAL(12, 8),
    vol_at_anchor DECIMAL(12, 8),
    c DECIMAL(18, 6),
    ret_1 DECIMAL(12, 8),
    range_norm DECIMAL(12, 8),
    vol_f DECIMAL(18, 2),
    dollar_f DECIMAL(24, 6),
    imb_f DECIMAL(8, 6),
    ret_1_ema10 DECIMAL(12, 8),
    ret_1_ema30 DECIMAL(12, 8),
    range_norm_ema20 DECIMAL(12, 8),
    vol_f_ema20 DECIMAL(18, 2),
    dollar_f_ema20 DECIMAL(24, 6),
    imb_f_ema20 DECIMAL(8, 6),
    vol_z20 DECIMAL(12, 8),
    dollar_z20 DECIMAL(12, 8),
    n INTEGER,
    weight DECIMAL(18, 12),
    PRIMARY KEY (ticker, date, anchor_ts),
    INDEX idx_label (label),
    INDEX idx_ticker_date (ticker, date),
    INDEX idx_anchor_ts (anchor_ts)
) PARTITION BY RANGE (date);
```

### View: `ml_dataset_train`
```sql
CREATE VIEW ml_dataset_train AS
SELECT *
FROM ml_dataset_daily
WHERE anchor_ts < '2024-07-01'  -- Aproximación del split
ORDER BY anchor_ts;
```

### View: `ml_dataset_valid`
```sql
CREATE VIEW ml_dataset_valid AS
SELECT *
FROM ml_dataset_daily
WHERE anchor_ts >= '2024-07-01'
ORDER BY anchor_ts;
```

---

## 16. Queries de Ejemplo

### Query 1: Contar eventos por label
```sql
SELECT
    label,
    COUNT(*) as count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) as pct
FROM labels_triple_barrier
GROUP BY label
ORDER BY label;
```

### Query 2: Top tickers por número de eventos
```sql
SELECT
    ticker,
    COUNT(DISTINCT date) as days,
    COUNT(*) as events,
    ROUND(AVG(ret_at_outcome), 6) as avg_return
FROM labels_triple_barrier
GROUP BY ticker
ORDER BY events DESC
LIMIT 20;
```

### Query 3: Estadísticas de barras por ticker-day
```sql
SELECT
    ticker,
    date,
    COUNT(*) as num_bars,
    AVG(dollar) as avg_dollar_flow,
    AVG(imbalance_score) as avg_imbalance,
    AVG(n) as avg_trades_per_bar
FROM bars_dollar_imbalance
GROUP BY ticker, date
ORDER BY num_bars DESC
LIMIT 100;
```

### Query 4: Join completo para ML
```sql
SELECT
    d.*,
    b.o, b.h, b.l, b.v, b.n, b.dollar, b.imbalance_score
FROM ml_dataset_daily d
LEFT JOIN bars_dollar_imbalance b
    ON d.ticker = b.ticker
    AND d.date = b.date
    AND d.anchor_ts = b.t_close
WHERE d.label != 0  -- Solo eventos con señal clara
ORDER BY d.anchor_ts;
```

---

## Conclusión

Este esquema documenta **exhaustivamente** toda la estructura de datos generada por el pipeline ML:

- **77,382 archivos** totales
- **5 capas de procesamiento** (raw → bars → labels → weights → dataset)
- **1,622,333 eventos** listos para ML
- **23 features** engineered por evento
- **Train/Valid splits** con walk-forward temporal

Los datos están en formato **Parquet** con **particionamiento Hive-style** (`ticker/date=YYYY-MM-DD`), listos para:
1. **Ingesta directa** a BBDD relacional (PostgreSQL, MySQL, etc.)
2. **Queries ad-hoc** con DuckDB/Polars
3. **Entrenamiento ML** con LightGBM/XGBoost/TensorFlow

**Archivos de referencia:**
- `DATA_STRUCTURE_MAP.json` - Mapa completo en JSON
- `processed/datasets/meta.json` - Metadata del pipeline
- `07_Ejecucion_Pipeline_DIB_Labels_Weights.md` - Documentación de ejecución
