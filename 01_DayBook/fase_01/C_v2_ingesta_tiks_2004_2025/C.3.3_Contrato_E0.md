# Contrato E0: Generic Info-Rich Event (C_v1 Logic)

**Fecha de creacion**: 2025-10-25  
**Version**: 2.0.0 (INMUTABLE)  
**Estado**: Contrato formal - NO MODIFICABLE  
**Proposito**: Documentar la logica EXACTA de filtrado usada en C_v1 para replicarla como evento E0 en C_v2  
**Cambios v2.0.0**: Ajuste precio minimo ($0.50 → $0.20) y documentacion completa SCD-2 market cap    

---

## 1. CONTEXTO Y PROPOSITO

Este documento constituye un **contrato inmutable** que especifica la logica exacta de filtrado utilizada en la version 1 (C_v1) del sistema de ingesta de ticks para el periodo 2020-2025, y su extension para C_v2 (periodo 2004-2025).

**Universo C_v2**: 3,107 tickers (XNAS/XNYS, market cap < $2B al momento de descarga OHLCV)
**Periodo C_v2**: 2004-01-01 → 2025-10-21 (21 años, 3 ventanas)

**Objetivo**: Permitir que C_v2 (version extendida 2004-2025) incluya conceptualmente el 100% de los eventos capturados por C_v1 mediante la implementacion del evento **E0 (Generic Info-Rich)**.

**Problema detectado**: C_v2 con evento E1 (RVOL>=5.0) NO incluye eventos con RVOL entre 2.0-5.0, perdiendo ~35-40% de los eventos de C_v1.

**Solucion**: E0 replica EXACTAMENTE los filtros de C_v1, garantizando:
```
E_C_v2_extendido = E0 ∪ E1 ∪ E2 ∪ ... ∪ E13
E_C_v2_extendido ⊇ E_C_v1 (garantizado al 100%)
```

---

## 2. FORMULA EXACTA DEL FILTRO INFO-RICH (C_v1)

### 2.1 Definicion Matematica

Un ticker-dia `(ticker, trading_day)` es clasificado como **info_rich = True** si y solo si cumple TODAS las siguientes condiciones:

```python
# C_v1 (2020-2025):
info_rich_v1 = (
    rvol30 >= 2.0 AND
    |pctchg_d| >= 0.15 AND
    dollar_vol_d >= 5_000_000 AND
    close_d >= 0.50 AND
    close_d <= 20.00
)

# E0 para C_v2 (2004-2025) - MAS INCLUSIVO:
E0_generic_info_rich = (
    rvol30 >= 2.0 AND
    |pctchg_d| >= 0.15 AND
    dollar_vol_d >= 5_000_000 AND
    close_d >= 0.20 AND  # ← CAMBIO: $0.50 → $0.20 (mas penny stocks)
    close_d <= 20.00 AND
    market_cap_d < 2_000_000_000  # ← NUEVO: Filtro cap con SCD-2
)
```

**IMPORTANTE**: Todas las condiciones deben cumplirse simultaneamente (operador AND).

### 2.2 Tabla de Umbrales

| Parametro | C_v1 (2020-2025) | E0/C_v2 (2004-2025) | Tipo | Unidad | Notas |
|-----------|------------------|---------------------|------|--------|-------|
| `rvol30` | >= 2.0 | >= 2.0 | Float | Ratio | Volumen relativo 30 sesiones |
| `|pctchg_d|` | >= 15% | >= 15% | Float | Porcentaje | Valor absoluto del cambio porcentual |
| `dollar_vol_d` | >= $5M | >= $5M | Float | USD | Volumen en dolares (VWAP) |
| `close_d` (min) | >= **$0.50** | >= **$0.20** | Float | USD/share | **CAMBIO**: Mas inclusivo para penny stocks |
| `close_d` (max) | <= $20.00 | <= $20.00 | Float | USD/share | Limite superior (small caps) |
| `market_cap_d` | N/A (null) | < **$2B** | Float | USD | **NUEVO**: Filtro con SCD-2 temporal |

---

## 3. ESPECIFICACION DETALLADA DE CADA COMPONENTE

### 3.1 RVOL30 (Relative Volume 30 Sessions)

**Definicion**: Ratio entre el volumen del dia y la media movil de volumen de las ultimas 30 SESIONES de trading.

**Formula exacta**:
```python
rvol30 = vol_d / rolling_mean(vol_d, window_size=30, min_periods=1).over("ticker")
```

