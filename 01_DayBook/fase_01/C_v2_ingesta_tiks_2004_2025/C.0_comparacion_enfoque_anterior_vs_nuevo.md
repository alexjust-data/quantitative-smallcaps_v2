# C.2 Comparación: Enfoque Anterior (C_v1) vs. Propuesta Nueva (C_v2)

**Fecha:** 2025-10-25
**Contexto:** Análisis comparativo de dos estrategias para descarga selectiva de ticks
**Objetivo:** Determinar cuál enfoque es más apropiado o si se deben combinar

---

## [RESUMEN EJECUTIVO]

| Dimensión | **Enfoque Anterior (C_v1)** | **Propuesta Nueva (C_v2)** | **Ganador** |
|-----------|------------------------|----------------------|-------------|
| **Filosofía** | Info-Rich Universal (RVOL/Dollar-Vol) | Event-Driven Específico (Patrones EduTrades) | **Empate** - Complementarios |
| **Cobertura** | 11,054 ticker-days (1,906 tickers, 2020-2025) | ~316K eventos estimados (8,686 tickers, 2004-2025) | **Nuevo** (+2,800%) |
| **Precisión** | Alta (RVOL≥2, %chg≥15%, $vol≥$5M) | Muy Alta (patrones específicos validados) | **Nuevo** |
| **Completitud** | 100% (11,054/11,054 ticker-days) | Pendiente implementación | **Anterior** |
| **Período** | 5 años (2020-2025) | 21 años (2004-2025) | **Nuevo** (+320%) |
| **Universo** | 1,906 tickers (solo info-rich recurrentes) | 8,686 tickers (híbrido sin survivorship bias) | **Nuevo** (+356%) |
| **Granularidad** | Día completo si info-rich | Ventanas específicas pre/post evento | **Nuevo** |
| **Reducción datos** | 99.6% vs descarga completa | 99.5% vs descarga completa | **Empate** |
| **Implementación** | ✅ Completado, validado, auditado | ❌ Diseñado, pendiente código | **Anterior** |

### **DECISIÓN RECOMENDADA:**

**Combinar ambos enfoques en pipeline secuencial:**
1. **Fase C_v1 (YA COMPLETADA)**: Usar como **dataset de entrenamiento inicial** (5 años recientes, alta calidad)
2. **Fase C_v2 (NUEVA)**

: Expandir retrospectivamente a 21 años con eventos específicos para **backtesting robusto**

---

## [ANÁLISIS DETALLADO]

### 1. Filosofía y Fundamento Teórico

#### **Enfoque Anterior (C_v1): "Info-Rich Universal"**

**Definición:**
```
Un ticker-day es info-rich si cumple SIMULTÁNEAMENTE:
1. RVOL(30d) ≥ 2.0          (volumen relativo)
2. |%chg diario| ≥ 15%       (movimiento precio)
3. Dollar-Volume ≥ $5M       (liquidez real)
4. Precio: $0.50 - $20       (rango operativo)
```

**Fundamento:**
- **López de Prado (2018, Cap 1):** "Event-based sampling: sample more frequently when new information arrives"
- **Easley, López de Prado & O'Hara (2012):** Flow toxicity y flow imbalance como proxies de información asimétrica

**Justificación del filtro:**
```
RVOL ≥ 2.0:
  → Detecta actividad anómala (participación 2x superior a media 30d)
  → Captura inicio de pumps, bounces, y first red days

|%chg| ≥ 15%:
  → Identifica movimientos extremos (runners o collapses)
  → Umbral derivado de setups EduTrades (Gap&Go +15%, FRD -15%)

Dollar-Volume ≥ $5M:
  → Filtra micro-caps zombis sin liquidez
  → Solo activos con flujo real e interés institucional
```

**Resultado:** 11,054 días info-rich en 1,906 tickers (2020-2025)

---

#### **Propuesta Nueva (C_v2): "Event-Driven Específico"**

**Definición:**
```
Detectar eventos ESPECÍFICOS del playbook EduTrades:
E1: Volume Explosion (RVOL > 5x)
E4: Parabolic Move (+50% en 5 días)
E7: First Red Day (post corrida 3+ días verdes)
E8: Gap Down Violento (<-15%)
E13: Offering Pricing (424B filings)
```

**Fundamento:**
- **López de Prado (2018, Cap 2.3.2):** "Information-driven bars detect activity from informed traders"
- **EduTrades Playbook:** Patrones validados empíricamente con >60% win-rate

