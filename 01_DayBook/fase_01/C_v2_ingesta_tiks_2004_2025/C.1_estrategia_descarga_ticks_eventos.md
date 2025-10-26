# C.1 Estrategia de Descarga de Ticks Basada en Eventos Clave

**Fecha:** 2025-10-25  
**Contexto:** Fase C - Descarga selectiva de ticks para construccion de Information-Driven Bars  
**Fundamento:** Lopez de Prado Cap 2 + EduTrades Pump & Dump Playbook  

---

## [OBJETIVO]

Descargar datos tick-by-tick (trades) de Polygon API **SOLO para ventanas temporales donde ocurren eventos clave** detectables en el universo hibrido (8,686 tickers, 21 anos).

### Por que NO descargar todo el historico de ticks?

**Problema de escala:**
- 8,686 tickers x 21 anos x ~252 dias/ano = **45.6 millones** de ticker-dias
- Promedio ~100,000 ticks/ticker-dia (small caps activos) = **4.5 TRILLONES** de ticks
- Tamano estimado: **500+ TB** sin comprimir
- Costo API: $$$$ (miles de requests)
- Tiempo: **meses** de descarga continua

**Solucion: Event-Driven Tick Download**
- Detectar **eventos clave** en datos OHLCV daily/intradía (ya descargados)
- Descargar ticks SOLO para ventanas temporales alrededor de esos eventos
- Reduccion estimada: **99% menos datos** (de 45M ticker-dias a ~450K eventos)

---

## [FUNDAMENTO TEORICO]

### 1. Lopez de Prado: Information-Driven Bars

**De "Advances in Financial Machine Learning" Cap 2.3.2 (pp. 29-32):**

> "The purpose of information-driven bars is to sample more frequently when new information arrives to the market."

**Dollar Imbalance Bars (DIBs)** y **Dollar Runs Bars (DRBs)** requieren datos tick-by-tick:
- **DIBs:** Detectan desbalance compra/venta (pump initiation)
- **DRBs:** Detectan sweeping agresivo (informed traders)

**Pero NO necesitamos ticks de TODO el historico:**
Solo necesitamos ticks de periodos con **actividad informativa relevante** = eventos de pump & dump

### 2. EduTrades: Eventos Clave en Small Caps

**Del Playbook Operativo (14 estrategias):**

Los pumps & dumps tienen **eventos detectables** en datos OHLCV:
1. **Explosion de volumen** (RVOL > 5x)
2. **Gaps significativos** (>15%)
3. **Movimientos parabolicos** (>50% en 1-5 dias)
4. **First Red Day** (primer dia rojo tras corrida)
5. **Dilution events** (offerings, correlacionados con colapsos)

**Estos eventos marcan las ventanas temporales criticas para descargar ticks.**

---

## [EVENTOS CLAVE A DETECTAR]

### Taxonomia de Eventos

Organizados por **fase del ciclo pump & dump:**

```
FASE 1: DORMIDO (skip - no descargar ticks)
    +-- Bajo volumen, sin volatilidad

FASE 2: CATALIZADOR (EVENTO 1)
    +-- [E1] Volume Explosion: RVOL > 5x
    +-- [E2] Gap Up Significativo: Gap > 10%
    +-- [E3] Price Spike Intraday: +20% intradía

FASE 3: PUMP / EXTENSION (EVENTO 2)
    +-- [E4] Parabolic Move: +50% en 1-5 dias
    +-- [E5] Breakout ATH/52W: Nuevo high
    +-- [E6] Multiple Green Days: 3+ dias verdes consecutivos

FASE 4: DUMP / COLLAPSE (EVENTO 3)
    +-- [E7] First Red Day (FRD): Primer dia rojo post-pump
    +-- [E8] Gap Down Violento: Gap < -15%
    +-- [E9] Crash Intraday: -30% en <2 horas

FASE 5: BOUNCE (EVENTO 4)
    +-- [E10] First Green Day Bounce: Verde post-dump
    +-- [E11] Volume Spike on Bounce: RVOL > 3x en rebote

FASE 6: MUERTE (skip - no descargar ticks)
    +-- Volver a niveles base, dormido
```

### Eventos Especiales (Ortogonales al Ciclo)

