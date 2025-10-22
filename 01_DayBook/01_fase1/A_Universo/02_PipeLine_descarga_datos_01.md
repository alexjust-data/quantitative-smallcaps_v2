¡Claro! Vamos a ordenarlo todo en **pipeline** + **lista exacta de datos de Polygon** y te indico **dónde encajan** Bar Construction, Triple Barrier, Sample Weighting y el PDF de **Fractionally Differentiated Features** (FFD) de López de Prado.

---

# 🚚 Pipeline “de cero” para Small Caps + ML

## 0) Definir universo (diario)

**Objetivo:** quedarte con *runners* potenciales (small/micro caps volátiles).

**Reglas base** (extraídas de tu Playbook: filtros de %chg, float, precio, volumen, sesgo small/micro, OTC opcional; y lógica de construcción de watchlist)   

* Market cap: *small/micro* (p. ej. < 1–2B).
* Precio: 0.5–20 USD (evitar sub-dollar salvo motivo).
* % change día: > +15%.
* Volumen: > 0.5–1M.
* Float: preferible < 60–100M.
* Exchange: NASDAQ/NYSE (OTC opcional).
* Señales negativas: operating cash flow negativo (riesgo de financiación/dilución).  

**De Polygon (diario):**

* `/v3/reference/tickers` → universo y metadatos (exchange, estado, type).
* `/v3/reference/tickers/{ticker}` → detalles: market cap, shares/float si disponible.
* (Complemento no-Polygon): **SEC EDGAR** para *S-1, S-3, 424B, ATM, PIPE, warrants* (clave en tu Q&A de Dilución). 

---

## 1) Ingesta de datos crudos (histórico + intradía)

**Objetivo:** máxima calidad para detección de patrones *long/short* del Playbook (VWAP, First Red Day, Gap & Go, LDF, OGD, etc.).  

**De Polygon:**

* **OHLCV diario**: `/v2/aggs/ticker/{T}/range/1/day/{from}/{to}`
* **OHLCV intradía (1m/5m)**: `/v2/aggs/ticker/{T}/range/1/minute/...`
* **Trades y Quotes (tick)**: `/v3/trades/{T}`, `/v3/quotes/{T}` (para microestructura: spread, imbalance).
* **Corporate actions**: `/v3/reference/splits`, `/v3/reference/dividends` (splits/reverse splits, útiles para *garbage* microcap).
* **News**: `/v2/reference/news` (catalizadores del día, validar “hot sector”).
* **Reference** (re-descarga periódica): `/v3/reference/tickers` (para delistings/simbología).

**Por qué tick/quotes:** tus setups usan VWAP, *tape reading*, *reclaim/rejection*, *late day fade*, *gap & crap*, etc.; la precisión intradía y el spread son críticos.  

---

## 2) Bar Construction (lo primero que “toca” el dato)

**Qué es:** transformar ticks de Polygon en barras **impulsadas por información** (no por reloj) para homogeneizar el proceso (dollar bars / volume bars / imbalance bars).
**Por qué:** evitar *oversampling* en horas muertas y capturar mejor *impulses/flushes/halts* típicos de runners. (Cap. *Financial Data Structures*, M. López de Prado).
**Decisión:** usa **Dollar Imbalance Bars (DIB)** y/o **Volume Imbalance Bars (VIB)** sobre trades de Polygon; tamaño relativo al float y RVOL del ticker.

**Encaje en el pipeline:** etapa 2, inmediatamente tras cargar trades/quotes.
**Impacto en tus patrones:** mejora la detección de **VWAP reclaim/rejection, panic bounces, late day fade** al reducir ruido y sesgo temporal.  

---

## 3) Feature Engineering (sobre barras + diario)

**Técnicos (intraday & daily):**

* VWAP, distancias a VWAP/J-lines; %gap open; HOD/LOD retests.
* RVOL, burst ratio, spike z-scores; momentum por rango.
* Microestructura (de quotes): spread, mid-price, order-flow/imbalance.
  **Fundamentales/Contexto:**
* Market cap, float, *operating cash flow* (señal de financiamiento). 
* Corporate actions (splits/reverse).
  **Catalizadores:**
* News sentiment/PR tags; *hot sectors* (desde News).

**FFD (Fractionally Differentiated Features)**

* Aplica **FFD** a features no estacionarias para **hacerlas estacionarias sin matar la memoria** (clave para ML). Determina *d* mínimo que pasa ADF (p<0.05) con **FFD fixed-width** (Snippet 5.3/5.4). Úsalo p.ej. en log-price cumulativo, VWAP cumulativo, etc. 

---

## 4) Detección de eventos (rule-based, prepara las etiquetas)

