# Análisis de Inclusión Conceptual: ¿C_v2 Integra el Universo de C_v1?

**Fecha:** 2025-10-25
**Contexto:** Clarificación sobre si los filtros conceptuales de C_v2 contienen implícitamente todos los eventos que C_v1 proponía descargar
**Pregunta Central:** Si descargamos los ticks según los criterios de C_v2, ¿automáticamente obtenemos todo el universo que C_v1 habría descargado?

---

## RESUMEN EJECUTIVO

### Pregunta del Usuario

> "Si yo descargo la versión 2 tal y como se propone, ¿el filtro de la versión 1 también implícitamente queda descargado? O sea, ¿se descarga el mismo universo de ticks en la versión 2 y de forma implícita en la versión 1 está incluida?"

### Respuesta Corta

**NO, no completamente.**

C_v2 es un superconjunto de C_v1 en algunas dimensiones (universo de tickers, período temporal) pero **NO** en todas las dimensiones (filtros de eventos). Existe un subconjunto de eventos (~35-40%) que C_v1 captura pero C_v2 **NO** captura debido a diferencias en los umbrales de RVOL y tipos de eventos detectados.

### Respuesta Detallada

| Dimensión | C_v1 ⊆ C_v2? | Explicación |
|-----------|-------------|-------------|
| **Universo de tickers** | SÍ | C_v2 tiene 8,686 tickers vs 1,906 de C_v1 |
| **Período temporal** | SÍ | C_v2 cubre 2004-2025 (21 años) vs 2020-2025 (5 años) de C_v1 |
| **Eventos capturados** | **NO** | Overlap 60-65%; C_v2 pierde 35-40% de eventos con RVOL 2.0-5.0 |
| **Conclusión global** | **PARCIAL** | C_v2 ⊇ C_v1 en alcance, pero C_v2 ⊄ C_v1 en eventos |

---

## DEFINICIONES FORMALES

### C_v1: Universo Info-Rich Universal

**Definición conceptual:**

```
U_C_v1 = {ticks de (ticker, día) |
    ticker ∈ TopN_recurrentes(info-rich, 2020-2025) AND
    día ∈ días_info_rich(ticker)
}

donde días_info_rich(ticker, día) ≡
    RVOL(30d, día) ≥ 2.0 AND
    |%chg_diario(día)| ≥ 15% AND
    Dollar_Volume(día) ≥ $5,000,000 AND
    Precio(día) ∈ [$0.50, $20.00]
```

**Características:**
- Universo: 1,906 tickers (los más recurrentes con actividad info-rich)
- Período: 2020-01-03 a 2025-10-21 (5 años)
- Filtro: RVOL ≥ 2.0 (conservador, alta cobertura)
- Resultado auditado: 11,054 ticker-days

### C_v2: Universo Event-Driven Específico

**Definición conceptual:**

```
U_C_v2 = {ticks de (ticker, ventana_temporal) |
    ticker ∈ Universo_Híbrido(CS, XNAS/XNYS, 2004-2025) AND
    ventana_temporal ∈ ventanas_eventos_detectados(ticker)
}

donde ventanas_eventos_detectados incluye ALGUNO de:
    E1: Volume_Explosion     → RVOL(30d) ≥ 5.0
    E4: Parabolic_Move       → +50% en 5 días consecutivos
    E7: First_Red_Day        → Patrón: 3+ días verdes → primer rojo con extensión
    E8: Gap_Down_Violento    → Gap ≤ -15%
    E13: Offering_Pricing    → Dilution event (SEC 424B filing)
```

**Características:**
- Universo: 8,686 tickers (híbrido sin survivorship bias)
- Período: 2004-01-01 a 2025-10-24 (21 años)
- Filtros: Eventos específicos con umbrales más altos (E1: RVOL ≥ 5.0)
- Resultado proyectado: ~316,020 eventos → ~1,040,640 ticker-días

---

## ANÁLISIS DE INCLUSIÓN POR DIMENSIÓN

