# Notebooks Modulares: Validación Híbrida Ventanas Óptimas

**Fecha creación**: 2025-10-30
**Pipeline**: Information Theory + Model Performance + Paper-Grade Analysis
**Objetivo**: Determinar ventanas óptimas [t_start, t_end] para eventos E1-E11

---

## 📁 ESTRUCTURA MODULAR (3 Notebooks)

### ✅ VENTAJAS de esta arquitectura:

1. **Checkpoints automáticos** → Cada notebook guarda `.pkl` con resultados
2. **Ejecución independiente** → Puedes correr Fase 2 mañana sin reejecutar Fase 1
3. **Debugging rápido** → Falla Fase 2? Solo rearrancas ese notebook
4. **Iteración rápida** → Cambiar parámetros Fase 3 sin reejecutar 1-2
5. **Sin pérdida de progreso** → Si falla a mitad, tienes resultados parciales guardados

---

## 📓 NOTEBOOK 1: Information Theory (Fase 1)

**Archivo**: `phase1_information_theory.ipynb`
**Tiempo**: 10-20 min (sample_size=200) | 40-60 min (completo)
**Objetivo**: Calcular Mutual Information por día relativo

### Inputs:
- `processed/dib_bars/pilot50_validation/` (96,897 DIB bars)
- `processed/universe/pilot50_validation/daily/` (5,579 watchlists)

### Proceso:
1. Carga watchlist con eventos
2. Para cada evento:
   - Calcula features agregados diarios (ret_day, range_day, vol_day, dollar_day, imb_day, n_bars)
   - Calcula MI entre features y retorno futuro 3d
   - Identifica días con señal > 10% threshold
3. Visualiza MI por día relativo
4. Guarda `phase1_results.pkl`

### Outputs:
- **phase1_results.pkl** → info_results, wl_expanded, events_available, suggested_windows
- **information_by_day_phase1.png** → Gráficos MI por evento

### Configuración:
```python
# Cell-4: Ajustar subset para prueba rápida
EVENTS_TO_TEST = events_available[:3]  # 3 eventos para prueba
MAX_PRE_DAYS = 3
MAX_POST_DAYS = 3
SAMPLE_SIZE = 200  # Reducir a 100 para velocidad, 500 para precisión
```

### Requisitos:
- ✅ DIB bars con columnas básicas (o, h, l, c, v, n, dollar, imbalance_score)
- ✅ NO requiere features enriquecidos
- ✅ NO requiere labels ni weights

---

## 📓 NOTEBOOK 2: Model Performance (Fase 2)

**Archivo**: `phase2_model_performance.ipynb`
**Tiempo**: 20-40 min (2 eventos × 6 ventanas) | 2-4 horas (completo)
**Objetivo**: Medir edge económico real con LightGBM

### Inputs:
- **phase1_results.pkl** (de Notebook 1)
- `processed/dataset_pilot50/` (D.4 features enriquecidos) ⚠️ CRÍTICO

### Proceso:
1. Carga resultados Fase 1
2. Para cada (evento, ventana):
   - Construye dataset con features enriquecidos
   - Entrena LightGBM classifier (profit vs loss)
   - Calcula AUC + Edge económico
   - Calcula score = (Edge × AUC) / log(n_bars)
3. Selecciona mejor ventana por evento
4. Compara vs ventanas cualitativas F.3
5. Guarda `phase2_results.pkl` + CSVs

### Outputs:
- **phase2_results.pkl** → res_df, best_per_event, comparison_f3
- **optimal_windows_empirical_phase2.csv** → Ventanas óptimas
- **window_optimization_phase2_full.csv** → Grid completo
- **comparison_empirical_vs_f3.csv** → Comparación cualitativo vs empírico
- **window_optimization_phase2.png** → Visualizaciones

### Configuración:
```python
# Cell-2: Ajustar subset
EVENTS_SUBSET = list(info_results.keys())[:2]  # 2 eventos para prueba
WINDOWS_SUBSET = CANDIDATE_WINDOWS[:6]  # 6 ventanas
MAX_SAMPLES = 300  # Sample por evento (500-1000 para más precisión)

# Features requeridos (generados por D.4):
FEATURE_COLS = [
    'ret_1', 'range_norm', 'vol_f', 'dollar_f', 'imb_f',
    'ret_1_ema10', 'ret_1_ema30', 'range_norm_ema20',
    'vol_f_ema20', 'dollar_f_ema20', 'imb_f_ema20',
    'vol_z20', 'dollar_z20', 'n'
]
```