```
DILUTION EVENTS (EVENTO 5)
    +-- [E12] S-3 Effective Date +/- 2 dias
    +-- [E13] 424B Pricing Date +/- 2 dias
    +-- [E14] Warrant Exercise Events

MICROSTRUCTURE ANOMALIES (EVENTO 6)
    +-- [E15] Halts (LUDP, LUDS)
    +-- [E16] SSR Trigger (Short Sale Restriction)
    +-- [E17] Extreme Spread Events (bid/ask > 10%)
```

---

## [VENTANAS TEMPORALES DE DESCARGA]

### Principio General

**Para cada evento detectado, descargar ticks en ventana:**

```
T_event = fecha/hora del evento (timestamp)

Ventana = [T_event - PRE_WINDOW, T_event + POST_WINDOW]
```

### Ventanas por Tipo de Evento

| Evento | Pre-Window | Post-Window | Total | Justificacion |
|--------|-----------|------------|-------|---------------|
| **E1: Volume Explosion** | 1 dia | 2 dias | 3 dias | Captura inicio pump + primeros dias |
| **E2: Gap Up >10%** | 1 dia | 1 dia | 2 dias | Previo + gap day completo |
| **E3: Spike Intraday** | Mismo dia | Mismo dia | 1 dia | Evento intradía |
| **E4: Parabolic Move** | 2 dias | 3 dias | 5 dias | Movimiento sostenido |
| **E5: Breakout ATH** | 1 dia | 2 dias | 3 dias | Confirmacion breakout |
| **E6: Multiple Greens** | 0 | Duracion corrida | N dias | Solo dias verdes consecutivos |
| **E7: First Red Day (FRD)** | 1 dia | 2 dias | 3 dias | **CRITICO** - ultimo dia verde + FRD + bounce |
| **E8: Gap Down >15%** | 1 dia | 1 dia | 2 dias | Previo + crash day |
| **E9: Crash Intraday** | Mismo dia | Mismo dia | 1 dia | Evento intradía |
| **E10: FG Bounce** | 1 dia | 1 dia | 2 dias | Setup + ejecucion |
| **E11: Vol Spike Bounce** | Mismo dia | 1 dia | 1-2 dias | Rebote rapido |
| **E12-E14: Dilution** | 2 dias | 2 dias | 4 dias | Anticipacion + ejecucion + colapso |
| **E15-E17: Anomalias** | Mismo dia | Mismo dia | 1 dia | Eventos puntuales |

### Eventos Priorizados (MVP)

**Para implementacion inicial, enfocarse en los 5 mas criticos:**

1. **[E7] First Red Day (FRD)** - El patron mas confiable segun EduTrades
2. **[E4] Parabolic Move** - Captura pumps grandes
3. **[E1] Volume Explosion** - Deteccion temprana
4. **[E8] Gap Down Violento** - Colapsos importantes
5. **[E13] Offering Pricing** - Dilution events

**Estimacion de cobertura:**
- Estos 5 eventos capturan ~80% de las oportunidades de trading segun el playbook
- Resto de eventos se pueden agregar iterativamente

---

## [DETECCION DE EVENTOS - ALGORITMOS]

### E1: Volume Explosion (RVOL > 5x)

**Input:** OHLCV Daily

```python
import polars as pl

def detect_volume_explosion(df_daily: pl.DataFrame, rvol_threshold: float = 5.0):
    """
    Detecta dias con volumen > 5x promedio 20 dias

    Returns: DataFrame con [ticker, date, rvol, event_type]
    """
    df = (
        df_daily
        .sort(["ticker", "date"])
        .with_columns([
            # Volumen promedio 20 dias
            pl.col("v").rolling_mean(window_size=20).over("ticker").alias("avg_vol_20d"),
        ])
        .with_columns([
            # RVOL = volumen actual / promedio
            (pl.col("v") / pl.col("avg_vol_20d")).alias("rvol")
        ])
        .filter(
            (pl.col("rvol") > rvol_threshold) &
            (pl.col("avg_vol_20d").is_not_null())  # Skip primeros 20 dias
        )
        .select([
            "ticker",
            "date",
            pl.lit("E1_VolExplosion").alias("event_type"),
            "rvol",
            "v",
            "avg_vol_20d"
        ])
    )

    return df


# Uso
events_e1 = detect_volume_explosion(df_daily, rvol_threshold=5.0)
print(f"Total E1 events: {len(events_e1):,}")
```

**Ventana de descarga:** `[date - 1 dia, date + 2 dias]`

---

### E4: Parabolic Move (+50% en 1-5 dias)

**Input:** OHLCV Daily