**Justificación de eventos:**
```
E7 (First Red Day):
  → Patrón MÁS CONFIABLE del playbook (win-rate 65-70%)
  → Marca inicio de fase dump (crítico para shorts)
  → Requiere contexto: día previo + FRD + 2 días post

E4 (Parabolic Move):
  → Captura pumps grandes (movimientos >50%)
  → Requiere contexto: 2 días previos (setup) + 3 días post (resolución)

E13 (Offering Pricing):
  → Dilution events correlacionados con colapsos -20% a -40%
  → Requiere contexto: 2 días anticipación + 2 días ejecución
```

**Resultado estimado:** ~316,020 eventos → ~1,040,640 ticker-días (2004-2025)

---

### 2. Comparación de Filtros y Umbrales

| Parámetro | **C_v1 (Info-Rich)** | **C_v2 (Event-Driven)** | **Análisis** |
|-----------|---------------------|----------------------|--------------|
| **RVOL** | ≥ 2.0 (conservador) | E1: ≥ 5.0 (agresivo) | C_v2 más estricto para E1, pero C_v1 captura más eventos generales |
| **%Change** | ≥ 15% absoluto | E4: +50% en 5d, E7: secuencia verde-rojo, E8: gap -15% | C_v2 patrones complejos vs umbral simple |
| **Dollar-Vol** | ≥ $5M (fijo) | Implícito en eventos (pumps grandes tienen $-vol alto) | C_v1 explícito, C_v2 derivado |
| **Precio** | $0.50 - $20 | No especificado (heredado de universo híbrido) | Similar |
| **Ventana temporal** | Día completo | Pre/post evento según tipo (1-5 días) | **C_v2 MÁS EFICIENTE** |
| **Market cap** | No aplicado (TopN de freq) | < $2B (filtro universo híbrido) | C_v2 más estricto |

**ANÁLISIS CRÍTICO:**

**¿Por qué C_v1 usa RVOL≥2.0 y C_v2 usa RVOL≥5.0 para E1?**

```
C_v1 (RVOL ≥ 2.0):
  Lógica: Captura TODO evento con volumen 2x superior a media
  Cobertura: Amplia (incluye bounces moderados, reclaims, continuaciones)
  Filosofía: "Muestreo universal de actividad anómala"

C_v2 E1 (RVOL ≥ 5.0):
  Lógica: Solo explosiones EXTREMAS de volumen
  Cobertura: Selectiva (inicio de pumps grandes, no bounces menores)
  Filosofía: "Detección de eventos excepcionales"
```

**¿Cuál es mejor?**
- **C_v1 es mejor para:** Capturar TODO evento con señal (training set exhaustivo)
- **C_v2 es mejor para:** Identificar eventos de MÁXIMA señal (backtest con menos ruido)

**Trade-off:**
- C_v1: **Más recall** (captura más eventos) pero **menos precisión** (incluye ruido)
- C_v2: **Más precisión** (eventos validados) pero **menos recall** (pierde eventos moderados)

---

### 3. Ventanas Temporales: Día Completo vs. Pre/Post Evento

#### **Enfoque Anterior (C_v1): Día Completo**

**Estrategia:**
```python
# Si día D cumple info-rich → descargar ticks completos de D
if is_info_rich(D):
    download_ticks(ticker, timestamp_start="D 00:00", timestamp_end="D 23:59")
```

**Ventajas:**
- ✅ Simplicidad: Un archivo por día
- ✅ Contexto completo: Captura pre-market + regular + after-hours
- ✅ Construcción de barras: Permite DIBs/DRBs intradía sin fragmentación

**Desventajas:**
- ❌ Datos redundantes: Si evento ocurre a las 10:00, ¿para qué ticks de 15:00-16:00?
- ❌ Storage: ~400 KB/archivo promedio (podría reducirse a 200-250 KB con ventanas)

**Resultado real (C_v1 auditado):**
- 11,054 días completos
- 3.0 GB total (434 KB promedio/archivo)
- Throughput: 7.1 ticker-days/segundo

---

#### **Propuesta Nueva (C_v2): Ventanas Pre/Post Evento**

**Estrategia:**
```python
# Para E7 (First Red Day) → descargar [D-1, D, D+1, D+2]
if detect_first_red_day(D):
    download_ticks(ticker, timestamp_start="D-1 00:00", timestamp_end="D+2 23:59")
    # Total: 3 días de contexto
```

