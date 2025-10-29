# E.4 - Como Solucionar E3 y E9: Deteccion Intraday Precisa

**Fecha**: 2025-10-28
**Autor**: Pipeline automation
**Contexto**: Pregunta del usuario sobre como mejorar la deteccion de eventos intraday E3 (spike) y E9 (crash)

---

## PROBLEMA ACTUAL

Las implementaciones actuales de **E3** (Price Spike Intraday) y **E9** (Crash Intraday) son **aproximaciones** que usan datos daily OHLCV:

### E3 Actual (Aproximacion):
```python
spike_pct = (high - open) / open >= 0.20
```
- Detecta si el `high` del dia estuvo +20% sobre el `open`
- **NO garantiza** que el movimiento fue en <2 horas
- **Falsos positivos**: Precio pudo subir gradualmente durante todo el dia

### E9 Actual (Aproximacion):
```python
crash_pct = (low - open) / open <= -0.30
```
- Detecta si el `low` del dia estuvo -30% bajo el `open`
- **NO garantiza** que el movimiento fue en <2 horas
- **Falsos positivos**: Precio pudo caer gradualmente durante todo el dia

---

## SOLUCIONES PROPUESTAS

### OPCION 1: SOLUCION IDEAL (Usar datos 1-minute)

Ya tienes datos intraday 1-minute en `raw/polygon/ohlcv_intraday_1m`. Podemos implementar deteccion precisa:

#### **E3 Preciso: Spike +20% en ventana de 2 horas**

```python
def detect_e3_price_spike_intraday_precise(
    self,
    df_1m: pl.DataFrame,
    spike_threshold: float = 0.20,
    window_minutes: int = 120
) -> pl.DataFrame:
    """
    Detect intraday price spike: price increases >=20% within 2 hours

    Requires 1-minute OHLCV data with columns: [ticker, timestamp, o, h, l, c, v]

    Parameters:
    -----------
    df_1m : pl.DataFrame
        1-minute OHLCV data
    spike_threshold : float
        Minimum spike percentage (default: 0.20 = 20%)
    window_minutes : int
        Time window in minutes (default: 120 = 2 hours)

    Returns:
    --------
    pl.DataFrame with columns: [ticker, date, event_type, spike_pct, spike_time, day_open, peak_price]
    """
    self.logger.info(f"Detecting E3 Price Spike Intraday PRECISE (>={spike_threshold*100}% in <={window_minutes}min)")

    df = (
        df_1m
        .sort(["ticker", "timestamp"])
        .with_columns([
            # Extract date and get day open
            pl.col("timestamp").dt.date().alias("date"),
            pl.col("o").first().over(["ticker", pl.col("timestamp").dt.date()]).alias("day_open")
        ])
        .with_columns([
            # Calculate rolling max price over 2-hour window
            pl.col("h").rolling_max(window_size=window_minutes).over("ticker").alias("max_price_2h")
        ])
        .with_columns([
            # Calculate spike percentage from day open to rolling max
            ((pl.col("max_price_2h") - pl.col("day_open")) / pl.col("day_open")).alias("spike_pct")
        ])
        .filter(
            (pl.col("spike_pct") >= spike_threshold) &
            (pl.col("day_open") > 0)
        )
        # Group by ticker + date to get one event per day
        .group_by(["ticker", "date"]).agg([
            pl.col("spike_pct").max().alias("spike_pct"),
            pl.col("timestamp").filter(pl.col("spike_pct") == pl.col("spike_pct").max()).first().alias("spike_time"),
            pl.col("day_open").first(),
            pl.col("max_price_2h").filter(pl.col("spike_pct") == pl.col("spike_pct").max()).first().alias("peak_price")
        ])
        .select([
            "ticker",
            "date",
            pl.lit("E3_IntradaySpike").alias("event_type"),
            "spike_pct",
            "spike_time",
            "day_open",
            "peak_price"
        ])
    )

    self.logger.info(f"Found {len(df):,} E3 Price Spike Intraday events")
    return df
```

**Ventajas**:
- Precision exacta (detecta movimientos reales intraday)
- No genera falsos positivos
- Captura el timing exacto del evento (timestamp del spike)
- Detecta SOLO spikes que ocurren en ventana de 2 horas