```python
def detect_parabolic_move(df_daily: pl.DataFrame, pct_threshold: float = 0.50, window_days: int = 5):
    """
    Detecta movimientos parabolicos: +50% en N dias

    Returns: DataFrame con [ticker, date_start, date_end, pct_change, days]
    """
    df = (
        df_daily
        .sort(["ticker", "date"])
        .with_columns([
            # Precio N dias atras
            pl.col("c").shift(window_days).over("ticker").alias("close_N_ago")
        ])
        .with_columns([
            # % cambio desde N dias atras
            ((pl.col("c") - pl.col("close_N_ago")) / pl.col("close_N_ago")).alias("pct_change")
        ])
        .filter(
            (pl.col("pct_change") > pct_threshold) &
            (pl.col("close_N_ago").is_not_null())
        )
        .select([
            "ticker",
            "date",
            pl.lit("E4_ParabolicMove").alias("event_type"),
            "pct_change",
            "c",
            "close_N_ago",
            pl.lit(window_days).alias("window_days")
        ])
    )

    return df


# Uso
events_e4 = detect_parabolic_move(df_daily, pct_threshold=0.50, window_days=5)
print(f"Total E4 events: {len(events_e4):,}")
```

**Ventana de descarga:** `[date - 2 dias, date + 3 dias]`

---

### E7: First Red Day (FRD) - **MAS CRITICO**

**Input:** OHLCV Daily

```python
def detect_first_red_day(df_daily: pl.DataFrame, min_run_days: int = 3, min_extension_pct: float = 0.50):
    """
    Detecta First Red Day (FRD): Primer dia rojo tras corrida verde de 3+ dias con +50%

    Criterios EduTrades:
    - Minimo 3 dias verdes consecutivos previos
    - Extension minima +50% desde inicio corrida
    - Dia actual cierra rojo (c < o)

    Returns: DataFrame con [ticker, date, run_days, extension_pct]
    """
    df = (
        df_daily
        .sort(["ticker", "date"])
        .with_columns([
            # Green day indicator
            (pl.col("c") > pl.col("o")).alias("is_green"),
            # Red day indicator
            (pl.col("c") < pl.col("o")).alias("is_red"),
        ])
    )

    # Detectar runs de dias verdes
    # (Implementacion completa requiere logica de window con state)
    # Pseudo-codigo simplificado:

    events = []

    for ticker in df["ticker"].unique():
        df_ticker = df.filter(pl.col("ticker") == ticker).sort("date")

        green_run_days = 0
        run_start_price = None

        for row in df_ticker.iter_rows(named=True):
            if row["is_green"]:
                if green_run_days == 0:
                    run_start_price = row["o"]  # Open del primer dia verde
                green_run_days += 1

            elif row["is_red"] and green_run_days >= min_run_days:
                # Calcular extension de la corrida
                extension_pct = (row["c"] - run_start_price) / run_start_price

                if extension_pct >= min_extension_pct:
                    events.append({
                        "ticker": ticker,
                        "date": row["date"],
                        "event_type": "E7_FirstRedDay",
                        "run_days": green_run_days,
                        "extension_pct": extension_pct,
                        "peak_price": df_ticker.filter(
                            pl.col("date") < row["date"]
                        )["h"].max(),  # High de la corrida
                    })

                # Reset contador
                green_run_days = 0
                run_start_price = None

            else:
                # Otro dia (ej: doji, gap) - reset contador
                green_run_days = 0
                run_start_price = None

    return pl.DataFrame(events)


# Uso
events_e7 = detect_first_red_day(df_daily, min_run_days=3, min_extension_pct=0.50)
print(f"Total E7 FRD events: {len(events_e7):,}")
```

**Ventana de descarga:** `[date - 1 dia, date + 2 dias]`
- date - 1: Ultimo dia verde (para comparacion)
- date: FRD completo
- date + 1 y +2: Posible First Green Day Bounce

---

### E8: Gap Down Violento (>15%)

**Input:** OHLCV Daily

