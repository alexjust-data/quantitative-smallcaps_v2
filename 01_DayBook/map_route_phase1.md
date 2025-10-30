# Validation Pipeline - Checkpoint Map
Certifica la ejecución completa del proyecto desde su inicio, que certifique cada paso completado con evidencia tangible + links a documentación detallada.  
**Última actualización**: 2025-10-30  

* Universo y fundamento teorico
    * [Eventos, la fase del ciclo pump & dump:](#eventos-a--fase-del-ciclo-pump--dump)
    * [Ventanas temporales de estos eventos](#ventanas-temporales-de-estos-eventos)
* Pipeline
    * [fase_01/A_universo](#--fase_01--a_universo)
    * [fase_01/B_ingesta_Daily_Minut_v2](#--fase_01--b_ingesta_daily_minut_v2)

**OBJETIVO de este pipeline**  
Descargar datos tick-by-tick (trades) de Polygon API, `SOLO para ventanas temporales donde ocurren eventos clave` detectables en el universo hibrido (8,686 tickers, 21 anos, 3,092 tikers activos y 5,594 inactivos). NO necesitamos ticks de TODO el historico (2004-2025): Solo necesitamos ticks de periodos con `actividad informativa relevante = eventos de pump & dump`. Estos eventos marcan las ventanas temporales criticas para descargar ticks.

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


## EVENTOS a : fase del ciclo pump & dump:

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

## VENTANAS temporales de estos eventos

Para cada evento detectado, descargar ticks en ventana

* E0 -> +1 -1

---

# Pipeline

## fase_01 / A_universo 

**Descargas:**

**Reference Universe**: 34,380 tickers (11,853 activos + 22,527 inactivos)

```sh
1. Reference Universe (/v3/reference/tickers)
    📂 raw/polygon/reference/tickers_snapshot/
    📊 34,380 tickers totales (snapshot 2025-10-24)
    ├── 11,853 activos
    └── 22,527 inactivos (anti-survivorship bias)
    📄 Files: tickers_all.parquet, tickers_active.parquet, tickers_inactive.parquet
```
**Splits**: 26,641 splits históricos (31 archivos parquet)
```sh
2. Splits (/v3/reference/splits)
    📂 raw/polygon/reference/splits/
    📊 26,641 splits históricos
    📄 31 archivos parquet (particionado)
```

**Dividends**: 1,878,357 dividendos (31 archivos parquet)
```sh
3. Dividends (/v3/reference/dividends)
    📂 raw/polygon/reference/dividends/
    📊 1,878,357 dividendos históricos
    📄 31 archivos parquet (particionado)
```

⚠️  **Ticker Details**: INCOMPLETO (<1% completitud)
```sh
4. Ticker Details (/v3/reference/tickers/{ticker})
    📂 raw/polygon/reference/ticker_details/
    📄 2 archivos parquet (enriquecimiento parcial)
    ⚠️  INCOMPLETO - Solo sample ejecutado
```

---

> **EVIDENCIA de los resultados**: [A_Universo / notebooks / notebook2.ipynb](../01_DayBook/fase_01/A_Universo/notebooks/notebook2.ipynb)  

---  

## fase_01 / B_ingesta_Daily_Minut_v2

```sh
hemos hecho :

../fase_01/A_universo (34,380 tickers) 
                            ↓
                        Filtrado Small Caps (market cap < $2B, XNAS/XNYS, CS)
                            ↓
                        Universo Híbrido: 8,686 tickers
                            ├── 3,092 activos
                            └── 5,594 inactivos (ANTI-SURVIVORSHIP BIAS)
                            ↓
ahora toca :

../fase_01/B_ingesta → OHLCV Polygon.io
```

**Objetivo**:  

Descargar `OHLCV (Open, High, Low, Close, Volume)` completo del Universo Híbrido: 8,686 tickers para:

* Eliminar survivorship bias (López de Prado Ch.1)  
* Preparar datos para Event Detection (pumps & dumps)  
* Base para construcción de DIB bars (Cap.2)  
* OHLCV Daily  
* OHLCV Intraday 1-minute  


```sh
# ¿que es OHLCV?
O = $175.20  ← Primer trade del minuto
H = $175.85  ← Máximo alcanzado
L = $175.10  ← Mínimo alcanzado  
C = $175.60  ← Último trade del minuto
V = 45,230   ← Total shares intercambiadas
```

**Output critical**:  `OHLCV` historical data es input para:
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

> EVIDENCIA de los resulados: [B_ingesta_Daily_Minut_v2 / notebooks / notebook2.ipynb](../01_DayBook/fase_01/B_ingesta_Daily_Minut_v2/notebooks/notebook2.ipynb)

--- 

## fase_01 \ C_v2_ingesta_tiks_2004_2025 \ 

```sh
hemos hecho :

../fase_01/A_universo (34,380 tickers) 
                            ↓
                    Filtrado Small Caps (market cap < $2B, XNAS/XNYS, CS)
                            ↓
                    Universo Híbrido: 8,686 tickers
                        ├── 3,092 activos
                        └── 5,594 inactivos (ANTI-SURVIVORSHIP BIAS)
                            
../fase_01/B_ingesta → OHLCV (8,619 daily + 8,623 intraday tickers)
                            ↓

ahora toca :

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

**Explicacion detallada**: [proceso [PASO 1]](EXPLICACION_PASO1_DAILY_CACHE.md) .  Este paso está agregando LAS barras OHLCV de 1-minuto EN barras diarias

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
Justificacion completa del porqué de los Filtros E0 : [LINK](../01_DayBook/fase_01/C_v2_ingesta_tiks_2004_2025/anotaciones/JUSTIFICACION_FILTROS_E0_COMPLETA.md)

PASO 2 NO depende de PASO 1, puedes hacerlo antes/después.  
Genera un YAML `universe_config.yaml` con :   
`RVOL≥2`, `|%chg|≥15%`, `$vol≥$5M`, `precio $0.20-$20`  


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
> EVIDENCIA de resulados: [[PASO 3] Generación Watchlists E0](../01_DayBook/fase_01/C_v2_ingesta_tiks_2004_2025/notebooks/analysis_paso3_executed.ipynb)

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

> EVIDENCIA de resulados: 
> [PASO 4 (Análisis Características)](../01_DayBook/fase_01/C_v2_ingesta_tiks_2004_2025/notebooks/analysis_paso4_executed.ipynb)
> [PASO 4 (validación adicional)](../01_DayBook/fase_01/C_v2_ingesta_tiks_2004_2025/notebooks/analysis_caracteristicas_paso4.ipynb)


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
└── ...                                ← 5,934 watchlists totales
```

```sh
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
> EVIDENCIA de resulados: 
>* [PASO 5 (Descarga Ticks)](../01_DayBook/fase_01/C_v2_ingesta_tiks_2004_2025/notebooks/analysis_paso5_executed.ipynb)  
>* [PASO 5 (validación adicional)](../01_DayBook/fase_01/C_v2_ingesta_tiks_2004_2025/notebooks/analysis_paso5_executed_2.ipynb)  
>* [Visualizaciones globales](../01_DayBook/fase_01/C_v2_ingesta_tiks_2004_2025/notebooks/analysis_estadisticas_visuales_executed.ipynb)  


## Estudio datos E0 en mercado

> ---  
>**Analisis profundo de eventos E0** : [**Link**](../01_DayBook/fase_01/C_v2_ingesta_tiks_2004_2025/notebooks/ANALISIS_PROFUNDO_EVENTOS_E0_FIXED.ipynb)  
> * Analiza trades tick-by-tick y encuentra la hora exacta del trigger E0
> * ¿cuándo ocurren los eventos?
> ---  

---


## fase_01 \ D_creando_DIB_VIB_2004_2025
```sh
hemos hecho :

../fase_01/A_universo (34,380 tickers) 
                            ↓
                    Filtrado Small Caps (market cap < $2B, XNAS/XNYS, CS)
                    Universo Híbrido: 8,686 tickers
                        ├── 3,092 activos
                        └── 5,594 inactivos (ANTI-SURVIVORSHIP BIAS)
                            
../fase_01/B_ingesta → OHLCV (8,619 daily + 8,623 intraday tickers)
                            ↓
../fase_01/C_v2_ingesta_tiks_2004_2025 (Event-Driven Pipeline)
        [PASO 1] 
        [PASO 2] 
        [PASO 3] 
        [PASO 4] 
        [PASO 5] Descarga Ticks Selectiva con eventos E0 (+1 / -1 día)
                            ↓
                OUTPUT:
                raw/polygon/trades/
                ├── ticker=AAM/
                │   ├── date=2024-01-01/trades.parquet  ← Tick-by-tick (price, size, conditions)
                │   ├── date=2024-01-02/trades.parquet
                │   └── date=2024-01-03/trades.parquet
                ├── ticker=BCRX/
                │   └── ...
                └── ...

                            ↓

ahora toca :

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

**Objetivo**:  

* Construir barras informacionales (Dollar Imbalance Bars) desde tick data, 
* aplicar Triple Barrier Labeling, 
* calcular Sample Weights con unicidad temporal, 
* y generar ML Dataset walk-forward listo para entrenamiento supervisado.   

**Cobertura**: 
* 2004-2025 (21 años), 4,874 tickers, 64,801 días únicos  

**Resultado final**: 

* 4.36M eventos ML-ready con 14 features intraday + labels + weights.  

### fase_01 / D_creando_DIB_VIB_2004_2025

---

#### [D.1] Dollar Imbalance Bars (DIB)

>**Explicación detallada**:
>- [D.0_Constructor_barras_Dollar_Vol_Imbalance.md](./D.0_Constructor_barras_Dollar_Vol_Imbalance.md)
>- [D.1.1_notas_6.1_DIB.md](./D.1.1_notas_6.1_DIB.md) - Parámetros target-usd y ema-window
>
>**Script**: `scripts/fase_D_creando_DIB_VIB/build_bars_from_trades.py`

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

- Parámetros clave:
    - `--target-usd 300000`: $300k por barra (~1-2% volumen diario small cap)
    - `--ema-window 50`: Suavización adaptativa del umbral (memoria ~sesión completa)
    - `--parallel 8`: Workers concurrentes

`OUTPUT`:
- `processed/bars/{ticker}/date={YYYY-MM-DD}/dollar_imbalance.parquet`
- **64,801 archivos** (100% completitud)
- Schema: `{t_open, t_close, o, h, l, c, v, n, dollar, imbalance_score}`
- Promedio: ~57 barras/día, ~190 KB/archivo

> ---
>   ...  
> EVIDENCIA de resultados:   
> [D.1_Ejecucion_Pipeline_DIB_Labels_Weights.md](./D.1_Ejecucion_Pipeline_DIB_Labels_Weights.md#1-dollar-imbalance-bars-dib)  
> ...  


#### [D.2] Triple Barrier Labeling

---

**Explicación detallada**: [D.1.2_notas_6.1_tripleBarrierLabeling.md](./D.1.2_notas_6.1_tripleBarrierLabeling.md)  
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

* Parámetros clave:
    - `--pt-mul 3.0`: Profit target = 3 × σ (significancia estadística)
    - `--sl-mul 2.0`: Stop loss = 2 × σ (asimétrico, stop más cercano)
    - `--t1-bars 120`: Vertical barrier ~2-3 horas trading
    - `--vol-est ema --vol-window 50`: Estimación volatilidad adaptativa

`OUTPUT`:
- `processed/labels/{ticker}/date={YYYY-MM-DD}/labels.parquet`
- **64,800 archivos** (99.998% completitud, 1 archivo faltante)
- Schema: `{anchor_ts, t1, pt_hit, sl_hit, label, ret_at_outcome, vol_at_anchor}`



> ---  
> EVIDENCIA de resultados: [D.1_Ejecucion_Pipeline_DIB_Labels_Weights.md](./D.1_Ejecucion_Pipeline_DIB_Labels_Weights.md#2-triple-barrier-labeling)  
> ...
---

#### [D.3] Sample Weights (Uniqueness + Magnitude + Time-Decay)

---

**Explicación detallada**: [D.1.3_notas_6.1_SampleWeights.md](./D.1.3_notas_6.1_SampleWeights.md)  
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

* Parámetros clave:
    - `--uniqueness`: Ajusta por concurrency (evita overfit a racimos temporales)
    - `--abs-ret-weight`: Peso base = |ret| (prioriza eventos significativos)
    - `--time-decay-half_life 90`: Semivida 90 días (hook preparado para cross-day)

`OUTPUT`:
- `processed/weights/{ticker}/date={YYYY-MM-DD}/weights.parquet`
- **64,801 archivos** (100% completitud)
- Schema: `{anchor_ts, weight}`



> --- 
> EVIDENCIA de resultados: [D.1_Ejecucion_Pipeline_DIB_Labels_Weights.md](./D.1_Ejecucion_Pipeline_DIB_Labels_Weights.md#3-sample-weights-unicidad--retorno--time-decay)  
> ...    

---

#### [D.4] ML Dataset Builder (Features + Walk-Forward Split)

---


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

* Parámetros clave:
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

> ---  
> EVIDENCIA de resultados: [D.1_Ejecucion_Pipeline_DIB_Labels_Weights.md](./D.1_Ejecucion_Pipeline_DIB_Labels_Weights.md#4-ml-dataset-builder-bonus)  
> ...  


---

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



---


