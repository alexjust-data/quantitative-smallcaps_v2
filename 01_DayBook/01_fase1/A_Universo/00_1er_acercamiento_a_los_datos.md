Lee todos los archivos (el README antiguo, el PlayBook PDF, los módulos de *Long Plays*, *Short Plays*, *Largo vs Corto*, *Construcción del Watchlist* y el Q&A sobre Dilución). 

# 🧠 Small Caps Pump & Dump Detection & Trading Framework

Sistema integral para **detección, análisis y ejecución algorítmica de patrones *pump & dump* en acciones *small caps***.
El proyecto combina **bases técnicas, fundamentales y de comportamiento**, integrando los principios del *Playbook Latin Day Trading* con infraestructura moderna de *data science* y machine learning.

---

## 🎯 Objetivo General

Construir un pipeline cuantitativo capaz de:

1. **Detectar automáticamente** los patrones característicos de *small caps runners* (corridas, destrucción y rebote).
2. **Clasificar eventos** (*IMPULSE_UP*, *FIRST_RED_DAY*, *BOUNCE*, *DILUTION*, etc.).
3. **Entrenar modelos ML** sobre datos reales de Polygon.io para predecir comportamiento intradía.
4. **Ejecutar estrategias algorítmicas** basadas en confirmaciones técnicas, volumen y estructura.

---

## 🧩 Universo de Compañías a Descargar (Polygon.io)

De acuerdo con el *Playbook*, los *small caps* presentan:

* Flujos de caja negativos y necesidad de financiamiento externo.
* Presencia frecuente de **S-3, 424B, ATM, PIPEs y warrants**.
* Alta volatilidad con floats pequeños.
* Ciclos predecibles: *spike → dump → rebote → muerte*.

### 🎚️ Filtros base del universo (Finviz/Polygon equivalentes)

| Criterio                      | Valor                            |
| ----------------------------- | -------------------------------- |
| **Market Cap**                | `< 2B USD` *(Small o Micro Cap)* |
| **Float**                     | `< 100M` *(ideal < 60M)*         |
| **Precio**                    | `$0.5 – $20`                     |
| **Cambio diario**             | `> +15%`                         |
| **Volumen diario**            | `> 500k` *(ideal > 1M)*          |
| **Cash Flow Operativo (TTM)** | Negativo o marginal              |
| **Filings recientes**         | S-3, 424B, ATM o PIPE activos    |
| **Exchange**                  | NASDAQ o NYSE *(OTC opcional)*   |

> 🔍 *La meta es capturar el comportamiento de empresas deficientes en fundamentales pero ricas en momentum técnico.*

---

## 🧮 Datos a Descargar de Polygon.io

### 1. **Core Market Data**

| Tipo                       | Endpoint                                   | Descripción                        | Uso Estratégico                                      |
| -------------------------- | ------------------------------------------ | ---------------------------------- | ---------------------------------------------------- |
| **Daily Bars (1d)**        | `/v2/aggs/ticker/{ticker}/range/1/day/`    | 20 años de OHLCV ajustado          | Identificar *First Green/Red Days*, *supernovas*     |
| **Intraday (1m, 5m)**      | `/v2/aggs/ticker/{ticker}/range/1/minute/` | Series de alta resolución          | Detectar *VWAP reclaim*, *late-day fade*, *gap runs* |
| **Trades & Quotes**        | `/v3/trades`, `/v3/quotes`                 | Tick-by-tick, bid/ask, condiciones | Análisis microestructural: delta, spread, liquidez   |
| **Snapshots / Aggregates** | `/v2/snapshot/locale/us/markets/stocks`    | Vista general en tiempo real       | Screening rápido de *gappers*                        |

---

### 2. **Reference & Fundamentals**

| Tipo                  | Endpoint                                          | Descripción                             | Uso                                                |
| --------------------- | ------------------------------------------------- | --------------------------------------- | -------------------------------------------------- |
| **Reference Tickers** | `/v3/reference/tickers`                           | Listado de activos activos + delistados | Crear universo limpio y sin sesgo de supervivencia |
| **Ticker Details**    | `/v3/reference/tickers/{ticker}`                  | Float, Market Cap, Sector, Exchange     | Clasificación y segmentación                       |
| **Financials**        | `/vX/reference/financials`                        | Income, Balance Sheet, Cash Flow        | Detectar déficits y riesgo de financiamiento       |
| **Corporate Actions** | `/v3/reference/splits`, `/v3/reference/dividends` | Splits, reverse splits                  | Indicadores de manipulación o dilución             |
| **News**              | `/v2/reference/news`                              | Noticias con *sentiment*                | Detectar *hot sectors*, PRs o *hype catalysts*     |

---

### 3. **Complementarios Externos**

| Fuente                     | Propósito                            | Ejemplo de integración                             |
| -------------------------- | ------------------------------------ | -------------------------------------------------- |
| **SEC EDGAR API**          | Leer *S-3*, *424B*, *S-1*, *8-K*     | Detectar ofertas y dilución                        |
| **FINRA Short Volume**     | Cortos minoristas / SSR activaciones | Confirmar *short squeeze* o *frontside exhaustion* |
| **Nasdaq Halts RSS**       | Suspensiones y *resumptions*         | Marcado de eventos en timelines                    |
| **Yahoo Finance / BAMSEC** | Confirmar Float, Cash Flow, Filings  | Validación cruzada de datos Polygon                |

