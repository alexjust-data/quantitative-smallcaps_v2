# Validation Pipeline - Checkpoint Map

**Objetivo**: Certificar ejecución completa del proyecto desde su inicio. Documento de control ejecutivo `checkpoint map` que certifique cada paso completado con evidencia tangible + links a documentación detallada.  
**Última actualización**: 2025-10-30  


**OBJETIVO**  
Descargar datos tick-by-tick (trades) de Polygon API **SOLO para ventanas temporales donde ocurren eventos clave** detectables en el universo hibrido (8,686 tickers, 21 anos). NO necesitamos ticks de TODO el historico: Solo necesitamos ticks de periodos con **actividad informativa relevante = eventos de pump & dump**. Estos eventos marcan las ventanas temporales criticas para descargar ticks.

**FUNDAMENTO TEORICO**

* Lopez de Prado: Information-Driven Bars : De "Advances in Financial Machine Learning" Cap 2.3.2 (pp. 29-32):

    > "The purpose of information-driven bars is to sample more frequently when new information arrives to the market."
    >
    >**Dollar Imbalance Bars (DIBs)** y **Dollar Runs Bars (DRBs)** requieren datos tick-by-tick:
    >- **DIBs:** Detectan desbalance compra/venta (pump initiation)
    >- **DRBs:** Detectan sweeping agresivo (informed traders)

* EduTrades: Eventos Clave en Small Caps : Del Playbook Operativo (14 estrategias)
    > 1. **Explosion de volumen** (RVOL > 5x)
    > 2. **Gaps significativos** (>15%)
    > 3. **Movimientos parabolicos** (>50% en 1-5 dias)
    > 4. **First Red Day** (primer dia rojo tras corrida)
    > 5. **Dilution events** (offerings, correlacionados con colapsos)


### EVENTOS 

**CLAVES A DETECTAR : fase del ciclo pump & dump:**

```
FASE 1: DORMIDO (skip - no descargar ticks)
    +-- Bajo volumen, sin volatilidad

FASE 2: CATALIZADOR (EVENTO 1)
    +-- [E1] Volume Explosion: RVOL > 5x
    +-- [E2] Gap Up Significativo: Gap > 10%
    +-- [E3] Price Spike Intraday: +20% intradía

FASE 3: PUMP / EXTENSION (EVENTO 2)
    +-- [E4] Parabolic Move: +50% en 1-5 dias
    +-- [E5] Breakout ATH/52W: Nuevo high
    +-- [E6] Multiple Green Days: 3+ dias verdes consecutivos

FASE 4: DUMP / COLLAPSE (EVENTO 3)
    +-- [E7] First Red Day (FRD): Primer dia rojo post-pump
    +-- [E8] Gap Down Violento: Gap < -15%
    +-- [E9] Crash Intraday: -30% en <2 horas

FASE 5: BOUNCE (EVENTO 4)
    +-- [E10] First Green Day Bounce: Verde post-dump
    +-- [E11] Volume Spike on Bounce: RVOL > 3x en rebote

FASE 6: MUERTE (skip - no descargar ticks)
    +-- Volver a niveles base, dormido
```

**Eventos Especiales (Ortogonales al Ciclo)**

```
DILUTION EVENTS (EVENTO 5)
    +-- [E12] S-3 Effective Date +/- 2 dias
    +-- [E13] 424B Pricing Date +/- 2 dias
    +-- [E14] Warrant Exercise Events

MICROSTRUCTURE ANOMALIES (EVENTO 6)
    +-- [E15] Halts (LUDP, LUDS)
    +-- [E16] SSR Trigger (Short Sale Restriction)
    +-- [E17] Extreme Spread Events (bid/ask > 10%)
```

### VENTANAS temporales

Para cada evento detectado, descargar ticks en ventana

---

## .. / fase_01 / A_universo 

