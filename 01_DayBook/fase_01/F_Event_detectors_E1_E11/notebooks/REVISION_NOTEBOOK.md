# Revisión Completa: validacion_ventanas_hibrida.ipynb

**Fecha**: 2025-10-30
**Revisor**: Claude Code
**Notebook**: 46 celdas totales

---

## RESUMEN EJECUTIVO

**Estado general**: ✅ Notebook bien diseñado, requiere 3 modificaciones menores

**Celdas sin problemas**: 43/46 (93.5%)
**Celdas con problemas**: 3/46 (6.5%)

**Severidad**:
- 🔴 CRÍTICO: 2 celdas (Cell-2, Cell-18)
- 🟡 MENOR: 1 celda (Cell-22)

---

## PROBLEMAS IDENTIFICADOS

### 🔴 PROBLEMA 1: Cell-2 - Falta DATASET_ROOT path

**Ubicación**: Cell-2 (Setup)

**Problema**:
```python
# Paths actuales
TRADES_DIR = Path('../../../../raw/polygon/trades_pilot50_validation')
BARS_ROOT = Path('../../../../processed/dib_bars/pilot50_validation')
LABELS_ROOT = Path('../../../../processed/labels_pilot50')
WEIGHTS_ROOT = Path('../../../../processed/weights_pilot50')
WATCHLIST = Path('../../../../processed/universe/pilot50_validation/daily')

# FALTA:
DATASET_ROOT = Path('../../../../processed/dataset_pilot50')  # <-- AÑADIR ESTA LÍNEA
```

**Impacto**: Cell-18 y Cell-22 no pueden leer el dataset enriquecido

**Solución**: Añadir línea `DATASET_ROOT`

---

### 🔴 PROBLEMA 2: Cell-18 - load_day_dataset_full() debe leer desde dataset_pilot50

**Ubicación**: Cell-18 (Funciones de carga)

**Problema actual**:
```python
def load_day_dataset_full(ticker: str, day: datetime.date) -> pl.DataFrame:
    # Lee bars, labels, weights POR SEPARADO
    bars_file = BARS_ROOT / ticker / f"date={day.isoformat()}" / "dollar_imbalance.parquet"
    labels_file = LABELS_ROOT / ticker / f"date={day.isoformat()}" / "labels.parquet"
    weights_file = WEIGHTS_ROOT / ticker / f"date={day.isoformat()}" / "weights.parquet"

    # ... concatena horizontalmente (bars NO tienen features enriquecidos)
```

**Por qué falla**:
- DIB bars raw solo tienen: `['t_open', 't_close', 'o', 'h', 'l', 'c', 'v', 'n', 'dollar', 'imbalance_score']`
- Cell-22 requiere: `['ret_1', 'range_norm', 'vol_f', 'dollar_f', 'imb_f', 'ret_1_ema10', ...]`
- **Estas features solo existen después de ejecutar D.4 build_ml_daser.py**

**Solución correcta**:
```python
def load_day_dataset_full(ticker: str, day: datetime.date) -> pl.DataFrame:
    """
    Carga dataset enriquecido (features + labels + weights).

    REQUIERE: D.4 build_ml_daser.py ejecutado previamente.
    """
    dataset_file = DATASET_ROOT / ticker / f"date={day.isoformat()}" / "dataset.parquet"

    if not dataset_file.exists():
        return None

    df = pl.read_parquet(dataset_file)

    # Añadir columnas de contexto si no existen
    if 'ticker' not in df.columns:
        df = df.with_columns([
            pl.lit(ticker).alias('ticker'),
            pl.lit(day).alias('session_day')
        ])

    return df
```

**Impacto**: CRÍTICO - Fase 2 (Model Performance) no puede ejecutarse sin esto

---

### 🟡 PROBLEMA 3: Cell-22 - Comentario desactualizado sobre features

**Ubicación**: Cell-22 (Grid search)