```python
def detect_gap_down_violent(df_daily: pl.DataFrame, gap_threshold: float = -0.15):
    """
    Detecta gap downs violentos: open < prev_close * (1 + gap_threshold)

    Returns: DataFrame con [ticker, date, gap_pct, prev_close, open]
    """
    df = (
        df_daily
        .sort(["ticker", "date"])
        .with_columns([
            # Close del dia anterior
            pl.col("c").shift(1).over("ticker").alias("prev_close")
        ])
        .with_columns([
            # Gap % = (open - prev_close) / prev_close
            ((pl.col("o") - pl.col("prev_close")) / pl.col("prev_close")).alias("gap_pct")
        ])
        .filter(
            (pl.col("gap_pct") < gap_threshold) &
            (pl.col("prev_close").is_not_null())
        )
        .select([
            "ticker",
            "date",
            pl.lit("E8_GapDownViolent").alias("event_type"),
            "gap_pct",
            "prev_close",
            "o",
            "c",
            "l"
        ])
    )

    return df


# Uso
events_e8 = detect_gap_down_violent(df_daily, gap_threshold=-0.15)
print(f"Total E8 events: {len(events_e8):,}")
```

**Ventana de descarga:** `[date - 1 dia, date + 1 dia]`

---

### E13: Offering Pricing Date

**Input:** SEC Filings (requiere integracion con SEC EDGAR API o scraping)

```python
def detect_offering_pricing(filings_df: pl.DataFrame):
    """
    Detecta pricing dates de offerings (424B filings)

    Input: DataFrame con SEC filings parseados
    Columns: [ticker, filing_type, filing_date, effective_date, pricing_date]

    Returns: DataFrame con [ticker, pricing_date, offering_size, price]
    """
    events = (
        filings_df
        .filter(
            pl.col("filing_type").is_in(["424B5", "424B2", "424B3"])  # Offering prospectuses
        )
        .select([
            "ticker",
            "pricing_date",
            pl.lit("E13_OfferingPricing").alias("event_type"),
            "offering_size_usd",
            "price_per_share"
        ])
    )

    return events


# Nota: Requiere pipeline de ingesta de SEC filings (Fase futura)
# Por ahora, puede usarse dataset manual o API de terceros (FMP, etc.)
```

**Ventana de descarga:** `[pricing_date - 2 dias, pricing_date + 2 dias]`

---

## [PIPELINE DE DESCARGA DE TICKS]

### Arquitectura General

```
PASO 1: Event Detection
    +-- Escanear OHLCV daily (8,686 tickers, 21 anos)
    +-- Detectar eventos E1, E4, E7, E8, E13
    +-- Output: events.parquet [ticker, date, event_type, metadata]

PASO 2: Window Construction
    +-- Para cada evento, calcular ventana temporal
    +-- Expandir a timestamps exactos (market hours: 9:30-16:00 ET)
    +-- Output: download_windows.parquet [ticker, timestamp_start, timestamp_end, event_id]

PASO 3: Deduplication & Merging
    +-- Combinar ventanas solapadas del mismo ticker
    +-- Evitar descargar mismo periodo multiple veces
    +-- Output: merged_windows.parquet [ticker, timestamp_start, timestamp_end, event_ids[]]

PASO 4: Tick Download
    +-- Para cada ventana en merged_windows:
    +-- GET /v3/trades/{ticker}?timestamp.gte={start}&timestamp.lt={end}
    +-- Paginacion con cursor
    +-- Output: raw/polygon/trades/{ticker}/event_id={id}/trades.parquet

PASO 5: Bar Construction
    +-- Construir Dollar Imbalance Bars (DIBs) desde ticks
    +-- Construir Dollar Runs Bars (DRBs) desde ticks
    +-- Output: processed/bars/{ticker}/event_id={id}/dibs.parquet
```

### Script de Event Detection

**Archivo:** `scripts/fase_C_ticks_eventos/detect_events.py`