---

## ⚙️ Integración con el *Playbook*

Cada patrón del *Playbook* requiere datos específicos:

| Patrón                       | Datos críticos de Polygon          | Confirmaciones                              |
| ---------------------------- | ---------------------------------- | ------------------------------------------- |
| **Breakout / Gap & Go**      | OHLCV 1m + premarket gap + volumen | Ruptura con volumen > 2× promedio           |
| **Red to Green**             | 1m bars + VWAP intradía            | Cambio de control intradía                  |
| **VWAP Bounce / Reclaim**    | VWAP derivado + trades bid/ask     | Reversión con volumen creciente             |
| **First Red Day / Gap Down** | 1d + news sentiment + filings      | Pérdida de interés tras sobreextensión      |
| **Dip Buy / Panic Bounce**   | 1m trades + delta + spread         | Identificar pánico sin catalizador negativo |
| **Late Day Fade**            | 1m OHLCV + J-lines                 | Ruptura VWAP en sesión tardía               |
| **Dilution / Offering Trap** | SEC filings + fundamental trends   | Detección de S-3/ATM activos                |
| **Halt & Resume Momentum**   | Halts RSS + 1s/1m trades           | Momentum tras *halt resumption*             |

---

## 🧱 Arquitectura de Datos

```
raw/
 ├── market_data/        # OHLCV, trades, quotes
 ├── fundamentals/       # Balance, cash flow
 ├── corporate_actions/  # Splits, dividends
 ├── reference/          # Universe tickers (active + delisted)
 └── news/               # Sentiment and catalysts
processed/
 ├── universe/           # Small caps filtradas
 ├── features/           # Variables técnicas/fundamentales
 └── events/             # Etiquetas de patrones detectados
```

---

## 🧠 Feature Engineering

Basado en el *Playbook técnico + Q&A Dilución*:

| Grupo                   | Ejemplo                                        | Relevancia                              |
| ----------------------- | ---------------------------------------------- | --------------------------------------- |
| **Volumen / Momentum**  | RVOL, %gap, burst ratio, spike z-score         | Confirmar fase de impulso o destrucción |
| **Microestructura**     | Bid-ask spread, imbalance, delta               | Identificar acumulación o distribución  |
| **Fundamentales**       | Cash Flow TTM, deuda/equity, filings recientes | Medir riesgo de financiamiento          |
| **Eventos**             | días desde último S-3 / Split / Halt           | Contextualizar riesgo operativo         |
| **Sentimiento**         | Score positivo/negativo                        | Filtrar *fake PRs* o hype sectorial     |
| **Catalizador técnico** | VWAP reclaim / pérdida VWAP                    | Señales de cambio de control intradía   |

---

## 🧩 Objetivo ML

Aprender la **probabilidad condicional de continuación o reversión** de un *runner*, usando señales combinadas:

[
P(\text{continuación} \mid \text{volumen}, \text{float}, \text{filings}, \text{VWAP}, \text{sentiment})
]

El sistema generará etiquetas automáticas:

| Etiqueta         | Descripción                     |
| ---------------- | ------------------------------- |
| `IMPULSE_UP`     | Inicio de corrida anómala       |
| `FIRST_RED_DAY`  | Primer día de debilidad         |
| `BOUNCE_GREEN`   | Rebote técnico post-dump        |
| `DILUTION_EVENT` | Activación de financiamiento    |
| `HALT_SEQ`       | Secuencia de halts consecutivos |
| `BLOWOFF`        | Parabólico terminal             |

---

## 🧮 Modelo Operativo

1. **Descarga masiva** de datos históricos (20 años × 13k tickers).
2. **Filtro dinámico** diario por volumen, spread, sector y float.
3. **Detección automática de eventos** (scripts `detect_events_intraday.py`, `detect_first_red_day.py`, etc.).
4. **Persistencia y labeling** en `processed/events/`.
5. **Entrenamiento ML** (LightGBM, TCN) sobre datasets etiquetados.
6. **Ejecución en DAS Trader Pro** vía bridge C# / Python.

---

## ⚠️ Riesgos Identificados

| Tipo                    | Riesgo                          | Mitigación                           |
| ----------------------- | ------------------------------- | ------------------------------------ |
| **Dilución**            | Offerings S-3, ATM, PIPEs       | Parsing SEC + news sentiment         |
| **Liquidez**            | Spreads amplios, halts          | Filtrado por volumen y spread máximo |
| **SSR / Short squeeze** | Restricción venta corta         | Señales de reversión confirmadas     |
| **Data Quality**        | Missing timestamps o duplicados | Validación y checkpoints             |
| **Overfitting ML**      | Dependencia temporal            | Walk-forward + purged CV             |

---

## 📚 Referencias

* *Playbook Latin Day Trading* (Módulos 7–8, Q&A Dilución)
* Polygon.io Docs: [https://polygon.io/docs/stocks](https://polygon.io/docs/stocks)
* SEC EDGAR API Docs: [https://www.sec.gov/edgar](https://www.sec.gov/edgar)
* FINRA Short Volume: [https://www.finra.org](https://www.finra.org)
* OTC Markets Screener: [https://www.otcmarkets.com/](https://www.otcmarkets.com/)

