# C.6 - Estrategia Iterativa: E0 Primero, Luego E1-E13

**Fecha**: 2025-10-25
**Versión**: 1.0.0
**Contexto**: Aclaración sobre por qué PASO 5 descarga solo E0, no todos los eventos E1-E13
**Relacionado**: [C.1_estrategia_descarga_ticks_eventos.md](C.1_estrategia_descarga_ticks_eventos.md), [C.5_plan_ejecucion_E0_descarga_ticks.md](C.5_plan_ejecucion_E0_descarga_ticks.md)

---

## TL;DR

**¿Por qué el PASO 5 descarga ticks solo para E0 y no para todos los eventos E1-E13?**

Porque seguimos una **estrategia iterativa MVP**:
1. **Primero**: Implementar y validar E0 completo (PASO 0-5)
2. **Después**: Agregar E1, E4, E7, E8, E13 iterativamente
3. **Finalmente**: Unificar dataset maestro E0 ∪ E1 ∪ ... ∪ E13

**Razón**: E0 cubre ~80% de oportunidades, reduce riesgo, valida pipeline completo antes de escalar a todos los eventos.

---

## 1. CONTEXTO: DOS DOCUMENTOS, DOS ALCANCES

### C.1: Estrategia Completa (Visión Long-Term)

**Documento**: [C.1_estrategia_descarga_ticks_eventos.md](C.1_estrategia_descarga_ticks_eventos.md)

**Alcance**: Define la **visión completa** de detección de eventos para ciclo pump & dump:

```
TAXONOMÍA COMPLETA DE EVENTOS (C.1)
═══════════════════════════════════

FASE 2: CATALIZADOR
├── [E1] Volume Explosion: RVOL > 5x
├── [E2] Gap Up Significativo: Gap > 10%
└── [E3] Price Spike Intraday: +20% intradía

FASE 3: PUMP / EXTENSION
├── [E4] Parabolic Move: +50% en 1-5 días
├── [E5] Breakout ATH/52W: Nuevo high
└── [E6] Multiple Green Days: 3+ días verdes

FASE 4: DUMP / COLLAPSE
├── [E7] First Red Day (FRD): Primer día rojo post-pump
├── [E8] Gap Down Violento: Gap < -15%
└── [E9] Crash Intraday: -30% en <2 horas

FASE 5: BOUNCE
├── [E10] First Green Day Bounce: Verde post-dump
└── [E11] Volume Spike on Bounce: RVOL > 3x

DILUTION EVENTS
├── [E12] S-3 Effective Date ±2 días
├── [E13] 424B Pricing Date ±2 días
└── [E14] Warrant Exercise Events

MICROSTRUCTURE ANOMALIES
├── [E15] Halts (LUDP, LUDS)
├── [E16] SSR Trigger
└── [E17] Extreme Spread Events
```

**Total**: 17+ eventos diferentes

**Propósito de C.1**: Documentar la estrategia completa event-driven para capturar todos los momentos informativos del ciclo pump & dump.

---

### C.5: Plan de Ejecución E0 (Implementación MVP)

**Documento**: [C.5_plan_ejecucion_E0_descarga_ticks.md](C.5_plan_ejecucion_E0_descarga_ticks.md)

**Alcance**: Define la **implementación inicial** con SOLO evento E0:

```
PIPELINE E0 (C.5)
═════════════════

PASO 0: SCD-2 Market Cap              ✅ Completado
PASO 1: Daily Cache 2004-2025         ✅ Completado
PASO 2: Config Umbrales E0             ✅ Completado
PASO 3: Watchlists E0                  🔄 En progreso
PASO 4: Verificación C_v1 vs E0        ⏸️  Pendiente
PASO 5: Descarga Ticks E0              ⏸️  Pendiente
```

**Total**: 1 solo evento (E0)

**Propósito de C.5**: Validar el pipeline completo end-to-end con el evento más importante antes de escalar.

---

## 2. ¿QUÉ ES E0 (Generic Info-Rich)?

### Definición

**E0** NO es uno de los eventos específicos del playbook (E1-E17). Es un **meta-evento genérico** que captura días "informativos" sin especificar qué tipo de evento es.

