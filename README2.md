# Small Caps Trading System: Event-Driven ML Pipeline

Sistema cuantitativo para detección y trading algorítmico de patrones característicos en acciones small caps con alta volatilidad.

---

## Objetivo

Construir un pipeline ML que:

1. **Detecta automáticamente** 11 eventos característicos en small caps runners
2. **Optimiza ventanas temporales** usando evidencia empírica (Information Theory + Economic Edge)
3. **Entrena modelos predictivos** sobre datos estructurados en Dollar Imbalance Bars (DIB)
4. **Valida económicamente** cada estrategia antes de producción

---

## Arquitectura: 4 Fases Modulares

### A. Universo & Filtrado
**Criterios**: Market Cap < $2B, Float < 100M, Precio $0.5-$20, Volumen > 500k
- **Fuente**: Polygon.io (20 años de datos históricos)
- **Output**: `raw/polygon/trades_*/` (tick-by-tick trades)

### B. Construcción DIB Bars
**Information-driven sampling** con target $300k USD por barra
- **Input**: Trades tick-by-tick
- **Output**: `processed/dib_bars/*/dollar_imbalance.parquet`
- **Features**: OHLCV + imbalance_score (EMA-50)

### C. Event Detection (E1-E11)
**11 detectores automáticos** de patrones característicos:
- **E1**: VolExplosion - **E2**: GapUp - **E3**: PriceSpikeIntraday
- **E4**: Parabolic - **E5**: BreakoutATH - **E6**: MultipleGreenDays
- **E7**: FirstRedDay - **E8**: GapDownViolent - **E9**: CrashIntraday
- **E10**: FirstGreenBounce - **E11**: VolumeBounce

**Output**: `processed/watchlists/wl_expanded_*.parquet` (44,189 eventos detectados)

### D. ML Dataset Builder
**Pipeline completo** con labeling + weights + features enriquecidos:

1. **D.1 - Triple Barrier Labeling**: Profit target=3σ, Stop=2σ, Vertical=120 bars
2. **D.2 - Sample Weights**: Uniqueness + return-weighted + time decay (90-day half-life)
3. **D.3 - Feature Engineering**: Technical indicators por ventana temporal
4. **D.4 - Dataset Construction**: Join completo (bars + labels + weights + features)

**Output**: `processed/dataset_pilot50/daily/TICKER/date=YYYY-MM-DD/dataset.parquet` (96,897 datasets)

---

## Validación Híbrida de Ventanas (F.6)

**Problema**: ¿Cuántos días antes/después del evento debemos recoger datos?

### Enfoque 2 Fases

**Phase1 - Information Theory** (filtro rápido):
- Mutual Information: I(X_t; y) por día relativo
- Identifica días con señal estadística significativa
- Model-agnostic, interpretable

**Phase2 - Economic Validation** (validación de $$):
- LightGBM por ventana candidata
- Métricas: AUC (separabilidad) + Economic Edge (expected return)
- Mide valor económico real

**Phase3 - Statistical Analysis**:
- Spearman correlation entre MI y Edge
- Concordance analysis para validar consistencia
- Selección final con hybrid score: α·MI + (1-α)·Edge

### Resultados Pilot50

| Event | Phase1 (MI) | Phase2 (Edge) | Economic Edge | Concordance |
|-------|-------------|---------------|---------------|-------------|
| E10_FirstGreenBounce | [-3,+3] | [0,0] | 1.21% (AUC=0.963) | ρ=-0.07 |
| E11_VolumeBounce | [-3,+3] | [0,0] | 2.09% (AUC=0.975) | (p=0.829) |

**Hallazgo clave**: MI y Edge **divergen** (correlación ≈0). Las ventanas óptimas por información ≠ ventanas óptimas por profit.

**Deliverables**:
- 44,189 eventos exportados a TradingView con timestamps exactos
- Pipeline modular 3-phase con checkpoints
- Documentación completa en `01_DayBook/fase_01/F_Event_detectors_E1_E11/`

---

## Data Flow

```
Polygon.io Trades (tick-by-tick)
    ↓
DIB Bars ($300k target, EMA-50)
    ↓
Event Detection (E1-E11) → Watchlist (44k eventos)
    ↓
Triple Barrier Labeling (3σ profit / 2σ stop / 120 bars)
    ↓
Sample Weights (uniqueness + return + decay)
    ↓
Feature Engineering (technical indicators × window)
    ↓
ML Dataset (96,897 enriched datasets)
    ↓
Window Validation (Phase1-3: MI + Edge + Stats)
    ↓
Production Model (LightGBM) → Backtesting → Live Trading
```

---

## Estado Actual

### Completado
- ✅ **Pilot50 Validation**: 50 tickers representativos (2004-2025)
- ✅ **DIB Bars**: 139,684 archivos construidos
- ✅ **Event Detection**: 44,189 eventos E1-E11 detectados
- ✅ **ML Pipeline**: D.1-D.4 completo (96,897 datasets)
- ✅ **Window Validation**: Phase1-3 ejecutado con resultados estadísticos
- ✅ **TradingView Export**: 11 CSV files para validación visual manual

### En Progreso
- 🔄 **Visual Validation**: Verificación manual en TradingView de patrones detectados
- 🔄 **Window Decision**: Selección final entre MI [-3,+3] vs Edge [0,0]

### Próximo
- ⏳ **Full Universe**: Expandir a universo completo (~13k tickers)
- ⏳ **Production Models**: Entrenar LightGBM por evento con ventanas optimizadas
- ⏳ **Backtesting**: Walk-forward validation + purged cross-validation
- ⏳ **Execution Bridge**: Integración con DAS Trader Pro (C#/Python)

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Data Source** | Polygon.io API |
| **Storage** | Parquet (columnar) + Polars (lazy evaluation) |
| **Bars** | Dollar Imbalance Bars (DIB) con EMA-50 |
| **ML** | LightGBM + Triple Barrier Labeling |
| **Validation** | Information Theory (MI/IG) + Economic Edge |
| **Execution** | DAS Trader Pro (future) |

---

## Estructura Proyecto

```
raw/polygon/                      # Trades tick-by-tick
processed/
├── dib_bars/                    # DIB bars construidos
├── watchlists/                  # Eventos detectados E1-E11
├── labels_pilot50/              # Triple barrier labels
├── weights_pilot50/             # Sample weights
└── dataset_pilot50/             # ML datasets enriquecidos
scripts/
├── fase_D_creando_DIB_VIB/      # Pipeline D.1-D.4
└── fase_E_Event_Detectors_*/    # Detectores E1-E11
01_DayBook/
├── fase_01/F_Event_detectors_*/ # Documentación + notebooks
└── map_route_phases.md          # Roadmap completo
```

---

## Referencias Clave

**Documentación Interna**:
- `F.3`: Arquitectura eventos E0-E11 (ventanas cualitativas iniciales)
- `F.6`: Validación matemática ventanas (enfoque híbrido MI + Edge)
- `D.4`: ML Dataset Builder (pipeline completo con 4 stages)
- `E.1`: Event detectors originales E1/E4/E7/E8

**Literatura**:
- *Advances in Financial Machine Learning* (López de Prado, 2018)
- *Machine Learning for Asset Managers* (López de Prado, 2020)

**APIs**:
- Polygon.io: https://polygon.io/docs/stocks
- SEC EDGAR: https://www.sec.gov/edgar

---

**Última actualización**: 2025-10-30