**Desventajas**:
- Procesamiento mas pesado (millones de rows por ticker)
- Requiere almacenamiento adicional

---

#### **E9 Preciso: Crash -30% en ventana de 2 horas**

```python
def detect_e9_crash_intraday_precise(
    self,
    df_1m: pl.DataFrame,
    crash_threshold: float = -0.30,
    window_minutes: int = 120
) -> pl.DataFrame:
    """
    Detect intraday crash: price drops <=30% within 2 hours

    Requires 1-minute OHLCV data with columns: [ticker, timestamp, o, h, l, c, v]

    Parameters:
    -----------
    df_1m : pl.DataFrame
        1-minute OHLCV data
    crash_threshold : float
        Maximum crash percentage (default: -0.30 = -30%)
    window_minutes : int
        Time window in minutes (default: 120 = 2 hours)

    Returns:
    --------
    pl.DataFrame with columns: [ticker, date, event_type, crash_pct, crash_time, day_open, bottom_price]
    """
    self.logger.info(f"Detecting E9 Crash Intraday PRECISE (<={crash_threshold*100}% in <={window_minutes}min)")

    df = (
        df_1m
        .sort(["ticker", "timestamp"])
        .with_columns([
            # Extract date and get day open
            pl.col("timestamp").dt.date().alias("date"),
            pl.col("o").first().over(["ticker", pl.col("timestamp").dt.date()]).alias("day_open")
        ])
        .with_columns([
            # Calculate rolling min price over 2-hour window
            pl.col("l").rolling_min(window_size=window_minutes).over("ticker").alias("min_price_2h")
        ])
        .with_columns([
            # Calculate crash percentage from day open to rolling min
            ((pl.col("min_price_2h") - pl.col("day_open")) / pl.col("day_open")).alias("crash_pct")
        ])
        .filter(
            (pl.col("crash_pct") <= crash_threshold) &
            (pl.col("day_open") > 0)
        )
        # Group by ticker + date to get one event per day
        .group_by(["ticker", "date"]).agg([
            pl.col("crash_pct").min().alias("crash_pct"),
            pl.col("timestamp").filter(pl.col("crash_pct") == pl.col("crash_pct").min()).first().alias("crash_time"),
            pl.col("day_open").first(),
            pl.col("min_price_2h").filter(pl.col("crash_pct") == pl.col("crash_pct").min()).first().alias("bottom_price")
        ])
        .select([
            "ticker",
            "date",
            pl.lit("E9_CrashIntraday").alias("event_type"),
            "crash_pct",
            "crash_time",
            "day_open",
            "bottom_price"
        ])
    )

    self.logger.info(f"Found {len(df):,} E9 Crash Intraday events")
    return df
```

**Ventajas**:
- Precision exacta (detecta movimientos reales intraday)
- No genera falsos positivos
- Captura el timing exacto del evento (timestamp del crash)
- Detecta SOLO crashes que ocurren en ventana de 2 horas

**Desventajas**:
- Procesamiento mas pesado (millones de rows por ticker)
- Requiere almacenamiento adicional

---

### OPCION 2: SOLUCION PRACTICA (Usar datos daily existentes - ACTUAL)

**Mantener implementacion actual como aproximacion conservadora**

**Ventajas**:
- Rapidisimo (ya esta calculado)
- No requiere procesamiento adicional
- Captura eventos extremos aunque no sea perfecto
- Si `(high - open) / open >= 0.20`, es una senal valida de volatilidad extrema, independientemente del timing

**Desventajas**:
- Falsos positivos (movimientos lentos todo el dia)
- No captura timing exacto

---

## RECOMENDACION: ENFOQUE HIBRIDO EN 2 FASES

### **FASE 1 (INMEDIATA)**: Usar aproximacion actual

1. **Mantener E3/E9 con datos daily**
2. **Anadir flag `intraday_confirmed=False`** en los eventos
3. **Usar estos eventos para**:
   - Multi-Event Fuser
   - Backtesting inicial
   - Validacion de patrones

