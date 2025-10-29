# F.7 - Pipeline Labels + Weights: Pilot50 para Validación Ventanas

**Fecha**: 2025-10-29
**Status**: EN EJECUCIÓN (D.2 Triple Barrier Labeling)
**Objetivo**: Generar labels + weights sobre Pilot50 para ejecutar validación híbrida de ventanas óptimas

---

## De Dónde Venimos

### Fase F.5: Descarga Pilot50 Completada ✅
**Documentación**: [F.5_auditoria_descarga_pilot50.md](F.5_auditoria_descarga_pilot50.md)

**Resultado**:
- 139,684 archivos `trades.parquet` descargados (ticks nivel 1)
- Eventos: E1-E11 (sin E0 - se agregará después)
- Periodo: 2020-2025
- 50 tickers representativos
- 100% tasa de éxito

**Estructura**:
```
raw/polygon/trades_pilot50_validation/{TICKER}/date={YYYY-MM-DD}/
├── trades.parquet    # Schema: {t, p, s, c}
└── _SUCCESS
```

### Fase F.6: DIB Bars Construidos ✅
**Script**: `scripts/fase_D_creando_DIB_VIB/build_bars_from_trades.py`

**Parámetros**:
```bash
--bar-type dollar_imbalance
--target-usd 300000
--ema-window 50
--parallel 12
--resume
```

**Resultado**:
- Archivos: 96,897 (100%)
- Tiempo: 102.1 min (~1h 42min)
- Errores: 0

**Output**:
```
processed/dib_bars/pilot50_validation/{TICKER}/date={YYYY-MM-DD}/
├── dollar_imbalance.parquet
│   Schema: {t_open, t_close, o, h, l, c, v, n, dollar, imbalance_score}
└── _SUCCESS
```

---

## Pipeline Actual (Fase F.7)

### Problema: Confusión de Paths

**Estructura antigua** (pipeline E0 - Fase D completa):
```
processed/
├── bars/           # 64,801 archivos E0 (2004-2025)
├── labels/         # Centenares de tickers E0
├── weights/        # Centenares de tickers E0
└── datasets/       # Dataset E0 completo
```

**Problema**: Si usamos `processed/labels/pilot50_validation/` hay confusión con `processed/labels/{TICKER}/`.

**Solución - Nueva estructura limpia para Pilot50**:
```
processed/
├── dib_bars/pilot50_validation/     ✅ (96,897 archivos)
├── labels_pilot50/                  🔄 (EN CONSTRUCCIÓN - D.2)
├── weights_pilot50/                 ⏳ (PENDIENTE - D.3)
└── dataset_pilot50/                 ⏳ (PENDIENTE - análisis notebook)
```

**Ventaja**: Separación total entre datos E0 antiguos y datos Pilot50 de validación.

---

## Fase F.7.1: Triple Barrier Labeling (EN EJECUCIÓN)

**Documentación base**: [D.1_Ejecucion_Pipeline_DIB_Labels_Weights.md](../../D_creando_DIB_VIB_2004_2025/D.1_Ejecucion_Pipeline_DIB_Labels_Weights.md)
**Script**: `scripts/fase_D_creando_DIB_VIB/triple_barrier_labeling.py`

**Comando ejecutado**:
```bash
python scripts/fase_D_creando_DIB_VIB/triple_barrier_labeling.py \
  --bars-root processed/dib_bars/pilot50_validation \
  --outdir processed/labels_pilot50 \
  --pt-mul 3.0 \
  --sl-mul 2.0 \
  --t1-bars 120 \
  --vol-est ema \
  --vol-window 50 \
  --parallel 12 \
  --resume
```

**Parámetros**:
- `--pt-mul 3.0`: Profit Target = 3σ
- `--sl-mul 2.0`: Stop Loss = 2σ
- `--t1-bars 120`: Vertical barrier (120 barras máximo)
- `--vol-est ema`: Estimación volatilidad con EMA
- `--vol-window 50`: Ventana EMA 50 barras

**Proceso**:
1. **Escaneo inicial** (5-10 min): Itera sobre 96,897 archivos DIB
2. **Labeling paralelo**: 12 workers procesan simultáneamente
3. **Por cada barra**: Aplica triple barrier (profit target, stop loss, time limit)
4. **Output**: Labels con `{anchor_ts, t1, pt_hit, sl_hit, label, ret_at_outcome, vol_at_anchor}`

**Tiempo estimado**:
- Escaneo: 5-10 min (sin output - normal)
- Procesamiento: 25-40 min
- **Total**: 30-50 min