**Ventajas:**
- ✅ **Contexto superior:** Captura setup (D-1) + ejecución (D) + resolución (D+1, D+2)
- ✅ **Señal más limpia:** Eventos tienen path-dependence (López de Prado Cap 3)
- ✅ **Mejor labeling:** Triple Barrier necesita contexto post-evento para calcular barreras

**Desventajas:**
- ❌ **Complejidad:** Múltiples archivos por evento (¿cómo organizar?)
- ❌ **Overlap:** Eventos consecutivos pueden generar descargas duplicadas (requiere merge)

**Estimación de storage:**
```
Ventana promedio: 3 días (E7, E1)
Eventos: 316K
Ticker-días únicos (tras merge overlaps): ~1M
Storage: 1M × 300 KB = ~300 GB (vs 3 GB de C_v1)
```

**PROBLEMA IDENTIFICADO:**
> **C_v2 genera 100x MÁS datos que C_v1** debido a:
> 1. Más universo (8,686 vs 1,906 tickers)
> 2. Más período (21 años vs 5 años)
> 3. Ventanas multi-día (3-5 días vs 1 día)

**¿Es esto un problema?**
- **Para producción:** SÍ (300 GB es manejable pero 10x más que C_v1)
- **Para investigación:** NO (disk space es barato, señal es valiosa)

---

### 4. Cobertura: Eventos Detectados

#### **C_v1: 11,054 Ticker-Days Info-Rich**

**Distribución observada:**
```
Tickers únicos:  1,906
Ticker-days:     11,054
Días/ticker:     5.8 promedio (mediana: 4)

Top tickers:
- TLRY: 33 días info-rich
- SNDL: ~25 días
- GEVO, OCGN, BBBY: 15-20 días cada uno

Insight: 50% de tickers tienen ≤4 días info-rich en 5 años
```

**Tipos de eventos capturados (implícitamente):**
- ✅ Gap & Go (cumple RVOL≥2, %chg≥15%)
- ✅ First Red Day (cumple RVOL≥2, %chg≤-15%)
- ✅ Parabolic Move (si el día pico cumple %chg≥15%)
- ✅ VWAP Reclaim (si día tiene volumen alto)
- ❌ **NO captura:** Eventos multi-día (bounces que tardan 2-3 días en resolver)

---

#### **C_v2: ~316,020 Eventos Estimados**

**Distribución proyectada (sin implementar):**
```
| Evento | Frecuencia | Total Eventos | Ventana | Ticker-Días |
|--------|-----------|--------------|---------|-------------|
| E1: Vol Explosion | 0.5% ticker-días | 228,000 | 3 días | 684,000 |
| E4: Parabolic | 0.1% | 45,600 | 5 días | 228,000 |
| E7: FRD | 0.05% | 22,800 | 3 días | 68,400 |
| E8: Gap Down | 0.02% | 9,120 | 2 días | 18,240 |
| E13: Offerings | 500/año×21 | 10,500 | 4 días | 42,000 |
| **TOTAL** | - | 316,020 | - | 1,040,640 |
```

**Tipos de eventos capturados (explícitamente):**
- ✅ **TODOS** los patrones EduTrades (diseño explícito)
- ✅ Eventos multi-día con contexto completo
- ✅ Dilution events (E13: requiere integración SEC)

**Overlap con C_v1:**
```
Estimación conservadora:
- E7 (FRD) con %chg≤-15% → ~80% overlap con C_v1
- E4 (Parabolic) con día pico %chg≥15% → ~60% overlap
- E1 (Vol Explosion RVOL≥5) → ~40% overlap (C_v1 usa RVOL≥2)

Overlap total estimado: 50-60% de eventos C_v2 ya están en C_v1
Eventos NUEVOS en C_v2: 40-50% (eventos multi-día, dilution, período extendido)
```

---

### 5. Implementación y Estado Actual

#### **C_v1: COMPLETADO y VALIDADO**

**Scripts funcionales:**
```
build_dynamic_universe_optimized.py   → Genera watchlists info-rich
download_trades_optimized.py          → Descarga ticks (modo watchlists)
retry_failed_trades.py                → Recuperación con range splitting
```