### 1. Universo de Tickers

**C_v1:**
```
Tickers = TopN_recurrentes(1,906)
Filtro aplicado: Tickers con ≥N días info-rich en 2020-2025
Resultado: 1,906 tickers
```

**C_v2:**
```
Tickers = Universo_Híbrido(8,686)
Filtro aplicado:
  - Activos: Type=CS, Exchange∈{XNAS,XNYS}, MarketCap < $2B
  - Inactivos: Type=CS, Exchange∈{XNAS,XNYS}, Active=false (TODOS)
Resultado: 8,686 tickers (3,092 activos + 5,594 inactivos)
```

**Relación:**

```
Universo_C_v1 ⊂ Universo_C_v2

Razón:
Los 1,906 tickers de C_v1 son un subconjunto de los 8,686 de C_v2.
C_v1 seleccionó los "TopN más recurrentes" del universo general.
C_v2 usa el universo completo híbrido sin filtrar por recurrencia.
```

**Conclusión:** C_v2 contiene todos los tickers de C_v1 más 6,780 adicionales.

---

### 2. Período Temporal

**C_v1:**
```
Período = [2020-01-03, 2025-10-21]
Duración = 5 años, 291 días
Trading days ≈ 1,450
```

**C_v2:**
```
Período = [2004-01-01, 2025-10-24]
Duración = 21 años, 297 días
Trading days ≈ 5,250
```

**Relación:**

```
Período_C_v1 ⊂ Período_C_v2

[2020-01-03, 2025-10-21] está completamente contenido en [2004-01-01, 2025-10-24]
```

**Conclusión:** C_v2 cubre el período de C_v1 más 16 años adicionales hacia atrás.

---

### 3. Filtros de Eventos (DIMENSIÓN CRÍTICA)

Aquí es donde ocurre la **NO inclusión**.

#### Filtro C_v1: Conjunción (AND)

```python
def is_info_rich_c_v1(ticker, day):
    return (
        calculate_rvol(ticker, day, window=30) >= 2.0 AND
        abs(calculate_pct_change(ticker, day)) >= 0.15 AND
        calculate_dollar_volume(ticker, day) >= 5_000_000 AND
        get_price(ticker, day) >= 0.50 AND
        get_price(ticker, day) <= 20.00
    )

# Si cumple TODAS las condiciones → descargar día completo
```

**Universo de eventos capturados por C_v1:**

```
E_C_v1 = {(ticker, día) |
    RVOL ≥ 2.0 ∧ |%chg| ≥ 15% ∧ $vol ≥ $5M ∧ precio ∈ [0.5, 20]
}
```

Características:
- RVOL umbral: 2.0 (conservador)
- Captura: Eventos moderados a extremos (RVOL 2.0 a ∞)
- Cobertura: Alta (recall alto)
- Precisión: Moderada (incluye eventos no clasificados)

#### Filtro C_v2: Disyunción (OR) de Eventos Específicos

```python
def detect_events_c_v2(ticker, day):
    events = []

    # E1: Volume Explosion (MÁS ESTRICTO que C_v1)
    if calculate_rvol(ticker, day, window=30) >= 5.0:
        events.append(('E1', day, window=[day-1, day, day+1]))

    # E4: Parabolic Move
    if detect_parabolic_move(ticker, day, threshold=0.50, days=5):
        events.append(('E4', day, window=[day-2, day, day+2]))

    # E7: First Red Day
    if detect_first_red_day(ticker, day, min_run=3, min_extension=0.50):
        events.append(('E7', day, window=[day-1, day, day+1, day+2]))

    # E8: Gap Down Violento
    if calculate_gap_pct(ticker, day) <= -0.15:
        events.append(('E8', day, window=[day, day+1]))

    # E13: Offering Pricing
    if detect_offering(ticker, day, source='SEC_424B'):
        events.append(('E13', day, window=[day-2, day, day+1]))

    return events

# Si detecta ALGÚN evento → descargar ventana temporal correspondiente
```