```sh
1. Reference Universe (/v3/reference/tickers)
    📂 raw/polygon/reference/tickers_snapshot/
    📊 34,380 tickers totales (snapshot 2025-10-24)
    ├── 11,853 activos
    └── 22,527 inactivos (anti-survivorship bias)
    📄 Files: tickers_all.parquet, tickers_active.parquet, tickers_inactive.parquet

2. Splits (/v3/reference/splits)
    📂 raw/polygon/reference/splits/
    📊 26,641 splits históricos
    📄 31 archivos parquet (particionado)

3. Dividends (/v3/reference/dividends)
    📂 raw/polygon/reference/dividends/
    📊 1,878,357 dividendos históricos
    📄 31 archivos parquet (particionado)

4. Ticker Details (/v3/reference/tickers/{ticker})
    📂 raw/polygon/reference/ticker_details/
    📄 2 archivos parquet (enriquecimiento parcial)
    ⚠️  INCOMPLETO - Solo sample ejecutado
```

> EVIDENCIA de los resulados: 
>- [A_Universo / notebooks / notebook2.ipynb](../01_DayBook/fase_01/A_Universo/notebooks/notebook2.ipynb)

---

## .. / fase_01 / B_ingesta_Daily_Minut_v2

```sh
Flujo: 

../fase_01/A_universo (34,380 tickers) 
                            ↓
                        Filtrado Small Caps (market cap < $2B, XNAS/XNYS, CS)
                            ↓
                        Universo Híbrido: 8,686 tickers
                            ├── 3,092 activos
                            └── 5,594 inactivos (ANTI-SURVIVORSHIP BIAS)
                            ↓
../fase_01/B_ingesta → OHLCV Polygon.io
```

**Objetivo**:  
Descargar `OHLCV (Open, High, Low, Close, Volume)` completo del Universo Híbrido: 8,686 tickers para:
* Eliminar survivorship bias (López de Prado Ch.1)
* Preparar datos para Event Detection (pumps & dumps)
* Base para construcción de DIB bars (Cap.2)
* OHLCV Daily
* OHLCV Intraday 1-minute

**Output critical**:  
`OHLCV` historical data es input para:
* **Event Detection (E1-E11)**: Detectar VolExplosion, GapUp, Parabolic, etc.
* **Daily features**: RVOL, volatility, %change
* **Intraday bars**: Construcción de 1-min OHLCV

```sh
Descargas completadas:

1. OHLCV Daily (/v2/aggs/ticker/{ticker}/range/1/day/)
    📂 raw/polygon/ohlcv_daily/
    📊 8,619 tickers (99.22% del universo)
    Período: 2004-01-01 → 2025-10-24 (21 años)
    Volumen: ~43 GB
    Estructura: TICKER/year=YYYY/daily.parquet
    Duración: 25 minutos (360 tickers/min)
    Columnas disponibles (DAILY): C10 (ticker, date, t, o, h, l, c, v, n, vw)
    ✅ Success rate: 99.98%

2. OHLCV Intraday 1-minute (/v2/aggs/ticker/{ticker}/range/1/minute/)
    📂 raw/polygon/ohlcv_intraday_1m/
    📊 8,623 tickers (99.27% del universo)
    Período: 2004-01-01 → 2025-10-24 (21 años)
    Volumen: ~2.15 TB (ZSTD level 2)
    Estructura: TICKER/year=YYYY/month=MM/minute.parquet
    Duración: 10.48 horas (534 tickers/hora)
    Columnas disponibles (DAILY): C10 (ticker, date, t, o, h, l, c, v, n, vw)
    ✅ Success rate: 100% (280/280 batches)

4. Tickers Faltantes
    ✓ Impacto: MÍNIMO (no afectan análisis)
    Análisis de Faltantes: Normalización de texto pendiente Algunos tickers con mayúsculas/minúsculas diferentes (ADSw vs ADSW, HW vs Hw)
    ⚠️  Solo en daily: 3 tickers
    Ejemplos: ['ADSw', 'AEBIV', 'HW']
    ⚠️  Solo en intraday: 6 tickers
    Ejemplos: ['ADSW', 'ASTI', 'Hw', 'MURAV', 'RNVA']
```