**Resultados auditados:**
```
✅ 11,054/11,054 ticker-days (100% completitud)
✅ 3.0 GB datos (434 KB promedio/archivo)
✅ Schema validado (t, p, s, c presentes)
✅ Zero nulls en columnas críticas
✅ Período: 2020-01-03 → 2025-10-21
✅ Trazabilidad completa (watchlists → CSV → ticks)
```

**Velocidad lograda:**
- Descarga inicial: 7.1 ticker-days/segundo (26.2 min para 11K)
- Retry (range splitting): 100% recovery de fallos (45 min adicionales)
- **Total: 71 minutos** para dataset completo

**Calidad probada:**
```
Muestra aleatoria 50 archivos:
- Trades totales: 2.1M
- Promedio: 42,101 trades/archivo
- Tamaño: 0.68 MB/archivo
```

---

#### **C_v2: DISEÑADO, Pendiente Implementación**

**Scripts propuestos (NO EXISTEN AÚN):**
```
detect_events.py              → Escanear OHLCV daily, detectar E1-E13
build_event_windows.py        → Generar ventanas pre/post evento
merge_overlapping_windows.py  → Deduplicar solapamientos
download_ticks_events.py      → Descargar ticks por ventanas
build_bars_events.py          → DIBs/DRBs desde ticks
```

**Tareas pendientes:**
1. Implementar detectores de eventos (E1, E4, E7, E8, E13)
2. Escanear 21 años de OHLCV daily (8,686 tickers)
3. Generar tabla de eventos con metadata
4. Construir ventanas temporales y merge overlaps
5. Descargar ticks (estimado: ~1M ticker-días)
6. Construir barras alternativas

**Estimación de tiempo:**
- Implementación: 11-16 días (según C_v2 roadmap)
- Descarga ticks: ~100-150 horas (1M ticker-días × 0.14 seg/cada)
- **Total: ~3-4 semanas** para completar

---

### 6. Casos de Uso: ¿Cuándo Usar Cada Uno?

#### **Usar C_v1 (Info-Rich Universal) cuando:**

1. **Entrenamiento inicial de modelos ML:**
   - Dataset limpio, validado, completo
   - 11K ticker-days suficiente para entrenar meta-labeling
   - Período reciente (2020-2025) captura régimen actual

2. **Desarrollo rápido de pipeline:**
   - Datos YA disponibles (no requiere esperar 3-4 semanas)
   - Construir DIBs/DRBs, probar triple barrier, calcular sample weights
   - Iterar rápido en features y labeling

3. **Backtesting en régimen reciente:**
   - 5 años incluyen COVID, meme stocks, pequeños bull/bear markets
   - Representativo de condiciones actuales

4. **Exploración de tickers desconocidos:**
   - 1,906 tickers capturan amplia variedad de small caps
   - Filtro RVOL≥2 es inclusivo (captura eventos moderados)

**Ejemplo de workflow:**
```python
# Ya tienes los datos
ticks = pl.read_parquet("raw/polygon/trades/TLRY/date=2024-10-18/trades.parquet")

# Construir DIBs
dibs = build_dollar_imbalance_bars(ticks, threshold=10_000)

# Triple Barrier
events = detect_vwap_reclaim(dibs)
labels = apply_triple_barrier(events, dibs['close'], ptSl=[3, 2], t1=timedelta(hours=2))

# Entrenar meta-modelo
model.fit(features, labels['bin'], sample_weight=weights)
```

---

#### **Usar C_v2 (Event-Driven Específico) cuando:**

1. **Backtesting robusto a largo plazo:**
   - 21 años eliminan sesgo de régimen (incluye 2008, 2015, 2020, etc.)
   - 8,686 tickers sin survivorship bias
   - Eventos específicos permiten walk-forward validation riguroso

2. **Estrategias basadas en patrones específicos:**
   - Si tu estrategia es "shortear First Red Days", C_v2 te da TODOS los FRDs históricos
   - Si operas "parabolic moves", C_v2 te da el catálogo completo 2004-2025

3. **Análisis de dilution events:**
   - E13 (Offerings) requiere cruce con SEC filings
   - C_v1 NO captura esto explícitamente

4. **Feature engineering path-dependent:**
   - López de Prado Cap 3: "Labels should be path-dependent"
   - Ventanas pre/post evento permiten features como:
     - `days_to_event`
     - `price_path_entropy`
     - `volume_buildup_ratio`