### Requisitos:
- ✅ `phase1_results.pkl` debe existir
- ✅ D.4 build_ml_daser.py debe haber completado
- ✅ `processed/dataset_pilot50/` con features enriquecidos
- ⚠️ **Si D.4 no completó**, este notebook FALLARÁ en Cell-0

---

## 📓 NOTEBOOK 3: Paper-Grade Analysis (Fase 3)

**Archivo**: `phase3_paper_grade_analysis.ipynb`
**Tiempo**: 5-10 min
**Objetivo**: Análisis estadístico riguroso para validación científica

### Inputs:
- **phase1_results.pkl** (de Notebook 1)
- **phase2_results.pkl** (de Notebook 2)

### Proceso:
1. Carga resultados Fase 1 + 2
2. Calcula Normalized Mutual Information (NMI)
3. Genera heatmap 2D (evento × día relativo)
4. Calcula correlación Spearman (MI vs Edge)
5. Aplica Hybrid Score (α·MI + (1-α)·Edge)
6. Genera reporte estadístico completo
7. Exporta diccionario Python para producción

### Outputs:
- **statistical_report_paper_grade.csv** → Métricas completas
- **concordance_analysis_full.csv** → Concordancia MI/Edge
- **heatmap_event_x_time.png** → Heatmap 2D
- **concordance_analysis.png** → Visualizaciones Spearman
- **EVENT_WINDOWS_EMPIRICAL** → Diccionario Python

### Configuración:
```python
# Cell-6: Ajustar parámetros hybrid score
ALPHA = 0.6  # Peso para MI (60% MI, 40% Edge)
QUANTILE_THRESHOLD = 0.8  # Top 20% ventanas
```

### Requisitos:
- ✅ `phase1_results.pkl` debe existir
- ✅ `phase2_results.pkl` debe existir
- ✅ **Este notebook es rápido** → Puede ejecutarse múltiples veces con diferentes α

---

## 🔄 FLUJO DE EJECUCIÓN RECOMENDADO

### Opción A: Ejecución Secuencial (Todo de una vez)

```bash
# Día 1 completo:
jupyter execute phase1_information_theory.ipynb      # 10-20 min
jupyter execute phase2_model_performance.ipynb        # 20-40 min
jupyter execute phase3_paper_grade_analysis.ipynb    # 5-10 min
# Total: ~35-70 min
```

### Opción B: Ejecución Incremental (Días separados)

```bash
# Día 1: Information Theory
jupyter execute phase1_information_theory.ipynb
# → Genera phase1_results.pkl

# Día 2: Model Performance (requiere D.4 completo)
jupyter execute phase2_model_performance.ipynb
# → Genera phase2_results.pkl

# Día 3: Análisis estadístico (puedes ejecutar N veces)
jupyter execute phase3_paper_grade_analysis.ipynb
```

### Opción C: Debugging (Rearrancar desde fallo)

```bash
# Si Fase 2 falló a mitad:
# 1. No pierdes resultados Fase 1 (phase1_results.pkl existe)
# 2. Arreglas el problema (ej: D.4 no completo)
# 3. Rearrancas solo Fase 2:
jupyter execute phase2_model_performance.ipynb

# Si quieres probar diferentes α en hybrid score:
# 1. Editas Cell-6 de Notebook 3
# 2. Rearrancas solo Fase 3 (5 min):
jupyter execute phase3_paper_grade_analysis.ipynb
```

---

## ⚙️ DEPENDENCIAS PRE-EJECUCIÓN

### Para Notebook 1:
- ✅ `processed/dib_bars/pilot50_validation/` (96,897 archivos)
- ✅ `processed/universe/pilot50_validation/daily/` (5,579 watchlists)

### Para Notebook 2:
- ✅ `phase1_results.pkl` (generado por Notebook 1)
- ✅ `processed/dataset_pilot50/` (⚠️ REQUIERE D.4 completo)

**Verificar D.4**:
```bash
# Check si dataset existe y tiene features:
python -c "import polars as pl; df = pl.read_parquet('processed/dataset_pilot50/AENT/date=2023-03-20/dataset.parquet'); print(df.columns)"

# Debe incluir: ret_1, range_norm, vol_f, dollar_f, imb_f, ret_1_ema10, etc.
```

**Si D.4 no completó**, ejecuta:
```bash
python scripts/fase_D_creando_DIB_VIB/build_ml_daser.py \
  --bars-root processed/dib_bars/pilot50_validation \
  --labels-root processed/labels_pilot50 \
  --weights-root processed/weights_pilot50 \
  --outdir processed/dataset_pilot50 \
  --bar-file dollar_imbalance.parquet \
  --parallel 12 \
  --resume \
  --split none
# Tiempo: ~15-30 min
```