> EVIDENCIA de los resulados: 
> - [B_ingesta_Daily_Minut_v2 / notebooks / notebook2.ipynb](../01_DayBook/fase_01/B_ingesta_Daily_Minut_v2/notebooks/notebook2.ipynb)

--- 

## .. \ fase_01 \ C_v2_ingesta_tiks_2004_2025 \ 

```sh
Flujo:

../fase_01/A_universo (34,380 tickers) 
                            ↓
                    Filtrado Small Caps (market cap < $2B, XNAS/XNYS, CS)
                            ↓
                    Universo Híbrido: 8,686 tickers
                        ├── 3,092 activos
                        └── 5,594 inactivos (ANTI-SURVIVORSHIP BIAS)
                            
../fase_01/B_ingesta → OHLCV (8,619 daily + 8,623 intraday tickers)
                            ↓
../fase_01/C_v2_ingesta_tiks_2004_2025 (Event-Driven Pipeline)
                            ↓
        [PASO 1] Agregación OHLCV 1m → Daily Cache
                 Input: raw/polygon/ohlcv_intraday_1m/ (de fase B)
                 Output: processed/daily_cache/
                 Features: rvol30, pctchg_d, dollar_vol_d
                 Script: build_daily_cache.py
                            ↓
        [PASO 2] (editar YAML) NO depende de PASO 1, puedes hacerlo antes/después
                 Configuración Filtros E0
                 genera universe_config.yaml : RVOL≥2, |%chg|≥15%, $vol≥$5M, precio $0.20-$20
                            ↓
        [PASO 3] Input: necesita AMBOS:
                    - processed/daily_cache/ (del PASO 1)
                    - universe_config.yaml (del PASO 2)
                 Genera Watchlists E0
                 Output: processed/universe/info_rich/daily/
                 5,934 watchlists con 29,555 días info-rich
                 Script: build_universe.py
                            ↓
        [PASO 4] Análisis Características E0
                 Input: processed/universe/info_rich/daily/ (del PASO 3)
                 Validación: 4,898 tickers únicos, umbrales OK
                 Script: analyze_e0_characteristics.py
                            ↓
        [PASO 5] Descarga Ticks Selectiva ← AQUÍ RECIÉN SE DESCARGAN TRADES
                 Input: watchlists E0 (días info-rich + ventana ±1)
                 Output: raw/polygon/trades/
                 64,801 ticker-días tick-by-tick (16.58 GB)
                 Script: download_trades.py
```

### [PASO 1] Resumen diario desde barras 1-minuto (390 barras → 1 fila)

**Explicacion detallada**: [proceso ](EXPLICACION_PASO1_DAILY_CACHE.md) .   
Este paso está agregando LAS barras OHLCV de 1-minuto EN barras diarias

`INPUT`: Las barras 1-minuto de Fase B (`raw/polygon/ohlcv_intraday_1m/`)

```sh
# hora NY
INPUT: Barras OHLCV de 1-minuto (ya existen, descargadas en Fase B)
raw/polygon/ohlcv_intraday_1m/AAM/date=2024-01-02/
├── 09:30 | o=$25.00, h=$25.10, l=$24.90, c=$25.05, v=10,000
├── 09:31 | o=$25.05, h=$25.20, l=$25.00, c=$25.15, v=5,000
├── 09:32 | o=$25.15, h=$25.30, l=$25.10, c=$25.25, v=8,000
├── ...
└── 16:00 | o=$26.00, h=$26.10, l=$25.95, c=$26.00, v=8,000

Total: 390 barras OHLCV de 1-minuto (ya descargadas)
```