**Ejemplo de workflow:**
```python
# Detectar todos los FRDs históricos
events_frd = detect_first_red_day(df_daily_21y, min_run=3, min_ext=0.50)
# Output: 22,800 eventos FRD en 21 años

# Para cada FRD, descargar ventana [D-1, D+2]
for event in events_frd:
    download_ticks(event.ticker, event.date - 1day, event.date + 2days)

# Construir features con path-dependence
features = []
for event in events_frd:
    ticks_pre = load_ticks(event.ticker, event.date - 1day)
    ticks_event = load_ticks(event.ticker, event.date)
    ticks_post = load_ticks(event.ticker, event.date + 1day, event.date + 2days)

    features.append({
        'peak_volume_timing': time_of_max_volume(ticks_event),
        'price_path_entropy': calculate_entropy(ticks_event['p']),
        'bounce_strength': (max(ticks_post['p']) - min(ticks_event['p'])) / min(ticks_event['p'])
    })
```

---

### 7. Ventajas y Desventajas Comparativas

| Dimensión | **C_v1 (Info-Rich)** | **C_v2 (Event-Driven)** |
|-----------|---------------------|----------------------|
| **VENTAJAS** | | |
| Completitud | ✅ 100% implementado y validado | ❌ Pendiente implementación |
| Tiempo deployment | ✅ Datos disponibles HOY | ❌ 3-4 semanas para completar |
| Simplicidad | ✅ Filtros sencillos (RVOL, %chg, $vol) | ❌ Lógica compleja (detectores multi-condición) |
| Storage | ✅ 3.0 GB (manejable) | ❌ ~300 GB estimado (10x más) |
| Debugging | ✅ Ya auditado, sin bugs conocidos | ❌ Requiere validación exhaustiva |
| Recall | ✅ Captura eventos moderados (RVOL≥2) | ❌ Pierde eventos menores (RVOL≥5 solo para E1) |
| **DESVENTAJAS** | | |
| Precisión | ❌ Incluye ruido (eventos no clasificados) | ✅ Solo patrones validados EduTrades |
| Contexto temporal | ❌ Solo día D (sin pre/post contexto) | ✅ Ventanas pre/post evento |
| Cobertura histórica | ❌ Solo 5 años (2020-2025) | ✅ 21 años (2004-2025) |
| Universo | ❌ 1,906 tickers (solo recurrentes) | ✅ 8,686 tickers (híbrido completo) |
| Dilution events | ❌ NO captura explícitamente | ✅ E13 detecta offerings (con SEC integration) |
| Path-dependence | ❌ Difícil construir features path-dependent | ✅ Diseñado para path-dependent features |
| Survivorship bias | ⚠️ Parcial (solo tickers con datos 2020-2025) | ✅ Eliminado (híbrido incluye delistados) |

---

### 8. Análisis Cuantitativo: Overlap y Complementariedad

#### **Estimación de Overlap**

**Método:** Comparar eventos C_v2 que caerían en filtros C_v1

```python
# Pseudocódigo de análisis
overlap_frd = []
for event in events_frd_c1:  # 22,800 FRDs detectados en C_v2
    # Verificar si el día D cumple filtros C_v1
    day_data = get_daily_data(event.ticker, event.date)

    is_info_rich_c_v1 = (
        day_data['rvol30'] >= 2.0 and
        abs(day_data['pctchg_d']) >= 0.15 and
        day_data['dollar_vol'] >= 5_000_000
    )

    if is_info_rich_c_v1:
        overlap_frd.append(event)

overlap_rate_frd = len(overlap_frd) / len(events_frd_c1)
```

**Resultados proyectados:**

| Evento C_v2 | Cumple Filtros C_v1 | Overlap Estimado |
|-----------|---------------------|------------------|
| E7 (FRD) | %chg≤-15%, RVOL≥2 típicamente | **80-85%** |
| E4 (Parabolic) | Día pico cumple %chg≥15% | **60-70%** |
| E1 (Vol Explosion) | RVOL≥5 vs RVOL≥2 | **40-50%** (C_v2 más estricto) |
| E8 (Gap Down) | Gap≥15%, RVOL variable | **70-80%** |
| E13 (Offerings) | NO detectado en C_v1 | **0%** (complementario) |

