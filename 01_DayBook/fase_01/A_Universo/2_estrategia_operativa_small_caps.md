# Estrategia Operativa de Trading en Small Caps
## Integración del Framework Académico (López de Prado) con el Playbook Táctico (EduTrades)

**Documento de referencia estratégica para operativa algorítmica y manual**

---

## Índice

### [1. Marco Conceptual — Comportamiento de Small Caps](#1-marco-conceptual--comportamiento-de-small-caps)
   * [a. Ciclo de vida típico](#a-ciclo-de-vida-típico)
   * [b. Características fundamentales](#b-características-fundamentales)
   * [c. Patrones de dilución](#c-patrones-de-dilución)

### [2. Principios Operativos Fundamentales](#2-principios-operativos-fundamentales)
   * [a. Comprar en debilidad, vender en fortaleza](#a-comprar-en-debilidad-vender-en-fortaleza)
   * [b. Probabilidad vs Risk-Reward](#b-probabilidad-vs-risk-reward)
   * [c. Adaptación sin bias](#c-adaptación-sin-bias)

### [3. Playbook de Estrategias Long](#3-playbook-de-estrategias-long)
   * [3.1 Breakout](#31-breakout)
   * [3.2 Red to Green](#32-red-to-green)
   * [3.3 VWAP Bounce](#33-vwap-bounce)
   * [3.4 VWAP Reclaim](#34-vwap-reclaim)
   * [3.5 Dip Buying Panics](#35-dip-buying-panics)
   * [3.6 First Green Day (Swing)](#36-first-green-day-swing)
   * [3.7 First Green Day Bounce](#37-first-green-day-bounce)
   * [3.8 Gap and Grab Reversal](#38-gap-and-grab-reversal)
   * [3.9 Gap and Go](#39-gap-and-go)

### [4. Playbook de Estrategias Short](#4-playbook-de-estrategias-short)
   * [4.1 First Red Day (FRD)](#41-first-red-day-frd)
   * [4.2 Overextended Gap Down (OGD)](#42-overextended-gap-down-ogd)
   * [4.3 Short into Resistance (SIR)](#43-short-into-resistance-sir)
   * [4.4 Late Day Fade (LDF)](#44-late-day-fade-ldf)
   * [4.5 Patrones complementarios](#45-patrones-complementarios)

### [5. Construcción del Watchlist Diario](#5-construcción-del-watchlist-diario)
   * [a. Filtros cuantitativos](#a-filtros-cuantitativos)
   * [b. Análisis por ticker](#b-análisis-por-ticker)
   * [c. Herramientas](#c-herramientas)

### [6. Análisis Fundamental — Red Flags de Dilución](#6-análisis-fundamental--red-flags-de-dilución)
   * [a. Shelf (S-3)](#a-shelf-s-3)
   * [b. S-1 Filing](#b-s-1-filing)
   * [c. PIPE (Private Placement)](#c-pipe-private-placement)
   * [d. Warrants y convertibles](#d-warrants-y-convertibles)

### [7. Integración con Framework López de Prado](#7-integración-con-framework-lópez-de-prado)
   * [a. Estructuras de datos óptimas](#a-estructuras-de-datos-óptimas)
   * [b. Labeling con Triple Barrier](#b-labeling-con-triple-barrier)
   * [c. Meta-Labeling para filtrado](#c-meta-labeling-para-filtrado)
   * [d. Sample Weights](#d-sample-weights)

### [8. Pipeline de Implementación ML](#8-pipeline-de-implementación-ml)

---

## 1. Marco Conceptual — Comportamiento de Small Caps

### a. Ciclo de vida típico

El patrón cíclico reconocible en small caps sigue esta secuencia:

```
FASE 1: Dormido         →  Bajo volumen, sin volatilidad (semanas/meses)
FASE 2: Catalizador     →  Noticia/PR/Filing → volumen explosivo
FASE 3: Pump (Extensión) →  Movimiento parabólico (ej: $5 → $70)
FASE 4: Dump (Destrucción)→ Pérdida ~50% del avance en 1-2 días
FASE 5: Rebote (Bounce)  →  First Green Day bounce (~20-40% recovery)
FASE 6: Muerte          →  Retorno a niveles iniciales, dormido
```

**Tiempo promedio del ciclo:** 5-15 días desde inicio del pump hasta regreso al nivel base.

**Implicación operativa:** Las mejores oportunidades están en **FASE 3 (primeros días del pump)** y **FASE 4 (First Red Day shorts)**.

---

### b. Características fundamentales

Las small caps que generan este patrón comparten:

| Característica | Criterio | Impacto |
|----------------|----------|---------|
| **Market Cap** | < $300M (idealmente < $100M) | Mayor manipulabilidad |
| **Float** | < 50M acciones (ideal < 20M) | Alta volatilidad |
| **Fundamentales** | Operating Cash Flow negativo | Necesidad de financiamiento |
| **Dilución activa** | S-3, ATM, Warrants, Convertibles | Presión bajista latente |
| **Institutional Ownership** | 40-50% (óptimo para longs) | Estabilidad relativa |
| **Sector** | Hot sectors: Cannabis, Biotech, EV, AI | Momentum retail |

**Regla de oro:** Estas empresas NO son inversiones. Son **vehículos de trading** con ventana operativa de 3-10 días.

---

### c. Patrones de dilución

**Estadística clave:** El 80% de las compañías que corren con gap se destruyen por dilución.

**Triángulo del pump & dump:**

```
Catalizador (PR/News)
        ↓
Volumen retail entra
        ↓
Precio sube → oportunidad de financiamiento
        ↓
Empresa ejecuta offering/ATM
        ↓
Fondos participan + cubren shorts
        ↓
Precio colapsa → pánico retail
        ↓
Ciclo se reinicia tras 6-12 meses
```

**Fondos recurrentes en offerings:** CBI, Anson, Empery, Bigger Capital, AW Investments
**Underwriters recurrentes:** H.C. Wainwright, Maxim, Aegis, Ladenburg, Think Equity

---

## 2. Principios Operativos Fundamentales

### a. Comprar en debilidad, vender en fortaleza

**Concepto:** El 90% de traders pierde dinero porque opera al revés: compra en breakouts y vende en pánicos.

**Aplicación correcta:**

| Tendencia | Acción correcta | Timing |
|-----------|----------------|--------|
| **Alcista** | Comprar en dips (debilidad) | Cuando toca VWAP o soporte |
| **Alcista** | Vender en extensión (fortaleza) | Cerca de resistencias/HOD |
| **Bajista** | Vender en rallies (fortaleza) | Rechazo de VWAP/resistencia |
| **Bajista** | Cubrir en pánicos (debilidad) | Soporte histórico/oversold |

**Clave temporal:** La tendencia de mayor temporalidad domina. Un soporte diario es más fuerte que uno en velas de 1 minuto.

---

### b. Probabilidad vs Risk-Reward

**Definiciones precisas:**

* **Riesgo:** Punto del gráfico donde se confirma que la tesis está equivocada (NO "lo que estoy dispuesto a perder").

* **Recompensa:** Punto del gráfico hasta donde el precio puede llegar si la tesis se cumple (NO "cuánto quiero ganar").

* **Risk-Reward mínimo aceptable:** 1:2 (arriesgar $0.05 para ganar $0.10+)

**Ejemplo de planificación:**

```
Ticker: GBR
Entrada: $9.40
Riesgo: $9.00 (–4.3%)
Target: $10.32 (+9.8%)
R:R = 1:2.3 → TRADE VÁLIDO
```

**Probabilidad:** Se mide con **spreadsheet tracking** de patrones previos, NO con intuición.

---

### c. Adaptación sin bias

**Regla profesional:** No tener preferencia direccional. Operar según estructura del mercado.

**Evaluación previa a cada trade:**

1. ¿Quién se está equivocando: longs o shorts?
2. ¿El volumen confirma la dirección?
3. ¿La acción del precio respeta/rompe niveles técnicos?
4. ¿Hay momentum en el sector?

**Diferencia Long vs Short en Small Caps:**

| Aspecto | Long | Short |
|---------|------|-------|
| **Probabilidad estadística** | Menor (~35-40%) | Mayor (~60-65%) |
| **Ganancia máxima** | Infinita | 100% |
| **Pérdida máxima** | 100% | Infinita (squeeze) |
| **Disponibilidad** | Fácil | Limitada (shares to borrow) |
| **Fees** | Bajos | Altos (0.5-1.5% diario) |
| **Riesgo operativo** | Bajo | Alto (squeeze, SSR, halts) |

**Conclusión:** Short tiene ventaja estadística pero mayor riesgo. Long tiene peores probabilidades pero pérdidas limitadas.

---

## 3. Playbook de Estrategias Long

### 3.1 Breakout

* **Definición:** Ruptura de resistencia clave con volumen confirmatorio.
* **Condiciones:**

    1. Resistencia clara: 52-week high, HOD anterior, nivel psicológico
    2. Volumen > 2× promedio en la ruptura
    3. Consolidación previa antes del break (evitar fakeouts)

* **Ejecución:**
    * **Entrada:** Primer dip posterior a la confirmación del break (NO en la vela del break)
    * **Stop loss:** Justo debajo del nivel de ruptura
    * **Target:** Extensión promedio del ticker o siguiente número redondo (1.5, 2.0, 2.5, etc.)

* **Evitar:**

    * Breakouts sin volumen
    * Consolidaciones largas (>5 días) sin dirección → indican agotamiento
    * Fases tardías del pump (día 3+)

* **Integración López de Prado:**

    * Usar **Dollar Imbalance Bars (DIBs)** para detectar desbalance de compras en el breakout
    * Aplicar **Triple Barrier** con barreras asimétricas: profit=2.5σ, stop=1.5σ
    * Meta-labeling filtra breakouts con features: float, RVOL, short interest, news sentiment

**Ejemplo de implementación:**

```python
# Detectar breakout con DIBs
dibs = build_dollar_imbalance_bars(trades, expected_size=E_0_T)

# Confirmar volumen > 2× promedio
if dibs['volume'].iloc[-1] > 2 * dibs['volume'].rolling(20).mean().iloc[-1]:
    # Confirmar ruptura de resistencia
    if dibs['close'].iloc[-1] > resistance_level:
        # Esperar primer dip para entrada
        entry_signal = True
```

---

### 3.2 Red to Green

* **Definición:** Acción que abre roja y durante el día logra girar a verde (recupera cierre anterior).

* **Condiciones de calidad:**

    1. Catalizador sólido (PR, earnings, sector caliente)
    2. NO filings activos (S-3, 424B, ATM, warrants recientes)
    3. Float manejable (<50M)
    4. Sin overhead resistance inmediata
    5. Institutional ownership 40-50% (óptimo)

* **Ejecución:**

    * **Entrada:** Primer dip posterior al cruce del nivel Red to Green con volumen creciente
    * **Stop loss:** Bajo mínimo del día o bajo VWAP
    * **Target:** Zonas psicológicas (1.5, 2.0, 2.5) o resistencias previas
    * **Gestión:** Tomar profits parciales; si vuelve a perder el nivel Green→Red, cerrar TODO

* **Por qué funciona:** Atrapa short sellers que apostaron a la debilidad de apertura → **short squeeze intradía**.

* **Timing óptimo:** Primeros días del run. Si ocurre en día 3+, es un bounce menos predecible.

* **Errores comunes:**

    * Entrar antes de la confirmación (comprar en caída libre)
    * Operar sin catalizador o con financing activo
    * No respetar VWAP como soporte crítico

* **Integración López de Prado:**

    * **DIBs** capturan el cambio de imbalance sell→buy al cruzar el nivel R2G
    * **Triple Barrier:** profit=3σ (pumps son explosivos), stop=2σ, tiempo=2 días
    * **Meta-labeling features:** short interest, float, dias desde último S-3, spread bid/ask

---

### 3.3 VWAP Bounce

* **Definición:** Acción verde y sobreextendida hace retroceso al VWAP y rebota.

* **Condiciones:**

    1. Acción verde en el día y >15% sobre VWAP
    2. VWAP actúa como soporte técnico dinámico
    3. Rebote con vela de volumen > barras anteriores

* **Ejecución:**

    * **Entrada:** Dip posterior a la primera vela verde con volumen creciente en el VWAP
    * **Stop loss:** Por debajo del VWAP o mínimo local
    * **Target:** Última resistencia o HOD

* **Evitar:**

    * Caídas violentas donde VWAP no se ha estabilizado
    * Volumen excesivo en velas bajistas (distribución, no consolidación)

* **Timing óptimo:** 30-60 min después de la apertura, cuando el mercado se estabiliza.

* **Integración López de Prado:**

    * **VWAP Bounce = soporte técnico dinámico** → usar como nivel de stop en Triple Barrier
    * Ideal con **Dollar Bars estándar** (no imbalance) porque buscamos consolidación neutral

---

### 3.4 VWAP Reclaim

* **Definición:** Acción que pierde el VWAP lo recupera con volumen alto.

* **Condiciones:**

    1. Acción verde en el día
    2. Perdió temporalmente el VWAP
    3. Recupera con barra de volumen > todas las anteriores del retroceso

* **Ejecución:**

    * **Entrada:** Dip posterior al reclaim, cerca del VWAP
    * **Stop loss:** Justo por debajo del VWAP
    * **Target:** Última resistencia o HOD

* **Nota crítica:** Si la acción está ROJA en el día, este patrón NO es válido para longs (pasa al short playbook).

* **Implicación:** Indica reposicionamiento institucional o cobertura de cortos.

* **Integración López de Prado:**

    * **DIBs** capturan el cambio de imbalance cuando recupera VWAP
    * **Triple Barrier:** profit=2.5σ, stop=1.5σ, tiempo=1 día (patrón intradía rápido)
    * Ideal para detectar **cambio de control** entre vendedores y compradores

---

### 3.5 Dip Buying Panics

* **Definición:** Estrategia avanzada para comprar caídas violentas en pánicos extremos.

* **Condiciones:**

    1. Caída ≥15-20% en pocos minutos
    2. Sin catalizador negativo (no financing, no delisting alert)
    3. Ideal en OTCs donde Level 2 es más legible

* **Ejecución:**

    * **Entrada:** Cuando aparece vela de reversión con volumen de compra > todos los anteriores
      **NUNCA en caída libre (falling knife)**
    * **Stop loss:** Bajo soporte anterior (~10% de riesgo)
    * **Target:** Al menos 2× el riesgo asumido

* **Dificultades:**

    * Timing incierto
    * Alta volatilidad y spreads amplios
    * Requiere experiencia en tape reading

* **Integración López de Prado:**

    * **Usar Dollar Runs Bars (DRBs)** para detectar cuando el selling run se agota
    * **Triple Barrier asimétrico:** profit=2σ, stop=3σ (más permisivo en caída)
    * Features críticas para meta-labeling: VPIN (toxicidad), spread %, distance from support

---

### 3.6 First Green Day (Swing)

* **Definición:** Patrón de swing que captura continuidad después de un día de alta rotación de volumen.

* **Condiciones:**

    1. Cierre cerca de HOD
    2. Volumen rotando el float completo o proporción significativa
    3. Catalizador reciente o sector caliente
    4. Precio sobre VWAP y sin dilución evidente

* **Ejecución:**

    * **Entrada:** Cerca del close con volumen creciente
    * **Mantener overnight:** SOLO si tape y sector confirman fortaleza
    * **Target:** Continuidad en pre-market o día siguiente

* **Gestión de riesgo:**

    * Tomar ganancias parciales en after-hours
    * Evitar mantener posición si volumen post-cierre disminuye bruscamente

* **Integración López de Prado:**

    * **Dollar Bars** para confirmar cierre cerca de HOD con volumen sostenido
    * **Triple Barrier:** profit=2.5σ, stop=2σ, tiempo=overnight hasta apertura siguiente
    * Features: rotation ratio (vol/float), distance from HOD, after-hours volume decay

---

### 3.7 First Green Day Bounce

* **Definición:** Primer rebote verde tras caída del 30-50% de un runner.

* **Condiciones:**

    1. Acción mantiene parte de ganancias previas (no cayó >50%)
    2. Sin catalizadores negativos activos
    3. Señales de reversión con volumen

* **Ejecución:**

    * **Entrada:** Cuando se mantiene verde en el día
    * **Stop loss:** Soporte inmediato o mínimo del día
    * **Target:** Por debajo de la resistencia principal (bajo HOD anterior)

* **Psicología:** Aprovecha la fase de recuperación post-colapso + cobertura de cortos.

* **Integración López de Prado:**

    * **DIBs** detectan cambio de selling pressure a buying pressure
    * **Triple Barrier:** profit=2σ (rebote limitado por overhead resistance), stop=1.5σ, tiempo=1 día
    * Features: days since peak, % retracement from high, short interest coverage ratio

---

### 3.8 Gap and Grab Reversal

* **Definición:** Acción abre roja, forma una "V" y recupera resistencias (reversión agresiva).

* **Condiciones:**

    1. Abre roja con gap bajo cierre anterior
    2. Forma base y rompe hacia arriba
    3. Volumen decrece en caída, aumenta en pickup del reversal

* **Ejecución:**

    * **Entrada:** En el pickup de volumen (inicio del reversal real)
    * **Stop loss:** Bajo low reciente
    * **Target:** Niveles psicológicos o resistencias anteriores

* **Recomendaciones:**

    * Esperar confirmación de la "V"
    * NO anticipar reversal sin cambio en volumen

* **Riesgo:** Es de los más arriesgados pero también más explosivos. Requiere tape reading preciso.

* **Integración López de Prado:**

    * **DRBs** detectan fin del selling run + inicio del buying run
    * **Triple Barrier:** profit=2.5σ, stop=2σ, tiempo=4 horas (patrón intradía volátil)
    * Features críticas: volume at bottom vs volume at pickup, gap size %, time to reversal

---

### 3.9 Gap and Go

* **Definición:** Clásico patrón de apertura en momentum. Breakout del pre-market high y continuación al alza.

* **Condiciones:**

    1. Acción verde en el día
    2. Breakout del pre-market high con volumen
    3. Sector caliente o catalizador relevante

* **Ejecución:**

    * **Entrada:** Rompimiento del nivel pre-market high
    * **Stop loss:** Justo debajo del nivel de ruptura
    * **Target:** Números redondos (1.5, 2.0, 2.5) o siguiente resistencia visible

* **CRÍTICO:** Solo aplicable en **primer día de corrida**. NO en fases tardías o post-parabolic run.

* **Velocidad:** Requiere ejecución precisa. Puede fallar en segundos si breakout no es real.

* **Integración López de Prado:**

    * **DIBs** capturan buying surge al romper pre-market high
    * **Triple Barrier:** profit=3σ (patrón explosivo día 1), stop=1.5σ, tiempo=2 horas
    * Features: pre-market volume, gap size %, RVOL, sector momentum score

---

## 4. Playbook de Estrategias Short

### 4.1 First Red Day (FRD)

* **Definición:** Primer día de debilidad tras corrida de varios días verdes. Primera señal de agotamiento.

* **Criterios principales para shorts:**

    1. **Sobreextensión:** Mínimo 50-60% de subida desde inicio de corrida, idealmente en <5 días
    2. **Dilución activa:** S-3, 424B, ATM, warrants, convertibles, offerings
    3. **Overhead resistance:** Resistencias visibles en gráfico (no ATH)
    4. **Float adecuado:** Evitar micro-floats (<5M) → propensos a squeezes

* **Confirmaciones clave:**

    * Pérdida del control de compradores
    * Volumen del día rojo < volumen del último día verde
    * Idealmente tras subida >50% en pocos días

* **Variantes:**

    | Variante | Descripción | Ejecución |
    |----------|-------------|-----------|
    | **FRD con Gap Up** | Abre por encima del cierre anterior, hace Green→Red y se destruye | Entrada en Green→Red, stop encima del open |
    | **FRD sin Gap** | Abre al nivel del cierre previo, mantiene estructura lateral, luego gira | Entrada cuando pierde VWAP con volumen |
    | **FRD con Gap Down** | Abre 10-15% por debajo del cierre anterior, pérdida inmediata de atención | Entrada en spikes hacia close anterior |

* **Integración López de Prado:**

    * **DIBs** detectan cambio de imbalance buy→sell
    * **Triple Barrier para shorts:** profit=2.5σ down, stop=1.5σ up, tiempo=1 día
    * **Meta-labeling features específicas para FRD:** días de corrida previa, volumen decreciente ratio, distance from VWAP, float rotation ratio

---

### 4.2 Overextended Gap Down (OGD)

* **Definición:** Gap bajista en acción extremadamente sobreextendida. Precio abre bajo cierre anterior y no lo recupera.

* **Condiciones:**

    1. Corrida previa de varios días o subida >100%
    2. Gap Down ≥8-10%
    3. Volumen decreciente

* **Ejecución:**

    * **Entrada:** En los spikes hacia el cierre anterior (previous close)
    * **Stop loss:** Unos centavos por encima del close anterior
    * **Construcción de posición:** Se puede hacer frontside short antes de confirmar debilidad

* **Detalles técnicos:**

    * Puede activar regla **SSR (Short Sale Restriction)** si cae >10% vs cierre previo
    * Con SSR activo: NO se puede atacar el bid → favorece a longs

* **ÚNICO patrón donde se puede shortear el frontside con convicción**, respetando previous close como resistencia crítica.

* **Integración López de Prado:**

    * **Dollar Bars** para medir rechazos repetidos del previous close
    * **Triple Barrier:** profit=3σ down (colapsos violentos), stop=1σ up (tight stop), tiempo=1 día
    * Features: gap size %, days of prior run, distance from peak, SSR status

---

### 4.3 Short into Resistance (SIR)

* **Definición:** Acción intenta romper resistencia previa y falla.

* **Condiciones:**

    1. Acción sobreextendida, con high anterior bien definido
    2. Volumen decreciente al aproximarse al high
    3. HOD anterior actúa como techo

* **Ejecución:**

    * **Entrada:** Primer rechazo del high
    * **Stop loss:** Justo por encima del high
    * **Confirmación:** Volumen NO supera el del día anterior

* **Nota:** Patrón más avanzado, considerado frontside short. Requiere lectura precisa del volumen y paciencia.

* **Integración López de Prado:**

    * **DIBs** detectan imbalance negativo en zona de resistencia (más sells que buys)
    * **Triple Barrier:** profit=2σ down, stop=1σ up (tight, patrón riesgoso), tiempo=6 horas
    * Features: volume at resistance vs yesterday, distance from high, overhead volume profile

---

### 4.4 Late Day Fade (LDF)

* **Definición:** Acción verde pierde fuerza en la tarde, rompiendo J-Lines o VWAP con volumen decreciente.

* **Condiciones:**

    1. Acción con gran sobreextensión (>100%)
    2. Se mantiene alcista toda la mañana respetando VWAP y J-Lines
    3. Entre 13:30-15:00 (hora NY), rompe esos niveles

* **Ejecución:**

    * **Entrada:** Al romper VWAP o J-Lines
    * **Stop loss:** Ligeramente por encima del nivel roto
    * **Target:** Mínimos del día

* **Timing:**

    * Caída suele durar 1-3 horas
    * NO operar este patrón después de 15:30

* **Dificultad:** De los setups más difíciles. Requiere disciplina y evitar shortear acciones fuertes en su primer día verde.

* **Integración López de Prado:**

    * **DRBs** capturan inicio del selling run cuando rompe VWAP
    * **Triple Barrier:** profit=2σ down, stop=1.5σ up, tiempo=2 horas (ventana temporal estrecha)
    * Features críticas: time of day, % extension from morning, volume decay ratio, VWAP slope

---

### 4.5 Patrones complementarios

#### Gap and Crap

* **Definición:** Apertura con gap up fuerte que se revierte rápidamente.

* **Características:**

    * Volumen alto al inicio, drenaje posterior
    * Se trata igual que FRD
    * VWAP y J-Lines actúan como guías de agotamiento

#### Gap and Extension (Stuff Move)

* **Definición:** Rechazo violento en pre-market high (Bull Trap del pre-market).

* **Características:**

    * Gran vela roja tras intento fallido de romper máximo
    * Produce all-day fade
    * Confirmar con barra de volumen ≤ impulso previo

#### Bull Trap

* **Definición:** Breakout fallido que atrapa compradores.

* **Características:**

    * Acción supera resistencia y rápidamente se revierte
    * Genera venta masiva de longs atrapados
    * Se detecta por mecha superior larga + volumen alto de rechazo

#### Green to Red

* **Definición:** Cambio intradía de vela verde a roja.

* **Características:**

    * Señal de pérdida de momentum
    * NO es setup independiente, sino **confirmación** dentro de patrón mayor (FRD o Gap & Crap)

#### VWAP Rejection

* **Definición:** Rechazo repetido del VWAP como resistencia dinámica.

* **Características:**

    * Ideal cuando VWAP está cercano al open
    * Si volumen decrece y no supera VWAP → control de vendedores
    * Si volumen crece → puede implicar Red to Green reversal

---

## 5. Construcción del Watchlist Diario

### a. Filtros cuantitativos

**Plataformas recomendadas:**

| Plataforma | Cobertura | Costo | Ventaja |
|------------|-----------|-------|---------|
| **Finviz.com** | NASDAQ, NYSE | Gratis (delay ~15 min) | Screener robusto |
| **OTCMarkets.com** | OTC | Gratis | Único para OTCs |
| **Interactive Brokers TWS** | Todos | $7-$90/mes (real-time data) | Real-time scanners |
| **ThinkorSwim / StocksToTrade** | Todos | Variable | Integrado con broker |

**Filtros estándar para watchlist:**

```
Market Cap:        < $1B (Small Caps) o < $300M (Micro Caps)
Precio:            < $20 (idealmente $2-$10)
% Cambio diario:   > +15% (ganadoras del día anterior)
Volumen:           > 500K acciones (ideal >1M)
Float:             < 50M acciones (alta volatilidad)
Exclusión:         Evitar subdollar (<$1) salvo excepciones
```

**Proceso nocturno (preparación día siguiente):**

1. Ejecutar screener en Finviz (NASDAQ/NYSE) y OTC Markets (OTCs)
2. Filtrar 10-20 tickers que cumplan criterios
3. Análisis individual de cada ticker (ver sección b)
4. Reducir a 5-7 tickers finales para el día siguiente
5. Complementar en pre-market con gappers (acciones con gap >10%)

---

### b. Análisis por ticker

Para cada ticker filtrado, completar esta checklist:

#### Template de análisis

**1. Sector y contexto:**

* ¿Qué sector? (Health Care, Biotech, Cannabis, Tech, etc.)
* ¿Hot sector actualmente? (ej: Cannabis 2018, EV 2020, AI 2023)
* ¿Relacionado con otro ticker en movimiento?

**2. Catalizador:**

* Press releases recientes (últimos 7 días)
* Earnings
* FDA approval / Clinical trials (Biotech)
* Partnerships / Collaborations
* Sector momentum (sin catalizador individual)

**3. Float:**

* Shares outstanding
* Float (shares disponibles para trading)
* Clasificación: Micro (<10M), Low (<30M), Medium (30-50M), High (>50M)

**4. Fundamentales:**

* Market Cap
* Net Income (últimos trimestres)
* Operating Cash Flow (OCF)
* ¿Ganando o perdiendo dinero?
* ¿Tiene cash para sobrevivir sin offering inmediato?

**5. History Chart:**

* Former runner (¿ha corrido antes?)
* Sobreextensión actual (% desde mínimo reciente)
* Volatilidad histórica (capacidad de hacer bounces)
* Breakouts multianuales / 52-week highs

**6. Filings y dilución:**

* S-3 activo (shelf vigente)
* 424B reciente (offering ejecutado)
* ATM offering
* Warrants (cantidad, exercise price, coverage %)
* Convertible notes
* Form D (PIPE)

**7. Precio actual y acción técnica:**

* ¿Dónde cerró vs HOD? (cerca de highs = fortaleza)
* ¿Volumen vs promedio? (rotó float completo?)
* ¿VWAP respetado como soporte?
* ¿Primer día verde/rojo?

**8. Play propuesto:**

* Escenario 1: Long play (condiciones, entrada, stop, target)
* Escenario 2: Short play (condiciones, entrada, stop, target)
* Niveles clave: soportes, resistencias, warrants exercise prices

**Ejemplo de análisis completado:**

```markdown
## CBSI — Cannabis / Health Care

**Catalizador:** Earnings (20 días atrás) + Board Director announcement + Short Squeeze
**Float:** 80M (medium)
**Cash Flow:** Ganando dinero últimos 3 trimestres (unusual para small cap)
**Market Cap:** $500M
**History:** Sobreextendida de $0.60 → $9.00, tiene volatilidad fuerte (capaz de ir $9→$3.50→$6.80)
**Filings:** 2M warrants convertibles (~2.5% del float, manejable)
**Precio:** Ayer fue First Red Day, hoy puede ser First Green Day Bounce

**Plays:**
1. Long: Si hace soporte en $4.00, entrada en dip hasta HOD anterior (~$7)
2. Long: Comprar pánico hacia $2.60 (zona de soporte fuerte)
3. Short: Si rechaza $7 con volumen decreciente, target $4.50
```

---

### c. Herramientas

#### Twitter: Detección de catalizadores

```
Sintaxis: $TICKER
Ejemplo: $KOSS

Ver:
- Latest (tweets recientes)
- Top (tweets más relevantes)
```

**Uso:** Si no encuentras catalizador en Yahoo Finance o MarketWatch, Twitter suele tener la noticia antes.

#### StockTwits: Feed social de acciones

* Crear watchlist dentro de la plataforma
* Feed personalizado de solo tus tickers
* **ADVERTENCIA:** NO seguir alertas ciegas (riesgo de pumps coordinados)
* Usar SOLO para detectar noticias/rumores, NO para decisiones de entrada

#### Interactive Brokers TWS: Integración StockTwits

```
New Window → More Advanced Tools → News → Stock Tweets
```

Muestra tweets real-time del ticker seleccionado. Útil para información, no para señales de trading.

---

## 6. Análisis Fundamental — Red Flags de Dilución

### a. Shelf (S-3)

**Definición:** "Canasta de acciones" registrada ante la SEC que permite emitir gradualmente durante 3 años.

**Regla IB6 (Baby Shelf Rule):**

Si **market value of public float** (float × precio máximo en últimos 60 días) < $75M,
la empresa SOLO puede recaudar **un tercio** de ese valor.

**Ejemplo:**

```
Float: 20M acciones
Precio máximo 60D: $3.00
Market value float: 20M × $3 = $60M
Máximo recaudable: $60M / 3 = $20M
```

**Implicación operativa:**

* Empresas con S-3 activo pueden elevar precio ANTES del offering para recaudar más
* Detectar S-3 nuevo (<90 días) es señal de offering inminente
* S-3 viejos (>1 año) son menos preocupantes pero latentes

**Cómo identificar:**

1. Ir a SEC.gov → buscar ticker → ver filings
2. Buscar "S-3" o "424B5" en últimos 12 meses
3. Leer prospectus para confirmar monto y timing

---

### b. S-1 Filing

**Definición:** Solicitud directa a la SEC para recaudar monto específico (ej: $10M). Uso único, caro para empresa.

**Proceso:**

```
Día 0: Empresa solicita S-1 a SEC
Día 1-2: SEC aprueba (effective date)
Día 2-3: Underwriter cierra deal con institucionales
Día 3: Pricing announced (precio del offering)
Día 3-5: Closing date (acciones se distribuyen)
```

**Underwriters comunes:** H.C. Wainwright, Maxim, Aegis, AGP, Ladenburg, Think Equity, Canaccord, Jefferies, Roth

**Estructura típica:**

```
Ejemplo: OGN
- 7.3M acciones + 7.3M warrants a $3.00
- Recaudación: $22M
- Market Cap previo: $9M
- Dilución: +220% (!)
```

**Warrants coverage:** 100-200% es altamente dilutivo.

**Estrategia operativa:**

1. **Frontside short:** Entrar short al anuncio del S-1 effective
2. **Cover on offering:** Cubrir al pricing announcement
3. **Alternative:** Participar en offering (requiere acceso institucional)

**NOTA:** Los S-1s son "account builders" según traders experimentados (bajo riesgo, alta probabilidad).

---

### c. PIPE (Private Placement)

**Definición:** Acuerdo privado empresa-inversor para emitir acciones/deuda convertible SIN necesidad de S-1 o S-3 vigente.

**Registro:** Form D (dentro de ~15 días post-deal)

**Características:**

* Difíciles de anticipar
* NO requieren shelf activo
* Permiten crear acciones "de la nada"
* Ejemplo reciente: COCP (10 abril) realizó PIPE sin previo shelf

**Edge operativo:**

* Traders con **newsfeed en tiempo real** (Newsedge, Newswear, Bloomberg) tienen ventaja de 10-30 segundos
* Alerta temprana permite entrar short antes del colapso

**Lockup period:** Private Investors (PI) tienen bloqueo de 6 meses antes de poder vender.

---

### d. Warrants y convertibles

**Tipos de warrants:**

| Tipo | Exercise Price | Uso | Dilución |
|------|----------------|-----|----------|
| **Comunes** | Variable (ej: $3.50) | Estructura estándar | Media |
| **Prefunded** | $0.001 | Cuando se alcanza límite de authorized shares | Alta |

**Coverage típico:** 100-200% (ej: 7M acciones + 7M warrants = 200% coverage)

**Ejemplo:**

```
XBIO:
- Float: 3.3M acciones
- Warrants: 270K con exercise a $4.33
- Coverage: 8% (manejable)
- Implicación: Resistencia fuerte en $4.30-$4.60
```

**Regla de conversión:** Warrants solo se convierten si hay volumen POR ENCIMA del exercise price durante días consecutivos.

**Rumor común en Twitter:** "Ya se pueden convertir los warrants" → generalmente FALSO. Nadie convierte warrants para ganarse 1 centavo.

**Deuda convertible (ejemplo: BBBY):**

* Conversión a 90% del VWAP de 5 días
* **Dilución pura:** "deuda a costo de shares"
* Genera presión bajista constante

---

## 7. Integración con Framework López de Prado

### a. Estructuras de datos óptimas

**Problema de Time Bars en Small Caps:**

Los pumps tienen actividad extremadamente concentrada: 90% del volumen en 30 min de apertura.
Time bars (1m, 5m) **oversample** periodos muertos y **undersample** el pump.

**Solución: Information-Driven Bars**

| Tipo | Fórmula cierre | Ventaja para Small Caps |
|------|----------------|-------------------------|
| **Dollar Bars** | Σ(price × volume) ≥ threshold | Ajuste automático a cambios de precio y splits |
| **Dollar Imbalance Bars (DIBs)** | \|Σ(b_t × price × volume)\| ≥ threshold | **Captura pump initiation** (desbalance masivo de compras) |
| **Dollar Runs Bars (DRBs)** | max(Σ buys, Σ sells) ≥ threshold | **Detecta sweeping agresivo** (órdenes consecutivas barriendo order book) |

**Configuración sugerida por patrón:**

| Patrón | Bar Type | Threshold | Razón |
|--------|----------|-----------|-------|
| **Gap & Go** | DIBs | 0.1% free-float × price | Captura buying surge inicial |
| **VWAP Reclaim** | DIBs | 0.05% float × price | Detecta cambio de control intradía |
| **First Red Day** | Dollar bars | 0.2% float × price | Volumen total importa más que dirección |
| **Late Day Fade** | DRBs | EWMA runs | Detecta distribución sostenida (selling runs) |
| **Panic Bounce** | DIBs | 0.15% float × price | Captura reversión de imbalance sell→buy |

**Beneficio esperado:**

* ⚡ Detección 2-5 minutos más temprana de pump initiation vs time bars
* 📊 Reducción ~30-40% en falsos positivos por mejor muestreo
* 🎯 Labels más limpias para ML (path-dependent, ajustadas por volatilidad)

---

### b. Labeling con Triple Barrier

**Aplicación a Small Caps:**

Los pumps tienen **asimetría extrema**: suben rápido (+parabólico) y caen violento (−colapso).

**Barreras asimétricas recomendadas:**

**Para LONGS (pumps):**

```python
profit_barrier = +3.0 × daily_vol  # Pumps pueden hacer 3σ fácilmente
stop_barrier   = -2.0 × daily_vol  # Stop más conservador
time_barrier   = 2 días             # Max holding period intradía

# Configuración: [1,1,1] (las 3 barreras activas)
```

**Para SHORTS (First Red Day):**

```python
profit_barrier = -2.5 × daily_vol  # Caídas son violentas pero cortas
stop_barrier   = +1.5 × daily_vol  # Stop ajustado (riesgo de squeeze)
time_barrier   = 1 día              # FRD se resuelve rápido

# Configuración: [1,1,1]
```

**Volatilidad dinámica (Snippet 3.1):**

```python
# Calcular diariamente con EWMA
daily_vol = getDailyVol(close, span0=100)
```

**Ejemplo de implementación:**

```python
# Paso 1: Construir DIBs
dibs = build_dollar_imbalance_bars(
    trades,
    threshold=0.1 * float_shares * current_price / 100
)

# Paso 2: Detectar eventos con CUSUM filter
cusum_events = detect_cusum_events(dibs['close'], threshold=2.5)

# Paso 3: Calcular volatilidad dinámica
daily_vol = getDailyVol(dibs['close'], span0=100)

# Paso 4: Definir barreras
events = getEvents(
    close=dibs['close'],
    tEvents=cusum_events,
    ptSl=[3, 2],                 # profit=3σ, stop=2σ
    trgt=daily_vol,
    t1=t1,                       # 2 días
    minRet=0.01,
    numThreads=4
)

# Paso 5: Generar labels
labels = getBins(events, dibs['close'])
# Output: DataFrame con 'ret' (return) y 'bin' (label ∈ {-1, 0, 1})
```

---

### c. Meta-Labeling para filtrado

**Arquitectura propuesta:**

```
MODELO PRIMARIO (Rule-Based, del Playbook)
    ↓
Detecta: VWAP Reclaim, Red to Green, Gap & Go, First Red Day
    ↓
Genera: Side (+1 long / -1 short) para cada evento
    ↓
META-MODELO (ML)
    ↓
Features: float, short interest, días desde último S-3,
          RVOL, news sentiment, bid/ask spread, market cap,
          volumen rotation ratio, distance from offering price
    ↓
Predice: Size (0 = ignorar, 1 = ejecutar)
    ↓
SALIDA FINAL: position = side × size × probability
```

**Features específicas para Small Caps:**

| Feature | Cálculo | Importancia |
|---------|---------|-------------|
| **float_category** | <10M, 10-30M, 30-50M, >50M | Alta |
| **short_interest_pct** | % del float en short | Alta |
| **days_since_s3** | Días desde último S-3 filing | Alta |
| **rvol** | Volume / Avg_Volume_20D | Alta |
| **distance_offering** | (Price - Last_Offering_Price) / Price | Media |
| **rotation_ratio** | Volume / Float | Alta |
| **spread_pct** | (Ask - Bid) / Mid × 100 | Media |
| **news_sentiment** | Sentimiento de últimas 24h (-1 a +1) | Media |
| **institutional_own** | % institutional ownership | Baja |
| **market_cap** | Market Cap en MM USD | Media |

**Implementación conceptual:**

```python
# Paso 1: Modelo primario genera señales
primary_signals = detect_vwap_reclaim(dibs) | detect_red_to_green(dibs)

# Paso 2: Crear meta-events con barreras asimétricas
meta_events = getEvents(
    close=dibs['close'],
    tEvents=primary_signals.index,
    ptSl=[2, 3],                # profit=2σ, stop=3σ (asimétrico para longs)
    trgt=daily_vol,
    t1=t1,
    side=primary_signals,       # Pasar side del modelo primario
    minRet=0.01
)

# Paso 3: Generar meta-labels binarios {0, 1}
meta_labels = getBins(meta_events, dibs['close'])
meta_labels['bin'] = (meta_labels['ret'] > 0).astype(int)

# Paso 4: Construir features
features = build_meta_features(
    dibs,
    float_shares,
    short_interest,
    days_since_s3,
    rvol,
    news_sentiment
)

# Paso 5: Entrenar clasificador binario
from sklearn.ensemble import RandomForestClassifier
model = RandomForestClassifier(
    n_estimators=100,
    max_depth=5,
    min_samples_split=50,
    class_weight='balanced'  # Crítico: dataset desbalanceado
)
model.fit(features, meta_labels['bin'])

# Paso 6: En producción
prob_execute = model.predict_proba(features_new)[:, 1]
final_position = primary_signals * prob_execute
```

**Métricas de éxito:**

* **Precision:** TP / (TP + FP) → cuántas señales ejecutadas fueron exitosas (objetivo >60%)
* **Recall:** TP / (TP + FN) → cuántas oportunidades reales capturamos (objetivo >50%)
* **F1-score:** 2 × (Precision × Recall) / (Precision + Recall)

Meta-labeling maximiza F1-score manteniendo high recall (modelo primario) y aumentando precision (meta-modelo filtra).

---

### d. Sample Weights

**Problema en Small Caps:**

* Un solo pump épico (ej: HKD 2022, de $2 → $1,500) puede dominar el dataset
* Pumps se solapan temporalmente (premarket + regular + after-hours)
* Observaciones NO son IID (independent and identically distributed)

**Solución: Sample Weights (Capítulo 4, López de Prado)**

**Componentes del peso:**

```python
weight_i = uniqueness_i × abs(return_i) × time_decay_i
```

**1. Uniqueness (Snippet 4.3):**

Mide cuánto del retorno pertenece SOLO a ese evento (sin solapamiento).

```python
# Pseudo-código
for event_i in events:
    overlapping_events = find_overlaps(event_i, all_events)
    uniqueness_i = 1.0 / len(overlapping_events)
```

**2. Return magnitude:**

```python
return_i = abs(log(close_t1 / close_t0))
```

**3. Time decay:**

```python
# Decay lineal (c=1) o exponencial (c=-1)
decay_i = exp(-c × (today - event_date) / 365)
```

**Aplicación práctica:**

```python
# Calcular uniqueness
uniqueness = compute_uniqueness(events, close_series)

# Calcular return magnitude
returns = abs(np.log(events['ret'] + 1))

# Time decay (last 6 months tienen peso completo, luego decay)
days_ago = (pd.Timestamp.now() - events.index).days
time_decay = np.exp(-1.0 × days_ago / 180)

# Peso final
sample_weights = uniqueness × returns × time_decay

# Normalizar
sample_weights /= sample_weights.sum()

# Entrenar con pesos
model.fit(features, labels, sample_weight=sample_weights)
```

**Beneficio:** Evita que un solo pump extremo (HKD, GME) domine el modelo. Da más peso a eventos únicos y recientes.

---

## 8. Pipeline de Implementación ML

**Arquitectura completa del sistema:**

```
┌─────────────────────────────────────────────────────────┐
│ CAPA 1: INGESTA DE DATOS (Polygon.io)                  │
├─────────────────────────────────────────────────────────┤
│ - /v3/trades/{ticker} → ticks (precio, volumen, ts)    │
│ - /v3/quotes/{ticker} → bid/ask para tick rule         │
│ - /v2/aggs/ticker/{ticker}/range → OHLCV backup        │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│ CAPA 2: CONSTRUCCIÓN DE BARRAS (López de Prado Cap 2)  │
├─────────────────────────────────────────────────────────┤
│ A. Dollar Bars (baseline)                              │
│ B. Dollar Imbalance Bars (DIBs) - PRIMARIO para longs  │
│ C. Dollar Runs Bars (DRBs) - para sweeping detection   │
│                                                         │
│ Threshold dinámico: f(float, market_cap, volatility)   │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│ CAPA 3: FEATURE ENGINEERING                            │
├─────────────────────────────────────────────────────────┤
│ Técnicos:                                               │
│ - VWAP, distance_from_VWAP                             │
│ - RSI, MACD, Bollinger Bands                           │
│ - Volume profile, RVOL                                  │
│ - Imbalance ratio (compras/ventas)                     │
│ - Tick rule classification                              │
│                                                         │
│ Microestructura:                                        │
│ - Bid/Ask spread                                        │
│ - Order flow toxicity (VPIN)                           │
│ - Roll measure (liquidez)                               │
│                                                         │
│ Fundamentales:                                          │
│ - Float, market cap                                     │
│ - Short interest %                                      │
│ - Days since S-3, offering price distance               │
│ - Cash flow status, institutional ownership             │
│                                                         │
│ Sentimiento:                                            │
│ - News sentiment (NLP en PRs)                           │
│ - Twitter/StockTwits volume                             │
│ - Hot sector indicator                                  │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│ CAPA 4: LABELING (López de Prado Cap 3)                │
├─────────────────────────────────────────────────────────┤
│ 1. Detectar eventos con CUSUM filter                   │
│ 2. Aplicar Triple Barrier Method:                      │
│    - Longs:  profit=+3σ, stop=-2σ, time=2 días         │
│    - Shorts: profit=-2.5σ, stop=+1.5σ, time=1 día      │
│ 3. Generar labels: {-1, 0, +1}                         │
│ 4. Calcular sample weights (uniqueness × return × decay)│
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│ CAPA 5: MODELO PRIMARIO (Rule-Based)                   │
├─────────────────────────────────────────────────────────┤
│ Implementación de Playbook:                            │
│                                                         │
│ LONGS:                                                  │
│ - detect_breakout()                                     │
│ - detect_red_to_green()                                 │
│ - detect_vwap_bounce()                                  │
│ - detect_vwap_reclaim()                                 │
│ - detect_gap_and_go()                                   │
│                                                         │
│ SHORTS:                                                 │
│ - detect_first_red_day()                                │
│ - detect_overextended_gap_down()                        │
│ - detect_late_day_fade()                                │
│ - detect_short_into_resistance()                        │
│                                                         │
│ Output: DataFrame con [timestamp, side, pattern_name]  │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│ CAPA 6: META-MODELO (ML - López de Prado Cap 3.6)      │
├─────────────────────────────────────────────────────────┤
│ Input: Side del modelo primario + Features             │
│                                                         │
│ Algoritmo: Random Forest / XGBoost / LightGBM          │
│ - n_estimators: 100-500                                 │
│ - max_depth: 3-7 (evitar overfitting)                  │
│ - min_samples_split: 50-100                             │
│ - class_weight: 'balanced' (dataset desbalanceado)     │
│                                                         │
│ Training con:                                           │
│ - Purged K-Fold CV (evitar data leakage)               │
│ - Sample weights                                        │
│ - Sequential bootstrap para test set                    │
│                                                         │
│ Output: Probabilidad de éxito [0, 1]                   │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│ CAPA 7: RISK MANAGEMENT Y EJECUCIÓN                    │
├─────────────────────────────────────────────────────────┤
│ Position Sizing:                                        │
│   size = kelly_criterion(prob, R:R) × capital          │
│   max_single_position = 10% capital                     │
│   max_correlated_positions = 25% capital               │
│                                                         │
│ Stop Loss:                                              │
│   - Técnico: nivel invalidación (VWAP, soporte/resist) │
│   - Temporal: time barrier del Triple Barrier           │
│   - Volatility-adjusted: f(ATR, daily_vol)             │
│                                                         │
│ Take Profit:                                            │
│   - Parcial 1: profit barrier del Triple Barrier        │
│   - Parcial 2: siguiente resistencia/número redondo     │
│   - Final: trailing stop desde profit barrier           │
│                                                         │
│ Execution:                                              │
│   - Limit orders en niveles definidos (NO market orders)│
│   - Slippage control: max 2% vs target price           │
│   - Partial fills: acepto ≥50% de size objetivo        │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│ CAPA 8: MONITOREO Y FEEDBACK LOOP                      │
├─────────────────────────────────────────────────────────┤
│ - Log de cada trade: entry, exit, P&L, pattern, reason │
│ - Métricas diarias: Win Rate, Avg R:R, Sharpe, MaxDD   │
│ - Retrain meta-modelo: semanal con últimos 3 meses     │
│ - Ajuste de thresholds: mensual según market regime    │
│ - Spreadsheet tracking: validación empírica de patterns│
└─────────────────────────────────────────────────────────┘
```


## Conclusión

Este documento integra:

1. **Marco teórico de López de Prado** (Dollar Imbalance Bars, Triple Barrier, Meta-Labeling, Sample Weights)
2. **Playbook táctico de EduTrades** (10 estrategias long, 5 estrategias short, construcción de watchlist)
3. **Análisis fundamental de dilución** (S-3, S-1, PIPE, warrants)
4. **Pipeline completo de ML** (desde ingesta hasta ejecución)

**Próximos pasos:**

1. Implementar construcción de DIBs/DRBs en Python
2. Codificar detección de patrones del Playbook
3. Entrenar meta-modelo con datos históricos (2020-2024)
4. Backtesting con Purged K-Fold CV
5. Paper trading durante 1 mes
6. Despliegue en producción con capital limitado (10% de cuenta)

---

**Referencias:**

* López de Prado, M. (2018). *Advances in Financial Machine Learning*. Wiley.
* EduTrades / Latin Day Trading 
* Polygon.io API Documentation
* SEC.gov — EDGAR Database

---

**Versión:** 1.0  
**Fecha:** 2024-01-15  
**Autor:** Trading Small Caps Project Team  