**Eventos alineados a tu Playbook:** *IMPULSE_UP, First Red Day, Red→Green/Green→Red, VWAP Reclaim/Reject, Overextended Gap Down, Late Day Fade, Bounce*… (definiciones y confirmaciones en tus módulos).  
**Entradas:** barras informacionales + features + reglas (volumen relativo, pérdida/recuperación de niveles, gap%…).
**Salida:** `events.parquet` con timestamps y ventanas [t0, t1].

---

## 5) Labeling (Triple Barrier) — *core* de ML

**Qué es:** para cada evento/instante, define **tres barreras** (profit-taking superior, stop inferior, time-out vertical) **proporcionales a la volatilidad** y a la granularidad de tus barras.
**Encaje:** después de detectar eventos, para construir **labels robustas** (continuación/reversión) sin *look-ahead bias*.
**Relación con estrategias:** mapea *First Red Day, OGD, LDF* a barreras asimétricas si procede; *Gap & Go, VWAP reclaim* a barreras más agresivas en la superior. (Tu libro de setups indica triggers/confirmaciones; Triple Barrier formaliza la etiqueta).  

---

## 6) Sample Weighting (+ Sequential Bootstrap)

**Problema:** los eventos **se solapan** (no IID).
**Solución:** pondera por **unicidad** (porción de retorno “no compartida”), magnitud de retorno e **incluye time-decay**; y selecciona *batches* con **sequential bootstrap** para reducir redundancia.
**Encaje:** justo **tras** el labeling, **antes** de entrenar el modelo.
**Efecto:** evita que un *mega-runner* (p. ej. “supernova”) domine el aprendizaje. (Cap. *Sample Weights*).

---

## 7) Meta-Labeling (opcional pero recomendado)

Usa un meta-modelo para filtrar señales del modelo primario (ej.: solo ejecutar *longs* cuando probabilidad > umbral condicionado a volatilidad/float/SSR). **Beneficio:** reduce falsos positivos en *pumps*.

---

## 8) Entrenamiento y validación

* Particionado **time-series** (walk-forward con *purged k-fold*).
* Modelos: tree ensembles (LightGBM/XGBoost) + *calibration*.
* Métricas: precision@k por patrón, utility ajustada por *borrow fees* (shorts) y *slippage*.

---

## 9) Producción (diario + live)

* **Job diario (EOD):** universo, ingesta, features, FFD, eventos, etiquetas, retrain si toca.
* **Job intradía (live):** ingesta 1m/tick, actualización de barras VWAP/DIB/VIB, scoring señales (Gap & Go, VWAP reclaim, LDF…), control de riesgo.
* **Monitores de dilución:** alertas si EDGAR publica S-1/S-3/424B/ATM o PIPE (tu Q&A de Dilución subraya su impacto operativo). 

---

# 📥 Datos concretos a descargar de Polygon (checklist)

## A. Universo y referencia

* `/v3/reference/tickers` (todos los tickers activos e inactivos; evita sesgo de supervivencia).
* `/v3/reference/tickers/{T}` (cap, shares/float si disponible, detalles de listing).
* `/v3/reference/splits`, `/v3/reference/dividends` (splits/reverse/acciones corporativas).

## B. Precio/volumen

* **Diario:** `/v2/aggs/ticker/{T}/range/1/day/{from}/{to}` (≥10–20 años).
* **Intraday:** `/v2/aggs/ticker/{T}/range/1/minute/{from}/{to}` (toda la historia disponible).
* **Tick-level (opcional pero recomendado):** `/v3/trades/{T}` y `/v3/quotes/{T}` (para spread/VWAP exacto, DIB/VIB, microestructura).

## C. Noticias / catalizadores

* `/v2/reference/news` filtrado por tickers y fechas (catalizador + *hot sector*).

> **Lo que NO viene “completo” en Polygon y debes complementar:**
>
> * **Filings de dilución** (S-1, S-3, 424B, ATM, PIPE, warrants, lockups) → **SEC EDGAR** (indispensable para tu framework de dilución y *account builders*). 
> * **Short Sale Restriction (SSR)** y *short interest* granular → FINRA/Nasdaq (opcional para features).

---

# 🧩 ¿Dónde encajan exactamente los 4 conceptos?

1. **Bar Construction** → **Etapa 2**
   Transforma *trades* Polygon en **Dollar/Volume/Imbalance Bars**. Base para todo lo intradía (VWAP, reclaim/reject, LDF, panic bounces). Mejora señal/ruido de tus **setups** (Long/Short Playbooks).  

2. **Triple Barrier** → **Etapa 5 (Labeling)**
   Genera etiquetas objetivas por evento: *continuación* vs *reversión* vs *timeout*, con umbrales ligados a volatilidad. Conecta 1:1 con tus patrones (*First Red Day/OGD/LDF* para cortos; *Gap & Go/VWAP Reclaim* para largos).  