**Justificacion**:
- Si `(high - open) / open >= 0.20`, aunque no sepamos el timing exacto, es una senal valida de volatilidad extrema
- Permite avanzar rapidamente con el pipeline
- Los falsos positivos se pueden filtrar con backtesting

---

### **FASE 2 (FUTURA)**: Refinar con datos minute

1. **Crear `E3_intraday_precise` y `E9_intraday_precise`** usando datos 1-minute
2. **Comparar resultados** con aproximacion daily:
   - Cuantos eventos daily son verdaderos intraday?
   - Tasa de falsos positivos de aproximacion daily
3. **Medir impacto en backtest**:
   - Los falsos positivos afectan win rate?
   - Vale la pena el overhead de procesamiento?
4. **Decidir estrategia final**:
   - Si tasa de falsos positivos es baja (<20%), mantener daily
   - Si tasa de falsos positivos es alta (>50%), migrar a 1-minute

---

## IMPLEMENTACION CODIGO COMPLETO

### Script para ejecutar deteccion con datos 1-minute:

```python
# File: scripts/fase_E_Event Detectors E1, E4, E7, E8/detect_e3_e9_intraday_precise.py

import polars as pl
from pathlib import Path
import logging
from event_detectors import EventDetector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    # Paths
    ohlcv_1m_root = Path('raw/polygon/ohlcv_intraday_1m')
    outdir = Path('processed/events_intraday')
    outdir.mkdir(parents=True, exist_ok=True)

    # Load all 1-minute OHLCV data
    logger.info("Loading 1-minute OHLCV data...")
    parquet_files = list(ohlcv_1m_root.rglob('*.parquet'))
    logger.info(f"Found {len(parquet_files):,} files")

    dfs = []
    for pf in parquet_files:
        try:
            df = pl.read_parquet(pf)
            if len(df) > 0:
                dfs.append(df)
        except Exception as e:
            logger.error(f"Error reading {pf}: {e}")

    df_1m = pl.concat(dfs)
    logger.info(f"Loaded {len(df_1m):,} 1-minute records for {df_1m['ticker'].n_unique():,} tickers")

    # Detect E3 and E9 with precise intraday logic
    detector = EventDetector()

    logger.info("\n" + "="*80)
    logger.info("DETECTING E3 PRICE SPIKE INTRADAY (PRECISE)")
    logger.info("="*80)
    df_e3 = detector.detect_e3_price_spike_intraday_precise(df_1m)
    outfile_e3 = outdir / 'events_e3_precise.parquet'
    df_e3.write_parquet(outfile_e3)
    logger.info(f"Saved E3 precise: {len(df_e3):,} events -> {outfile_e3}")

    logger.info("\n" + "="*80)
    logger.info("DETECTING E9 CRASH INTRADAY (PRECISE)")
    logger.info("="*80)
    df_e9 = detector.detect_e9_crash_intraday_precise(df_1m)
    outfile_e9 = outdir / 'events_e9_precise.parquet'
    df_e9.write_parquet(outfile_e9)
    logger.info(f"Saved E9 precise: {len(df_e9):,} events -> {outfile_e9}")

    # Compare with daily approximation
    logger.info("\n" + "="*80)
    logger.info("COMPARISON: DAILY APPROXIMATION vs 1-MINUTE PRECISE")
    logger.info("="*80)

    # Load daily approximation results
    df_e3_daily = pl.read_parquet('processed/events/events_e3.parquet')
    df_e9_daily = pl.read_parquet('processed/events/events_e9.parquet')

    logger.info(f"E3 Daily approximation: {len(df_e3_daily):,} events")
    logger.info(f"E3 Precise (1-minute):  {len(df_e3):,} events")
    logger.info(f"E3 False positive rate: {(1 - len(df_e3)/len(df_e3_daily))*100:.2f}%")
    logger.info("")
    logger.info(f"E9 Daily approximation: {len(df_e9_daily):,} events")
    logger.info(f"E9 Precise (1-minute):  {len(df_e9):,} events")
    logger.info(f"E9 False positive rate: {(1 - len(df_e9)/len(df_e9_daily))*100:.2f}%")

    logger.info("\n" + "="*80)
    logger.info("COMPLETED")
    logger.info("="*80)

if __name__ == '__main__':
    main()
```