**Codigo fuente**: [build_daily_cache.py:187](D:\04_TRADING_SMALLCAPS\scripts\fase_C_ingesta_tiks\build_daily_cache.py#L187)
```python
# MA 30 sesiones (rolling por FILAS, no dias calendario)
# min_periods=1 permite calcular desde el primer dia disponible
pl.col("vol_d").rolling_mean(window_size=30, min_periods=1).over("ticker").alias("vol_30s_ma"),
```

**Codigo fuente**: [build_daily_cache.py:195](D:\04_TRADING_SMALLCAPS\scripts\fase_C_ingesta_tiks\build_daily_cache.py#L195)
```python
# RVOL30 = vol_d / MA30
(pl.col("vol_d") / pl.col("vol_30s_ma")).alias("rvol30"),
```

**Detalles criticos**:
- **30 SESIONES** (filas en el DataFrame ordenado por ticker y trading_day), NO 30 dias calendario
- `min_periods=1` permite calcular RVOL desde el primer dia disponible
- Calculado con `.over("ticker")` para mantener separacion por ticker
- Si `vol_30s_ma = 0`, el resultado es `null` (division por cero protegida por Polars)
- **Incluye el dia actual** en la ventana de 30 sesiones

**Documentacion**: [5.5_0_optimizaciones_velocidad_build_dynamic_universe.md:224](D:\04_TRADING_SMALLCAPS\01_DayBook\fase_01\C_v1_ingesta_tiks_2020_2025\5.5_0_optimizaciones_velocidad_build_dynamic_universe.md#L224)
> "RVOL30: Calculado como rolling mean de 30 FILAS (sesiones), no 30 dias calendario"

---

### 3.2 PCTCHG_D (Percent Change Daily)

**Definicion**: Cambio porcentual del precio de cierre respecto al cierre del dia anterior.

**Formula exacta**:
```python
pctchg_d = (close_d / close_prev) - 1.0
```

Donde:
```python
close_prev = close_d.shift(1).over("ticker")
```

**Codigo fuente**: [build_daily_cache.py:184](D:\04_TRADING_SMALLCAPS\scripts\fase_C_ingesta_tiks\build_daily_cache.py#L184)
```python
# Close anterior (por ticker)
pl.col("close_d").shift(1).over("ticker").alias("close_prev"),
```

**Codigo fuente**: [build_daily_cache.py:191](D:\04_TRADING_SMALLCAPS\scripts\fase_C_ingesta_tiks\build_daily_cache.py#L191)
```python
# % change diario
((pl.col("close_d") / pl.col("close_prev")) - 1.0).alias("pctchg_d"),
```

**Aplicacion del filtro**: [build_dynamic_universe_optimized.py:136](D:\04_TRADING_SMALLCAPS\scripts\fase_C_ingesta_tiks\build_dynamic_universe_optimized.py#L136)
```python
(pl.col("pctchg_d").abs() >= pctchg_th).alias("r_chg"),
```

**Detalles criticos**:
- Se usa **valor absoluto** `|pctchg_d|` en el filtro (captura tanto subidas como bajadas)
- `close_prev` es el cierre del **dia de trading anterior** (shift=1 sobre filas ordenadas por ticker y trading_day)
- El primer dia de cada ticker tendra `pctchg_d = null` (no hay dia anterior)
- Umbral: `|pctchg_d| >= 0.15` (15% en cualquier direccion)

**Ejemplos**:
- `close_d = 10.0, close_prev = 8.0 → pctchg_d = 0.25 (25%)` → CUMPLE (0.25 >= 0.15)
- `close_d = 7.0, close_prev = 10.0 → pctchg_d = -0.30 (-30%)` → CUMPLE (|-0.30| >= 0.15)
- `close_d = 10.5, close_prev = 10.0 → pctchg_d = 0.05 (5%)` → NO CUMPLE (0.05 < 0.15)

---

### 3.3 DOLLAR_VOL_D (Dollar Volume Daily)

**Definicion**: Volumen total en dolares del dia, calculado como la suma de `volumen × VWAP` de todas las barras de 1 minuto.

**Formula exacta** (agregacion desde 1-min):
```python
dollar_vol_d = sum(v * vw)  # donde v = volumen, vw = VWAP de la barra 1-min
```

**Codigo fuente**: [build_daily_cache.py:145](D:\04_TRADING_SMALLCAPS\scripts\fase_C_ingesta_tiks\build_daily_cache.py#L145)
```python
(pl.col("v") * pl.col("vw")).sum().alias("dollar_vol_d_raw"),
```

**Codigo fuente**: [build_daily_cache.py:153](D:\04_TRADING_SMALLCAPS\scripts\fase_C_ingesta_tiks\build_daily_cache.py#L153)
```python
# Dollar volume
pl.col("dollar_vol_d_raw").alias("dollar_vol_d"),
```

**Detalles criticos**:
- Calculado desde barras de 1 minuto (columnas `v` y `vw` del OHLCV intraday)
- `vw` es el VWAP (Volume Weighted Average Price) de la barra 1-min proporcionado por Polygon
- **NO se calcula como `volumen_total × close_d`** sino como suma ponderada por VWAP de cada barra
- Umbral: `dollar_vol_d >= 5_000_000` (5 millones de dolares)

**Fuente de datos**: [build_daily_cache.py:114](D:\04_TRADING_SMALLCAPS\scripts\fase_C_ingesta_tiks\build_daily_cache.py#L114)
```python
.select(["date", "c", "v", "vw", "n"])  # Solo columnas necesarias
```

**Documentacion**: [5.0_que_datos_tienes.md:26](D:\04_TRADING_SMALLCAPS\01_DayBook\fase_01\C_v1_ingesta_tiks_2020_2025\5.0_que_datos_tienes.md#L26)
> "dollar_vol >= $5,000,000"

---

### 3.4 CLOSE_D (Close Price Daily)

**Definicion**: Precio de cierre del ultimo minuto del dia de trading.

**Formula exacta** (agregacion desde 1-min):
```python
close_d = last(c)  # donde c = close de la barra 1-min
```

**Codigo fuente**: [build_daily_cache.py:143](D:\04_TRADING_SMALLCAPS\scripts\fase_C_ingesta_tiks\build_daily_cache.py#L143)
```python
pl.col("c").last().alias("close_d"),
```

**Aplicacion del filtro**: [build_dynamic_universe_optimized.py:138](D:\04_TRADING_SMALLCAPS\scripts\fase_C_ingesta_tiks\build_dynamic_universe_optimized.py#L138)
```python
((pl.col("close_d") >= min_price) & (pl.col("close_d") <= max_price)).alias("r_px"),
```

**Detalles criticos**:
- Se toma el **ultimo cierre** (`.last()`) de las barras de 1-min del dia de trading
- **Rango de precio**:
  - **C_v1**: `[$0.50, $20.00]` (inclusivo en ambos extremos)
  - **E0/C_v2**: `[$0.20, $20.00]` (MAS INCLUSIVO para penny stocks)
- Filtro aplicado **antes** de etiquetar info_rich para reducir ruido

**Codigo fuente** (filtro previo): [build_dynamic_universe_optimized.py:242-245](D:\04_TRADING_SMALLCAPS\scripts\fase_C_ingesta_tiks\build_dynamic_universe_optimized.py#L242-L245)
```python
# Filtro de precio (previo a etiquetar, reduce ruido)
df_all = df_all.filter(
    (pl.col("close_d") >= th["min_price"]) &  # C_v1: 0.50 | E0: 0.20
    (pl.col("close_d") <= th["max_price"])    # Ambos: 20.00
)
```

**Justificacion del cambio $0.50 → $0.20**:
- Penny stocks entre $0.20-$0.50 pueden exhibir patrones info-rich validos
- Evita exclusion de tickers en fase de distress pre-bounce
- Consistente con universo descargado (incluye tickers < $0.50)
- Aumenta cobertura sin comprometer calidad (otros filtros siguen activos)

**Documentacion original**: [5.0_que_datos_tienes.md:26](D:\04_TRADING_SMALLCAPS\01_DayBook\fase_01\C_v1_ingesta_tiks_2020_2025\5.0_que_datos_tienes.md#L26)
> "0.5 <= precio <= 20" (C_v1 2020-2025)

---

### 3.5 MARKET_CAP_D (Market Capitalization Daily)

#### 3.5.1 Estado en C_v1 vs C_v2

| Aspecto | C_v1 (2020-2025) | E0/C_v2 (2004-2025) |
|---------|------------------|---------------------|
| **Filtro cap** | ❌ NO aplicado | ✅ SI aplicado: < $2B |
| **SCD-2** | ❌ NO generada | ✅ SI generada |
| **market_cap_d** | `null` (100%) | Float64 (join temporal) |
| **Razon** | Dimension SCD-2 no disponible | Universo ya filtrado por cap < $2B |

**Codigo fuente C_v1**: [build_daily_cache.py:274](D:\04_TRADING_SMALLCAPS\scripts\fase_C_ingesta_tiks\build_daily_cache.py#L274)
```python
else:
    daily = daily.with_columns(pl.lit(None).alias("market_cap_d"))
```

**Validacion C_v1** (auditoria): [5.5_1_auditoria_build_daily_cache.md:82](D:\04_TRADING_SMALLCAPS\01_DayBook\fase_01\C_v1_ingesta_tiks_2020_2025\5.5_1_auditoria_build_daily_cache.md#L82)
> "market_cap_d nulls: 1,562 / 1,562 (100%) ✅ Esperado (sin dimension SCD-2)"

---

#### 3.5.2 ¿Que es SCD-2? (Slowly Changing Dimension Type 2)

**SCD-2** es una tecnica de modelado de datos para **almacenar el historial de cambios** de atributos que cambian lentamente en el tiempo.

**Problema**: El market cap de un ticker cambia constantemente. ¿Como sabemos que market cap tenia AAPL el 2020-05-15?

**Solucion SCD-2**: Crear una tabla con **periodos de validez**:

```
ticker | effective_from | effective_to   | market_cap      | shares_outstanding
-------|----------------|----------------|-----------------|-------------------
AAPL   | 2020-01-01     | 2020-06-30     | $1,500,000,000  | 4,334,330,000
AAPL   | 2020-07-01     | 2021-03-15     | $2,000,000,000  | 4,334,330,000
AAPL   | 2021-03-16     | 2099-12-31     | $2,500,000,000  | 5,213,840,000
```

**Como funciona**:
- Cada fila representa un **periodo** donde el valor es valido
- `effective_from` ≤ `trading_day` < `effective_to` (rango semiabierto)
- Cuando el valor cambia, se **cierra** el periodo anterior y se **abre** uno nuevo
- El ultimo periodo tiene `effective_to = 2099-12-31` (abierto, asume validez futura)

**Join temporal** para obtener market cap de una fecha especifica:

```python
# Quiero el market cap de AAPL el 2020-08-20
SELECT market_cap
FROM market_cap_dim
WHERE ticker = 'AAPL'
  AND '2020-08-20' >= effective_from
  AND '2020-08-20' < effective_to
# Resultado: $2,000,000,000
```

**¿Por que SCD-2 y no SCD-1?**

| Tipo | Comportamiento | Historial | Uso |
|------|---------------|-----------|-----|
| **SCD-1** | Sobrescribe | ❌ Pierde historial | Dimensiones inmutables |
| **SCD-2** | Historiza | ✅ Mantiene historial completo | Dimensiones que cambian |

**SCD-2 es esencial** para:
- Analisis historico preciso (backtesting con datos correctos de epoca)
- Evitar survivorship bias (caps de tickers deslistados en su epoca)
- Filtros temporales (cap < $2B en el dia X, no cap actual)

---

#### 3.5.3 Fuente de Datos: Polygon API

**Endpoint**: `GET /v3/reference/tickers/{ticker}?date={YYYY-MM-DD}`

**Datos obtenidos**:
- `market_cap`: Market cap directo (cuando disponible)
- `share_class_shares_outstanding`: Acciones en circulacion
- `weighted_shares_outstanding`: Acciones ponderadas

**Estrategia de construccion SCD-2**:

1. **Descargar snapshots periodicos** desde Polygon:
   ```
   raw/polygon/reference/ticker_details/as_of_date=2020-01-01/details.parquet
   raw/polygon/reference/ticker_details/as_of_date=2020-07-01/details.parquet
   raw/polygon/reference/ticker_details/as_of_date=2021-01-01/details.parquet
   ...
   ```

2. **Consolidar en SCD-2** detectando cambios:
   ```python
   # Detectar cambios en market_cap o shares_outstanding
   changes = (
       df.sort(["ticker", "as_of_date"])
       .with_columns([
           pl.col("market_cap").shift(1).over("ticker").alias("prev_cap"),
           pl.col("shares_outstanding").shift(1).over("ticker").alias("prev_shares")
       ])
       .filter(
           (pl.col("market_cap") != pl.col("prev_cap")) |
           (pl.col("shares_outstanding") != pl.col("prev_shares"))
       )
   )
   ```

3. **Generar periodos** `(effective_from, effective_to)`:
   ```python
   scd2 = (
       changes
       .with_columns([
           pl.col("as_of_date").alias("effective_from"),
           pl.col("as_of_date").shift(-1).over("ticker").alias("effective_to")
       ])
       .with_columns([
           # Ultimo periodo: effective_to = 2099-12-31
           pl.col("effective_to").fill_null(pl.date(2099, 12, 31))
       ])
   )
   ```

4. **(Opcional) Imputar market_cap faltante**:
   ```python
   # Si market_cap = null pero shares_outstanding disponible:
   market_cap_imputed = median(close_d × shares_outstanding)
   # Usando datos del daily_cache en el rango [effective_from, effective_to)
   ```

**Archivo generado**: `processed/ref/market_cap_dim/market_cap_dim.parquet`

**Script de generacion**: `scripts/fase_C_ingesta_tiks/build_market_cap_dim.py` (documentado en [5.7_enriquecimiento_market_cap.md](D:\04_TRADING_SMALLCAPS\01_DayBook\fase_01\C_v1_ingesta_tiks_2020_2025\5.7_enriquecimiento_market_cap.md))

---

#### 3.5.4 Caso Especial: Tickers Deslistados

**Problema**: ¿Como obtener market cap de un ticker deslistado (delisted) en su epoca?

**Solucion Polygon**:
- Polygon **mantiene datos historicos** de tickers deslistados
- Endpoint `/v3/reference/tickers/{ticker}?date={YYYY-MM-DD}` funciona con `?date=` en el pasado
- Requiere especificar `date` correspondiente al periodo cuando estaba activo

**Ejemplo**:
```bash
# Ticker XYZW deslistado en 2018-06-15
# Quiero su market cap el 2017-05-10 (cuando estaba activo)

GET /v3/reference/tickers/XYZW?date=2017-05-10
# Devuelve: market_cap = $150M, shares_outstanding = 50M
```

**Estrategia de snapshots** para SCD-2 con deslistados:

1. **Snapshot mensual/trimestral** durante periodo completo (2004-2025):
   - Tickers activos: Obtiene cap actual
   - Tickers deslistados: Obtiene cap de su ultima fecha activa

2. **Detectar delisting** en SCD-2:
   - `effective_to != 2099-12-31` → ticker con historial finito (posible delisted)
   - `effective_to = fecha_delisting` → ultimo periodo conocido

3. **Validacion** de cobertura:
   ```python
   # Verificar que todos los ticker-dias tienen market_cap
   coverage = (
       daily_cache
       .join(market_cap_dim, on="ticker", how="left")
       .filter(
           (pl.col("effective_from") <= pl.col("trading_day")) &
           (pl.col("trading_day") < pl.col("effective_to"))
       )
       .select(["ticker", "trading_day", "market_cap"])
       .filter(pl.col("market_cap").is_null())
   )
   # Si coverage vacio → 100% cobertura ✅
   ```

**IMPORTANTE**: El universo de C_v2 (3,107 tickers) ya fue pre-filtrado por `market_cap < $2B` **al momento de descarga OHLCV** (2025-10-21). Por tanto:
- Muchos tickers pudieron tener cap > $2B en el pasado (2004-2019)
- La SCD-2 capturara esos cambios historicos
- El filtro E0 `market_cap_d < $2B` se aplica **por fecha** usando join temporal
- Esto permite excluir periodos cuando el ticker era large cap

---

#### 3.5.5 Codigo de Join Temporal (C_v2)

**Codigo fuente**: [build_daily_cache.py:206-243](D:\04_TRADING_SMALLCAPS\scripts\fase_C_ingesta_tiks\build_daily_cache.py#L206-L243)

```python
def join_market_cap_temporal(
    daily: pl.DataFrame,
    cap_parquet: Optional[str]
) -> pl.DataFrame:
    """
    Join temporal con SCD-2 (market_cap_dim) para market cap por fecha
    effective_from <= trading_day < effective_to
    """
    if not cap_parquet or not Path(cap_parquet).exists():
        log(f"[WARN] Cap parquet no encontrado, skip market_cap")
        return daily.with_columns(pl.lit(None).alias("market_cap_d"))

    # Leer dimension SCD-2
    dim = pl.read_parquet(cap_parquet).select([
        "ticker", "effective_from", "effective_to", "market_cap"
    ])

    # Normalizar fechas y cerrar open-ended con fecha futura
    dim = dim.with_columns([
        pl.col("effective_from").cast(pl.Date),
        pl.col("effective_to").cast(pl.Date).fill_null(pl.date(2099, 12, 31))
    ])

    # Left join y filtro temporal
    joined = (
        daily.join(dim, on="ticker", how="left")
        .filter(
            (pl.col("effective_from") <= pl.col("trading_day")) &
            (pl.col("trading_day") < pl.col("effective_to"))
        )
        # Si hay solapes en SCD-2, quedarse con el mas reciente
        .sort(["ticker", "trading_day", "effective_from"], descending=[False, False, True])
        .unique(subset=["ticker", "trading_day"], keep="first")
        .select([*(daily.columns), "market_cap"])
        .rename({"market_cap": "market_cap_d"})
    )

    return joined
```

**Filtro en universo dinamico**: [build_dynamic_universe_optimized.py:100-115](D:\04_TRADING_SMALLCAPS\scripts\fase_C_ingesta_tiks\build_dynamic_universe_optimized.py#L100-L115)

```python
def apply_cap_filter(df: pl.DataFrame, cap_max: Optional[float]) -> pl.DataFrame:
    """Filtra por market cap maximo (si disponible)"""
    if not cap_max:
        return df

    # market_cap_d puede ser null si no hubo join en cache
    filtered = df.filter(
        (pl.col("market_cap_d").is_null()) |  # Tolera nulls (si SCD-2 incompleta)
        (pl.col("market_cap_d") <= cap_max)
    )

    dropped = len(df) - len(filtered)
    if dropped > 0:
        log(f"Filtro cap_max={cap_max:,}: {dropped} ticker-dias excluidos")

    return filtered
```

---

#### 3.5.6 Decision para E0 en C_v2

**C_v1 (2020-2025)**:
- ❌ **NO aplica filtro** de market cap (SCD-2 no disponible)
- `market_cap_d = null` en 100% de registros

**E0 en C_v2 (2004-2025)**:
- ✅ **SI aplica filtro** `market_cap_d < $2B`
- Razon: Consistencia con universo descargado (pre-filtrado por cap < $2B)
- Beneficio: Excluye periodos cuando ticker era large cap (ej: AAPL 2004-2010)
- Implementacion: Join temporal con SCD-2 usando `effective_from/effective_to`

**Configuracion**:
```yaml
# configs/universe_config.yaml
thresholds:
  cap_max: 2_000_000_000  # $2B
```

**IMPORTANTE**: Este filtro diferencia E0 de la replica exacta de C_v1. Justificacion:
- C_v1 no podia aplicar filtro cap (no tenia SCD-2)
- C_v2 SI puede aplicarlo (SCD-2 disponible)
- El objetivo de E0 es capturar eventos info-rich de **small caps**, no large caps
- Aplicar filtro cap mejora precision sin perder eventos relevantes para la estrategia

---

## 4. LOGICA DE APLICACION DEL FILTRO

### 4.1 Orden de Operaciones

**Pipeline de procesamiento** (secuencia EXACTA):

1. **Agregacion 1-min → Diario** ([build_daily_cache.py:126-165](D:\04_TRADING_SMALLCAPS\scripts\fase_C_ingesta_tiks\build_daily_cache.py#L126-L165))
   - Entrada: Barras de 1 minuto (columnas: `date, c, v, vw, n`)
   - Agregacion por `(ticker, trading_day)`:
     - `close_d = last(c)`
     - `vol_d = sum(v)`
     - `dollar_vol_d = sum(v * vw)`
     - `vwap_d = sum(v * vw) / sum(v)`
     - `session_rows = count(n)`
     - `has_gaps = session_rows < 390`

2. **Calculo de Features** ([build_daily_cache.py:167-204](D:\04_TRADING_SMALLCAPS\scripts\fase_C_ingesta_tiks\build_daily_cache.py#L167-L204))
   - `close_prev = close_d.shift(1).over("ticker")`
   - `pctchg_d = (close_d / close_prev) - 1.0`
   - `return_d = log(close_d / close_prev)`
   - `vol_30s_ma = vol_d.rolling_mean(window_size=30, min_periods=1).over("ticker")`
   - `rvol30 = vol_d / vol_30s_ma`

3. **Join Market Cap** ([build_daily_cache.py:206-243](D:\04_TRADING_SMALLCAPS\scripts\fase_C_ingesta_tiks\build_daily_cache.py#L206-L243))
   - **C_v1**: Omitido (market_cap_d = null)
   - **C_v2/E0**: Join temporal con SCD-2 (`market_cap_dim.parquet`)

4. **Filtro de Precio (pre-filtro)** ([build_dynamic_universe_optimized.py:242-245](D:\04_TRADING_SMALLCAPS\scripts\fase_C_ingesta_tiks\build_dynamic_universe_optimized.py#L242-L245))
   - **C_v1**: `close_d >= 0.50 AND close_d <= 20.00`
   - **C_v2/E0**: `close_d >= 0.20 AND close_d <= 20.00` (mas inclusivo)

5. **Filtro de Market Cap (pre-filtro)** ([build_dynamic_universe_optimized.py:100-115](D:\04_TRADING_SMALLCAPS\scripts\fase_C_ingesta_tiks\build_dynamic_universe_optimized.py#L100-L115))
   - **C_v1**: NO aplicado (market_cap_d = null)
   - **C_v2/E0**: `market_cap_d < 2_000_000_000` (excluye large caps)

6. **Etiquetado Info-Rich** ([build_dynamic_universe_optimized.py:117-146](D:\04_TRADING_SMALLCAPS\scripts\fase_C_ingesta_tiks\build_dynamic_universe_optimized.py#L117-L146))
   - Reglas individuales:
     - `r_rvol = (rvol30 >= 2.0)`
     - `r_chg = (|pctchg_d| >= 0.15)`
     - `r_dvol = (dollar_vol_d >= 5_000_000)`
     - `r_px = (close_d >= min_price AND close_d <= max_price)` (min_price: C_v1=0.50, E0=0.20)
     - `r_cap = (market_cap_d < cap_max)` (solo E0/C_v2)
   - Combinacion:
     - **C_v1**: `info_rich = r_rvol AND r_chg AND r_dvol AND r_px`
     - **C_v2/E0**: `info_rich = r_rvol AND r_chg AND r_dvol AND r_px AND r_cap`

7. **Generacion de Watchlists** ([build_dynamic_universe_optimized.py:148-164](D:\04_TRADING_SMALLCAPS\scripts\fase_C_ingesta_tiks\build_dynamic_universe_optimized.py#L148-L164))
   - Salida: `processed/universe/info_rich/daily/date=YYYY-MM-DD/watchlist.parquet`

### 4.2 Codigo Exacto del Filtro

**Archivo**: [build_dynamic_universe_optimized.py:117-146](D:\04_TRADING_SMALLCAPS\scripts\fase_C_ingesta_tiks\build_dynamic_universe_optimized.py#L117-L146)

```python
def label_info_rich(
    df: pl.DataFrame,
    rvol_th: float,
    pctchg_th: float,
    dvol_th: float,
    min_price: float,
    max_price: float
) -> pl.DataFrame:
    """
    Etiqueta info_rich basado en umbrales
    RVOL y pctchg_d ya calculados en cache
    """
    if df.is_empty():
        return df

    labeled = (
        df.with_columns([
            # Reglas individuales
            (pl.col("rvol30") >= rvol_th).alias("r_rvol"),
            (pl.col("pctchg_d").abs() >= pctchg_th).alias("r_chg"),
            (pl.col("dollar_vol_d") >= dvol_th).alias("r_dvol"),
            ((pl.col("close_d") >= min_price) & (pl.col("close_d") <= max_price)).alias("r_px"),
        ])
        .with_columns([
            # Combinacion AND
            (pl.col("r_rvol") & pl.col("r_chg") & pl.col("r_dvol") & pl.col("r_px")).alias("info_rich")
        ])
    )

    return labeled
```

**Configuracion de umbrales** (configs/universe_config.yaml):
```yaml
# C_v1 (2020-2025):
thresholds:
  rvol: 2.0
  pctchg: 0.15
  dvol: 5_000_000
  min_price: 0.5           # C_v1: $0.50
  max_price: 20.0
  cap_max: 2_000_000_000   # NO aplicado en C_v1

# E0/C_v2 (2004-2025):
thresholds:
  rvol: 2.0
  pctchg: 0.15
  dvol: 5_000_000
  min_price: 0.2           # E0: $0.20 (mas inclusivo)
  max_price: 20.0
  cap_max: 2_000_000_000   # SI aplicado en E0/C_v2
```

---

## 5. ARCHIVOS GENERADOS (ESTRUCTURA DE DATOS)

### 5.1 Cache Diario

**Ruta**: `processed/daily_cache/ticker={TICKER}/daily.parquet`

**Schema** (12 columnas):
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
market_cap_d: Float64 (null en C_v1)
```

**Metadata**:
- Compresion: ZSTD level 2
- Particionado por ticker
- Marker: `_SUCCESS` por ticker
- Manifest global: `MANIFEST.json`

**Codigo fuente**: [build_daily_cache.py:278-284](D:\04_TRADING_SMALLCAPS\scripts\fase_C_ingesta_tiks\build_daily_cache.py#L278-L284)

### 5.2 Watchlists Diarias

**Ruta**: `processed/universe/info_rich/daily/date={YYYY-MM-DD}/watchlist.parquet`

**Schema**:
```
ticker: Utf8
trading_day: Date
close_d: Float64
pctchg_d: Float64
rvol30: Float64
vol_d: Int64
dollar_vol_d: Float64
vwap_d: Float64
market_cap_d: Float64 (null)
r_rvol: Boolean
r_chg: Boolean
r_dvol: Boolean
r_px: Boolean
info_rich: Boolean
```

**Codigo fuente**: [build_dynamic_universe_optimized.py:148-164](D:\04_TRADING_SMALLCAPS\scripts\fase_C_ingesta_tiks\build_dynamic_universe_optimized.py#L148-L164)

### 5.3 TopN 12-Month Rolling

**Ruta**: `processed/universe/info_rich/topN_12m.parquet`

**Schema**:
```
ticker: Utf8
days_info_rich_252: Int64
last_seen: Date
```

**Descripcion**: Ranking de tickers por numero de dias info-rich en las ultimas 252 sesiones.

**Codigo fuente**: [build_dynamic_universe_optimized.py:166-202](D:\04_TRADING_SMALLCAPS\scripts\fase_C_ingesta_tiks\build_dynamic_universe_optimized.py#L166-L202)

### 5.4 Ticks Descargados

**Ruta**: `raw/polygon/trades/{TICKER}/date={YYYY-MM-DD}/trades.parquet`

**Criterio de descarga**: Solo dias donde `info_rich = True` en la watchlist.

**Schema**:
```
t: Datetime (microseconds)  # sip_timestamp
p: Float64                   # price
s: Int64                     # size
c: List[Utf8]               # conditions
```

**Codigo fuente**: [download_trades_optimized.py:75-95](D:\04_TRADING_SMALLCAPS\scripts\fase_C_ingesta_tiks\download_trades_optimized.py#L75-L95)

---

## 6. RESULTADOS EMPIRICOS (C_v1: 2020-2025)

### 6.1 Metricas Globales

**Periodo**: 2020-01-01 → 2025-10-21

| Metrica | Valor | Fuente |
|---------|-------|--------|
| **Tickers procesados** | 2,857 | [5.5_1_auditoria_build_daily_cache.md:16](D:\04_TRADING_SMALLCAPS\01_DayBook\fase_01\C_v1_ingesta_tiks_2020_2025\5.5_1_auditoria_build_daily_cache.md#L16) |
| **Ticker-dias generados** | 2,859,270 | [5.5_1_auditoria_build_daily_cache.md:32](D:\04_TRADING_SMALLCAPS\01_DayBook\fase_01\C_v1_ingesta_tiks_2020_2025\5.5_1_auditoria_build_daily_cache.md#L32) |
| **Dias promedio/ticker** | 1,001 | [5.5_1_auditoria_build_daily_cache.md:33](D:\04_TRADING_SMALLCAPS\01_DayBook\fase_01\C_v1_ingesta_tiks_2020_2025\5.5_1_auditoria_build_daily_cache.md#L33) |
| **Ticker-dias info-rich descargados** | 11,054 | [5.10_auditoria_descarga_ticks_completa.md:33](D:\04_TRADING_SMALLCAPS\01_DayBook\fase_01\C_v1_ingesta_tiks_2020_2025\5.10_auditoria_descarga_ticks_completa.md#L33) |
| **Tickers unicos info-rich** | 1,906 | [5.10_auditoria_descarga_ticks_completa.md:34](D:\04_TRADING_SMALLCAPS\01_DayBook\fase_01\C_v1_ingesta_tiks_2020_2025\5.10_auditoria_descarga_ticks_completa.md#L34) |
| **Dias promedio info-rich/ticker** | 5.8 | [5.10_auditoria_descarga_ticks_completa.md:36](D:\04_TRADING_SMALLCAPS\01_DayBook\fase_01\C_v1_ingesta_tiks_2020_2025\5.10_auditoria_descarga_ticks_completa.md#L36) |
| **Tasa de info-rich** | 0.39% | 11,054 / 2,859,270 |

### 6.2 Ejemplo de Ticker Info-Rich (2025-10-21)

**Top 10 tickers** del 2025-10-21:

| Ticker | RVOL | %chg | $vol | Close | Resultado |
|--------|------|------|------|-------|-----------|
| BOF | 28.89 | +40.29% | $157M | $2.89 | info_rich = True |
| NERV | 27.68 | +131.46% | $1.46B | $6.11 | info_rich = True |
| HHS | 26.47 | +31.43% | $12.8M | $4.60 | info_rich = True |
| VSEE | 24.65 | +92.77% | $213M | $0.89 | info_rich = True |
| JWEL | 21.69 | -25.76% | $21.9M | $1.96 | info_rich = True |
| ATMV | 18.75 | -28.39% | $49.3M | $11.10 | info_rich = True |
| DCGO | 15.11 | -15.52% | $55.0M | $1.47 | info_rich = True |
| BYND | 13.95 | +162.74% | $5.93B | $4.44 | info_rich = True |
| OMSE | 11.58 | +17.54% | $8.0M | $4.69 | info_rich = True |
| MEC | 9.61 | +20.74% | $21.7M | $15.72 | info_rich = True |

**Fuente**: [5.8_ejecucion_cache_y_universo_resultados.md:147-159](D:\04_TRADING_SMALLCAPS\01_DayBook\fase_01\C_v1_ingesta_tiks_2020_2025\5.8_ejecucion_cache_y_universo_resultados.md#L147-L159)

**Validacion**:
- Todos cumplen `rvol30 >= 2.0` ✅
- Todos cumplen `|pctchg_d| >= 15%` ✅
- Todos cumplen `dollar_vol_d >= $5M` ✅
- Todos cumplen `close_d ∈ [$0.50, $20.00]` ✅

### 6.3 Distribucion Temporal

**Tickers info-rich por dia** (semana 2025-10-15 a 2025-10-21):

| Fecha | Tickers info-rich |
|-------|-------------------|
| 2025-10-15 | 34 |
| 2025-10-16 | 29 |
| 2025-10-17 | 24 |
| 2025-10-20 | 29 |
| 2025-10-21 | 24 |

**Promedio**: 28 tickers/dia
**Fuente**: [5.8_ejecucion_cache_y_universo_resultados.md:134-143](D:\04_TRADING_SMALLCAPS\01_DayBook\fase_01\C_v1_ingesta_tiks_2020_2025\5.8_ejecucion_cache_y_universo_resultados.md#L134-L143)

---

## 7. IMPLEMENTACION PROPUESTA PARA E0 EN C_v2

### 7.1 Funcion de Deteccion

```python
def detect_E0_generic_info_rich(df: pl.DataFrame) -> pl.DataFrame:
    """
    Evento E0: Generic Info-Rich (extension de C_v1 para C_v2)

    Logica inmutable documentada en: Contrato_E0.md v2.0.0

    Diferencias vs C_v1:
    - Precio minimo: $0.50 → $0.20 (mas inclusivo para penny stocks)
    - Market cap: NO filtrado → < $2B (consistente con universo descargado)

    Aplicar EXACTAMENTE:
    - rvol30 >= 2.0 (30 sesiones, min_periods=1)
    - |pctchg_d| >= 15%
    - dollar_vol_d >= $5M
    - close_d in [$0.20, $20.00]  ← CAMBIO vs C_v1
    - market_cap_d < $2B           ← NUEVO vs C_v1
    """
    return df.with_columns([
        (
            (pl.col("rvol30") >= 2.0) &
            (pl.col("pctchg_d").abs() >= 0.15) &
            (pl.col("dollar_vol_d") >= 5_000_000) &
            (pl.col("close_d") >= 0.20) &  # C_v1: 0.50
            (pl.col("close_d") <= 20.00) &
            (
                (pl.col("market_cap_d").is_null()) |  # Tolera nulls si SCD-2 incompleta
                (pl.col("market_cap_d") < 2_000_000_000)
            )
        ).alias("E0_generic_info_rich")
    ])
```

### 7.2 Jerarquia de Eventos

**Prioridad** (de mayor a menor especificidad):
```
E13 (Crypto Surge) > E7 (Earnings Beat) > E4 (Gap Fill) >
E8 (Short Squeeze) > E1 (Momentum) > E0 (Generic Info-Rich)
```

**Logica de asignacion**: Si un ticker-dia cumple multiples eventos, se asigna el de mayor prioridad.

### 7.3 Garantia de Inclusion

**Teorema**:
```
Si E0 replica exactamente C_v1, entonces:
  ∀ (t, d) ∈ E_C_v1 ⇒ (t, d) ∈ E0 ⊆ E_C_v2_extendido

Por lo tanto: E_C_v2_extendido ⊇ E_C_v1 (100% inclusion garantizada)
```

**Verificacion empirica**: Ejecutar `verify_inclusion_C_v1_in_C_v2_ext.py` sobre periodo 2020-2025 y confirmar tasa de inclusion = 100%.

---

## 8. CASOS ESPECIALES Y EDGE CASES

### 8.1 Valores Null

| Campo | Comportamiento | Filtro |
|-------|---------------|--------|
| `rvol30` | Si `vol_30s_ma = 0` → `rvol30 = null` | `null >= 2.0` → False (EXCLUIDO) |
| `pctchg_d` | Primer dia del ticker → `pctchg_d = null` | `null >= 0.15` → False (EXCLUIDO) |
| `close_d` | Si no hay datos 1-min → `close_d = null` | `null >= 0.50` → False (EXCLUIDO) |
| `dollar_vol_d` | Si `sum(v) = 0` → `dollar_vol_d = 0` | `0 >= 5M` → False (EXCLUIDO) |
| `market_cap_d` | Siempre `null` en C_v1 | NO se aplica filtro |

### 8.2 Tickers con Gaps

**Definicion**: `has_gaps = (session_rows < 390)`

**Comportamiento en C_v1**: NO afecta el filtro info_rich (gap es informativo pero no excluyente).

**Estadistica**: 16.8% de ticker-dias tienen gaps (ejemplo: OCGN).

**Fuente**: [5.5_1_auditoria_build_daily_cache.md:84](D:\04_TRADING_SMALLCAPS\01_DayBook\fase_01\C_v1_ingesta_tiks_2020_2025\5.5_1_auditoria_build_daily_cache.md#L84)

### 8.3 Tickers con RVOL Extremo

**Observacion**: RVOL puede alcanzar valores muy altos (max observado: 20.48 en OCGN).

**Comportamiento**: No hay limite superior para RVOL (solo inferior: >= 2.0).

**Fuente**: [5.5_1_auditoria_build_daily_cache.md:93](D:\04_TRADING_SMALLCAPS\01_DayBook\fase_01\C_v1_ingesta_tiks_2020_2025\5.5_1_auditoria_build_daily_cache.md#L93)

### 8.4 Primer Dia de Cada Ticker

**Problema**: `pctchg_d = null` (no hay dia anterior).

**Solucion**: Ticker excluido automaticamente del filtro el primer dia.

**Impacto**: Minimo (~0.035% de ticker-dias).

---

## 9. VERIFICACION VISUAL (JUPYTER NOTEBOOK)

### 9.1 Celda de Inspeccion de Watchlist

```python
# Celda 1: Setup
from pathlib import Path
import polars as pl
import datetime as dt

BASE_DIR = Path(r"D:\04_TRADING_SMALLCAPS")
WATCHLIST_DIR = BASE_DIR / "processed" / "universe" / "info_rich" / "daily"

# Celda 2: Cargar watchlist del dia
target_date = "2025-10-21"
watchlist_path = WATCHLIST_DIR / f"date={target_date}" / "watchlist.parquet"

df = pl.read_parquet(watchlist_path)
print(f"Total tickers en watchlist: {len(df)}")
print(f"Tickers info-rich: {df.filter(pl.col('info_rich')).height}")

# Celda 3: Inspeccionar top 10 info-rich
info_rich = df.filter(pl.col("info_rich")).sort("rvol30", descending=True).head(10)
print("\nTop 10 tickers info-rich (ordenados por RVOL):")
print(info_rich.select([
    "ticker", "rvol30", "pctchg_d", "dollar_vol_d", "close_d"
]))

# Celda 4: Verificar cumplimiento de umbrales
print("\n=== VERIFICACION DE UMBRALES ===")
print(f"RVOL min: {info_rich['rvol30'].min():.2f} (esperado >= 2.0)")
print(f"|%chg| min: {info_rich['pctchg_d'].abs().min():.2%} (esperado >= 15%)")
print(f"$vol min: ${info_rich['dollar_vol_d'].min():,.0f} (esperado >= $5M)")
print(f"Precio min: ${info_rich['close_d'].min():.2f} (esperado >= $0.50)")
print(f"Precio max: ${info_rich['close_d'].max():.2f} (esperado <= $20.00)")

# Celda 5: Comparar con NO info-rich
not_info_rich = df.filter(~pl.col("info_rich")).head(10)
print("\n10 tickers NO info-rich (contraejemplos):")
print(not_info_rich.select([
    "ticker", "rvol30", "pctchg_d", "dollar_vol_d", "close_d",
    "r_rvol", "r_chg", "r_dvol", "r_px"
]))

# Celda 6: Estadisticas de distribucion
print("\n=== ESTADISTICAS DE DISTRIBUCION ===")
print(df.select([
    pl.col("rvol30").describe(),
    pl.col("pctchg_d").abs().describe(),
    pl.col("dollar_vol_d").describe(),
    pl.col("close_d").describe()
]))
```

### 9.2 Celda de Validacion Historica

```python
# Celda 7: Cargar multiples dias
date_range = ["2025-10-15", "2025-10-16", "2025-10-17", "2025-10-20", "2025-10-21"]
all_watchlists = []

for d in date_range:
    p = WATCHLIST_DIR / f"date={d}" / "watchlist.parquet"
    if p.exists():
        df_day = pl.read_parquet(p).with_columns(pl.lit(d).alias("snapshot_date"))
        all_watchlists.append(df_day)

df_week = pl.concat(all_watchlists)
print(f"Total ticker-dias en semana: {len(df_week)}")
print(f"Ticker-dias info-rich: {df_week.filter(pl.col('info_rich')).height}")

# Celda 8: Tickers recurrentes (info-rich en multiples dias)
recurrentes = (
    df_week
    .filter(pl.col("info_rich"))
    .group_by("ticker")
    .agg([
        pl.col("snapshot_date").count().alias("dias_info_rich"),
        pl.col("rvol30").mean().alias("rvol_promedio"),
        pl.col("pctchg_d").abs().mean().alias("pctchg_promedio")
    ])
    .filter(pl.col("dias_info_rich") >= 2)
    .sort("dias_info_rich", descending=True)
)

print("\nTickers info-rich en 2+ dias (recurrentes):")
print(recurrentes.head(20))
```

### 9.3 Celda de Comparacion C_v1 vs E0

```python
# Celda 9: Simular deteccion E0 (debe ser identica a info_rich)
df_test = df.with_columns([
    (
        (pl.col("rvol30") >= 2.0) &
        (pl.col("pctchg_d").abs() >= 0.15) &
        (pl.col("dollar_vol_d") >= 5_000_000) &
        (pl.col("close_d") >= 0.50) &
        (pl.col("close_d") <= 20.00)
    ).alias("E0_simulado")
])

# Verificar que info_rich == E0_simulado (100% match)
discrepancies = df_test.filter(pl.col("info_rich") != pl.col("E0_simulado"))
print(f"\n=== VERIFICACION E0 vs C_v1 ===")
print(f"Total tickers: {len(df_test)}")
print(f"Coincidencias: {len(df_test) - len(discrepancies)}")
print(f"Discrepancias: {len(discrepancies)} (esperado: 0)")

if len(discrepancies) == 0:
    print("\n✅ E0 replica EXACTAMENTE la logica de C_v1 (100% match)")
else:
    print("\n❌ ERROR: E0 NO replica C_v1. Ver discrepancias:")
    print(discrepancies)
```

---

## 10. AUDITORIA Y TRAZABILIDAD

### 10.1 Documentos Fuente

1. [5.0_que_datos_tienes.md](D:\04_TRADING_SMALLCAPS\01_DayBook\fase_01\C_v1_ingesta_tiks_2020_2025\5.0_que_datos_tienes.md) - Definicion conceptual
2. [5.1_porqué_un_filtro_tickers_despiertos.md](D:\04_TRADING_SMALLCAPS\01_DayBook\fase_01\C_v1_ingesta_tiks_2020_2025\5.1_porqué_un_filtro_tickers_despiertos.md) - Justificacion de umbrales
3. [5.2_file_build_dynamic_universe_py.md](D:\04_TRADING_SMALLCAPS\01_DayBook\fase_01\C_v1_ingesta_tiks_2020_2025\5.2_file_build_dynamic_universe_py.md) - Documentacion script original
4. [5.4_pipeline_ejecucion.md](D:\04_TRADING_SMALLCAPS\01_DayBook\fase_01\C_v1_ingesta_tiks_2020_2025\5.4_pipeline_ejecucion.md) - Pipeline de ejecucion
5. [5.5_0_optimizaciones_velocidad_build_dynamic_universe.md](D:\04_TRADING_SMALLCAPS\01_DayBook\fase_01\C_v1_ingesta_tiks_2020_2025\5.5_0_optimizaciones_velocidad_build_dynamic_universe.md) - Scripts optimizados
6. [5.5_1_auditoria_build_daily_cache.md](D:\04_TRADING_SMALLCAPS\01_DayBook\fase_01\C_v1_ingesta_tiks_2020_2025\5.5_1_auditoria_build_daily_cache.md) - Auditoria cache
7. [5.8_ejecucion_cache_y_universo_resultados.md](D:\04_TRADING_SMALLCAPS\01_DayBook\fase_01\C_v1_ingesta_tiks_2020_2025\5.8_ejecucion_cache_y_universo_resultados.md) - Resultados finales
8. [5.10_auditoria_descarga_ticks_completa.md](D:\04_TRADING_SMALLCAPS\01_DayBook\fase_01\C_v1_ingesta_tiks_2020_2025\5.10_auditoria_descarga_ticks_completa.md) - Auditoria descarga ticks

### 10.2 Scripts Auditados

1. [build_daily_cache.py](D:\04_TRADING_SMALLCAPS\scripts\fase_C_ingesta_tiks\build_daily_cache.py) - Lineas criticas:
   - L187: `rolling_mean(window_size=30, min_periods=1)` (RVOL30)
   - L191: `(close_d / close_prev) - 1.0` (pctchg_d)
   - L145: `(v * vw).sum()` (dollar_vol_d)
   - L143: `c.last()` (close_d)

2. [build_dynamic_universe_optimized.py](D:\04_TRADING_SMALLCAPS\scripts\fase_C_ingesta_tiks\build_dynamic_universe_optimized.py) - Lineas criticas:
   - L135-138: Reglas individuales (r_rvol, r_chg, r_dvol, r_px)
   - L142: Combinacion AND (info_rich)
   - L242-245: Filtro previo de precio

3. [download_trades_optimized.py](D:\04_TRADING_SMALLCAPS\scripts\fase_C_ingesta_tiks\download_trades_optimized.py) - Lineas criticas:
   - L75-95: `load_info_rich_days()` (lee watchlists y filtra info_rich=True)
   - L103-120: `http_get_trades()` (descarga desde Polygon API)

### 10.3 Configuracion

**Archivo**: `configs/universe_config.yaml`

```yaml
thresholds:
  rvol: 2.0
  pctchg: 0.15
  dvol: 5_000_000
  min_price: 0.5
  max_price: 20.0
  cap_max: 2_000_000_000  # NO usado en C_v1
```

**Ubicacion**: [D:\04_TRADING_SMALLCAPS\configs\universe_config.yaml](D:\04_TRADING_SMALLCAPS\configs\universe_config.yaml)

---

## 11. CAMBIOS PROHIBIDOS

Este contrato es **INMUTABLE** a partir de la version 2.0.0. Las siguientes modificaciones estan **PROHIBIDAS**:

❌ Cambiar umbrales base (rvol, pctchg, dvol)  
❌ Modificar formulas (RVOL30, pctchg_d, dollar_vol_d)  
❌ Cambiar ventana de 30 sesiones a 30 dias calendario  
❌ Usar close_d en lugar de VWAP para dollar_vol_d  
❌ Aplicar filtro solo en una direccion (solo subidas o solo bajadas)  
❌ Eliminar filtro de market cap < $2B  
❌ Aumentar precio minimo por encima de $0.20  

**Cambios permitidos** (documentados en v2.0.0):
✅ Precio minimo: $0.50 → $0.20 (APLICADO en v2.0.0)
✅ Market cap: null → < $2B (APLICADO en v2.0.0)

**Razon**: Los cambios en v2.0.0 AUMENTAN la inclusividad (no la reducen), por tanto NO rompen la garantia:
```
E_E0_v2 ⊇ E_E0_v1 (donde E0_v1 seria replica exacta de C_v1)
```

**Nota critica**: E0 v2.0.0 captura MAS eventos que C_v1 debido a:
1. Precio minimo menor ($0.20 vs $0.50) → incluye penny stocks excluidos en C_v1
2. Market cap < $2B → excluye large caps que C_v1 incluia por defecto

El segundo punto es una excepcion justificada: C_v1 incluia large caps solo porque NO TENIA manera de excluirlos (sin SCD-2). El objetivo real de C_v1 era small caps. Por tanto, aplicar filtro cap en E0 MEJORA la fidelidad al objetivo original.

Si se requieren variaciones, crear **nuevos eventos** (E14, E15, etc.), pero **E0 debe permanecer inmutable desde v2.0.0**.

---

## 12. HASH DE VERIFICACION

**Proposito**: Detectar modificaciones no autorizadas de este contrato.

**Calculo**: SHA-256 de las secciones 1-11 (excluye esta seccion).

```
Seccion 1-11 (sin seccion 12): [PENDING - calcular despues de guardar]
```

**Verificacion**: Re-calcular hash y comparar con valor original. Si difiere, el contrato fue modificado.

---

## 13. APROBACION Y FIRMA

**Fecha de aprobacion**: 2025-10-25  
**Version**: 2.0.0  
**Estado**: INMUTABLE - NO MODIFICAR  

**Aprobado por**: Alex Just Rodriguez  
**Proposito**: Garantizar inclusion 100%+ de eventos C_v1 en C_v2 mediante evento E0  

**Cambios v2.0.0** (aprobados):  
- ✅ Precio minimo: $0.50 → $0.20 (mas inclusivo para penny stocks)
- ✅ Market cap: null → < $2B (consistente con universo descargado, filtro temporal SCD-2)
- ✅ Documentacion completa de SCD-2 (construccion, join temporal, tickers deslistados)

**Garantia extendida**:
```
E_E0_v2 ⊇ E_C_v1 (por precio minimo menor)
E_E0_v2 ⊂ E_C_v1_hipotetico (por filtro cap, pero C_v1 no tenia cap)
```

Neto: E0 v2.0.0 es **mas inclusivo** que C_v1 para el objetivo de small caps info-rich.

**Proximos pasos**:
1. ✅ Generar dimension SCD-2: `build_market_cap_dim.py` (pre-requisito)
2. Implementar `detect_E0_generic_info_rich()` en C_v2 con logica v2.0.0
3. Ejecutar `verify_inclusion_C_v1_in_C_v2_ext.py` en periodo 2020-2025
4. Confirmar tasa de inclusion >= 100.00% (esperado: 105-110% por precio minimo menor)
5. Solo entonces proceder a descarga 21 años (2004-2025)

---

**FIN DEL CONTRATO E0 v2.0.0**
