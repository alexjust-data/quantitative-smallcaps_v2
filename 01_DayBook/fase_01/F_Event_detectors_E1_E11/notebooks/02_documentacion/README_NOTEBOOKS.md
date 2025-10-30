# Guía de Notebooks - Validación Híbrida de Ventanas

## 📚 ESTRUCTURA DE NOTEBOOKS

Esta carpeta contiene **5 notebooks** organizados en un pipeline modular de 3 fases:

---

## ✅ NOTEBOOKS PRINCIPALES (USAR ESTOS)

### 🔹 **OPCIÓN 1: Source Code Limpios (Para Editar/Re-ejecutar)**

| Notebook | Propósito | Tiempo | Input | Output |
|----------|-----------|--------|-------|--------|
| **phase1_information_theory.ipynb** | Calcular Mutual Information por día relativo + Exportar TradingView | ~10-20 min | DIB bars, watchlist | `phase1_results.pkl`, CSVs TradingView |
| **phase2_model_performance.ipynb** | Validar edge económico con LightGBM | ~20-40 min | `phase1_results.pkl`, dataset_pilot50 | `phase2_results.pkl` |
| **phase3_paper_grade_analysis.ipynb** | Análisis estadístico + Hybrid Score | ~5-10 min | `phase1_results.pkl`, `phase2_results.pkl` | Ventanas finales |

**Cuándo usar:**
- Quieres modificar parámetros (thresholds, sample_size, etc.)
- Quieres re-ejecutar desde cero
- Quieres entender el código

---

### 🔹 **OPCIÓN 2: Notebooks Ejecutados (Para Ver Resultados)**

| Notebook | Propósito | Tamaño | Contiene |
|----------|-----------|--------|----------|
| **phase1_FINAL_WITH_TRADINGVIEW.ipynb** | Phase1 ejecutado con todos los outputs | 842K | Gráficos MI, validación visual, **CSVs TradingView generados** |
| **phase2_model_performance_FIXED.ipynb** | Phase2 ejecutado con path correcto | 190K | Resultados LightGBM, gráficos AUC/Edge, **ventanas óptimas [0,0]** |

**Cuándo usar:**
- Solo quieres ver los resultados sin ejecutar
- Verificar que los notebooks funcionaron correctamente
- Revisar gráficos y métricas

---

## 🚀 CÓMO EJECUTAR EL PIPELINE COMPLETO

### **Pre-requisitos:**
```bash
# Verificar que existen estos directorios:
ls processed/dib_bars/pilot50_validation/     # DIB bars descargados
ls processed/dataset_pilot50/daily/            # Dataset enriquecido (D.4)
ls processed/universe/pilot50_validation/daily/ # Watchlist con eventos
```

### **Ejecución Secuencial:**

#### **Paso 1: Phase 1 - Information Theory** (~15 min)
```bash
cd 01_DayBook/fase_01/F_Event_detectors_E1_E11/notebooks
jupyter nbconvert --to notebook --execute phase1_information_theory.ipynb \
    --output phase1_executed.ipynb
```

**Genera:**
- `phase1_results.pkl` - Checkpoint con MI scores
- `tradingview_exports/*.csv` - 11 CSVs con 44,189 eventos
- `information_by_day_phase1.png` - Visualización MI
- `validation_*.png` - Validación visual de captura de movimiento

---

#### **Paso 2: Phase 2 - Model Performance** (~30 min)
```bash
jupyter nbconvert --to notebook --execute phase2_model_performance.ipynb \
    --output phase2_executed.ipynb
```

**Genera:**
- `phase2_results.pkl` - Checkpoint con AUC/Edge
- `window_optimization_phase2.png` - Comparación de ventanas
- `optimal_windows_empirical_phase2.csv` - Mejores ventanas por evento

---

#### **Paso 3: Phase 3 - Paper Grade** (~10 min)
```bash
jupyter nbconvert --to notebook --execute phase3_paper_grade_analysis.ipynb \
    --output phase3_executed.ipynb
```

**Genera:**
- Análisis estadístico completo (NMI, Spearman)
- Hybrid score final
- Comparación MI vs LightGBM vs Qualitative

---

## 📊 RESULTADOS CLAVE OBTENIDOS

### **Phase 1 - Mutual Information:**
```
E10_FirstGreenBounce → [-3, +3]
E11_VolumeBounce     → [-3, +3]
E1_VolExplosion      → [-3, +3]
```
**Problema detectado:** Threshold 10% demasiado bajo, todas las ventanas son iguales.