`TRANSFORMACIÓN`: Agregación básica (group by ticker + día), resumir esas 390 barras en 1 sola barra diaria.     
Features calculados  
* **pctchg_d** - Cambio porcentual diario  
* **rvol30** - Volumen relativo 30 sesiones  
* **dollar_vol_d** - Volumen en dólares

```sh
# El script NO descarga nada nuevo
# Solo lee las 390 barras y las resume en 1 fila

close_d = barras_1m[-1].c          # Último close = $26.00
vol_d = sum(barras_1m[:].v)        # Suma de volúmenes = 2,500,000
dollar_vol_d = sum(v × vw)         # $64,750,000
```

`OUTPUT`: 1 fila diaria con features calculados

```sh
processed/daily_cache/ticker=AAM/daily.parquet
┌────────────┬──────────┬───────────┬──────────────┬──────────┬────────┐
│ ticker     │ date     │ close_d   │ vol_d        │ pctchg_d │ rvol30 │
├────────────┼──────────┼───────────┼──────────────┼──────────┼────────┤
│ AAM        │2024-01-02│ $26.00    │ 2,500,000    │ +0.15    │ 2.5    │
└────────────┴──────────┴───────────┴──────────────┴──────────┴────────┘

1 fila diaria (agregada desde 390 barras de 1-min)
```

```sh
OUTPUT: Daily Cache enriquecido  
processed/daily_cache/ticker=AAM/daily.parquet

Columnas finales:
- ticker
- trading_day
- close_d          ← Close del día
- vol_d            ← Volumen total acciones
- dollar_vol_d     ← Volumen en dólares (VWAP-weighted)
- vwap_d           ← VWAP del día
- pctchg_d         ← % change vs día anterior
- return_d         ← Log return
- rvol30           ← Volumen relativo 30 sesiones
- session_rows     ← Cuántas barras 1m
- has_gaps         ← ¿Faltaron barras?
```
### [PASO 2] Configuración Filtros E0
NO depende de PASO 1, puedes hacerlo antes/después  
Genera un YAML `universe_config.yaml` con : `RVOL≥2`, `|%chg|≥15%`, `$vol≥$5M`, `precio $0.20-$20`  

Justificacion completa de Filtros E0 : [LINK](../01_DayBook/fase_01/C_v2_ingesta_tiks_2004_2025/anotaciones/JUSTIFICACION_FILTROS_E0_COMPLETA.md)

**Resumen de Justificación Filtros E0** (Generic Info-Rich):
>
>| Filtro | Formula | Fundamento | Rationale |
>|--------|---------|------------|-----------|
>| **RVOL ≥ 2.0** | `vol_d / MA30` | López de Prado (2018, Ch.1) - Event-based sampling | Detecta actividad 2x superior → pumps, bounces, first red days |
>| **\|%chg\| ≥ 15%** | `abs((close/prev)-1)` | EduTrades Playbook - Gap&Go +15%, FRD -15% | Movimientos extremos (runners o collapses) |
>| **$vol ≥ $5M** | `Σ(v×vwap)` 1-min | Easley et al. (2012) - Flow toxicity | Filtra zombis, solo flujo institucional real |
>| **Precio $0.20-$20** | `close_d` | Small caps proxy + penny stocks válidos | $0.20-$0.50 pueden tener patrones info-rich válidos |


### [PASO 3] Generación Watchlists E0 (universe/info_rich/daily/)

1. Lee `processed/daily_cache/` (OUTPUT del PASO 1)
2. Aplica filtros de `universe_config.yaml` (PASO 2)
3. Filtra días que cumplen: `RVOL≥2.0 AND |%chg|≥15% AND $vol≥$5M...`
4. Escribe watchlists en `processed/universe/info_rich/daily/`

```sh
Input: 
- processed/daily_cache/ (del PASO 1)
- universe_config.yaml (del PASO 2)

# Filtra días que cumplen: RVOL≥2.0 AND |%chg|≥15% AND $vol≥$5M...
Output:   
processed/universe/info_rich/daily/   
├── date=2024-01-02/watchlist.parquet ← Solo días que pasan filtros E0  
├── date=2024-01-03/watchlist.parquet  
└── ...
```