**Overlap total:**
```
Eventos C_v2 que YA están en C_v1:  ~60-65%
Eventos NUEVOS en C_v2:              ~35-40%

Nuevos por:
1. RVOL≥5 para E1 (más selectivo pero pierde eventos RVOL 2-5)
2. Ventanas multi-día (captura setup/resolución que C_v1 no tiene)
3. Período extendido (2004-2020 NO está en C_v1)
4. Universo ampliado (tickers delisted, menos recurrentes)
5. Dilution events E13 (completamente nuevo)
```

---

#### **Complementariedad: Qué aporta cada uno**

**C_v1 aporta:**
1. **Eventos de intensidad moderada** (RVOL 2-5, %chg 15-30%)
   - Ejemplo: VWAP bounces, continuaciones, first green day bounces
2. **Cobertura exhaustiva del régimen reciente** (2020-2025)
3. **Dataset limpio y validado** para training inmediato

**C_v2 aporta:**
1. **Eventos extremos** (RVOL≥5, %chg≥50%)
   - Ejemplo: Pumps parabólicos (DRYS $1M, HKD $2→$1,500)
2. **Contexto temporal** (pre/post evento)
3. **Cobertura histórica profunda** (21 años incluyendo 2008, 2011, 2015)
4. **Dilution events explícitos** (E13 con SEC filings)

---

### 9. Recomendación Final: Pipeline Híbrido

**PROPUESTA: Usar ambos enfoques de forma SECUENCIAL**

#### **Fase 1: Training Inicial con C_v1 (AHORA)**

**Objetivo:** Desarrollar y validar pipeline ML rápidamente

**Acciones:**
1. ✅ **Datos disponibles:** 11,054 ticker-days (3.0 GB) YA descargados
2. **Construir barras:** DIBs/DRBs desde ticks existentes
3. **Labeling:** Triple Barrier sobre eventos 2020-2025
4. **Feature engineering:** VPIN, spread, imbalance ratio, etc.
5. **Entrenar meta-modelo:** RandomForest/XGBoost con sample weights
6. **Backtesting:** Walk-forward validation en 5 años

**Entregables:**
- Pipeline funcional de construcción de barras
- Biblioteca de features microestructurales
- Meta-modelo entrenado (win-rate esperado: 55-60%)
- Métricas de baseline (Sharpe, MaxDD, precision/recall)

**Tiempo:** 2-3 semanas

---

#### **Fase 2: Expansión Retrospectiva con C_v2 (DESPUÉS)**

**Objetivo:** Robustecer backtesting con 21 años de historia

**Acciones:**
1. **Implementar detectores:** E1, E4, E7, E8, E13 sobre OHLCV daily 2004-2025
2. **Generar eventos:** ~316K eventos con metadata (tipo, ventana, ticker, fecha)
3. **Filtrar redundancia:** Excluir eventos ya presentes en C_v1 (overlap 60%)
4. **Descargar ticks NUEVOS:** ~400K ticker-días adicionales (período 2004-2020 + eventos extremos)
5. **Construir barras:** Reutilizar pipeline Fase 1
6. **Re-entrenar modelo:** Incorporar 21 años de datos
7. **Backtesting robusto:** Walk-forward en múltiples régimenes

**Entregables:**
- Dataset histórico completo (21 años, sin survivorship bias)
- Modelo robusto entrenado en 400K eventos
- Análisis de estabilidad de estrategia en múltiples regímenes
- Identificación de eventos de máxima señal (E7 FRD, E4 Parabolic)

**Tiempo:** 3-4 semanas

---

#### **Integración de Outputs**

**Dataset final consolidado:**
```
processed/events/
├── events_info_rich_2020_2025.parquet      (C_v1: 11K eventos)
├── events_specific_2004_2025.parquet       (C_v2: 316K eventos)
└── events_merged_deduplicated.parquet      (Merge inteligente)

raw/polygon/trades/
├── {TICKER}/date={DATE}/                   (C_v1: 11K ticker-days)
└── {TICKER}/event_id={ID}/                 (C_v2: 400K ticker-days NUEVOS)

processed/bars/
├── {TICKER}/date={DATE}/dibs.parquet       (DIBs desde C_v1)
└── {TICKER}/event_id={ID}/dibs.parquet     (DIBs desde C_v2)
```