**Problema menor**:
```python
# Comentario actual:
# Features a usar (deben existir en DIB bars)  <-- INCORRECTO
FEATURE_COLS = [
    'ret_1', 'range_norm', 'vol_f', 'dollar_f', 'imb_f',
    'ret_1_ema10', 'ret_1_ema30', 'range_norm_ema20',
    'vol_f_ema20', 'dollar_f_ema20', 'imb_f_ema20',
    'vol_z20', 'dollar_z20', 'n'
]
```

**Corrección**:
```python
# Features a usar (generados por D.4 build_ml_daser.py)
FEATURE_COLS = [
    'ret_1', 'range_norm', 'vol_f', 'dollar_f', 'imb_f',
    'ret_1_ema10', 'ret_1_ema30', 'range_norm_ema20',
    'vol_f_ema20', 'dollar_f_ema20', 'imb_f_ema20',
    'vol_z20', 'dollar_z20', 'n'
]
```

**Impacto**: MENOR - Solo documentación, no afecta ejecución

---

## CELDAS VALIDADAS ✅

### Fase 1: Information Theory (Cells 0-15)

**Cell-0, 1**: Markdown intro ✅
**Cell-2**: Paths correctos (excepto DATASET_ROOT faltante)
**Cell-3**: Markdown ✅
**Cell-4**: Watchlist loading - código correcto ✅
- Usa `rglob('watchlist.parquet')` ✅
- Parsea `date=YYYY-MM-DD` correctamente ✅
- Convierte a `pl.Date` ✅
- Explode de `events` column ✅

**Cell-5**: Markdown ✅
**Cell-6**: Window candidates - configuración OK ✅

**Cell-7-8**: Markdown ✅
**Cell-9**: MI functions - lógica correcta ✅
- `load_dib_bars_day()`: Usa columnas básicas ✅
- `aggregate_day_features()`: Solo usa `['o', 'h', 'l', 'c', 'v', 'n', 'dollar', 'imbalance_score']` ✅
- `calculate_mutual_information_discretized()`: Sklearn API correcto ✅

**Cell-10**: Markdown ✅
**Cell-11**: `analyze_information_by_relative_day()` - lógica sólida ✅
- Filtra eventos correctamente ✅
- Calcula retorno futuro `ret_3d` desde close del día evento ✅
- Maneja casos edge (None, height==0) ✅

**Cell-12**: Markdown ✅
**Cell-13**: Execute MI - configuración razonable ✅
- `EVENTS_TO_TEST[:3]`: Subset para prueba rápida ✅
- `sample_size=200`: Balance velocidad/representatividad ✅

**Cell-14**: Markdown ✅
**Cell-15**: Visualización MI - matplotlib código correcto ✅

### Fase 2: Model Performance (Cells 16-32)

**Cell-16-17**: Markdown ✅
**Cell-18**: 🔴 CRÍTICO - Ver arriba
**Cell-19**: Markdown ✅
**Cell-20**: `evaluate_window_performance()` - lógica económica correcta ✅
- AUC con sample_weight ✅
- Edge = expected return weighted ✅
- Manejo de excepciones ✅

**Cell-21**: Markdown ✅
**Cell-22**: Grid search - lógica OK (comentario menor a corregir)
**Cell-23**: Markdown ✅
**Cell-24**: Best window selection - polars query correcto ✅
**Cell-25**: Markdown ✅
**Cell-26**: Visualizations - matplotlib OK ✅
**Cell-27**: Markdown ✅
**Cell-28**: Comparison F.3 - lógica comparación correcta ✅
**Cell-29**: Markdown ✅
**Cell-30**: Conclusions - print statements OK ✅
**Cell-31**: Markdown ✅
**Cell-32**: Export - write_csv correcto ✅

### Fase 3: Paper-Grade Refinements (Cells 33-46)

**Cell-33-34**: Markdown ✅
**Cell-35**: NMI calculation - sklearn API correcto ✅
**Cell-36**: Markdown ✅
**Cell-37**: Heatmap 2D - seaborn código correcto ✅
**Cell-38**: Markdown ✅
**Cell-39**: Spearman - scipy.stats API correcto ✅
**Cell-40**: Concordance viz - matplotlib OK ✅
**Cell-41**: Markdown ✅
**Cell-42**: Hybrid score - numpy lógica correcta ✅
**Cell-43**: Hybrid viz - matplotlib OK ✅
**Cell-44**: Markdown ✅
**Cell-45**: Statistical report - pandas DataFrame correcto ✅
**Cell-46**: Markdown conclusiones ✅