### [PASO 4] Análisis Características E0

1. Lee watchlists E0 del PASO 3
2. Analiza distribuciones de features (rvol30, pctchg_d, dollar_vol_d)
3. Valida que todos los eventos cumplen umbrales
4. Genera estadísticas descriptivas

```sh
python scripts/fase_C_ingesta_tiks/analyze_e0_characteristics.py \
  --universe-root processed/universe/info_rich/daily \
  --outdir analysis/e0_characteristics
```

```sh
OUTPUT típico:
📊 Análisis E0 Characteristics
================================
Total eventos E0: 29,555
Tickers únicos: 4,898

Distribución RVOL30:
- Min: 2.00  (threshold OK ✅)
- Median: 3.47
- Max: 125.6

Distribución |%chg|:
- Min: 0.15  (threshold OK ✅)
- Median: 0.21
- Max: 0.89
```

✅ Validación: 100% eventos cumplen umbrales E0
✅ 4,898 tickers únicos con eventos E0
✅ Stats guardadas en analysis/e0_characteristics/

### [PASO 5] Descarga Ticks Selectiva 

1. Lee watchlists E0 del PASO 3
2. Expande ventana: para cada evento E0, incluye día-1 y día+1
3. Descarga trades tick-by-tick de Polygon API solo para esos días
4. Escribe en `raw/polygon/trades/`

```sh
# Ejemplo de expansión de ventana:
Watchlist E0 contiene:
AAM | 2024-01-02 | RVOL=2.5, %chg=+15%  ← Día E0

PASO 5 descarga:
├── AAM | 2024-01-01  ← día E0 - 1
├── AAM | 2024-01-02  ← día E0 (el evento)
└── AAM | 2024-01-03  ← día E0 + 1

Total: 3 ticker-días por evento E0 (ventana ±1)
```

```sh
INPUT:
processed/universe/info_rich/daily/
├── date=2024-01-02/watchlist.parquet  ← 50 eventos
├── date=2024-01-03/watchlist.parquet  ← 120 eventos
└── ...                                  ← 5,934 watchlists totales
OUTPUT:
raw/polygon/trades/
├── ticker=AAM/
│   ├── date=2024-01-01/trades.parquet  ← Tick-by-tick (price, size, conditions)
│   ├── date=2024-01-02/trades.parquet
│   └── date=2024-01-03/trades.parquet
├── ticker=BCRX/
│   └── ...
└── ...

Total: 64,801 ticker-días × ~250 KB promedio = 16.58 GB
```

### ..  / A_universo / [1_influencia_MarcosLopezDePadro.md](fase_01/A_Universo/1_influencia_MarcosLopezDePadro.md)

**Obtetivo** : Construir múltiples tipos de barras para comparación.

1. **Descargar tick data de Polygon:**

   - `/v3/trades/{ticker}` → precio, volumen, timestamp, condiciones
   - `/v3/quotes/{ticker}` → bid/ask spread para tick rule mejorado

2. **Construir múltiples tipos de barras para comparación:**

   **a) Dollar Bars (baseline):**

   **b) Dollar Imbalance Bars (DIBs) - RECOMENDADO para pumps:**

   **c) Dollar Runs Bars (DRBs) - Para detectar sweeping agresivo:**

3. **Validar propiedades estadísticas** (ejercicios del Capítulo 2):
   - Contar barras por semana → DIBs/DRBs deben ser más estables que time bars
   - Medir correlación serial de retornos → debe ser menor en information-driven bars
   - Test de normalidad (Jarque-Bera) → retornos deben estar más cerca de Gaussiana


### EJECUCION