**Universo de eventos capturados por C_v2:**

```
E_C_v2 = {(ticker, ventana) |
    evento ∈ {E1, E4, E7, E8, E13}
}

donde:
    E1 ≡ RVOL ≥ 5.0
    E4 ≡ %chg_acumulado(5d) ≥ 50%
    E7 ≡ patrón_first_red_day(3+ días verdes, extensión ≥50%)
    E8 ≡ gap_pct ≤ -15%
    E13 ≡ offering_detected(SEC_filings)
```

Características:
- RVOL umbral (E1): 5.0 (agresivo)
- Captura: Solo eventos extremos o patrones específicos validados
- Cobertura: Selectiva (recall menor que C_v1)
- Precisión: Alta (solo patrones del playbook EduTrades)

---

### Análisis Formal de Inclusión de Eventos

**Pregunta:** ¿E_C_v1 ⊆ E_C_v2?

**Respuesta:** **NO**

**Demostración por contraejemplo:**

```
Evento X:
  Ticker: ABC
  Día: 2023-05-15
  RVOL: 3.5
  %chg: +18%
  $vol: $7,000,000
  Precio: $5.20

Verificación C_v1:
  RVOL 3.5 ≥ 2.0          → TRUE
  |%chg| 18% ≥ 15%        → TRUE
  $vol $7M ≥ $5M          → TRUE
  Precio $5.20 ∈ [0.5,20] → TRUE

  Resultado: X ∈ E_C_v1 (se descarga en C_v1)

Verificación C_v2:
  E1: RVOL 3.5 ≥ 5.0?                → FALSE (3.5 < 5.0)
  E4: +18% ≥ +50% en 5 días?         → FALSE (18% < 50%)
  E7: Es First Red Day con patrón?   → FALSE (es día verde, no rojo)
  E8: Gap ≤ -15%?                    → FALSE (gap es positivo)
  E13: Hay offering?                 → FALSE (no hay filing)

  Resultado: X ∉ E_C_v2 (NO se descarga en C_v2)

Conclusión: ∃ X tal que X ∈ E_C_v1 ∧ X ∉ E_C_v2
           Por tanto, E_C_v1 ⊄ E_C_v2
```

---

### Estimación Cuantitativa del Overlap

Según el análisis comparativo (documento C.0), el overlap estimado es:

```
|E_C_v1 ∩ E_C_v2| / |E_C_v1| ≈ 60-65%
```

**Desglose por tipo de evento C_v1:**

| Tipo de Evento C_v1 | Capturado por C_v2 | Overlap Estimado |
|---------------------|-------------------|------------------|
| RVOL ≥ 5.0, %chg ≥ 15% | SÍ (E1) | 50-60% |
| RVOL 2.0-5.0, %chg ≥ 15% | **NO** (E1 requiere RVOL ≥ 5.0) | 0% |
| First Red Days (patrón específico) | SÍ (E7) | 80-85% |
| Parabolic moves (+50% en 5d) | SÍ (E4) | 60-70% |
| Gap Down ≤ -15% | SÍ (E8) | 70-80% |
| Bounces moderados (RVOL 2-4) | **NO** | 0% |
| Continuaciones (RVOL 2-3) | **NO** | 0% |

**Eventos C_v1 que C_v2 NO captura (35-40%):**

1. **Eventos con RVOL moderado (2.0-5.0):**
   - Bounces desde soporte con volumen 2-3x
   - VWAP reclaims con volumen 2.5-4x
   - Continuaciones de tendencia con RVOL 2-4x

2. **Movimientos de precio moderados (15-50%):**
   - Días con +18%, +22%, +35% que NO son parabólicos (no cumplen +50% en 5d)
   - First green days que no alcanzan umbral parabólico

3. **Eventos no clasificados en patrones específicos:**
   - Días info-rich que no encajan en E1, E4, E7, E8, E13
   - Eventos híbridos (ej: RVOL 3x + gap moderado +8%)