```python
#!/usr/bin/env python
"""
Detecta eventos clave en universo hibrido para descarga selectiva de ticks
"""
import polars as pl
from pathlib import Path
from typing import List
import datetime as dt

# Paths
BASE_DIR = Path("D:/04_TRADING_SMALLCAPS")
DAILY_DIR = BASE_DIR / "raw/polygon/ohlcv_daily"
OUTPUT_DIR = BASE_DIR / "processed/events"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Event detectors
from event_detectors import (
    detect_volume_explosion,
    detect_parabolic_move,
    detect_first_red_day,
    detect_gap_down_violent,
)

def load_all_daily_data() -> pl.DataFrame:
    """Carga todos los datos OHLCV daily del universo hibrido"""
    print(f"Loading daily data from {DAILY_DIR}...")

    all_dfs = []
    ticker_dirs = [d for d in DAILY_DIR.iterdir() if d.is_dir()]

    for ticker_dir in ticker_dirs:
        ticker = ticker_dir.name
        parquet_files = list(ticker_dir.rglob("*.parquet"))

        if not parquet_files:
            continue

        # Leer y concatenar todos los anos
        dfs = [pl.read_parquet(f) for f in parquet_files]
        df = pl.concat(dfs)

        all_dfs.append(df)

    df_all = pl.concat(all_dfs)
    print(f"Total rows loaded: {len(df_all):,}")

    return df_all


def main():
    print("="*80)
    print("EVENT DETECTION - Pump & Dump Cycles")
    print("="*80)

    # Cargar datos daily
    df_daily = load_all_daily_data()

    # Detectar eventos
    print("\n[E1] Detecting Volume Explosions...")
    events_e1 = detect_volume_explosion(df_daily, rvol_threshold=5.0)
    print(f"  Found: {len(events_e1):,} events")

    print("\n[E4] Detecting Parabolic Moves...")
    events_e4 = detect_parabolic_move(df_daily, pct_threshold=0.50, window_days=5)
    print(f"  Found: {len(events_e4):,} events")

    print("\n[E7] Detecting First Red Days...")
    events_e7 = detect_first_red_day(df_daily, min_run_days=3, min_extension_pct=0.50)
    print(f"  Found: {len(events_e7):,} events")

    print("\n[E8] Detecting Gap Downs...")
    events_e8 = detect_gap_down_violent(df_daily, gap_threshold=-0.15)
    print(f"  Found: {len(events_e8):,} events")

    # Combinar todos los eventos
    all_events = pl.concat([events_e1, events_e4, events_e7, events_e8])

    # Agregar event_id unico
    all_events = all_events.with_row_count("event_id")

    print(f"\n{'='*80}")
    print(f"TOTAL EVENTS DETECTED: {len(all_events):,}")
    print(f"{'='*80}")

    # Guardar eventos
    output_path = OUTPUT_DIR / f"events_detected_{dt.date.today().isoformat()}.parquet"
    all_events.write_parquet(output_path)
    print(f"\nSaved: {output_path}")

    # Estadisticas por tipo
    print("\nEvent Type Distribution:")
    event_counts = all_events.group_by("event_type").agg(pl.count().alias("count")).sort("count", descending=True)
    print(event_counts)

    # Tickers con mas eventos
    print("\nTop 20 Tickers by Event Count:")
    ticker_counts = all_events.group_by("ticker").agg(pl.count().alias("count")).sort("count", descending=True).head(20)
    print(ticker_counts)


if __name__ == "__main__":
    main()
```

---

## [ESTIMACION DE VOLUMENES]

### Eventos Esperados (Orden de Magnitud)

Basado en universo hibrido de 8,686 tickers en 21 anos:

| Evento | Frecuencia Estimada | Total Eventos | Ventana Promedio | Ticker-Dias Totales |
|--------|-------------------|--------------|-----------------|---------------------|
| E1: Vol Explosion | 0.5% ticker-dias | ~228,000 | 3 dias | 684,000 |
| E4: Parabolic Move | 0.1% ticker-dias | ~45,600 | 5 dias | 228,000 |
| E7: First Red Day | 0.05% ticker-dias | ~22,800 | 3 dias | 68,400 |
| E8: Gap Down | 0.02% ticker-dias | ~9,120 | 2 dias | 18,240 |
| E13: Offerings | ~500/ano x 21 anos | ~10,500 | 4 dias | 42,000 |
| **TOTAL** | - | **~316,020** | - | **~1,040,640** |

**Reduccion vs descarga completa:**
- Descarga completa: 45.6M ticker-dias
- Descarga selectiva: 1.04M ticker-dias
- **Reduccion: 97.7%**

### Tamano de Datos Ticks

**Estimaciones:**
- Promedio ticks/dia en small cap activo: ~100,000 ticks
- Tamano promedio tick: ~50 bytes (ticker, price, size, timestamp, conditions)
- Tamano/ticker-dia: 100K x 50 = ~5 MB sin comprimir

**Total estimado:**
- 1,040,640 ticker-dias x 5 MB = **~5.2 TB** sin comprimir
- Con ZSTD level 2 (50% compresion): **~2.6 TB**

**Comparacion:**
- Descarga completa: 500+ TB
- Descarga selectiva: 2.6 TB
- **Reduccion: 99.5%**

---

## [IMPLEMENTACION - ROADMAP]

### Fase C.1: Event Detection (2-3 dias)