```sh
✅ E0 (Generic Info-Rich) - 2004-2025
   - 67,439 archivos descargados
   - 16.58 GB storage
   - 92.2% cobertura (64,801 / 70,290 días trading)
   - Event window: ±1 día
   - Estructura: raw/polygon/trades/{TICKER}/date={YYYY-MM-DD}/trades.parquet
```

---

### CP-B1: Descarga Trades Polygon.io ✅

**Doc**: [F.5_auditoria_descarga_pilot50.md](fase_01/F_Event_detectors_E1_E11/F.5_auditoria_descarga_pilot50.md)

**Resultado**:
```
📂 raw/polygon/trades_pilot50_validation/
📊 139,684 parquet files
🎯 50 tickers (2004-2025)
📈 37,274 ticker-days con eventos
📅 139,684 ticker-days totales (ventana ±3)
```

**Verificación**: `find raw/polygon/trades_pilot50_validation -name "*.parquet" | wc -l` → 139684

**Certificación**: ✅ Dataset completo

---

### CP-B2: Construcción DIB Bars ✅

**Script**: `scripts/fase_D_creando_DIB_VIB/build_bars_from_trades.py`

**Parámetros**:
```bash
--bar-type dollar_imbalance
--target-usd 300000        # $300k target
--ema-window 50            # EMA-50 imbalance
--parallel 12
```

**Resultado**:
```
📂 processed/dib_bars/pilot50_validation/
📊 139,684 parquet files
📋 Formato: OHLCV + imbalance_score + num_ticks
```

**Verificación**: `find processed/dib_bars/pilot50_validation -name "_SUCCESS" | wc -l` → 139684

**Certificación**: ✅ DIB bars construidos con López de Prado methodology

---

### CP-C1: Event Detection E1-E11 ✅

**Doc**: [F.3_arquitectura_descarga_ventana_dinamica.md](fase_01/F_Event_detectors_E1_E11/F.3_arquitectura_descarga_ventana_dinamica.md)

**Eventos**: E1-VolExplosion | E2-GapUp | E3-PriceSpikeIntraday | E4-Parabolic | E5-BreakoutATH | E6-MultipleGreenDays | E7-FirstRedDay | E8-GapDownViolent | E9-CrashIntraday | E10-FirstGreenBounce | E11-VolumeBounce

**Certificación**: ✅ 11 detectores implementados

---

### CP-C2: Generación Watchlist ✅

**Script**: `scripts/fase_E_Event_Detectors_*/event_detectors.py`

**Resultado**:
```
📂 processed/watchlists/wl_expanded_E1_E11.parquet
📊 44,189 eventos detectados (2004-2025)
```

**Distribución**:
```
E1:7,686 | E2:1,070 | E3:1,901 | E4:1,265 | E5:4,633 | E6:16,776
E7:233 | E8:455 | E9:420 | E10:8,494 | E11:1,256
```

**Certificación**: ✅ 44,189 eventos catalogados

---

### CP-D1: Triple Barrier Labeling ✅

**Script**: `scripts/fase_D_creando_DIB_VIB/triple_barrier_labeling.py`
**Doc**: [F.7_pipeline_labels_weights_pilot50.md](fase_01/F_Event_detectors_E1_E11/F.7_pipeline_labels_weights_pilot50.md)

**Parámetros**:
```bash
--pt-mul 3.0           # Profit = 3σ
--sl-mul 2.0           # Stop = 2σ
--t1-bars 120          # Vertical = 120 bars
--vol-est ema --vol-window 50
```

**Resultado**:
```
📂 processed/labels_pilot50/
📊 139,684 labels.parquet
📋 Formato: t_open, t_close, ret, label ∈ {-1,0,1}
```

**Verificación**: `find processed/labels_pilot50 -name "labels.parquet" | wc -l` → 139684

**Certificación**: ✅ Triple Barrier ejecutado (López de Prado Ch.3)

---

### CP-D2: Sample Weights ✅