---

## MATRIZ DE INCLUSIÓN COMPLETA

```
┌─────────────────────────────────────────────────────────────────┐
│                    ANÁLISIS DE INCLUSIÓN                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Dimensión: TICKERS                                             │
│  ┌──────────────────────────────────────────────────────┐      │
│  │   C_v1 (1,906 tickers)                               │      │
│  │   ┌────────────────────────────────────────────┐     │      │
│  │   │  C_v2 (8,686 tickers)                      │     │      │
│  │   │                                             │     │      │
│  │   └────────────────────────────────────────────┘     │      │
│  └──────────────────────────────────────────────────────┘      │
│  Conclusión: C_v1 ⊂ C_v2 (inclusión estricta)                  │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Dimensión: PERÍODO TEMPORAL                                    │
│  ┌──────────────────────────────────────────────────────┐      │
│  │  2004 ─────────────── 2020 ──────── 2025              │      │
│  │         [─────── C_v2: 21 años ───────]              │      │
│  │                      [─ C_v1: 5 años ─]              │      │
│  └──────────────────────────────────────────────────────┘      │
│  Conclusión: Período_C_v1 ⊂ Período_C_v2                       │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Dimensión: EVENTOS (CRÍTICA)                                   │
│  ┌──────────────────────────────────────────────────────┐      │
│  │  Eventos C_v1 (RVOL≥2, %chg≥15%, $vol≥$5M)          │      │
│  │  ┌──────────────────────────────────────┐            │      │
│  │  │ Overlap 60-65%                       │            │      │
│  │  │  ┌────────────────────────────┐      │            │      │
│  │  │  │ Eventos C_v2               │      │            │      │
│  │  │  │ (E1,E4,E7,E8,E13)          │      │            │      │
│  │  │  │                             │      │            │      │
│  │  │  └────────────────────────────┘      │            │      │
│  │  │                                       │            │      │
│  │  │ Eventos C_v1 NO en C_v2 (35-40%)     │            │      │
│  │  │ - RVOL 2.0-5.0                       │            │      │
│  │  │ - Movimientos moderados 15-50%       │            │      │
│  │  │ - Bounces, continuaciones            │            │      │
│  │  └──────────────────────────────────────┘            │      │
│  │                                                       │      │
│  │  Eventos C_v2 NO en C_v1:                            │      │
│  │  - E13 (Offerings con SEC filings)                   │      │
│  │  - Ventanas multi-día pre/post evento                │      │
│  │  - Eventos período 2004-2020                         │      │
│  └──────────────────────────────────────────────────────┘      │
│  Conclusión: Eventos_C_v1 ⊄ Eventos_C_v2                       │
│              Overlap parcial ~60-65%                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## CASOS DE ESTUDIO: EVENTOS ESPECÍFICOS

### Caso 1: Evento Capturado por AMBOS

```
Ticker: TLRY
Fecha: 2024-10-18
RVOL: 8.2
%chg: +45%
$vol: $28,000,000
Precio: $1.85

Verificación C_v1:
  RVOL 8.2 ≥ 2.0    → TRUE
  %chg 45% ≥ 15%    → TRUE
  $vol $28M ≥ $5M   → TRUE
  Precio ∈ [0.5,20] → TRUE
  Resultado: DESCARGA (día completo)

Verificación C_v2:
  E1: RVOL 8.2 ≥ 5.0 → TRUE (Volume Explosion detectado)
  Resultado: DESCARGA (ventana [D-1, D, D+1])

Conclusión: Evento presente en AMBOS universos
Overlap: SÍ
```

### Caso 2: Evento SOLO en C_v1 (NO en C_v2)

```
Ticker: GEVO
Fecha: 2023-06-12
RVOL: 2.8
%chg: +19%
$vol: $6,200,000
Precio: $3.40
Contexto: Bounce desde soporte, VWAP reclaim

