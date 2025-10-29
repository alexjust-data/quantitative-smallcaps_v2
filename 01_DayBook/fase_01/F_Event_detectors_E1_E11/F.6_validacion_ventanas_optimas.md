# F.6 - Validación Matemática de Ventanas Temporales Óptimas

**Fecha**: 2025-10-29
**Status**: 🔄 EN PROCESO
**Objetivo**: Determinar empíricamente las ventanas temporales óptimas `[t_start, t_end]` para cada evento E1-E11 usando datos reales del Pilot50.

---

## 1. CONTEXTO Y MOTIVACIÓN

### 1.1 Problema

En **F.3** definimos ventanas cualitativas basadas en razonamiento:

```python
EVENT_WINDOWS = {
    'E0_AlwaysTrue': 1,
    'E1_VolExplosion': 1,
    'E2_GapUp': 2,
    'E4_Parabolic': 3,
    'E7_FirstRedDay': 2,
    # ... etc
}
```

**Pregunta central**: ¿Son estas ventanas óptimas? ¿Cuándo debemos **comenzar a recoger ticks anticipando** el evento y hasta cuándo después del evento para **maximizar información predictiva**?

### 1.2 Enfoque Híbrido (2 Fases)

**FASE 1: Information Theory** (Filtro Rápido)
- Mutual Information: $I(X_t; y)$
- Information Gain: $IG(X_t) = H(y) - H(y|X_t)$
- Feature Importance por día
- **Objetivo**: Identificar días sin señal → descartarlos rápidamente

**FASE 2: Model Performance** (Validación Económica)
- Entrenar LightGBM por ventana candidata
- Medir AUC (separabilidad)
- Medir Edge económico (expected weighted return)
- **Objetivo**: Cuantificar valor económico real de cada ventana

**Ventaja del enfoque híbrido**:
- ✅ Fase 1 es model-agnostic e interpretable
- ✅ Fase 2 mide directamente lo que importa: $$
- ✅ Combinados: máxima eficiencia (descartar rápido) + máxima precisión (validar edge)

### 1.3 Ventana Óptima

La ventana óptima maximiza información total con restricciones de costo:

$$
[t^*_{start}, t^*_{end}] = \arg\max_{t_{start}, t_{end}} \left[ \sum_{t=t_{start}}^{t_{end}} I(X_t; y) - \lambda \cdot \text{window_size} \right]
$$

Donde:
- $I(X_t; y)$ = Información mutua entre features día $t$ y target
- $\lambda$ = Costo por día adicional (descarga, procesamiento, storage)
- Restricciones: $t_{start} \geq -7$, $t_{end} \leq +7$

---

## 2. METODOLOGÍA

### 2.1 Dataset: Pilot50 Validation

- **Tickers**: 50 representativos del universo
- **Período**: 2004-2025
- **Ticker-days con eventos E1-E11**: 37,274
- **Ticker-days totales (con ventana ±3)**: 139,684
- **Trades files descargados**: ✅ 100% completo (2025-10-29)
- **DIB bars construidos**: 🔄 EN PROCESO

**Ubicación datos**:
- Trades: `raw/polygon/trades_pilot50_validation/`
- DIB bars: `processed/dib_bars/pilot50_validation/`

### 2.2 Pipeline de Análisis

```
trades.parquet → DIB bars → Features Engineering → Labeling → Ventana Optimal Analysis
```

**Etapas**:

1. **Construcción DIB bars** (🔄 EN CURSO)
   - Script: `scripts/fase_D_creando_DIB_VIB/build_bars_from_trades.py`
   - Target: $300k USD por barra
   - EMA window: 50
   - Output: OHLCV + imbalance_score por barra

2. **Feature Engineering** (⏳ PENDIENTE)
   - Features técnicos: returns, volatility, volume ratios, imbalance metrics
   - Por cada día $t \in [-7, +7]$ relativo al evento
   - Agrupación por día: $X_t = \text{features}(t)$

3. **Labeling** (⏳ PENDIENTE)
   - Targets: `ret_1d`, `ret_3d`, `ret_5d`, `ret_10d`
   - Triple Barrier Labeling para clasificación

4. **Análisis de Información por Día** (⏳ PENDIENTE)
   - Calcular $I(X_t; y)$ para cada $t \in [-7, +7]$
   - Normalizar: $I_{norm}(t) = I(t) / \max(I)$
   - Visualizar información temporal

5. **Determinación de Ventana Óptima** (⏳ PENDIENTE)
   - Threshold: $I_{norm}(t) > 0.1$ (10% del máximo)
   - Continuidad: No gaps > 2 días
   - Cost-benefit optimization

### 2.3 Notebooks de Análisis

#### A. Notebook Híbrido (RECOMENDADO)

**Ubicación**: `01_DayBook/fase_01/F_Event_detectors_E1_E11/notebooks/validacion_ventanas_hibrida.ipynb`