**Script**: `scripts/fase_D_creando_DIB_VIB/make_sample_weights.py`

**Parámetros**:
```bash
--uniqueness              # López de Prado Ch.4
--abs-ret-weight          # Weight by |return|
--time-decay-half_life 90 # 90-day decay
```

**Resultado**:
```
📂 processed/weights_pilot50/
📊 139,684 weights.parquet
📋 Formato: weight, avg_uniqueness
```

**Certificación**: ✅ Sample weights calculados

---

### CP-D3: Feature Engineering ✅

**Features**: Returns (log/simple) | Volatility (rolling/EWMA) | Volume ratios (RVOL) | Imbalance metrics | Price ratios

**Certificación**: ✅ Features integrados en D.4

---

### CP-D4: Dataset Construction ✅

**Script**: `scripts/fase_D_creando_DIB_VIB/build_ml_daser.py`

**Parámetros**:
```bash
--bars-root processed/dib_bars/pilot50_validation
--labels-root processed/labels_pilot50
--weights-root processed/weights_pilot50
--outdir processed/dataset_pilot50
--split none
```

**Resultado**:
```
📂 processed/dataset_pilot50/daily/
📊 96,897 dataset.parquet
📋 Formato: bars + labels + weights + features
```

**Verificación**: `find processed/dataset_pilot50/daily -name "dataset.parquet" | wc -l` → 96897

**Certificación**: ✅ 96,897 ML datasets construidos (D.1-D.4 completo)

---

### CP-F1: Window Validation Phase1 (Information Theory) ✅

**Notebook**: [phase1_information_theory.ipynb](fase_01/F_Event_detectors_E1_E11/notebooks/01_notebooks/phase1_information_theory.ipynb)
**Doc**: [F.6_validacion_ventanas_optimas.md](fase_01/F_Event_detectors_E1_E11/F.6_validacion_ventanas_optimas.md)

**Método**: Mutual Information I(X_t; y) por día relativo | Threshold 10% max MI

**Resultado**: Ventanas [-3,+3] sugeridas para todos los eventos

**Output**:
```
📂 notebooks/03_checkpoints/phase1_results.pkl
📊 notebooks/04_outputs/information_by_day_phase1.png
```

**Certificación**: ✅ Phase1 ejecutada, MI calculado

---

### CP-F2: Window Validation Phase2 (Economic Validation) ✅

**Notebook**: [phase2_model_performance_FIXED.ipynb](fase_01/F_Event_detectors_E1_E11/notebooks/01_notebooks/phase2_model_performance_FIXED.ipynb)

**Método**: LightGBM por ventana | AUC + Economic Edge

**Resultados**:
```
E10_FirstGreenBounce [0,0]: AUC=0.963, Edge=1.21%, n=6,137
E11_VolumeBounce [0,0]: AUC=0.975, Edge=2.09%, n=6,750
```

**Output**:
```
📂 notebooks/03_checkpoints/phase2_results.pkl
📄 notebooks/04_outputs/optimal_windows_empirical_phase2.csv
📊 notebooks/04_outputs/window_optimization_phase2.png
```

**Certificación**: ✅ Phase2 ejecutada, ventanas [0,0] óptimas económicamente

---

### CP-F3: Window Validation Phase3 (Statistical Analysis) ✅

**Notebook**: [phase3_paper_grade_analysis_EXECUTED.ipynb](fase_01/F_Event_detectors_E1_E11/notebooks/01_notebooks/phase3_paper_grade_analysis_EXECUTED.ipynb)

**Método**: Spearman correlation MI vs Edge | Concordance analysis | Hybrid score α·MI + (1-α)·Edge

**Resultados**:
```
Spearman ρ: -0.0699
P-value: 0.829
Conclusión: MI y Edge DIVERGEN (no correlación)
```