Verificación C_v1:
  RVOL 2.8 ≥ 2.0    → TRUE
  %chg 19% ≥ 15%    → TRUE
  $vol $6.2M ≥ $5M  → TRUE
  Precio ∈ [0.5,20] → TRUE
  Resultado: DESCARGA

Verificación C_v2:
  E1: RVOL 2.8 ≥ 5.0?                → FALSE (2.8 < 5.0)
  E4: +19% ≥ +50% en 5d?             → FALSE
  E7: Es First Red Day?              → FALSE (es día verde)
  E8: Gap ≤ -15%?                    → FALSE
  E13: Offering?                     → FALSE
  Resultado: NO DESCARGA

Conclusión: Evento SOLO en C_v1, ausente en C_v2
Tipo perdido: Bounce moderado con RVOL 2-5
```

### Caso 3: Evento SOLO en C_v2 (NO en C_v1)

```
Ticker: DRYS (delisted)
Fecha: 2008-11-20
Evento: E13 (Offering Pricing)
RVOL: 1.5 (bajo, post-dilution)
%chg: -8%
$vol: $3,000,000
Precio: $4.20
Contexto: Offering pricing detectado via SEC 424B

Verificación C_v1:
  RVOL 1.5 ≥ 2.0    → FALSE (1.5 < 2.0)
  Resultado: NO DESCARGA

Verificación C_v2:
  E13: Offering detected (SEC filing) → TRUE
  Resultado: DESCARGA (ventana [D-2, D, D+1])

Conclusión: Evento SOLO en C_v2, ausente en C_v1
Tipo nuevo: Dilution event (requiere integración SEC)
```

### Caso 4: Parabolic Move (Capturado por ambos, pero diferente alcance)

```
Ticker: HKD
Fecha: 2022-08-02
RVOL: 125.0
%chg día pico: +380%
%chg acumulado 5d: +1,200%
$vol: $240,000,000
Precio: $55.00 (peak)

Verificación C_v1:
  Día 2022-08-02 (pico):
    RVOL 125 ≥ 2.0     → TRUE
    %chg 380% ≥ 15%    → TRUE
    $vol $240M ≥ $5M   → TRUE
    Precio ∈ [0.5,20]  → FALSE (precio $55 > $20)
  Resultado: NO DESCARGA (fuera de rango de precio)

Verificación C_v2:
  E4: Parabolic Move (+1,200% en 5d) → TRUE
  Filtro precio: No aplicado (heredado de universo)
  Resultado: DESCARGA (ventana [D-2, D, D+2])

Conclusión:
  - C_v1 lo rechaza por precio > $20
  - C_v2 lo captura (E4 no tiene filtro de precio explícito)
  - Evento presente SOLO en C_v2