**Pipeline completo**:
1. **Fase 1 - Information Theory**:
   ```python
   analyze_information_by_relative_day(event, max_pre=7, max_post=7) -> Dict[int, float]
   ```
   - Carga DIB bars por día relativo
   - Calcula MI/IG para cada día
   - Identifica días significativos (threshold 10%)

2. **Fase 2 - Model Performance**:
   ```python
   build_dataset_for_window(event, pre_days, post_days) -> pl.DataFrame
   evaluate_window_performance(df, feature_cols) -> {'auc', 'edge', 'n_bars'}
   ```
   - Construye dataset completo (bars + labels + weights)
   - Entrena LightGBM por ventana
   - Mide AUC y edge económico
   - Calcula score: `(edge × AUC) / log(n_bars)`

3. **Grid Search**:
   - 12 ventanas candidatas × 11 eventos = 132 combinaciones
   - Selección óptima por score compuesto
   - Comparación con ventanas cualitativas F.3

#### B. Notebook Information Theory (Alternativo)

**Ubicación**: `01_DayBook/fase_01/F_Event_detectors_E1_E11/notebooks/validacion_ventanas_optimas_matematica.ipynb`

**Para análisis rápido sin labels/weights**:
```python
calculate_mutual_information(X_t, y) -> float
calculate_information_gain(X_t, y) -> float
determine_optimal_window(info_by_day, threshold=0.1) -> Tuple[int, int]
cost_benefit_analysis(info_by_day, cost_per_day=0.01) -> DataFrame
```

---

## 3. RESULTADOS (PENDIENTE)

### 3.1 Información Mutua por Evento

**Formato esperado**:

| Evento | t=-3 | t=-2 | t=-1 | t=0 | t=+1 | t=+2 | t=+3 | Ventana Óptima |
|--------|------|------|------|-----|------|------|------|----------------|
| E1_VolExplosion | 0.02 | 0.05 | 0.15 | **1.00** | 0.45 | 0.12 | 0.03 | `[-1, +1]` |
| E4_Parabolic | 0.08 | 0.25 | 0.60 | **1.00** | 0.85 | 0.50 | 0.20 | `[-2, +2]` |
| E7_FirstRedDay | 0.15 | **0.80** | **1.00** | 0.50 | 0.25 | 0.08 | 0.02 | `[-2, 0]` |
| ... | ... | ... | ... | ... | ... | ... | ... | ... |

### 3.2 Comparación: Empírico vs Cualitativo

| Evento | Ventana Empírica | Size | Ventana Cualitativa (F.3) | Size | Diferencia | Status |
|--------|------------------|------|---------------------------|------|------------|--------|
| E1_VolExplosion | `[-1, +1]` | 3 | `±1` | 3 | 0 | ✅ Match |
| E4_Parabolic | `[-2, +2]` | 5 | `±3` | 7 | -2 | Más pequeño |
| E7_FirstRedDay | `[-2, 0]` | 3 | `±2` | 5 | -2 | Asimétrico |
| ... | ... | ... | ... | ... | ... | ... |

### 3.3 Hallazgos Clave

**PENDIENTE EJECUCIÓN**

Expectativas:
1. ✅ Ventanas asimétricas: Algunos eventos tienen más información **antes** que después
2. ✅ Variabilidad: Cada evento E1-E11 tiene patrón temporal único
3. ✅ Rendimientos decrecientes: Ventanas más grandes ≠ más información útil
4. ✅ Validación cualitativa: Algunas ventanas F.3 ya son óptimas

---

## 4. VENTANAS RECOMENDADAS (PROVISIONAL)

### 4.1 Actualizadas con Evidencia Empírica

**PENDIENTE**: Ejecutar análisis con datos reales

Formato esperado:
```python
EVENT_WINDOWS_EMPIRICAL = {
    'E0_AlwaysTrue': (0, 1),           # Baseline: día evento + siguiente
    'E1_VolExplosion': (-1, 1),        # Evento súbito, poca anticipación
    'E2_GapUp': (-1, 2),               # Gap requiere confirmación post-evento
    'E3_PriceSpikeIntraday': (0, 1),   # Intraday, mínima anticipación
    'E4_Parabolic': (-2, 2),           # Proceso gradual, contexto necesario
    'E5_BreakoutATH': (-2, 2),         # Necesita build-up y confirmación
    'E6_MultipleGreenDays': (-2, 1),   # Patrón multi-día requiere historia
    'E7_FirstRedDay': (-2, 1),         # Anticipación importante (reversal)
    'E8_GapDownViolent': (-1, 2),      # Similar a E2 pero crash
    'E9_CrashIntraday': (0, 1),        # Súbito como E3
    'E10_FirstGreenBounce': (-1, 1),   # Bounce requiere contexto previo
    'E11_VolumeBounce': (-1, 2),       # Volumen requiere confirmación
}
```