**Output esperado**:
```
processed/labels_pilot50/{TICKER}/date={YYYY-MM-DD}/
└── labels.parquet
    Schema:
    - anchor_ts: Datetime        # Timestamp de la barra etiquetada
    - t1: Datetime               # Timestamp cuando se resuelve la label
    - pt_hit: Boolean            # ¿Tocó profit target?
    - sl_hit: Boolean            # ¿Tocó stop loss?
    - label: Int8                # 1=profit, -1=loss, 0=vertical barrier
    - ret_at_outcome: Float64    # Retorno al resolver
    - vol_at_anchor: Float64     # Volatilidad en anchor_ts
```

**Status final** (2025-10-29 21:13:55):
- ✅ **COMPLETADO**: 96,897 / 96,897 archivos (100%)
- ⏱️ **Tiempo total**: 126.1 minutos (~2h 6min)
- 🔄 **Errores**: 0
- 📊 **Velocidad promedio**: ~12.8 archivos/segundo

---

## Fase F.7.2: Sample Weights (PENDIENTE)

**Documentación base**: [D.1.3_notas_6.1_SampleWeights.md](../../D_creando_DIB_VIB_2004_2025/D.1.3_notas_6.1_SampleWeights.md)
**Script**: `scripts/fase_D_creando_DIB_VIB/make_sample_weights.py`

**Parámetros previstos**:
```bash
--bars-root processed/dib_bars/pilot50_validation
--labels-root processed/labels_pilot50
--outdir processed/weights_pilot50
--uniqueness              # Temporal overlap weighting
--abs-ret-weight          # Weight by |ret_at_outcome|
--time-decay-half_life 90 # 90-day half-life
--parallel 12
--resume
```

**Fórmula**:
```
weight[i] = (|ret_at_outcome[i]| / concurrency[i]) × decay[i]
Normalización: sum(weights) = 1.0 por archivo
```

**Output esperado**:
```
processed/weights_pilot50/{TICKER}/date={YYYY-MM-DD}/
└── weights.parquet
    Schema: {anchor_ts, weight}
```

**Tiempo estimado**: 20-30 min

---

## A Dónde Vamos

### Objetivo Final: Validación Híbrida Ventanas Óptimas

**Documentación**: [F.6_validacion_ventanas_optimas.md](F.6_validacion_ventanas_optimas.md)
**Notebook**: [validacion_ventanas_hibrida.ipynb](notebooks/validacion_ventanas_hibrida.ipynb)

**Enfoque híbrido de 3 fases**:

1. **Fase 1 (Information Theory)**:
   - Mutual Information I(X_t; y) por día relativo
   - Filtrado rápido: descarta días sin señal
   - Model-agnostic

2. **Fase 2 (Model Performance)**:
   - LightGBM + AUC + Edge económico
   - Score = (edge × AUC) / log(n_bars)
   - Mide valor económico real

3. **Fase 3 (Paper-Grade Refinements)**:
   - Normalized Mutual Information (NMI)
   - Heatmap bidimensional (evento × tiempo)
   - Coeficiente Spearman (concordancia MI vs Edge)
   - Hybrid score automático: α·MI + (1-α)·Edge

**Resultado esperado**:
- Ventanas óptimas [t_start, t_end] para cada evento E1-E11
- Comparación vs ventanas cualitativas (F.3)
- Actualización de `EVENT_WINDOWS` en `event_detectors.py`

---

## Pipeline Completo: Resumen

```
┌─────────────────────────────────────────────────────────────┐
│ FASE F.5: DESCARGA PILOT50 ✅                               │
├─────────────────────────────────────────────────────────────┤
│ Input:  universe/pilot50_validation/daily/                 │
│ Output: raw/polygon/trades_pilot50_validation/             │
│ Files:  139,684 trades.parquet                             │
│ Time:   162.8 min                                           │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ FASE F.6: DIB BARS ✅                                       │
├─────────────────────────────────────────────────────────────┤
│ Input:  raw/polygon/trades_pilot50_validation/             │
│ Output: processed/dib_bars/pilot50_validation/             │
│ Files:  96,897 dollar_imbalance.parquet                    │
│ Time:   102.1 min                                           │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ FASE F.7.1: TRIPLE BARRIER LABELING ✅                     │
├─────────────────────────────────────────────────────────────┤
│ Input:  processed/dib_bars/pilot50_validation/             │
│ Output: processed/labels_pilot50/                          │
│ Files:  96,897 labels.parquet                              │
│ Time:   126.1 min                                           │
│ Status: COMPLETADO (100%, 0 errores)                       │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ FASE F.7.2: SAMPLE WEIGHTS ⏳                              │
├─────────────────────────────────────────────────────────────┤
│ Input:  processed/dib_bars/pilot50_validation/             │
│         processed/labels_pilot50/                          │
│ Output: processed/weights_pilot50/                         │
│ Files:  96,897 weights.parquet (esperado)                  │
│ Time:   20-30 min (estimado)                               │
│ Status: PENDIENTE                                           │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ FASE F.8: VALIDACIÓN HÍBRIDA VENTANAS ⏳                   │
├─────────────────────────────────────────────────────────────┤
│ Input:  processed/dib_bars/pilot50_validation/             │
│         processed/labels_pilot50/                          │
│         processed/weights_pilot50/                         │
│ Output: Ventanas óptimas [t_start, t_end] por evento      │
│         optimal_windows_empirical.csv                      │
│         Notebooks ejecutados + visualizaciones             │
│ Time:   30-60 min (notebook completo)                      │
│ Status: PENDIENTE (esperando labels + weights)             │
└─────────────────────────────────────────────────────────────┘
```