### Para Notebook 3:
- ✅ `phase1_results.pkl` (generado por Notebook 1)
- ✅ `phase2_results.pkl` (generado por Notebook 2)

---

## 📊 OUTPUTS FINALES ESPERADOS

Después de ejecutar los 3 notebooks:

### Archivos pickle (checkpoints):
- `phase1_results.pkl` → info_results, wl_expanded, suggested_windows
- `phase2_results.pkl` → res_df, best_per_event, comparison_f3

### CSVs (análisis):
- `optimal_windows_empirical_phase2.csv` → Ventanas óptimas por evento
- `window_optimization_phase2_full.csv` → Grid search completo
- `comparison_empirical_vs_f3.csv` → Comparación cualitativo vs empírico
- `statistical_report_paper_grade.csv` → Métricas estadísticas
- `concordance_analysis_full.csv` → Concordancia MI/Edge

### Imágenes (visualizaciones):
- `information_by_day_phase1.png` → MI por día relativo (Fase 1)
- `window_optimization_phase2.png` → Grid search visualizations (Fase 2)
- `heatmap_event_x_time.png` → Heatmap 2D evento×tiempo (Fase 3)
- `concordance_analysis.png` → Spearman + divergencias (Fase 3)

### Diccionario Python (producción):
```python
EVENT_WINDOWS_EMPIRICAL = {
    'E1_VolExplosion': (1, 1),  # AUC=0.xxx, Edge=0.xxxx
    'E2_GapUp': (2, 1),  # AUC=0.xxx, Edge=0.xxxx
    # ...
}
```

---

## 🐛 TROUBLESHOOTING

### Error: "Dataset directory not found"
**Problema**: D.4 no completó
**Solución**: Ejecuta `build_ml_daser.py` (ver sección Dependencias)

### Error: "phase1_results.pkl not found"
**Problema**: No ejecutaste Notebook 1
**Solución**: Ejecuta `phase1_information_theory.ipynb` primero

### Error: "KeyError: 'ret_1_ema10'"
**Problema**: Dataset no tiene features enriquecidos
**Solución**: Verifica que D.4 completó correctamente, re-ejecuta si necesario

### Notebook tarda demasiado (> 1 hora)
**Problema**: Usando dataset completo en prueba
**Solución**: Reduce subset en configuración:
```python
# Notebook 1, Cell-4:
EVENTS_TO_TEST = events_available[:3]
SAMPLE_SIZE = 100

# Notebook 2, Cell-2:
EVENTS_SUBSET = list(info_results.keys())[:2]
WINDOWS_SUBSET = CANDIDATE_WINDOWS[:6]
MAX_SAMPLES = 300
```

### Quiero probar diferentes parámetros
**Opción**: Solo rearranca el notebook específico
- Cambiar MI threshold → Notebook 1
- Cambiar ventanas candidatas → Notebook 2
- Cambiar α hybrid score → Notebook 3

---

## 📈 MÉTRICAS DE ÉXITO

### Fase 1 (Information Theory):
- ✅ MI > 0.1 (normalizado) en al menos 1 día por evento
- ✅ Ventanas sugeridas detectadas automáticamente
- ✅ Gráficos muestran picos claros alrededor de t=0

### Fase 2 (Model Performance):
- ✅ AUC > 0.55 (mejor que random)
- ✅ Edge > 0 (expected return positivo)
- ✅ Score compuesto identifica ventanas óptimas
- ✅ Comparación vs F.3 muestra concordancia o mejora

### Fase 3 (Paper-Grade):
- ✅ Spearman ρ > 0.4 (concordancia moderada-alta MI vs Edge)
- ✅ P-value < 0.05 (significancia estadística)
- ✅ Hybrid score selecciona top 20% ventanas
- ✅ Diccionario Python generado para producción

---

## 🎯 PRÓXIMOS PASOS POST-EJECUCIÓN

1. **Análisis resultados**:
   - Revisar `optimal_windows_empirical_phase2.csv`
   - Comparar vs ventanas cualitativas F.3
   - Validar que AUC > 0.55 y Edge > 0

2. **Actualizar código producción**:
   - Copiar `EVENT_WINDOWS_EMPIRICAL` a `event_detectors.py`
   - Reemplazar ventanas qualitativas con empíricas

3. **Generar watchlist E0-E11**:
   - Ejecutar `compute_events_watchlist.py` con nuevas ventanas
   - Output: `processed/universe/e0_e11/daily/`

4. **Descargar universo completo**:
   - Lanzar download con ventanas optimizadas
   - ~300K ticker-days adicionales

---

**Última actualización**: 2025-10-30
**Autor**: Claude Code + User Collaboration
**Versión**: 1.0 - Notebooks Modulares con Checkpoints