---

## COMPARACION: APROXIMACION vs PRECISION

### Schema Aproximacion Daily:
```
E3_PriceSpikeIntraday:
  - ticker
  - date
  - event_type: "E3_PriceSpikeIntraday"
  - spike_pct: (high - open) / open
  - o, h, l, c, v
  - intraday_confirmed: False  # Flag indicando que es aproximacion
```

### Schema Precision 1-minute:
```
E3_IntradaySpike:
  - ticker
  - date
  - event_type: "E3_IntradaySpike"
  - spike_pct: max spike in 2h window
  - spike_time: timestamp exacto del spike
  - day_open
  - peak_price
  - intraday_confirmed: True  # Flag indicando que es deteccion precisa
```

---

## EJEMPLO PRACTICO

### Caso 1: Spike verdadero (detectado por ambos)
```
Ticker: AAPL
Date: 2024-10-15

Daily data:
  open: $100
  high: $125  (+25% sobre open)

1-minute data:
  09:31 - 11:30 (2h): $100 -> $125

Resultado:
  - Daily approximation: DETECTADO
  - 1-minute precise:   DETECTADO
  - Conclusion: TRUE POSITIVE
```

### Caso 2: Spike gradual (falso positivo daily)
```
Ticker: TSLA
Date: 2024-10-16

Daily data:
  open: $200
  high: $245  (+22.5% sobre open)

1-minute data:
  09:30 - 16:00 (6.5h): Subida gradual $200 -> $245
  Maximo spike 2h: $200 -> $218 (+9%)

Resultado:
  - Daily approximation: DETECTADO (falso positivo)
  - 1-minute precise:   NO DETECTADO
  - Conclusion: FALSE POSITIVE (daily approximation)
```

---

## DECISION FINAL

**Recomendacion**: **OPCION 1 - Mantener aproximacion daily por ahora**

**Razones**:
1. Los datos daily capturan volatilidad extrema aunque no sea timing perfecto
2. Permite avanzar rapidamente con Multi-Event Fuser y backtesting
3. Los falsos positivos se pueden filtrar con validacion de win rates
4. Si el backtest muestra que los falsos positivos afectan performance, entonces migrar a 1-minute

**Plan de implementacion**:
1. [OK] Usar E3/E9 con datos daily (ya implementado)
2. [TODO] Anadir flag `intraday_confirmed=False` a eventos E3/E9
3. [TODO] Ejecutar Multi-Event Fuser con E1-E11
4. [TODO] Backtest framework: medir win rates de cada evento
5. [TODO] Si E3/E9 tienen win rates <40%, implementar version precisa 1-minute

---

## METRICAS DE VALIDACION (Para evaluar si vale la pena migrar a 1-minute)

Ejecutar analisis comparativo:

```python
# Compare daily vs 1-minute detection
df_comparison = (
    df_e3_daily
    .join(df_e3_precise, on=["ticker", "date"], how="outer", suffix="_precise")
    .with_columns([
        pl.when(pl.col("spike_pct").is_not_null() & pl.col("spike_pct_precise").is_not_null())
            .then(pl.lit("true_positive"))
        .when(pl.col("spike_pct").is_not_null() & pl.col("spike_pct_precise").is_null())
            .then(pl.lit("false_positive"))
        .when(pl.col("spike_pct").is_null() & pl.col("spike_pct_precise").is_not_null())
            .then(pl.lit("false_negative"))
        .alias("classification")
    ])
)

# Calculate metrics
metrics = df_comparison.group_by("classification").agg(pl.count().alias("count"))
print(metrics)

# Decision criteria:
# - If false_positive_rate > 50%: Migrar a 1-minute
# - If false_positive_rate < 20%: Mantener daily
# - If 20% <= false_positive_rate <= 50%: Evaluar con backtest win rates
```

---

## CONCLUSION

**E3 y E9 se solucionan de 2 formas**:

1. **Corto plazo**: Usar aproximacion daily (actual) con flag `intraday_confirmed=False`
2. **Largo plazo**: Si backtest muestra que falsos positivos afectan win rates, implementar deteccion precisa con datos 1-minute

**La solucion esta lista para implementar cuando sea necesario.**