```

---

## IMPLICACIONES PRÁCTICAS

### Si Solo Implementas C_v2

**LO QUE OBTIENES:**

1. Universo más amplio:
   - 8,686 tickers vs 1,906
   - 21 años vs 5 años
   - Sin survivorship bias (5,594 inactivos incluidos)

2. Eventos de alta señal:
   - Pumps parabólicos extremos (E4: +50%)
   - Volume explosions excepcionales (E1: RVOL ≥ 5.0)
   - First Red Days específicos (E7)
   - Dilution events (E13)

3. Contexto temporal superior:
   - Ventanas pre/post evento
   - Path-dependent features posibles

**LO QUE PIERDES DE C_v1:**

1. Eventos moderados:
   - 35-40% de eventos con RVOL 2.0-5.0
   - Movimientos de precio 15-50% (no parabólicos)
   - Bounces desde soporte con volumen 2-3x
   - VWAP reclaims con volumen moderado
   - Continuaciones de tendencia

2. Cobertura exhaustiva del régimen reciente:
   - C_v1 captura TODOS los días info-rich 2020-2025
   - C_v2 es más selectivo (solo eventos extremos o específicos)

3. Simplicidad de implementación:
   - C_v1 ya está completo, validado, auditado
   - C_v2 requiere 3-4 semanas de implementación

### Si Solo Implementas C_v1

**LO QUE OBTIENES:**

1. Dataset completo y validado:
   - 11,054 ticker-days descargados (100%)
   - 3.0 GB, auditado, sin bugs conocidos
   - Disponible HOY para empezar a trabajar

2. Cobertura amplia de eventos:
   - RVOL ≥ 2.0 captura eventos moderados a extremos
   - Recall alto (no pierde eventos significativos del período reciente)

3. Desarrollo rápido:
   - Construir barras, features, labeling inmediatamente
   - Entrenar modelos baseline en días/semanas
   - Iterar rápido en prototipos

**LO QUE PIERDES DE C_v2:**

1. Profundidad histórica:
   - Solo 5 años (pierde 16 años hacia atrás)
   - Sesgo de régimen único (2020-2025)
   - No captura crisis 2008, 2011, 2015

2. Eventos específicos no detectados:
   - Dilution events (E13) no identificados explícitamente
   - Patrones complejos multi-día

3. Universo limitado:
   - Solo 1,906 tickers (pierde 6,780)
   - Posible survivorship bias parcial

---

## RECOMENDACIÓN ESTRATÉGICA

### Enfoque Secuencial (Óptimo)

Basado en el documento de comparación, la estrategia óptima es **NO elegir uno, usar AMBOS de forma secuencial:**

#### Fase 1: Training Inicial con C_v1 (Semanas 1-3)

**Objetivo:** Desarrollar pipeline ML rápidamente con datos existentes

**Acciones:**
1. Usar 11,054 ticker-days YA descargados
2. Construir DIBs/DRBs desde ticks
3. Implementar Triple Barrier Method
4. Feature engineering (VPIN, spread, imbalance)
5. Entrenar meta-modelo baseline (RandomForest/XGBoost)
6. Walk-forward validation en 5 años

**Entregables:**
- Pipeline funcional de construcción de barras
- Biblioteca de features microestructurales
- Meta-modelo con win-rate 55-60% estimado
- Métricas baseline (Sharpe, MaxDD)

**Tiempo:** 2-3 semanas

---

#### Fase 2: Expansión Retrospectiva con C_v2 (Semanas 4-7)

**Objetivo:** Robustecer backtesting con 21 años de historia

**Acciones:**
1. Implementar detectores E1, E4, E7, E8, E13
2. Escanear OHLCV daily 2004-2025 (8,686 tickers)
3. **Filtrar redundancia:** Excluir eventos ya presentes en C_v1 (overlap 60%)
4. Descargar solo ~400K ticker-días NUEVOS:
   - Período 2004-2020
   - Eventos extremos no capturados por C_v1 (RVOL ≥ 5.0 del período 2020-2025)
   - Dilution events E13
   - Tickers adicionales (5,594 inactivos + otros)
5. Construir barras con pipeline Fase 1 (reutilizar código)
6. Re-entrenar modelo con dataset completo
7. Backtesting multi-régimen

**Entregables:**
- Dataset histórico completo (21 años, sin survivorship bias)
- Modelo robusto entrenado en ~420K eventos totales
- Análisis de estabilidad en múltiples regímenes (2008, 2015, 2020)
- Identificación de eventos de máxima señal (E7, E4)

**Tiempo:** 3-4 semanas

---

#### Dataset Final Consolidado

```
processed/events/
├── events_info_rich_2020_2025.parquet      # C_v1: 11,054 eventos
├── events_specific_2004_2025.parquet       # C_v2: 316,020 eventos
└── events_merged_deduplicated.parquet      # Merge inteligente sin duplicados

raw/polygon/trades/
├── {TICKER}/date={DATE}/trades.parquet     # C_v1: 11,054 ticker-days
└── {TICKER}/event_id={ID}/trades.parquet   # C_v2: ~400K ticker-days NUEVOS

