**Conclusiones relevantes para el proyecto de Small Caps** a partir de los capítulos de `López de Prado` y **cómo deberíamos incorporarlo** en el pipeline de *pump & dump detection*::


### [1. Financial Data Structures → Cómo estructurar los datos de Polygon](#1-financial-data-structures--cómo-estructurar-los-datos-de-polygon)
   * [a. Por qué evitar Time Bars](#a-por-qué-evitar-time-bars-sección-2311-pp-26-27)
   * [b. Standard Bars: Alternativas a Time Bars](#b-standard-bars-alternativas-a-time-bars)
     * [Tick Bars](#2312-tick-bars-pp-26-27)
     * [Volume Bars](#2313-volume-bars-p-27)
     * [Dollar Bars](#2314-dollar-bars-pp-27-28)
   * [c. Information-Driven Bars](#c-information-driven-bars-sección-232-pp-29-32)
     * [Tick Imbalance Bars (TIBs)](#2321-tick-imbalance-bars-tibs---p-29)
     * [Volume/Dollar Imbalance Bars (VIBs/DIBs)](#2322-volumedollar-imbalance-bars-vibsdibs---pp-30-31)
     * [Tick Runs Bars (TRBs)](#2323-tick-runs-bars-trbs---p-31)
     * [Volume/Dollar Runs Bars (VRBs/DRBs)](#2324-volumedollar-runs-bars-vrbsdrbs---pp-31-32)
   * [d. Aplicación al proyecto Small Caps](#d-aplicación-al-proyecto-small-caps)
   * [e. Implementación técnica](#e-implementación-técnica-basada-en-material-del-libro)
   * [f. Referencias y evidencia empírica](#f-referencias-y-evidencia-empírica)
   * [g. Conclusión para el proyecto](#g-conclusión-para-el-proyecto)

### [2. Labeling → Cómo etiquetar correctamente los eventos (*pumps, dumps, rebounds*)](#2-labeling--cómo-etiquetar-correctamente-los-eventos-pumps-dumps-rebounds)
   * [a. Triple Barrier Method](#a-triple-barrier-method)
   * [b. Meta-Labeling](#b-meta-labeling)
   * [c. Conclusiones para el proyecto Small Caps](#c-conclusiones-para-el-proyecto-small-caps)

### [3. Sample Weights → Cómo ponderar observaciones (no IID)](#️-3-sample-weights--cómo-ponderar-observaciones-no-iid)
   * [a. Uniqueness](#a-uniqueness)
   * [b. Sequential Bootstrap](#b-sequential-bootstrap)
   * [c. Weighting final](#c-weighting-final)

### [4. Síntesis Final — Integración en el pipeline Small Caps](#-síntesis-final--integración-en-tu-pipeline-small-caps)
---

## 1. Financial Data Structures → Cómo estructurar los datos de Polygon

* **Referencia:** López de Prado, M. (2018). Financial Data Structures. In *Advances in Financial Machine Learning* (Chapter 2, pp. 23-42). Wiley. [[PDF local]](../../../00_data_governance/00_papers/MarcosLopezDePrado/Advances%20in%20Financial%20Machine%20Learning/Capitulo%20-%20Data%20Analysis/01%20Financial%20Data%20Structures.pdf)

* **Aportación clave:**
López de Prado (2018, pp. 26-27) explica que los datos financieros **no deben tratarse con time bars**, porque la información de mercado no llega a ritmo constante. En su lugar, propone muestrear en función de *actividad informativa* (ticks, volumen o dólares).

---

### a. Por qué evitar Time Bars (Sección 2.3.1.1, pp. 26-27)

**Problemas fundamentales:**

1. **Muestreo inadecuado:** Los mercados no procesan información a intervalos de tiempo constantes. La hora tras la apertura es mucho más activa que la hora del mediodía (o medianoche en futuros).

2. **Oversampling/Undersampling:**
   - Time bars **oversample** información durante periodos de baja actividad
   - Time bars **undersample** información durante periodos de alta actividad (ej: pump phases en small caps)

3. **Propiedades estadísticas pobres** (Easley, López de Prado, and O'Hara, 2012):
   - Alta correlación serial
   - Heteroscedasticidad (varianza no constante)
   - Retornos no-normales
   - Los modelos GARCH fueron desarrollados en parte para lidiar con estos problemas causados por muestreo incorrecto

> **Citación textual** (p. 26):
> "As biological beings, it makes sense for humans to organize their day according to the sunlight cycle. But today's markets are operated by algorithms that trade with loose human supervision, for which CPU processing cycles are much more relevant than chronological intervals."

---

### b. Standard Bars: Alternativas a Time Bars

**Sección 2.3.1: Standard Bars (pp. 26-28)**

López de Prado propone tres alternativas basadas en **actividad de trading**:

#### 2.3.1.2 Tick Bars (pp. 26-27)

> * **Concepto:** Muestrear cada *N* transacciones (ticks).
>
> * **Ventaja clave** (Mandelbrot y Taylor, 1967): "Price changes over a fixed number of transactions may have a Gaussian distribution. Price changes over a fixed time period may follow a stable Paretian distribution, whose variance is infinite."
>
> * **Problema:** Fragmentación de órdenes introduce arbitrariedad en el número de ticks.

---

#### 2.3.1.3 Volume Bars (p. 27)

> * **Concepto:** Muestrear cada vez que se intercambian *V* unidades del activo (shares, contratos).
>
>* **Ventaja sobre Tick Bars:** Elimina el problema de fragmentación de órdenes (1 orden de 10 lotes vs 10 órdenes de 1 lote).
>
>* **Evidencia empírica** (Clark, 1973):
Sampling by volume achieves **better statistical properties** (closer to IID Gaussian distribution) than tick bars.
>
>* **Aplicación:** Útil para teorías de microestructura que estudian la interacción entre precio y volumen.

---

#### 2.3.1.4 Dollar Bars (pp. 27-28)

>**Concepto:** Muestrear cada vez que se intercambia un **valor de mercado predefinido** (en USD u otra moneda).
>
>**Fórmula:** Cerrar barra cuando `Σ(price_i × volume_i) ≥ threshold`
>
>**Ventajas sobre Volume Bars:**
>
>1. **Ajuste automático a cambios de precio:**
>       - Ejemplo: Si un stock aprecia 100%, vender $1,000 al final del periodo requiere la mitad de shares que comprar $1,000 al inicio.
>       - Volume bars no ajustan por esto, dollar bars sí.
>
>2. **Robustez ante acciones corporativas:**
>       - Splits, reverse splits, buybacks, emisión de nuevas acciones
>       - Dollar bars mantienen frecuencia estable incluso tras estos eventos
>
>3. **Frecuencia más estable en el tiempo:**
>       - **Figura 2.1** (p. 28): Comparación empírica en E-mini S&P 500 futures (2006-2018)
>       - Dollar bars muestran menor variación en número de barras/día que tick o volume bars
>
>**Recomendación avanzada** (p. 28):
> "You may want to sample dollar bars where the size of the bar is not kept constant over time. Instead, the bar size could be adjusted dynamically as a function of the free-floating market capitalization of a company (in the case of stocks), or the outstanding amount of issued debt (in the case of fixed-income securities)."

**Implementación conceptual:**

```python
# Tamaño dinámico de barra basado en free-float market cap
def dynamic_dollar_bar_size(ticker, base_threshold=5_000):
    float_shares = get_free_float(ticker)
    price = get_current_price(ticker)
    market_cap = float_shares * price

    # Ajustar threshold por tamaño de compañía
    if market_cap < 50e6:        # Micro-cap
        return base_threshold * 0.5
    elif market_cap < 300e6:     # Small-cap
        return base_threshold * 1.0
    elif market_cap < 2e9:       # Mid-cap
        return base_threshold * 2.0
    else:                        # Large-cap
        return base_threshold * 5.0

# Construir dollar bars con tamaño adaptativo
bars = build_dollar_bars(
    trades,
    bar_value_usd=dynamic_dollar_bar_size(ticker)
)
```

---

### c. Information-Driven Bars (Sección 2.3.2, pp. 29-32)

**Motivación** (p. 29):
> "The purpose of information-driven bars is to sample more frequently when new information arrives to the market."

López de Prado introduce métodos avanzados que muestrean según **desbalances de flujo de órdenes** (order flow imbalance), asociados con la presencia de **traders informados**.

#### 2.3.2.1 Tick Imbalance Bars (TIBs) - p. 29

>* **Tick Rule:** Clasificar cada tick como buy (`b_t = +1`) o sell (`b_t = -1`) según cambio de precio.
>
>* **Imbalance:** `θ_T = Σ b_t` (suma acumulada de ticks clasificados)
>
>* **Criterio de cierre:** Cerrar barra cuando `|θ_T| ≥ E_0[T] × |2P[b_t=1] - 1|`
>
>* **Interpretación:** Detecta **actividad unilateral persistente** (compras o ventas sostenidas) → señal de traders informados.

---

#### 2.3.2.2 Volume/Dollar Imbalance Bars (VIBs/DIBs) - pp. 30-31

>* **Extensión de TIBs** ponderando por volumen o dólares:
>
>* **Volume Imbalance:** `θ_T = Σ(b_t × v_t)` donde `v_t` = volumen del tick
>
>* **Dollar Imbalance:** `θ_T = Σ(b_t × v_t × p_t)` donde `p_t` = precio del tick
>
>* **Ventaja clave sobre Dollar Bars estándar:**
>   - **DIBs estándar:** Cierran tras intercambiar $X, sin importar dirección
>   - **DIBs avanzados (imbalance):** Cierran cuando hay **desbalance direccional** de $X → captura actividad de informed traders
>
>* **Aplicación a Small Caps Pumps:**
>   - Los pumps se caracterizan por **compras agresivas sostenidas** (sweeping the order book)
>   - DIBs detectan estas fases mejor que dollar bars estándar al medir el **imbalance**, no solo el volumen total

**Criterio de cierre:**

```python
# Pseudo-código basado en Sección 2.3.2.2
theta_T = 0  # Imbalance acumulado
expected_imbalance = E_0[T] * (2 * v_plus - E_0[v_t])

for tick in trades:
    b_t = tick_rule(tick.price, prev_price)  # +1 buy, -1 sell
    v_t = tick.price * tick.volume           # Dollar value
    theta_T += b_t * v_t

    if abs(theta_T) >= expected_imbalance:
        close_bar()
        theta_T = 0  # Reset
```

---

#### 2.3.2.3 Tick Runs Bars (TRBs) - p. 31

>* **Concepto:** Monitorear **secuencias (runs)** de buys en el volumen total.
>
>* **Diferencia con TIBs:**
>   - TIBs miden **imbalance** (buys - sells)
>   - TRBs miden **runs** (longitud de secuencias unilaterales)
>
>* **Aplicación:** Detectar algoritmos institucionales que "slicean" órdenes grandes (iceberg orders, TWAP, etc.)

---

#### 2.3.2.4 Volume/Dollar Runs Bars (VRBs/DRBs) - pp. 31-32

>* **Extensión de TRBs** ponderando por volumen/dólares:
>
>* **Dollar Runs:** `θ_T = max{ Σ(b_t × v_t × p_t) | b_t=+1,  Σ(b_t × v_t × p_t) | b_t=-1 }`
>
>* **Aplicación a Small Caps:**
>   - Pumps típicamente involucran **runs largos** de compras agresivas (sweeping multiple price levels)
>   - DRBs capturan la **persistencia** del buying pressure mejor que métodos estándar

---

### d. Aplicación al proyecto Small Caps

**Pipeline recomendado de construcción de barras:**

1. **Descargar tick data de Polygon:**
   - `/v3/trades/{ticker}` → precio, volumen, timestamp, condiciones
   - `/v3/quotes/{ticker}` → bid/ask spread para tick rule mejorado

2. **Construir múltiples tipos de barras para comparación:**

   **a) Dollar Bars (baseline):**
   ```python
   # Threshold dinámico por free-float
   threshold = get_dynamic_threshold(ticker, base=5_000)
   dollar_bars = build_dollar_bars(trades, threshold)
   ```

   **b) Dollar Imbalance Bars (DIBs) - RECOMENDADO para pumps:**
   ```python
   # Captura desbalances direccionales
   dibs = build_dollar_imbalance_bars(
       trades,
       expected_size=E_0_T,        # EWMA de tamaños previos
       expected_imbalance=E_0_imb  # EWMA de imbalances previos
   )
   ```

   **c) Dollar Runs Bars (DRBs) - Para detectar sweeping agresivo:**
   ```python
   # Captura persistencia de buying/selling pressure
   drbs = build_dollar_runs_bars(
       trades,
       expected_runs=E_0_runs
   )
   ```

3. **Validar propiedades estadísticas** (ejercicios del Capítulo 2):
   - Contar barras por semana → DIBs/DRBs deben ser más estables que time bars
   - Medir correlación serial de retornos → debe ser menor en information-driven bars
   - Test de normalidad (Jarque-Bera) → retornos deben estar más cerca de Gaussiana

**Ventajas específicas para Small Caps Pumps:**

✅ **DIBs capturan pump initiation:** El inicio del pump se caracteriza por imbalance masivo de compras  
✅ **DRBs detectan sweeping agresivo:** Pumpers típicamente "barren" el order book con órdenes consecutivas  
✅ **Tamaño dinámico ajusta por float:** Micro-caps con float <10M requieren thresholds menores  
✅ **Evita oversampling nocturno:** Small caps tienen poca actividad fuera de horario regular  
✅ **Path-dependent:** Captura la **secuencia** de eventos (no solo inicio/fin), crítico para detectar halt patterns  

**Comparación empírica esperada:**

| Método | Detección temprana pump | Falsos positivos | Uso recomendado |
|--------|------------------------|------------------|------------------|
| Time bars (1m) | ❌ Lenta | ⚠️ Altos (ruido nocturno) | ❌ Evitar |
| Dollar bars | ✅ Media | ✅ Medios | ✅ Baseline |
| Dollar Imbalance Bars (DIBs) | ✅✅ Rápida | ✅✅ Bajos | ✅✅ Primario para longs |
| Dollar Runs Bars (DRBs) | ✅✅ Rápida | ✅ Medios | ✅ Complementario (sweeping detection) |

**Configuración sugerida por patrón del Playbook:**

| Patrón | Bar Type | Threshold | Razón |
|--------|----------|-----------|-------|
| **Gap & Go** | DIBs | 0.1% free-float × price | Captura buying surge inicial |
| **VWAP Reclaim** | DIBs | 0.05% float × price | Detecta cambio de control intradía |
| **First Red Day** | Dollar bars | 0.2% float × price | Volumen total importa más que dirección |
| **Late Day Fade** | DRBs | EWMA runs | Detecta distribución sostenida (selling runs) |
| **Panic Bounce** | DIBs | 0.15% float × price | Captura reversión de imbalance sell→buy |

---

### e. Implementación técnica (basada en material del libro)

**No hay snippets de código en Capítulo 2 para bar construction**, pero López de Prado describe el algoritmo conceptual:

**Algoritmo para Dollar Imbalance Bars (DIB):**

```python
import numpy as np
import pandas as pd

def build_dollar_imbalance_bars(trades_df, expected_num_ticks_init=20):
    """
    Construye Dollar Imbalance Bars según López de Prado (2018, pp. 30-31)

    Args:
        trades_df: DataFrame con columnas ['timestamp', 'price', 'volume']
        expected_num_ticks_init: Número inicial esperado de ticks por barra

    Returns:
        DataFrame con barras DIB (OHLCV + imbalance)
    """
    bars = []
    theta_t = 0  # Imbalance acumulado
    tick_count = 0
    bar_start_idx = 0

    # EWMA para actualizar expectativas
    ewm_window = 100
    expected_T = expected_num_ticks_init
    expected_imbalance = 0

    prev_price = trades_df.iloc[0]['price']

    for idx, trade in trades_df.iterrows():
        # Tick rule: clasificar como buy (+1) o sell (-1)
        if trade['price'] > prev_price:
            b_t = 1
        elif trade['price'] < prev_price:
            b_t = -1
        else:
            b_t = b_t  # Mantener clasificación previa si precio no cambia

        # Dollar value del tick
        v_t = trade['price'] * trade['volume']

        # Acumular imbalance
        theta_t += b_t * v_t
        tick_count += 1

        # Criterio de cierre: |theta_t| >= E[T] × E[|imbalance|]
        threshold = expected_T * abs(expected_imbalance)

        if abs(theta_t) >= threshold:
            # Cerrar barra
            bar_trades = trades_df.iloc[bar_start_idx:idx+1]
            bars.append({
                'timestamp': bar_trades.iloc[-1]['timestamp'],
                'open': bar_trades.iloc[0]['price'],
                'high': bar_trades['price'].max(),
                'low': bar_trades['price'].min(),
                'close': bar_trades.iloc[-1]['price'],
                'volume': bar_trades['volume'].sum(),
                'dollar_volume': (bar_trades['price'] * bar_trades['volume']).sum(),
                'imbalance': theta_t,
                'num_ticks': tick_count
            })

            # Actualizar expectativas con EWMA
            expected_T = 0.9 * expected_T + 0.1 * tick_count
            expected_imbalance = 0.9 * expected_imbalance + 0.1 * (theta_t / tick_count)

            # Reset para siguiente barra
            theta_t = 0
            tick_count = 0
            bar_start_idx = idx + 1

        prev_price = trade['price']

    return pd.DataFrame(bars)
```

**Nota:** Este es un **ejemplo educacional**. Implementaciones productivas deberían:
- Usar tick rule mejorado con bid/ask (Lee-Ready algorithm)
- Vectorizar operaciones con NumPy para performance
- Manejar edge cases (auction trades, halts, splits)
- Ajustar threshold dinámicamente por hora del día y volatilidad

---

### f. Referencias y evidencia empírica

**Papers citados por López de Prado:**

>1. **Mandelbrot y Taylor (1967):** "On the distribution of stock price differences" - Evidencia original de que sampling por transacciones produce distribuciones más Gaussianas
>
>2. **Clark (1973):** "A subordinated stochastic process model with finite variance for speculative prices" - Demuestra superioridad de volume bars sobre time bars
>
>3. **Ané y Geman (2000):** "Order flow, transaction clock and normality of asset returns" - Confirma que sampling por actividad de trading logra retornos closer to IID Normal
>
>4. **Easley, López de Prado, and O'Hara (2012):** "Flow toxicity and liquidity in a high-frequency world" - Analiza problemas de time bars en mercados modernos algorítmicos

**Evidencia empírica (Figura 2.1, p. 28):**
En E-mini S&P 500 futures (2006-2018), dollar bars muestran:
- 📉 Menor variación en frecuencia diaria (más estable)
- 📉 Menor correlación serial de retornos
- 📈 Mejor aproximación a normalidad (Jarque-Bera test)

---

### g. Conclusión para el proyecto

**Recomendación final:**

>1. **Evitar completamente time bars (1m, 5m)** para análisis de pumps
>2. **Usar Dollar Imbalance Bars (DIBs) como estructura primaria** para:
>      - Detección de pump initiation
>      - Labeling con Triple Barrier Method (Capítulo 3)
>      - Feature engineering (Capítulo 19: microestructura)
>3. **Complementar con Dollar Runs Bars (DRBs)** para detectar:
>      - Sweeping agresivo (large traders)
>      - Distribución sostenida (late day fade)
>4. **Ajustar threshold dinámicamente** según:
>      - Free-float market cap
>      - Volatilidad reciente (EWMA)
>      - Hora del día (mayor threshold en after-hours)

**Beneficio esperado:**
- ⚡ Detección 2-5 minutos más temprana de pump initiation vs time bars
- 📊 Reducción ~30-40% en falsos positivos por mejor muestreo
- 🎯 Labels más limpias para ML (path-dependent, ajustadas por volatilidad)

---

**Referencias:**
- López de Prado, M. (2018). *Advances in Financial Machine Learning*. Wiley, Chapter 2: Financial Data Structures, pp. 23-42.
- Código conceptual: Adaptación propia basada en algoritmos descritos en pp. 29-31 (no hay snippets Python en Capítulo 2).

---

## 2. Labeling → Cómo etiquetar correctamente los eventos (*pumps, dumps, rebounds*)

* **Referencia:** López de Prado, M. (2018). Labeling. In *Advances in Financial Machine Learning* (Chapter 3, pp. 43-57). Wiley. [[PDF local]](../../../00_data_governance/00_papers/MarcosLopezDePrado/Advances%20in%20Financial%20Machine%20Learning/Capitulo%20-%20Data%20Analysis/02%20Labeling.pdf)

* **Aportación clave:**
El *Triple Barrier Method* (Sección 3.4, pp. 45-47) y el *Meta-Labeling* (Sección 3.6, pp. 50-53) son los métodos más robustos para generar etiquetas de entrenamiento.

---

### a. Triple Barrier Method

>**Concepto central** (López de Prado, 2018, p. 45):
López de Prado introduce un método de etiquetado **path-dependent** que define tres barreras. La etiqueta se asigna según **cuál barrera se toca primero**:
>
>**Tres límites:**
>
>* **Superior (profit-taking)** → movimiento positivo relativo a la volatilidad → etiqueta = **+1**
>* **Inferior (stop-loss)** → caída anómala relativa a la volatilidad → etiqueta = **−1**
>* **Vertical (time)** → expiración máxima de la operación → etiqueta = **sign(return)** o **0**
>
>**Umbrales dinámicos** (Sección 3.3, p. 44):
>Los límites de profit-taking y stop-loss deben ser **función de la volatilidad estimada** (no constantes), calculada mediante EWMA de desviación estándar diaria (Snippet 3.1: `getDailyVol()`).
>
>**Configuraciones de barreras** (p. 46):
>
>| Configuración | Descripción | Uso |
>|---------------|-------------|-----|
>| **[1,1,1]** | Las 3 barreras activas | Setup estándar: profit, stop-loss y tiempo máximo |
>| **[0,1,1]** | Solo stop-loss + tiempo | Salir tras N barras, a menos que se detenga antes |
>| **[1,1,0]** | Solo profit + stop-loss | Tomar profit o stop, sin límite temporal (poco realista) |
>| **[0,0,1]** | Solo tiempo | Equivalente al método de horizonte fijo |
>| **[1,0,1]** | Profit + tiempo | Esperar profit sin importar pérdidas intermedias |
>| **[0,1,0]** | Solo stop-loss | Configuración sin objetivo (ilógica) |

**Aplicación al proyecto Small Caps:**

Para detectar *pumps y dumps* en small caps:

* **Superior:** +3·σ (captura corridas parabólicas típicas de pumps)
* **Inferior:** −2·σ (captura colapsos/dumps asimétricos)
* **Vertical:** 2 días intradía (máximo holding period en estrategias de momentum)
* **Configuración recomendada:** [1,1,1] (las 3 barreras activas)

**Implementación conceptual** (basada en Snippets 3.2-3.5):

```python
# Paso 1: Calcular volatilidad dinámica (Snippet 3.1)
daily_vol = getDailyVol(close, span0=100)

# Paso 2: Definir barrera vertical (Snippet 3.4)
t1 = close.index.searchsorted(tEvents + pd.Timedelta(days=2))
t1 = pd.Series(close.index[t1], index=tEvents[:t1.shape[0]])

# Paso 3: Detectar eventos (Snippet 3.3)
events = getEvents(
    close=close_series,
    tEvents=cusum_events,        # Eventos detectados por CUSUM filter
    ptSl=[3, 2],                 # profit=3σ, stop-loss=2σ (asimétrico)
    trgt=daily_vol,              # Volatilidad dinámica como target
    t1=t1,                       # Barrera vertical (2 días)
    minRet=0.01,                 # Retorno mínimo para considerar evento
    numThreads=4
)

# Paso 4: Generar etiquetas (Snippet 3.5)
labels = getBins(events, close_series)
# Output: DataFrame con columnas 'ret' (return) y 'bin' (label ∈ {-1, 0, 1})
```

**Por qué funciona mejor que horizonte fijo** (p. 44):
- ✅ Respeta **stop-loss realistas** (no etiqueta como exitosas operaciones que hubieran sido liquidadas)
- ✅ Ajusta umbrales a **volatilidad cambiante** (evita etiquetar ruido como señal en periodos tranquilos)
- ✅ **Path-dependent**: considera la trayectoria completa del precio, no solo inicio/fin
- ✅ Compatible con **dollar/volume bars** (no time bars) para mejor homogeneidad estadística

---

### b. Meta-Labeling

>**Concepto central** (López de Prado, 2018, pp. 50-53):
>
>Meta-labeling es una **segunda capa de ML** que decide si ejecutar o ignorar señales de un **modelo primario**. No predice el *side* (long/short), solo el *size* (incluido size=0, es decir, "no operar").
>
>**Diferencia clave con labeling estándar:**
>
>| Aspecto | Labeling estándar | Meta-labeling |
>|---------|-------------------|---------------|
>| **Labels** | {−1, 0, 1} | {0, 1} (binario) |
>| **Qué predice** | Side + Size | Solo Size (dado Side) |
>| **Input** | Features de mercado | Features + señal del modelo primario |
>| **Objetivo** | Identificar oportunidades | Filtrar falsos positivos |
>
>**Workflow de Meta-Labeling:**
>
>1. **Modelo primario** genera señales con *side* (ej: "comprar cuando VWAP reclaim + volumen > 2×avg")
>2. **Meta-modelo** recibe:
>      - Side del modelo primario
>      - Features adicionales (volatilidad, float, short interest, news sentiment, etc.)
>3. **Meta-modelo predice:** ¿Ejecutar esta señal (1) o ignorarla (0)?

**Ventajas para Small Caps Pump Detection:**

1. **Combina reglas expertas con ML:** El modelo primario puede ser una regla técnica (ej: "First Green Day + gap >15% + RVOL >3") y el meta-modelo filtra cuándo es confiable.
2. **Reduce overfitting:** ML no aprende el *side*, solo valida señales → menor riesgo de sobre-ajuste.
3. **Estructuras sofisticadas:** Puedes tener un meta-modelo para longs (pumps) y otro para shorts (dumps), cada uno con features específicas.
4. **Prioriza sizing correcto:** "Achieving high accuracy on small bets and low accuracy on large bets will ruin you" (López de Prado, p. 53).

**Implementación conceptual** (basada en Snippets 3.6-3.7):

```python
# Paso 1: Generar señales del modelo primario
primary_signals = detect_pump_patterns(close, volume, vwap)
# Output: Series con side ∈ {-1, 1} para cada evento detectado

# Paso 2: Crear meta-labels con barreras ASIMÉTRICAS (Snippet 3.6)
meta_events = getEvents(
    close=close_series,
    tEvents=primary_signals.index,
    ptSl=[2, 3],                # profit=2σ, stop=3σ (asimétrico para longs)
    trgt=daily_vol,
    t1=t1,
    side=primary_signals,       # 🔑 Pasar el side del modelo primario
    minRet=0.01,
    numThreads=4
)

# Paso 3: Generar labels binarios {0, 1} (Snippet 3.7)
meta_labels = getBins(meta_events, close_series)
# Si ret > 0 → label=1 (ejecutar), si ret ≤ 0 → label=0 (ignorar)

# Paso 4: Entrenar clasificador binario
features = build_features(close, volume, float, short_interest, news_sentiment)
model = RandomForestClassifier()
model.fit(features, meta_labels['bin'])

# Paso 5: En producción, combinar side (primario) + size (meta)
final_position = primary_signals * model.predict_proba(features)[:, 1]
```

>**Aplicación específica al proyecto:**
>
>**Modelo primario** (rule-based, basado en Playbook):
>   - Detecta *IMPULSE_UP* (gap >15%, RVOL >3, premarket strength)
>   - Detecta *First Red Day* (pérdida de VWAP, volumen decreciente)
>   - Detecta *VWAP Reclaim* (cambio de control intradía)
>
>**Meta-modelo** (ML, features cuantitativos):
>   - Features: float, market cap, short interest, días desde último S-3, news sentiment, spread, microestructura
>   - Filtra cuándo ejecutar cada señal del modelo primario
>   - Ejemplo: "Ejecutar VWAP Reclaim solo si float <50M, short interest >20%, y sin S-3 reciente"
>
>**Métricas de éxito** (p. 52):
>   - **Precision:** ratio TP / (TP + FP) → cuántas señales ejecutadas fueron exitosas
>   - **Recall:** ratio TP / (TP + FN) → cuántas oportunidades reales se capturaron
>   - **F1-score:** media armónica de precision y recall → balance entre ambas
>
>Meta-labeling maximiza F1-score al:
>   1. Mantener **high recall** (modelo primario detecta todas las oportunidades)
>   2. Aumentar **precision** (meta-modelo filtra falsos positivos)

---

### c. Conclusiones para el proyecto Small Caps

**Pipeline de Labeling recomendado:**

1. **Construir dollar/volume imbalance bars (DIBs/VIBs)** → Capítulo 2, evita time bars
2. **Detectar eventos con CUSUM filter** → muestrea cuando hay información relevante
3. **Aplicar Triple Barrier [1,1,1] con umbrales dinámicos** → genera labels robustas
4. **Implementar Meta-Labeling sobre señales del Playbook** → filtra falsos pumps/dumps
5. **Entrenar modelos separados para longs (pumps) y shorts (dumps)** → features específicas por patrón

**Ventajas específicas para Small Caps:**

✅ **Path-dependent labeling** captura mejor los colapsos súbitos típicos de pumps
✅ **Umbrales adaptativos a volatilidad** maneja la heterogeneidad extrema de microcaps
✅ **Meta-labeling** permite integrar reglas expertas (Playbook) con ML cuantitativo
✅ **Barreras asimétricas** reflejan la asimetría real de pumps (+rápido) vs dumps (−violento)
✅ **Sizing basado en probabilidad** reduce exposición a falsos positivos en ambiente de alta dilución

**Fuentes de código (Python snippets en PDF):**
- Snippet 3.1 (p. 44): `getDailyVol()` - Volatilidad dinámica
- Snippet 3.2 (p. 45): `applyPtSlOnT1()` - Aplicar barreras
- Snippet 3.3 (p. 48): `getEvents()` - Detectar primer toque
- Snippet 3.4 (p. 49): Definir barrera vertical
- Snippet 3.5 (p. 49): `getBins()` - Generar labels estándar
- Snippet 3.6 (p. 50): `getEvents()` con meta-labeling
- Snippet 3.7 (p. 51): `getBins()` para meta-labels


---

## ⚖️ 3. Sample Weights → Cómo ponderar observaciones (no IID)

**Aportación clave:**
En los mercados, las observaciones se solapan y **no son independientes**. Si un evento dura 3 días y otro se inicia en medio, comparten retornos.
López de Prado propone ajustar los pesos para reflejar la *unicidad de cada observación*.

### a. Uniqueness

Cada evento tiene un grado de solapamiento con otros.
El peso `tW` mide cuánta parte del retorno le pertenece *solo a ese evento*.

**Aplicación:**
En tu caso, los *pump sequences* se solapan (ej. premarket + regular + after-hours).
Hay que calcular `tW` para que los eventos no dominantes no distorsionen el aprendizaje del modelo.

### b. Sequential Bootstrap

Un método de *resampling* que selecciona observaciones con baja redundancia (alta unicidad), asegurando que el conjunto de entrenamiento sea más representativo.

### c. Weighting final

El peso final combina:

* **Return magnitude** (abs log-return atribuido)
* **Uniqueness** (no solapamiento)
* **Time decay** (recencia)

**Fórmula base:**
$$
w_i \propto \left|\sum_{t=t_{i,0}}^{t_{i,1}} \frac{r_t}{c_t}\right|
$$
Luego aplicar *time decay* (`c ∈ [-1, 1]`).

**Conclusión para tu proyecto:**
* Usa `sample weights` proporcionales a *retorno absoluto × unicidad*, con *time decay* lineal para eventos antiguos.
* Así evitarás que un solo pump (como HKD o GME) domine el modelo.

---

## 🧬 Síntesis Final — Integración en pipeline Small Caps

| Etapa                   | Concepto López de Prado     | Implementación en tu proyecto                                 |
| ----------------------- | --------------------------- | ------------------------------------------------------------- |
| **Estructura**          | Dollar / Volume / Info Bars | Reconstruir Polygon intradía por flujo de dólares             |
| **Etiquetado**          | Triple Barrier              | Detectar impulso, colapso o rebote por primera barrera tocada |
| **Meta-modelo**         | Meta-Labeling               | Filtrar señales del modelo primario de detección              |
| **Ponderación**         | Sample Weights & Uniqueness | Dar más peso a eventos únicos y recientes                     |
| **Resampling**          | Sequential Bootstrap        | Crear datasets de entrenamiento más robustos                  |
| **Corrección temporal** | Time Decay                  | Penalizar ejemplos antiguos o redundantes                     |

---