3. **Sample Weighting** (+ Sequential Bootstrap) → **Etapa 6 (Pesos & muestreo)**
   Corrige **solapamiento** y sesgo de grandes *runners*; aplica **time-decay** y unicidad para que el modelo no sobre-aprenda casos redundantes.

4. **Fractionally Differentiated Features (FFD)** → **Etapa 3 (Features)**
   Haz **estacionarias** las features **sin borrar su memoria** (elige *d* mínimo que pasa ADF). Especialmente útil con series de nivel (precios, VWAP cumulativo). Implementa **FFD fixed-width** (Snippet 5.3) y encuentra *d* mínimo (Snippet 5.4). 

---

# ❓¿Se puede construir el “Labeling Pipeline” **solo** con Polygon?

* **Sí** para **precio/volumen** (daily/intraday/tick), **barras**, **VWAP**, **volatilidad**, **labeling triple-barrier**, **sample weighting** y **FFD** (toda la mecánica cuantitativa sale de Polygon).
* **No del todo** para **dilución**: los *triggers* (S-1, S-3, 424B, ATM, PIPE, warrants, lockups) hay que **leerlos en la SEC**. Es **clave** en tu Q&A de Dilución para filtrar/ponderar setups *short* y entender *risk on/off* tras *pumps*. 

**Conclusión práctica:** arma el pipeline con Polygon; **enriquece** con un **ingestor EDGAR** que convierta filings recientes en *flags/fechas/montos/precios de exercise*, y añádelos como **features y reglas** de riesgo.

---

# 🗂️ Estructura de carpeta sugerida

```
raw/
  polygon/
    reference/ (tickers.json, details.json)
    daily_ohlcv/{ticker}.parquet
    intraday_1m/{ticker}/{yyyy-mm}.parquet
    trades/{ticker}/{date}.parquet
    quotes/{ticker}/{date}.parquet
  edgar/
    filings/{ticker}/{yyyy}/S1_S3_424B_ATM.json
processed/
  bars/{ticker}/(dollar|volume|imbalance).parquet
  features/{date}/{ticker}.parquet    # (VWAP, RVOL, microestructura, FFD...)
  events/{date}/{ticker}.parquet      # detecciones rule-based
  labels/{date}/{ticker}.parquet      # triple barrier
  weights/{date}/{ticker}.parquet     # uniqueness/time-decay
models/
  artifacts/
reports/
  watchlist_daily.md
```

---

# 🧪 Mapeo rápido de **patrones → datos** (de tus módulos)

| Patrón                          | Datos Polygon necesarios                                   | Complementos                                      |
| ------------------------------- | ---------------------------------------------------------- | ------------------------------------------------- |
| **Gap & Go / Breakout**         | Premarket + 1m OHLCV, VWAP, RVOL                           | —                                                 |
| **Red→Green / Green→Red**       | 1m OHLCV + VWAP + volumen                                  | —                                                 |
| **VWAP Bounce/Reclaim/Reject**  | 1m + VWAP preciso (de ticks) + quotes/spread               | —                                                 |
| **First Red Day**               | Diario + 1m, %extensión previa, volumen decreciente        | —                                                 |
| **Overextended Gap Down (OGD)** | Diario + open gap %, pérdida de prev. close                | —                                                 |
| **Late Day Fade (LDF)**         | 1m tarde sesión, ruptura VWAP/J-lines con vol. decreciente | —                                                 |
| **Offering/Dilution traps**     | —                                                          | **Filings SEC (S-1/S-3/424B/ATM/PIPE/warrants)**  |

(Definiciones operativas de cada setup en tus documentos de Long/Short/Watchlist).   

---

## ✅ Resumen ejecutivo

1. **Descarga de Polygon**: reference, daily, intradía (1m), **trades/quotes**, news, corporate actions.
2. **Construye barras informacionales** (DIB/VIB) → base intradía.
3. **Features** (VWAP, RVOL, microestructura, catalizadores) + **FFD** para estacionar sin perder memoria. 
4. **Eventos** alineados a tu Playbook (determinísticos).  
5. **Triple Barrier** para etiquetas robustas.
6. **Sample Weighting** (+ sequential bootstrap) para no-IID.
7. **Meta-labeling** y entrenamiento walk-forward.
8. **Producción** (EOD + live) con **alertas de dilución** (SEC).

En breve escribimos **el plan técnico “Labeling Pipeline”** en pseudo-código (módulos, inputs/outputs y nombres de tablas) para que el equipo lo implemente directamente con Polygon + un ingestor mínimo de EDGAR.
