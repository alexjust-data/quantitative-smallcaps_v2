# C.4 - Anotación: Descarga de Ticks a Nivel Diario

Aquí es donde mucha gente se lía y mezcla niveles de resolución. Te lo aclaro muy directo:

---

## TL;DR

* El filtrado E0 / E1 / E4 / E7 / E8 / E13 (o sea, decidir "este ticker/día merece ticks") se hace usando **datos agregados diarios** que tú ya calculaste a partir del 1 minuto.
* **NO** se hace mirando tick ni raw 1m en cada barra individual para decidir si descargar.
* Las velas de 1 minuto entran **ANTES** (para construir métricas diarias limpias) y **DESPUÉS** (para análisis intradía, DIBs, labeling), pero no son necesarias en tiempo real en el paso de "marcar qué día bajar".

---

## FASE 0: Qué datos tienes ya

Ya tienes:

1. **OHLCV diario** (2004→2025)
2. **OHLCV 1m** (2004→2025)
3. **daily_cache** = por-ticker-por-día, con:
   * `close_d`
   * `vol_d`
   * `dollar_vol_d`
   * `pctchg_d`
   * `rvol30`
   * etc.

Ese `daily_cache` lo calculaste **PASANDO** por la carpeta `intraday_1m`, pero el resultado final está en un parquet por ticker y día. Es **"datos diarios enriquecidos con métricas intradía"**.

Ese `daily_cache` es lo que vamos a usar para filtrar.

---

## FASE 1: Cómo decides si un TICKER-DÍA es interesante (info-rich / evento)

Aquí es donde aplicas E0, E1, E4, E7…

### Ejemplo E0 (info-rich genérico, nuestro contrato):

* `rvol30 ≥ 2.0`
* `|pctchg_d| ≥ 15%`
* `dollar_vol_d ≥ $5M`
* `0.20 ≤ close_d ≤ 20`
* `market_cap_d < $2B`

**Fíjate**: todo eso son métricas **A NIVEL DÍA**.

### No estás mirando:

* ¿en qué minuto rompió VWAP?
* ¿a qué hora hizo flush + reclaim?
* ¿cuántos halts seguidos intradía?

Nada de eso es necesario para **DECIDIR** "bájame ticks de este día".

### Esto es intencional, por dos razones:

#### 1. Velocidad / coste

Para saber si un día es interesante **no quieres bajar ticks primero**, porque ticks son lo caro.

Quieres decidir "es interesante" usando datos que **ya tienes baratos** (diario + 1m ya descargado).

#### 2. Consistencia

Estas reglas definen el **UNIVERSO** sobre el que vamos a estudiar, entrenar ML, hacer DIBs.

Ese universo tiene que ser **estable, auditable, repetible** en 2004 igual que en 2025.

Las reglas diarias son mucho más estables y fáciles de explicar a un auditor:
- "¿por qué descargaste este día?"
- → "por estos umbrales diarios"

### Entonces:

✅ El gating (E0 / E1 / E4 / …) se calcula **solo con datos diarios enriquecidos**.

No necesitas leer cada vela 1m una por una en este paso.

---

## FASE 2: Una vez marcado un ticker-día como interesante → ahora sí bajas ticks

### Pipeline real:

#### 1. `build_daily_cache.py`

Lee tus velas 1m históricas y condensa por día y ticker:

* `vol_d`
* `dollar_vol_d`
* `VWAP_d` (si quieres)
* `rvol30` (vol_d / media_vol_30d)
* `pctchg_d`
* etc.

**→ Resultado**: `daily_cache` (muy rápido, muy barato)

#### 2. `build_dynamic_universe_optimized.py`

Lee `daily_cache` y aplica las reglas de eventos:

* E0 (info-rich genérico)
* E4 (parabolic)
* E7 (first red day)
* E8 (gap down grande)
* E13 (offering pricing)
* etc.

**Te escupe**:

* una **watchlist diaria**: para cada fecha, qué tickers disparamos
* un **catálogo** `(ticker, date, event_type, window_start, window_end)`

**→ Esto es todavía SIN ticks**. Esto es la **"lista de objetivos"**.

#### 3. `download_trades_optimized.py`

Usa **ESA LISTA** de objetivos:

* Para cada `(ticker, date, window_start, window_end)` → hace la llamada a Polygon `/v3/trades/{ticker}` o `/v2/trades` según el endpoint
* Descarga tick real
* Lo guarda en `raw/polygon/trades/...`

**Aquí sí entran los ticks brutos.**

### Entonces:

📌 Las velas de 1 minuto **NO** son lo que define quién baja ticks.

📌 Las velas de 1 minuto **SON** la materia prima para construir el `daily_cache` que luego sí define eso.

### Piensa así:

* El 1m es **input** para construir tu "diagnóstico diario"
* Ese diagnóstico diario es el **filtro** info-rich/eventos
* Ese filtro decide qué días merece la pena bajar tick-level
* El tick-level se baja **después**, no antes

---

## FASE 3: ¿Y las velas de 1 minuto vuelven a usarse luego? Sí, pero ya en modelado

Una vez tienes tick-level:

### 1. Construyes DIB / VIB / imbalance bars

Barras por flujo de dinero/información.

Eso usa **ticks** (trade stream), no 1m.

### 2. Calculas features intradía de microestructura

* burst de volumen
* halts
* distancia al VWAP intradía
* reclaim de niveles
* slope de precio
* expansión/contracción de spread (si añades quotes)
* etc.

### 3. Etiquetas con triple barrier

* pt / sl / t1
* en ventanas reales (por ejemplo 120 barras de DIB)

### 4. Ponderas con sample weights

* unicidad temporal (overlap)
* importancia económica del evento
* time decay

Todo esto ya está en la parte de **ML**.

Pero para llegar ahí primero necesitabas decir **qué días valen la pena procesar**.

Eso se decide en **FASE 1** (diario enriquecido).