**Features compartidos:**
```python
# Ambos enfoques usan el mismo pipeline de features
def build_features(dibs: pl.DataFrame) -> pl.DataFrame:
    return dibs.with_columns([
        calculate_vpin(dibs),           # Flow toxicity
        calculate_imbalance_ratio(dibs), # Buy/sell pressure
        calculate_spread_pct(dibs),     # Liquidity
        # ... etc
    ])

# La diferencia está en el EVENT CONTEXT
if source == "C_v1":
    # Evento genérico info-rich, sin tipo específico
    features = features.with_columns(pl.lit("generic").alias("event_type"))
elif source == "C_v2":
    # Evento específico con tipo (E1, E4, E7, etc.)
    features = features.with_columns(pl.col("event_type"))  # E7, E4, etc.
```

**Meta-labeling mejorado:**
```python
# Usar tipo de evento como feature en meta-modelo
features_meta = [
    'event_type',          # Nuevo: E1, E4, E7, E8, E13, generic
    'float_category',
    'short_interest_pct',
    'rvol',
    'distance_offering',
    # ... features microestructurales
]

# Modelo aprende que FRDs (E7) tienen mayor tasa de éxito en shorts
# que eventos genéricos info-rich
```

---

### 10. Respuesta a Tu Pregunta Original

> "¿Por qué antes se filtraron los eventos con otros parámetros y por qué el tuyo es mejor o no?"

**RESPUESTA:**

### **Ninguno es "mejor" - Son COMPLEMENTARIOS**

#### **C_v1 (Info-Rich) es mejor para:**
✅ **Desarrollo rápido:** Datos YA disponibles, empezar a entrenar HOY
✅ **Cobertura amplia:** RVOL≥2.0 captura eventos moderados (más recall)
✅ **Régimen actual:** 2020-2025 refleja condiciones recientes del mercado
✅ **Simplicidad:** Filtros sencillos, fácil de explicar y mantener

#### **C_v2 (Event-Driven) es mejor para:**
✅ **Precisión:** Solo patrones validados del playbook (más precision)
✅ **Contexto temporal:** Ventanas pre/post permiten path-dependent features
✅ **Backtesting robusto:** 21 años eliminan sesgo de régimen único
✅ **Casos específicos:** Si quieres SOLO FRDs o SOLO dilution events

#### **La estrategia ÓPTIMA es SECUENCIAL:**

```
AHORA (Fase 1):
  └─> Usar C_v1 (11K ticker-days YA descargados)
      └─> Construir pipeline (barras, features, labeling)
      └─> Entrenar modelo baseline
      └─> Validar en 5 años recientes

DESPUÉS (Fase 2):
  └─> Implementar C_v2 (detectores de eventos específicos)
      └─> Expandir a 21 años (400K ticker-days NUEVOS)
      └─> Re-entrenar modelo con dataset completo
      └─> Backtesting multi-régimen

RESULTADO FINAL:
  └─> Dataset híbrido: C_v1 (exhaustivo reciente) + C_v2 (específico histórico)
  └─> Modelo robusto entrenado en ~420K eventos
  └─> Coverage: 60% overlap + 40% eventos nuevos
```

---

## [DECISIÓN RECOMENDADA]

### **NO ELEGIR UNO, USAR AMBOS:**

1. **Corto plazo (próximas 2-3 semanas):**
   - Trabajar con C_v1 (11K ticker-days)
   - Desarrollar pipeline de barras + features + labeling
   - Entrenar meta-modelo baseline

2. **Medio plazo (semanas 4-7):**
   - Implementar detectores C_v2
   - Expandir a 21 años con eventos específicos
   - Integrar ambos datasets

3. **Largo plazo (producción):**
   - Pipeline consolidado que usa:
     - C_v1 para **event detection universal** (screening diario)
     - C_v2 para **event classification** (identificar tipo específico)

**FUNDAMENTO:**
> "En ML, más datos (bien etiquetados) SIEMPRE es mejor que menos datos"

C_v1 + C_v2 = **~420K eventos etiquetados** es superior a cualquiera por separado.

---

## [REFERENCIAS]

- **C_v1 Docs:** `C_v1_ingesta_tiks_2020_2025/5.10_auditoria_descarga_ticks_completa.md`
- **C_v2 Proposal:** `C_descarga_ticks_eventos/C_v2_estrategia_descarga_ticks_eventos.md`
- **EduTrades Playbook:** `A_Universo/2_estrategia_operativa_small_caps.md`
- **López de Prado:** *Advances in Financial Machine Learning* (2018), Cap 2-4