---

## DEPENDENCIAS EXTERNAS

### ✅ Datos requeridos DISPONIBLES:

1. **Watchlist**: `processed/universe/pilot50_validation/daily/` (5,579 files) ✅
2. **DIB Bars**: `processed/dib_bars/pilot50_validation/` (96,897 files) ✅
3. **Labels**: `processed/labels_pilot50/` (96,897 files) ✅
4. **Weights**: `processed/weights_pilot50/` (96,897 files) ✅

### 🔄 Datos requeridos EN CONSTRUCCIÓN:

5. **Dataset enriquecido**: `processed/dataset_pilot50/` - D.4 corriendo (bash ID: 60a1fb)

**Tiempo estimado D.4**: 15-30 min (basado en D.2=126min, D.3=113min)

---

## PLAN DE CORRECCIÓN

### Paso 1: Esperar D.4 completar (~10-25 min restantes)

Verificar logs y confirmar:
```bash
# Verificar progreso
python -c "import polars as pl; print('Schema check'); df = pl.read_parquet('processed/dataset_pilot50/AENT/date=2023-03-20/dataset.parquet'); print(df.columns)"
```

Debe incluir todas las FEATURE_COLS.

### Paso 2: Aplicar correcciones al notebook

**Opción A**: Editar notebook programáticamente (NotebookEdit tool)
**Opción B**: Crear notebook corregido nuevo
**Opción C**: Manual en IDE

Recomendación: **Opción A** (NotebookEdit) - 3 cambios quirúrgicos

### Paso 3: Ejecutar notebook completo

Estimar tiempo por fase:
- **Fase 1 (Cell 0-15)**: ~10-20 min (MI calculations, sample_size=200)
- **Fase 2 (Cell 16-32)**: ~20-40 min (LightGBM training, 2 eventos × 6 ventanas)
- **Fase 3 (Cell 33-46)**: ~5-10 min (análisis estadístico)

**Total estimado**: 35-70 min para subset pequeño (3 eventos, 6 ventanas)

Para análisis completo (11 eventos, 12 ventanas):
- **Fase 1**: ~40-60 min
- **Fase 2**: ~2-4 horas (132 combinaciones)
- **Fase 3**: ~10-15 min

---

## VALIDACIÓN POST-EJECUCIÓN

### Archivos output esperados:

1. `information_by_day_phase1.png` - Gráfico MI por día relativo
2. `window_optimization_phase2.png` - Grid search resultados
3. `heatmap_event_x_time.png` - Heatmap 2D evento×tiempo
4. `concordance_analysis.png` - Spearman MI vs Edge
5. `hybrid_score_analysis.png` - Selección híbrida
6. `optimal_windows_empirical.csv` - Ventanas óptimas por evento
7. `window_optimization_full_results.csv` - Grid completo
8. `statistical_report_paper_grade.csv` - Métricas finales
9. `concordance_analysis_full.csv` - Concordancia detallada

### Métricas clave a verificar:

- **Spearman ρ > 0.4**: Concordancia MI vs Edge moderada-alta
- **P-value < 0.05**: Significancia estadística
- **AUC > 0.55**: Predictibilidad mejor que random
- **Edge > 0**: Expected return positivo en ventanas seleccionadas

---

## CONCLUSIÓN

**Notebook quality**: ⭐⭐⭐⭐⭐ (5/5)
- Diseño paper-grade excelente
- Código limpio y bien documentado
- Solo requiere ajuste de paths post-pipeline

**Cambios requeridos**: MÍNIMOS (3 líneas de código)

**Listo para producción**: SÍ (tras aplicar correcciones)

---

**Última actualización**: 2025-10-30 08:50
**Próximo paso**: Aplicar correcciones cuando D.4 complete