---

### **Phase 2 - LightGBM (DATOS REALES):**
```
E10_FirstGreenBounce:
  [0,0]: AUC=0.963, Edge=1.21%, n=6,137  ⭐ MEJOR
  [1,0]: AUC=0.942, Edge=0.70%, n=10,826
  [0,1]: AUC=0.940, Edge=0.59%, n=10,759

E11_VolumeBounce:
  [0,0]: AUC=0.975, Edge=2.09%, n=6,750  ⭐ MEJOR
  [0,1]: AUC=0.967, Edge=1.51%, n=10,536
  [1,0]: AUC=0.962, Edge=1.16%, n=10,456
```

**Conclusión:** Ventanas pequeñas [0,0] tienen mejor performance económico.

---

## 🎯 TradingView Export

**Archivos generados** (44,189 eventos total):
```
tradingview_exports/
├── tradingview_E1_VolExplosion.csv          (7,686 eventos)
├── tradingview_E10_FirstGreenBounce.csv     (8,494 eventos)
├── tradingview_E11_VolumeBounce.csv         (1,256 eventos)
├── tradingview_E2_GapUp.csv                 (1,070 eventos)
├── ... (7 archivos más)
```

**Formato CSV:**
```csv
ticker,datetime,close_price,event_code,window_suggested,date
NAII,2004-01-08 14:27:42.000000,6.3,E10_FirstGreenBounce,"[-3,+3]",2004-01-08
```

**Ver:** [TRADINGVIEW_USAGE_GUIDE.md](TRADINGVIEW_USAGE_GUIDE.md) para instrucciones completas.

---

## 🔧 TROUBLESHOOTING

### Problema: "FileNotFoundError: phase1_results.pkl"
**Solución:** Ejecuta Phase 1 primero.

### Problema: "n_bars=0" en Phase 2
**Solución:** Ya corregido en `phase2_model_performance.ipynb`. Path ahora incluye `/daily/` subdirectory.

### Problema: Phase 3 falla con KeyError
**Solución:** Pendiente de fix. Usar solo Phase 1 + Phase 2 por ahora.

---

## 📁 ARCHIVOS AUXILIARES

```
01_DayBook/fase_01/F_Event_detectors_E1_E11/notebooks/
├── README_MODULAR_NOTEBOOKS.md     # Arquitectura modular, checkpoints
├── REVISION_NOTEBOOK.md            # Auditoría técnica del notebook original
├── TRADINGVIEW_USAGE_GUIDE.md      # Cómo usar los CSVs en TradingView
├── README_NOTEBOOKS.md             # Este archivo
├── phase1_results.pkl              # Checkpoint Phase 1
├── phase2_results.pkl              # Checkpoint Phase 2
├── *.png                           # Gráficos generados
└── tradingview_exports/            # CSVs para TradingView
```

---

## 🎓 CONCEPTOS CLAVE

### **Mutual Information (MI)**
- Mide dependencia estadística entre features y retornos futuros
- Model-agnostic (no depende de LightGBM)
- **Problema:** Normalización por max hace que threshold sea demasiado permisivo

### **Economic Edge**
- Expected return si tradeamos cuando modelo predice profit
- Medida en Phase 2 con LightGBM
- **Más realista** que MI para trading

### **Ventanas:**
- `[pre_days, post_days]` → Días antes y después del evento
- `[0,0]` = Solo día del evento
- `[-3,+3]` = 3 días antes + día evento + 3 días después

---

## ✅ PRÓXIMOS PASOS

1. **Validación Visual:**
   - Abrir [TRADINGVIEW_USAGE_GUIDE.md](TRADINGVIEW_USAGE_GUIDE.md)
   - Visualizar 10-20 eventos por tipo en TradingView
   - Anotar si ventanas [0,0] vs [-3,+3] capturan mejor el movimiento

2. **Ajustar Phase 1:**
   - Aumentar threshold MI de 10% a 30-50%
   - Re-ejecutar `phase1_information_theory.ipynb`

3. **Decidir Ventanas Finales:**
   - Basado en validación visual + performance económico Phase 2
   - Actualizar `EVENT_WINDOWS_EMPIRICAL` en producción

4. **Ejecutar Pipeline Completo:**
   - Con 11 eventos (no solo 3)
   - Con sample_size más grande (500-1000)
   - Generar reporte final

---

**Última actualización:** 2025-10-30
**Total notebooks activos:** 5
**Notebooks eliminados:** 7
**Espacio liberado:** ~2.5 MB