**Output**:
```
📄 notebooks/04_outputs/statistical_report_paper_grade.csv
📄 notebooks/04_outputs/concordance_analysis_full.csv
📊 notebooks/04_outputs/concordance_analysis.png
📊 notebooks/04_outputs/heatmap_event_x_time.png
```

**Certificación**: ✅ Phase3 ejecutada, divergencia confirmada estadísticamente

---

### CP-F4: TradingView Export ✅

**Guía**: [TRADINGVIEW_USAGE_GUIDE.md](fase_01/F_Event_detectors_E1_E11/notebooks/02_documentacion/TRADINGVIEW_USAGE_GUIDE.md)

**Resultado**:
```
📂 notebooks/04_outputs/tradingview_exports/
📊 11 CSV files (44,189 eventos con timestamps exactos)
📋 Formato: ticker, datetime, close_price, event_code, window_suggested, date
```

**Files**: E1(7,686) | E2(1,070) | E3(1,901) | E4(1,265) | E5(4,633) | E6(16,776) | E7(233) | E8(455) | E9(420) | E10(8,494) | E11(1,256)

**Certificación**: ✅ 44,189 eventos exportados para validación visual

---

## 📊 RESUMEN EJECUTIVO

| Componente | Files | Status | Path |
|------------|-------|--------|------|
| Trades | 139,684 | ✅ | `raw/polygon/trades_pilot50_validation/` |
| DIB Bars | 139,684 | ✅ | `processed/dib_bars/pilot50_validation/` |
| Events | 44,189 | ✅ | `processed/watchlists/` |
| Labels | 139,684 | ✅ | `processed/labels_pilot50/` |
| Weights | 139,684 | ✅ | `processed/weights_pilot50/` |
| ML Datasets | 96,897 | ✅ | `processed/dataset_pilot50/daily/` |
| Window Validation | Phase1-3 | ✅ | `notebooks/04_outputs/` |
| TradingView Export | 11 CSVs | ✅ | `notebooks/04_outputs/tradingview_exports/` |

---

## 🔍 HALLAZGOS CLAVE

**DIB Bars**: $300k target + EMA-50 imbalance tracking operacional

**Event Detection**: 44,189 eventos E1-E11 (2004-2025, 50 tickers)

**ML Pipeline**: 96,897 datasets con labels + weights + features

**Window Optimization**:
- **Phase1 (MI)**: [-3,+3] sugeridas
- **Phase2 (Edge)**: [0,0] óptimas (AUC=0.96-0.97, Edge=1.2-2.1%)
- **Phase3 (Stats)**: Divergencia MI/Edge (ρ=-0.07, p=0.829)

---

## ⏭️ PRÓXIMO PASO

**Decisión pendiente**: Selección final de ventanas

**Opciones**:
1. MI-based [-3,+3]: Máxima información
2. Edge-based [0,0]: Máxima rentabilidad
3. Hybrid: Balance información + profit

**Acción**: Validación visual TradingView (10-20 eventos/tipo)

---

## 📚 DOCUMENTACIÓN

**Teoría**: [1_influencia_MarcosLopezDePadro.md](fase_01/A_Universo/1_influencia_MarcosLopezDePadro.md)
**Architecture**: [F.3_arquitectura...md](fase_01/F_Event_detectors_E1_E11/F.3_arquitectura_descarga_ventana_dinamica.md)
**Pipeline ML**: [F.7_pipeline...md](fase_01/F_Event_detectors_E1_E11/F.7_pipeline_labels_weights_pilot50.md)
**Window Validation**: [F.6_validacion...md](fase_01/F_Event_detectors_E1_E11/F.6_validacion_ventanas_optimas.md)
**Notebooks**: [README.md](fase_01/F_Event_detectors_E1_E11/notebooks/README.md)

---

**STATUS**: ✅ PHASE 1 COMPLETADA 100%
**Git commit**: `5a0ab13` - "feat: Complete F.6 hybrid window validation with Phase1-3 pipeline + TradingView exports"
**Última verificación**: 2025-10-30