---

## Archivos Clave Creados/Modificados

### Scripts
- `scripts/fase_D_creando_DIB_VIB/build_bars_from_trades.py` (usado para DIB)
- `scripts/fase_D_creando_DIB_VIB/triple_barrier_labeling.py` (D.2 - ejecutando)
- `scripts/fase_D_creando_DIB_VIB/make_sample_weights.py` (D.3 - pendiente)

### Notebooks
- **`notebooks/validacion_ventanas_hibrida.ipynb`** (46 celdas - objetivo final)
  - Actualizado con paths limpios:
    - `LABELS_ROOT = Path('../../../../processed/labels_pilot50')`
    - `WEIGHTS_ROOT = Path('../../../../processed/weights_pilot50')`

### Documentación
- [F.5_auditoria_descarga_pilot50.md](F.5_auditoria_descarga_pilot50.md) - Descarga Pilot50
- [F.6_validacion_ventanas_optimas.md](F.6_validacion_ventanas_optimas.md) - Framework híbrido
- [F.7_pipeline_labels_weights_pilot50.md](F.7_pipeline_labels_weights_pilot50.md) - **Este documento**

### Directorios de Datos
```
processed/
├── dib_bars/pilot50_validation/     # 96,897 archivos ✅
├── labels_pilot50/                  # En construcción 🔄
├── weights_pilot50/                 # Pendiente ⏳
└── dataset_pilot50/                 # Para análisis notebook ⏳
```

---

## Diferencias vs Pipeline E0 (Fase D)

| Aspecto | Pipeline E0 (Fase D) | Pipeline Pilot50 (Fase F.7) |
|---------|---------------------|----------------------------|
| **Periodo** | 2004-2025 (21 años) | 2020-2025 (5 años) |
| **Tickers** | 4,874 tickers | 50 tickers (Pilot) |
| **Eventos** | E0 (Always True) | E1-E11 (sin E0) |
| **Archivos DIB** | 64,801 | 96,897 |
| **Objetivo** | Dataset ML definitivo | Validación ventanas óptimas |
| **Paths output** | `processed/labels/` | `processed/labels_pilot50/` |
| **Uso final** | Baseline model E0 | Determinar EVENT_WINDOWS empírico |

**Nota crítica**: E0 se agregará DESPUÉS de validar ventanas. Entonces se descargará universo completo E0-E11 con ventanas empíricamente optimizadas.

---

## Siguiente Paso Inmediato

Una vez complete F.7.2 (Sample Weights):

1. **Ejecutar notebook completo**: `validacion_ventanas_hibrida.ipynb`
   - Fase 1: Information Theory (MI, IG, FI)
   - Fase 2: Model Performance (AUC, Edge, Score)
   - Fase 3: Paper-grade (NMI, Spearman, Hybrid)

2. **Analizar resultados**:
   - Comparar ventanas empíricas vs cualitativas (F.3)
   - Identificar ventanas asimétricas
   - Generar `EVENT_WINDOWS_EMPIRICAL`

3. **Actualizar producción**:
   - Modificar `event_detectors.py` con ventanas validadas
   - Generar watchlist E0-E11 completo con ventanas óptimas
   - Lanzar descarga universo completo (~300K ticker-days adicionales)

---

## Monitoreo en Tiempo Real

**Comando para ver progreso**:
```bash
# Contar archivos procesados
find processed/labels_pilot50 -name "labels.parquet" | wc -l

# Ver logs del proceso
# (output se actualiza automáticamente cada 200 archivos)
```

**Indicadores de éxito**:
- ✅ Directorio `processed/labels_pilot50/` creado
- ✅ Primer log: `"Tareas: 96,897 | paralelismo=12"`
- ✅ Logs cada 200 archivos: `"Progreso: 200/96897"`, `"Progreso: 400/96897"`, etc.
- ✅ Log final: `"FIN en X.X min"`
- ✅ 96,897 archivos `labels.parquet` creados

---

**Última actualización**: 2025-10-29 21:13:55
**Status**: D.2 Triple Barrier Labeling COMPLETADO ✅ (126.1 min, 96,897 archivos, 0 errores)
**Próximo paso**: D.3 Sample Weights (20-30 min estimado)