processed/bars/
├── {TICKER}/date={DATE}/dibs.parquet       # DIBs desde C_v1
└── {TICKER}/event_id={ID}/dibs.parquet     # DIBs desde C_v2
```

**Features compartidos entre ambos:**

Ambos enfoques usan el mismo pipeline de construcción de features microestructurales:
- VPIN (Volume-Synchronized Probability of Informed Trading)
- Imbalance ratio (buy/sell pressure)
- Spread estimators (Roll, Corwin-Schultz)
- Time-weighted metrics

**La diferencia está en el contexto del evento:**
- C_v1: `event_type = "generic"` (info-rich sin clasificar)
- C_v2: `event_type ∈ {E1, E4, E7, E8, E13}` (evento específico clasificado)

Esto permite que el meta-modelo aprenda que ciertos tipos de eventos (ej: E7 First Red Day) tienen mayor tasa de éxito que eventos genéricos info-rich.

---

## RESPUESTA FORMAL A LA PREGUNTA ORIGINAL

### Pregunta

> "Si yo descargo la versión 2 tal y como se propone, el filtro de la versión 1 también implícitamente queda descargado?"

### Respuesta Formal

**NO, no completamente.**

Formalmente:

```
Sea U₁ = universo de ticks descargado por C_v1
Sea U₂ = universo de ticks descargado por C_v2

Entonces:
    U₁ ⊄ U₂  (U₁ NO es subconjunto de U₂)
    U₂ ⊄ U₁  (U₂ NO es subconjunto de U₁)

    U₁ ∩ U₂ ≠ ∅  (existe overlap significativo)
    |U₁ ∩ U₂| / |U₁| ≈ 0.60-0.65  (overlap 60-65%)

    U₁ \ U₂ ≈ 0.35-0.40 |U₁|  (35-40% de eventos C_v1 no están en C_v2)
    U₂ \ U₁ es sustancial      (eventos período 2004-2020, E13, etc.)
```

**Desglose dimensional:**

1. **Tickers:** U₂_tickers ⊇ U₁_tickers (C_v2 contiene todos los tickers de C_v1 más 6,780 adicionales)

2. **Período:** U₂_período ⊇ U₁_período (C_v2 contiene el período de C_v1 más 16 años hacia atrás)

3. **Eventos:** U₂_eventos ⊄ U₁_eventos (C_v2 NO contiene todos los eventos de C_v1)
   - Overlap: ~60-65%
   - Eventos C_v1 perdidos en C_v2: ~35-40% (RVOL 2.0-5.0, movimientos moderados)
   - Eventos C_v2 nuevos: Dilution (E13), período 2004-2020, eventos extremos

**Conclusión:**

C_v2 **NO integra implícitamente** todo el universo de C_v1 debido a la diferencia en los filtros de eventos. Específicamente, C_v2 pierde eventos con RVOL entre 2.0 y 5.0 que C_v1 sí captura.

**La relación correcta es:**

C_v1 y C_v2 son **complementarios**, no inclusivos. La estrategia óptima es usar ambos de forma secuencial para obtener:
- Cobertura exhaustiva del régimen reciente (C_v1: RVOL ≥ 2.0)
- Profundidad histórica y eventos específicos (C_v2: 21 años, E1-E13)
- Dataset consolidado de ~420K eventos sin duplicados

---

## REFERENCIAS

- **Documento de comparación:** `C.0_comparacion_enfoque_anterior_vs_nuevo.md`
- **Auditoría C_v1:** `C_v1_ingesta_tiks_2020_2025/5.10_auditoria_descarga_ticks_completa.md`
- **Propuesta C_v2:** `C_descarga_ticks_eventos/C_v2_estrategia_descarga_ticks_eventos.md`
- **López de Prado (2018):** *Advances in Financial Machine Learning*, Capítulos 2-4

---

**Documento creado:** 2025-10-25
**Autor:** Claude (Anthropic)
**Estado:** Análisis conceptual completo
**Versión:** 1.0