1. Implementar detectores de eventos E1, E4, E7, E8
2. Escanear universo completo OHLCV daily
3. Generar `events_detected.parquet` (~300K eventos)
4. Validar distribucion de eventos

### Fase C.2: Window Construction (1 dia)

1. Implementar logica de ventanas temporales por evento
2. Expandir a timestamps exactos (market hours)
3. Merge ventanas solapadas
4. Generar `download_windows.parquet` (~1M ticker-dias)

### Fase C.3: Tick Download (5-7 dias)

1. Adaptar script de descarga para API `/v3/trades`
2. Implementar paginacion con cursor
3. Descarga en batches de 100 ventanas
4. Rate-limit adaptativo (similar a intradía OHLCV)
5. Output: `raw/polygon/trades/{ticker}/event_id={id}/trades.parquet`

### Fase C.4: Bar Construction (3-5 dias)

1. Implementar Dollar Imbalance Bars (DIBs) - Snippet 2.4
2. Implementar Dollar Runs Bars (DRBs) - Snippet 2.5
3. Threshold dinamico por ticker (funcion de float)
4. Output: `processed/bars/{ticker}/event_id={id}/dibs.parquet`

**Total estimado: 11-16 dias**

---

## [PREGUNTAS ABIERTAS]

### 1. Integracion con SEC Filings?

**Opcion A:** Usar API de terceros (Financial Modeling Prep, Alpha Vantage)
- Pros: Rapido, datos limpios
- Cons: Costo adicional, coverage limitado

**Opcion B:** Scraping SEC EDGAR directo
- Pros: Gratis, coverage completo
- Cons: Parsing complejo, lento

**Opcion C:** Dataset manual inicial
- Pros: Control total, calidad alta
- Cons: No escalable, trabajo manual

**Recomendacion:** Opcion C para MVP, migrar a B en produccion

### 2. Como manejar pre-market y after-hours?

**Problema:** Eventos importantes ocurren fuera de horario regular (9:30-16:00 ET)

**Opcion A:** Incluir extended hours (4:00-20:00 ET)
- Pros: Captura gaps y catalizadores pre-market
- Cons: +200% datos, menos liquidez

**Opcion B:** Solo regular hours
- Pros: Datos mas limpios, menos ruido
- Cons: Pierde eventos pre/post market

**Recomendacion:** Opcion A para eventos E2 (Gap Up) y E8 (Gap Down), Opcion B para resto

### 3. Umbral de RVOL y % cambios?

**Parametros propuestos:**
- RVOL threshold: 5x (conservador)
- Parabolic move: +50% en 5 dias
- Gap down: -15%

**Recomendacion:** Validar con analisis exploratorio (EDA) de daily data antes de escaneo completo

---

## [DECISION FINAL]

### Eventos a Implementar (MVP)

**Priorizados por impacto ML:**

1. **[E7] First Red Day** - Patron mas confiable EduTrades
2. **[E4] Parabolic Move** - Captura pumps grandes
3. **[E1] Volume Explosion** - Deteccion temprana
4. **[E8] Gap Down Violento** - Colapsos
5. **[E13] Offering Pricing** - Dilution (manual MVP)

### Ventanas de Descarga

**Configuracion final:**

| Evento | Pre-Window | Post-Window | Total |
|--------|-----------|------------|-------|
| E1 | 1 dia | 2 dias | 3 dias |
| E4 | 2 dias | 3 dias | 5 dias |
| E7 | 1 dia | 2 dias | 3 dias |
| E8 | 1 dia | 1 dia | 2 dias |
| E13 | 2 dias | 2 dias | 4 dias |

**Justificacion Lopez de Prado:**
- Pre-window: Contexto antes del evento (setup phase)
- Post-window: Resolucion del evento (execution + aftermath)
- Total: Captura ciclo completo de informed trading

---

## [REFERENCIAS]

- Lopez de Prado, M. (2018). *Advances in Financial Machine Learning*. Chapter 2 (pp. 23-42)
- EduTrades Playbook: `01_DayBook/fase_01/A_Universo/2_estrategia_operativa_small_caps.md`
- Polygon API Docs: `/v3/trades/{ticker}` - https://polygon.io/docs/stocks/get_v3_trades__stockticker
- SEC EDGAR: https://www.sec.gov/edgar/searchedgar/companysearch.html

---

**Proximo Paso:** Implementar `detect_events.py` y ejecutar escaneo completo del universo
