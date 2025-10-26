
### 1. **Clarify objectives — “What exactly are we trying to do or improve?”**

**objetivo de negocio**:

> **Construir un pipeline científico y operativo para detectar, analizar y modelar patrones de *pump & dump* en small caps**, integrando teoría académica (López de Prado) y táctica de trading real (Playbook EduTrades).

**En concreto:**
  
* **Qué se quiere mejorar:** la **capacidad de detección temprana** y **clasificación precisa** de fases de un pump & dump (impulso, distribución, colapso, rebote).
* **Qué se está midiendo:** el **valor informacional** de los activos (actividad, volumen, volatilidad) y la **eficacia predictiva** de las señales construidas con *Dollar/Imbalance Bars*, *Triple Barrier Labeling* y *Meta-Labeling*.
* **En qué nivel:** es un proyecto **empresa–producto**, no solo de usuario final, porque su propósito es crear una **infraestructura robusta de datos y modelos** para trading algorítmico y análisis de microestructura.

👉 **Business case:** reducir falsos positivos y mejorar el *timing* de entrada/salida en estrategias long/short sobre microcaps, maximizando rentabilidad ajustada por riesgo.

---

### 2. **Define metrics — “Which metric are we trying to improve?”**

Según el marco de López de Prado y tu Playbook, las métricas de evaluación deben alinearse tanto con el **rendimiento operativo** (trading) como con la **precisión estadística** (modelo).

**🔹 Métricas cuantitativas de modelo (machine learning)**

* **F1-score / Recall:** medir detección correcta de *pump phases* (eventos raros, por tanto *recall* es crítico).
* **Precision:** evitar falsos positivos (falsas alarmas de pump).
* **AUC-ROC / PR Curve:** evaluar discriminación general en eventos desbalanceados.
* **Mean Absolute Error (MAE)** en predicción de duración o magnitud del movimiento.

**🔹 Métricas de negocio/trading**

* **Profit factor** (ganancia media / pérdida media).
* **Max Drawdown y Sharpe ratio.**
* **Win rate** y **expectancy** por setup.
* **Lead time de detección:** cuánto antes el sistema detecta el pump antes del pico de volumen.

**🔹 Métricas de datos (*data quality / coverage*)**

* **Porcentaje de barras informacionales válidas** (DIB/DRB sin huecos).
* **Cobertura temporal (años, tickers)** y **unicidad de eventos** (según Sample Weights).

---