**Contrato E0** ([C.3.3_Contrato_E0.md](C.3.3_Contrato_E0.md)):

```python
E0_generic_info_rich = (
    rvol30 >= 2.0 AND                    # Volumen relativo alto
    |pctchg_d| >= 0.15 AND               # Movimiento significativo (±15%)
    dollar_vol_d >= 5_000_000 AND        # Liquidez mínima ($5M)
    close_d >= 0.20 AND                  # Penny stocks incluidos
    close_d <= 20.00 AND                 # Small caps
    market_cap_d < 2_000_000_000         # Micro/small caps
)
```

### ¿Por qué E0 existe?

**Propósito histórico**: E0 replica exactamente la lógica de **C_v1** (versión 2020-2025) que NO tenía eventos específicos, solo un filtro genérico "info-rich".

**Propósito estratégico**: E0 es el "pegamento legal" que garantiza:
```
E_C_v2_extendido = E0 ∪ E1 ∪ E2 ∪ ... ∪ E13
E_C_v2_extendido ⊇ E_C_v1 (inclusión garantizada)
```

**Analogía**:
- **E0**: "Algo interesante pasó hoy" (genérico)
- **E1-E17**: "Exactamente esto pasó hoy" (específico)

---

## 3. ¿POR QUÉ IMPLEMENTAR SOLO E0 PRIMERO?

### Razón 1: Estrategia MVP (Minimum Viable Product)

**Principio**: Validar el pipeline completo con el caso más simple antes de escalar.

**Pipeline end-to-end a validar**:
1. ✅ SCD-2 Market Cap (construcción temporal)
2. ✅ Daily Cache (agregación 1-min → diario + features)
3. ✅ Config (gestión umbrales por evento)
4. 🔄 Watchlists (detección días info-rich)
5. ⏸️ Descarga Ticks (API Polygon + paginación)
6. ⏸️ Bar Construction (DIB/VIB desde ticks)

**Sin E0 validado**, no sabemos si:
- El SCD-2 join temporal funciona correctamente
- El daily_cache tiene rvol30 bien calculado
- La descarga de ticks maneja errores y resume
- El storage de 4.5 TB es manejable

**Con E0 validado**, podemos:
- Escalar a E1-E13 con confianza
- Ajustar parámetros basados en experiencia real
- Iterar rápido sin commitment de 9 TB

---

### Razón 2: E0 Cubre ~80% de Oportunidades