### 4.2 Impacto en Descarga

**Comparación size**:

| Métrica | Ventanas Cualitativas (F.3) | Ventanas Empíricas | Diferencia |
|---------|-----------------------------|--------------------|------------|
| Size promedio | 3.9 días | **TBD** | **TBD** |
| Total ticker-days (universo completo) | ~15M | **TBD** | **TBD** |
| Reducción potencial | - | **TBD** | **TBD** |

**Objetivo**: Si las ventanas empíricas son más pequeñas, reducir costo de descarga significativamente.

---

## 5. PRÓXIMOS PASOS

### 5.1 Inmediatos (Fase 2: En Curso)

- [x] ✅ Descargar trades Pilot50 (139,684 files)
- [ ] 🔄 Construir DIB bars (EN PROCESO)
- [ ] ⏳ Feature engineering con ventanas ±7 días
- [ ] ⏳ Ejecutar notebook validación matemática
- [ ] ⏳ Analizar información mutua por evento
- [ ] ⏳ Determinar ventanas óptimas empíricas
- [ ] ⏳ Documentar resultados (completar sección 3)

### 5.2 Siguientes (Fase 3: Full Universe)

- [ ] ⏳ Implementar E0 "Always True" event
- [ ] ⏳ Generar watchlist E0-E11 completo con ventanas empíricas
- [ ] ⏳ Lanzar descarga universo completo con `--resume`
- [ ] ⏳ Construir ML dataset completo

---

## 6. REFERENCIAS

### 6.1 Documentos Relacionados

- **F.3**: Definición arquitectura eventos E0-E11 (ventanas cualitativas)
- **F.5**: Auditoría descarga Pilot50 + estrategia E0-E11 incremental
- **E.1**: Event detectors originales E1/E4/E7/E8
- **D.4**: ML Dataset Builder + pipeline completo

### 6.2 Scripts y Notebooks

- `scripts/fase_D_creando_DIB_VIB/build_bars_from_trades.py`: Construcción DIB bars
- `scripts/fase_E_Event Detectors E1, E4, E7, E8/event_detectors.py`: Detectores E1-E11
- `notebooks/validacion_ventanas_optimas_matematica.ipynb`: Análisis matemático ventanas

### 6.3 Literatura

- **Advances in Financial Machine Learning** (López de Prado, 2018): Information-driven bars, Triple Barrier Method
- **Machine Learning for Asset Managers** (López de Prado, 2020): Feature importance, purging/embargo

---

## ANEXO A: Fórmulas Matemáticas

### A.1 Mutual Information

$$
I(X_t; y) = \sum_{x_t} \sum_{y} p(x_t, y) \log \frac{p(x_t, y)}{p(x_t)p(y)}
$$

**Interpretación**: Información (en bits) sobre target $y$ obtenida al observar features del día $t$.

### A.2 Information Gain

$$
IG(X_t) = H(y) - H(y|X_t)
$$

Donde:
- $H(y) = -\sum_{y} p(y) \log p(y)$ (entropía sin condición)
- $H(y|X_t) = \sum_{x_t} p(x_t) H(y|X_t=x_t)$ (entropía condicional)

### A.3 Feature Importance (LightGBM)

$$
\text{Importance}(f) = \sum_{s \in \text{splits using } f} \text{Gain}(s)
$$

Agregamos por día:
$$
\text{Importance}(t) = \sum_{f \in \text{features day } t} \text{Importance}(f)
$$

### A.4 Cost-Benefit Optimization

$$
[t^*_{start}, t^*_{end}] = \arg\max_{[t_s, t_e]} \left[ \sum_{t=t_s}^{t_e} I(X_t; y) - \lambda \cdot (t_e - t_s + 1) \right]
$$

**Trade-off**: Información ganada vs costo de ventana más grande.

---

## ANEXO B: Estado de Construcción DIB Bars

### B.1 Comando Lanzado

```bash
python scripts/fase_D_creando_DIB_VIB/build_bars_from_trades.py \
  --trades-root raw/polygon/trades_pilot50_validation \
  --outdir processed/dib_bars/pilot50_validation \
  --bar-type dollar_imbalance \
  --target-usd 300000 \
  --ema-window 50 \
  --parallel 12 \
  --resume
```

### B.2 Progreso

**Última actualización**: 2025-10-29 15:11 UTC

- **Status**: 🔄 EN PROCESO
- **Files esperados**: 139,684
- **Files completados**: TBD (monitoreando con `_SUCCESS` markers)
- **Tiempo estimado**: 20-40 minutos con 12 workers

**Monitoreo**:
```bash
python scripts/fase_F_validacion_ventanas/monitor_dib_build.py
```

---

**FIN DE DOCUMENTO PROVISIONAL**

Este documento será actualizado con resultados reales una vez completada la construcción de DIB bars y ejecutado el análisis matemático.