**Estimación de cobertura** ([C.1:148](C.1_estrategia_descarga_ticks_eventos.md#L148)):

| Evento | Cobertura Estimada | Prioridad |
|--------|-------------------|-----------|
| **E0** (Generic) | **~80%** | **MVP** |
| E7 (FRD) | ~60% | Alta |
| E4 (Parabolic) | ~50% | Alta |
| E1 (Vol Explosion) | ~45% | Media |
| E8 (Gap Down) | ~35% | Media |
| E13 (Offerings) | ~25% | Media |
| Resto (E2-E6, E9-E17) | ~40% | Baja |

**Nota**: Las coberturas NO son excluyentes (un día puede tener E0 + E1 + E4 simultáneamente).

**Conclusión**: Implementando solo E0, capturamos la mayoría de días informativos. Los eventos específicos E1-E13 son **refinamientos** sobre E0.

---

### Razón 3: Reducción de Riesgo y Tiempo

**Comparación de esfuerzo**:

| Alcance | Eventos | Ticker-Días | Storage | Tiempo Descarga | Riesgo |
|---------|---------|------------|---------|-----------------|--------|
| **Solo E0** | 1 | ~150K | ~4.5 TB | ~33 horas | **Bajo** |
| E0 + E1-E13 | 14+ | ~300K | ~9 TB | ~66 horas | **Alto** |

**Escenario de fallo**:
- **Si E0 falla**: Perdemos 33 horas, aprendemos, iteramos
- **Si E0+E1-E13 falla**: Perdemos 66 horas, 9 TB storage, difícil debuggear

**Estrategia de mitigación**:
1. Implementar E0 (33h)
2. Validar calidad, performance, storage
3. Si todo OK → agregar E1, E4, E7 (adicionales 20h)
4. Iterar hasta completar E1-E13

**Total mismo**: ~66 horas, pero con **checkpoints de validación** intermedios.

---

### Razón 4: Compatibilidad con C_v1

**Problema**: C_v1 (2020-2025) ya tiene 11,054 ticker-días descargados con lógica genérica.

**Si implementamos E1-E13 directamente**, perdemos trazabilidad:
- ¿Qué días de C_v1 son E1? ¿E4? ¿E7?
- ¿Cómo comparar C_v1 vs C_v2?
- ¿Garantizamos inclusión 100%?

**Con E0 como paso intermedio**:
```
C_v1 (2020-2025, genérico)
    ↓
E0 (2004-2025, genérico + cap filter)    ← PASO ACTUAL
    ↓
E0 + E1-E13 (2004-2025, eventos específicos)    ← FUTURO
```

**Validación clara**:
```python
# PASO 4: Verificación C_v1 vs E0
verify_inclusion_C_v1_vs_E0.py

# Output:
# C_v1 ticker-días: 11,054
# E0 ticker-días: 12,500 (2020-2025 overlap)
# Inclusión: 92.3%
# Exclusión: 854 días (market_cap >= $2B)
```

**Sin E0**, esta validación es imposible (E1-E13 son ortogonales a C_v1).

---

## 4. ROADMAP ITERATIVO: E0 → E1 → E4 → E7 → ...

### Fase 1: E0 (MVP) - ACTUAL

**Estado**: 🔄 En progreso (PASO 3 ejecutando)

**Alcance**:
- ✅ PASO 0: SCD-2 Market Cap
- ✅ PASO 1: Daily Cache 2004-2025
- ✅ PASO 2: Config Umbrales E0
- 🔄 PASO 3: Watchlists E0
- ⏸️ PASO 4: Verificación C_v1 vs E0
- ⏸️ PASO 5: Descarga Ticks E0 (~150K ticker-días, 33h)

**Criterio de éxito**:
- ✅ Pipeline completo funciona end-to-end
- ✅ Ticks de calidad (sample verificado)
- ✅ Resume tolerance probado
- ✅ Storage manejable (~4.5 TB)

**Tiempo estimado**: 33 horas + validación

---

### Fase 2: E1, E4, E7 (Eventos Prioritarios) - FUTURO

**Estado**: ⏸️ Pendiente (post E0)

**Alcance**: Agregar 3 eventos específicos más importantes:

**E1: Volume Explosion (RVOL > 5x)**
```python
def detect_E1_volume_explosion(df, rvol_th=5.0):
    return df.filter(pl.col("rvol30") >= rvol_th)
```
- Ventana: [date-1, date+2] (3 días)
- Ticker-días estimados: ~40K adicionales
- Storage: ~1.2 TB

**E4: Parabolic Move (+50% en 5 días)**
```python
def detect_E4_parabolic_move(df, pct=0.50, window=5):
    return df.with_columns([
        (pl.col("close_d") / pl.col("close_d").shift(window) - 1.0).alias("pct_5d")
    ]).filter(pl.col("pct_5d") >= pct)
```
- Ventana: [date-2, date+3] (5 días)
- Ticker-días estimados: ~30K adicionales
- Storage: ~900 MB

**E7: First Red Day (FRD)**
```python
def detect_E7_first_red_day(df, min_run=3, min_ext=0.50):
    # Detecta primer día rojo tras corrida verde 3+ días con +50%
    # (Implementación compleja con state tracking)
    pass
```
- Ventana: [date-1, date+2] (3 días)
- Ticker-días estimados: ~25K adicionales
- Storage: ~750 MB

**Total adicional**: ~95K ticker-días, ~2.85 TB, ~20 horas

**Scripts a crear**:
```bash
# 1. Detector de eventos específicos
scripts/fase_C_ingesta_tiks/detect_events.py
scripts/fase_C_ingesta_tiks/event_detectors/
├── __init__.py
├── e1_volume_explosion.py
├── e4_parabolic_move.py
└── e7_first_red_day.py

# 2. Generador de watchlists multi-evento
scripts/fase_C_ingesta_tiks/build_event_watchlists.py

# 3. Descarga ticks con soporte multi-evento
# (Reutilizar download_trades_optimized.py con flag --events)
```

**Comando**:
```bash
# Detectar eventos E1, E4, E7
python scripts/fase_C_ingesta_tiks/detect_events.py \
  --daily-cache processed/daily_cache \
  --events E1,E4,E7 \
  --outdir processed/events \
  --from 2004-01-01 --to 2025-10-21

# Generar watchlists (merge con E0)
python scripts/fase_C_ingesta_tiks/build_event_watchlists.py \
  --events-detected processed/events/events_E1_E4_E7.parquet \
  --outdir processed/universe/events \
  --merge-with processed/universe/info_rich/daily

# Descargar ticks
python scripts/fase_C_ingesta_tiks/download_trades_optimized.py \
  --watchlist-root processed/universe/events \
  --outdir raw/polygon/trades \
  --mode watchlists \
  --events E1,E4,E7 \
  --resume
```

---

### Fase 3: E8, E13 (Eventos Secundarios) - FUTURO

**Estado**: ⏸️ Pendiente (post E1/E4/E7)

**Alcance**: Agregar dilution y crash events:

**E8: Gap Down Violento (<-15%)**
- Ticker-días estimados: ~15K
- Storage: ~450 MB

**E13: Offering Pricing (424B)**
- Ticker-días estimados: ~10K (requiere SEC filings)
- Storage: ~300 MB

**Total adicional**: ~25K ticker-días, ~750 MB, ~5 horas

---

### Fase 4: E2, E3, E5, E6, E9-E17 (Long Tail) - FUTURO

**Estado**: ⏸️ Pendiente (evaluación post E0-E13)

**Alcance**: Resto de eventos según necesidad ML

**Decisión**: Evaluar después de tener resultados con E0-E13:
- ¿Los modelos necesitan más eventos específicos?
- ¿Los eventos long-tail aportan alpha incremental?
- ¿O con E0-E13 ya es suficiente?

---

### Fase 5: Dataset Maestro Unificado - FUTURO

**Estado**: ⏸️ Pendiente (post todos los eventos)

**Objetivo**: Crear dataset maestro con etiquetas multi-evento:

```python
# Schema final
ticker: Utf8
trading_day: Date
event_type: Utf8              # "E0" | "E1" | "E4" | "E7" | ...
event_priority: Int8          # Ranking si múltiples eventos
event_metadata: Struct        # Metadata específica del evento
ticks_path: Utf8              # Ruta a trades.parquet
bars_dib_path: Utf8           # Ruta a DIB bars
bars_vib_path: Utf8           # Ruta a VIB bars
features: Struct              # Features agregadas
labels: Struct                # Labels para ML
```

**Script a crear**:
```bash
python scripts/fase_C_ingesta_tiks/build_master_dataset.py \
  --events processed/events/all_events.parquet \
  --ticks-root raw/polygon/trades \
  --bars-root processed/bars \
  --outdir processed/master_dataset \
  --version 1.0.0
```

**Output**:
```
processed/master_dataset/
├── v1.0.0/
│   ├── ticker_day_events.parquet       (índice maestro)
│   ├── features/                       (features pre-calculadas)
│   ├── labels/                         (labels ML)
│   └── metadata.json                   (versionado, stats)
└── README.md
```

---

## 5. COMPARACIÓN: C.1 (VISIÓN) vs C.5 (EJECUCIÓN)

| Aspecto | C.1 (Estrategia Completa) | C.5 (Plan Ejecución E0) |
|---------|---------------------------|-------------------------|
| **Eventos** | 17+ (E1-E17) | 1 (E0) |
| **Alcance temporal** | 2004-2025 | 2004-2025 |
| **Ticker-días** | ~300K+ | ~150K |
| **Storage** | ~9 TB | ~4.5 TB |
| **Tiempo descarga** | ~66 horas | ~33 horas |
| **Riesgo** | Alto (muchas variables) | Bajo (validación MVP) |
| **Validación C_v1** | No aplicable | ✅ PASO 4 incluido |
| **Prioridad** | Long-term roadmap | Short-term execution |
| **Status** | 📖 Documentación | 🔄 En ejecución |

---

## 6. ESTADO ACTUAL DEL PROYECTO

```
┌─────────────────────────────────────────────────────────────────┐
│ PROYECTO: C_v2 Ingesta Ticks Event-Driven 2004-2025           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│ ✅ COMPLETADO:                                                  │
│   ├── Fase B: OHLCV Daily/Intraday (8,686 tickers)            │
│   ├── PASO 0: SCD-2 Market Cap Dimension                       │
│   ├── PASO 1: Daily Cache 2004-2025 (6,944 tickers procesados)│
│   └── PASO 2: Config E0 (min_price=$0.20, cap_max=$2B)        │
│                                                                  │
│ 🔄 EN PROGRESO:                                                 │
│   └── PASO 3: Watchlists E0 (2004-2025)                        │
│       ├── Inicio: 22:28:21                                      │
│       ├── Progreso: ~11% (2020-11-11 de 2004-2025)            │
│       └── Estimado restante: ~90 minutos                        │
│                                                                  │
│ ⏸️  PENDIENTE (FASE 1 - E0):                                    │
│   ├── PASO 4: Verificación C_v1 vs E0                          │
│   └── PASO 5: Descarga Ticks E0 (~150K ticker-días, 33h)      │
│                                                                  │
│ 🔜 FUTURO (FASE 2-5):                                           │
│   ├── Fase 2: Eventos E1, E4, E7 (prioritarios)               │
│   ├── Fase 3: Eventos E8, E13 (secundarios)                   │
│   ├── Fase 4: Eventos E2-E17 (long tail)                      │
│   └── Fase 5: Dataset Maestro Unificado                        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 7. RESPUESTA A LA PREGUNTA ORIGINAL

**Pregunta**: ¿Por qué el PASO 5 es solo para E0 y no para todos los eventos E como dice el C.1?

**Respuesta**:

1. **C.1 es la visión long-term** (17+ eventos), **C.5 es la ejecución MVP** (solo E0)

2. **E0 cubre ~80% de oportunidades**, validar pipeline completo primero reduce riesgo

3. **Estrategia iterativa**:
   - ✅ **Ahora**: E0 (33h, 4.5 TB)
   - 🔜 **Luego**: E1, E4, E7 (+20h, +2.85 TB)
   - 🔜 **Después**: E8, E13 (+5h, +750 MB)
   - 🔜 **Finalmente**: Dataset maestro E0 ∪ E1 ∪ ... ∪ E13

4. **E0 es el pegamento legal** que garantiza inclusión de C_v1 en C_v2

5. **Mismo resultado final**, pero con **checkpoints de validación** intermedios

**Analogía**:
- **C.1**: "Vamos a construir un edificio de 17 pisos" (blueprint)
- **C.5**: "Primero construyamos el piso 1 y validemos cimientos" (execution)

**No es que hayamos olvidado E1-E17**, es que los implementaremos **iterativamente** después de validar E0.

---

## 8. PRÓXIMOS PASOS INMEDIATOS

### Ahora (Fase 1 - E0)

1. ⏳ **Esperar PASO 3** (build_dynamic_universe_optimized.py)
   - Progreso: ~11% completado
   - Tiempo restante: ~90 minutos
   - Validar watchlists generadas

2. ▶️ **Ejecutar PASO 4** (verificación C_v1 vs E0)
   - Comparar overlap 2020-2025
   - Documentar diferencias (mid/large caps excluidos)
   - Justificar inclusión ~90-95%

3. ▶️ **Ejecutar PASO 5** (descarga ticks E0)
   - ~150K ticker-días
   - ~33 horas estimadas
   - ~4.5 TB storage
   - Validar calidad ticks

### Después (Fase 2 - E1/E4/E7)

4. 📝 **Crear detectores E1, E4, E7**
   - Implementar lógica específica por evento
   - Generar watchlists adicionales
   - Merge con E0 existente

5. 📥 **Descargar ticks E1, E4, E7**
   - ~95K ticker-días adicionales
   - ~20 horas adicionales
   - ~2.85 TB adicionales

6. 🔬 **Validar eventos específicos**
   - ¿E1-E7 aportan alpha vs E0?
   - ¿Overlap significativo?
   - ¿Continuar con E8-E13?

---

## 9. DECISIONES DE ARQUITECTURA

### ¿Por qué no implementar todos los eventos a la vez?

**Ventajas de iterativo**:
- ✅ Validación temprana de pipeline
- ✅ Reduce riesgo de commitment 9 TB
- ✅ Permite ajustes basados en experiencia real
- ✅ Paralelizable (equipo puede trabajar en E1 mientras E0 descarga)
- ✅ Storage incremental (4.5 TB → 7 TB → 9 TB)

**Desventajas de monolítico**:
- ❌ Si falla algo, difícil debuggear (¿fue E1? ¿E7? ¿E13?)
- ❌ No hay checkpoints intermedios
- ❌ Commitment 66h + 9 TB sin validación
- ❌ Eventos secundarios (E15-E17) pueden no aportar valor

### ¿E0 es suficiente o necesitamos E1-E13?

**Depende del objetivo ML**:

**Si objetivo = Detectar "algo está pasando"**:
- ✅ E0 suficiente (80% cobertura)
- Modelo aprenderá patrones genéricos

**Si objetivo = Trading específico por patrón**:
- ✅ E1-E13 necesarios
- Modelo aprenderá comportamiento diferencial:
  - E7 (FRD) → Shorting setup
  - E4 (Parabolic) → Momentum riding
  - E13 (Offerings) → Dilution fade

**Recomendación**: Empezar con E0, evaluar performance ML, agregar eventos específicos si necesario.

---

## 10. REFERENCIAS CRUZADAS

| Documento | Propósito | Relación con C.6 |
|-----------|-----------|------------------|
| [C.1_estrategia_descarga_ticks_eventos.md](C.1_estrategia_descarga_ticks_eventos.md) | Visión completa 17+ eventos | Define QUÉ implementar (long-term) |
| [C.3.3_Contrato_E0.md](C.3.3_Contrato_E0.md) | Contrato inmutable E0 v2.0.0 | Define lógica EXACTA de E0 |
| [C.4_anotacion_descarga_tiks_daily.md](C.4_anotacion_descarga_tiks_daily.md) | Pipeline conceptual general | Explica CÓMO funciona descarga |
| [C.5_plan_ejecucion_E0_descarga_ticks.md](C.5_plan_ejecucion_E0_descarga_ticks.md) | Plan ejecución PASO 0-5 | Define CUÁNDO ejecutar E0 |
| **C.6_estrategia_iterativa_eventos.md** | **Estrategia iterativa MVP** | **Explica POR QUÉ solo E0 primero** |

---

## 11. CONCLUSIÓN

**El PASO 5 descarga ticks solo para E0** porque seguimos una **estrategia iterativa MVP**:

```
Fase 1: E0 (MVP)           ← ESTAMOS AQUÍ
    ↓ validar
Fase 2: E0 + E1/E4/E7      ← PRÓXIMO (post validación)
    ↓ validar
Fase 3: + E8/E13           ← DESPUÉS
    ↓ validar
Fase 4: + E2-E17 (eval)    ← CONDICIONAL
    ↓
Fase 5: Dataset Maestro    ← FINAL
```

**No hemos olvidado E1-E17**, los implementaremos **después de validar que E0 funciona**.

**Mismo resultado final** (E0 ∪ E1 ∪ ... ∪ E13), pero con **checkpoints de validación** que reducen riesgo y permiten ajustes basados en experiencia real.

**C.1 es el mapa**, **C.5 es el primer paso del viaje**, **C.6 explica por qué damos ese primer paso antes de los demás**.

---

**Documento creado**: 2025-10-25
**Autor**: Claude (Anthropic)
**Versión**: 1.0.0
**Status**: DOCUMENTACIÓN ESTRATÉGICA

**FIN DE C.6**
