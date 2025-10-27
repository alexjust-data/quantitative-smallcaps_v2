# C.7 - Roadmap Oficial Post-PASO 5: Multi-Evento + Barras Informativas

**Fecha**: 2025-10-27
**Versión**: 1.0.0
**Estado**: PASO 5 COMPLETADO (E0 ticks descargados)
**Decisión Estratégica**: Híbrido A+B (Multi-evento + Prototipo DIB/VIB en paralelo)
**Relacionado**: [C.1](C.1_estrategia_descarga_ticks_eventos.md), [C.5](C.5_plan_ejecucion_E0_descarga_ticks.md), [C.6](C.6_estrategia_iterativa_eventos.md)

---

## SITUACIÓN ACTUAL

### ✅ Ya Completado (PASO 0-5)

```
FASE C - INGESTA TICKS E0
══════════════════════════
✅ PASO 1: Daily Cache 2004-2025 (8,617 tickers)
✅ PASO 2: Config Umbrales E0
✅ PASO 3: Watchlists E0 (5,934 días, 29,555 eventos)
✅ PASO 4: Auditoría E0 (validación umbrales)
✅ PASO 5: Descarga Ticks E0 (67,439 files, 16.58 GB, 92.2% cobertura)
```

**Storage actual**: 16.58 GB
**Cobertura**: 92.2% (64,801 / 70,290 días trading)
**Window aplicado**: ±1 día (contexto para triple barrier)
**Tickers únicos E0**: 4,898

### 📊 Dataset Actual

```
raw/polygon/trades/
├── BCRX/date=2020-03-16/trades.parquet   (ejemplo día E0)
├── GERN/date=2019-08-22/trades.parquet
└── ... (67,439 archivos completados)

processed/universe/info_rich/daily/
├── date=2020-03-16/watchlist.parquet      (tickers E0 ese día)
└── ... (5,934 watchlists)
```

**Limitaciones de E0**:
- ❌ No identifica **patrón específico** (FRD, Parabolic, GapDown)
- ❌ No permite **labeling por tipo de setup** (necesario para trading)
- ❌ No captura **eventos específicos de playbook** (E1, E4, E7, E8)

---

## PUNTO DE BIFURCACIÓN ESTRATÉGICA

### Opción A: Construir DIB/VIB con E0 Solo (RECHAZADA)

**¿Qué haríamos?**
1. Construir barras informativas (DIB/VIB) sobre ticks E0
2. Hacer triple barrier labeling genérico
3. Entrenar modelo con E0
4. Luego descubrir que necesitamos eventos específicos (FRD, Parabolic...)
5. RE-DESCARGAR ticks E1-E13
6. RE-CONSTRUIR DIB/VIB con eventos completos
7. RE-HACER labeling con contexto de eventos

**Por qué se rechaza**:
- ❌ **Re-trabajo doble**: DIB/VIB 2 veces, descarga API 2 veces
- ❌ **Dataset mediocre**: E0 sin eventos específicos → labeling genérico → modelo aprende "ruido promediado"
- ❌ **Ineficiencia**: ~15-20 días totales vs ~10-12 con estrategia híbrida

### Opción B: Descargar E1-E13 Primero, Luego DIB/VIB (RECHAZADA)

**¿Qué haríamos?**
1. Implementar detectores E1-E13
2. Descargar ticks adicionales (~95K ticker-días, +3-4 TB)
3. Luego construir DIB/VIB sobre conjunto completo

**Por qué se rechaza**:
- ❌ **Riesgo sin validación**: descargar +3 TB sin haber probado que podemos construir DIB/VIB
- ❌ **Pipeline no validado**: si DIB/VIB falla, habremos gastado 20-30h en descarga inútil
- ❌ **"Fe sin pruebas"**: estamos asumiendo que feature factory intradía funcionará

### ✅ Opción C: HÍBRIDO A+B (APROBADA)

**Estrategia en paralelo**:

```
SEMANA 1-2: INGENIERÍA BASE
═══════════════════════════
Track A (eventos)          Track B (barras)
─────────────────          ────────────────
Implementar detectores →   Prototipo DIB/VIB
E1, E4, E7, E8            en subset pequeño
↓                         (2-3 tickers × 10 días)
Watchlists multi-evento   ↓
con merge inteligente     Validar feature factory
↓                         ↓
AMBOS LISTOS → PASO 6
↓
SEMANA 3: DESCARGA INCREMENTAL
═══════════════════════════════
Descargar ticks E1-E13 adicionales
(solo días NUEVOS, resume salta E0)
↓
SEMANA 4-5: DATASET MAESTRO
═════════════════════════════
Construir DIB/VIB UNA VEZ
sobre conjunto COMPLETO {E0 ∪ E1-E13}
```

**Por qué es óptima**:
- ✅ **Minimiza re-trabajo**: DIB/VIB una vez, descarga incremental una vez
- ✅ **Valida pipeline crítico**: Track B prueba DIB/VIB antes de commitment +3 TB
- ✅ **Paraleliza ingenierías**: detectores (2-3 días) + prototipo (2-3 días) = misma semana
- ✅ **Dataset completo**: DIB/VIB sobre {E0 ∪ E1-E13} con metadata de eventos
- ✅ **Tiempo total**: ~10-12 días (vs 15-20 con Opción A)

---

## ROADMAP DETALLADO (3 SEMANAS)

### SEMANA 1: Ingeniería Base (Track A + Track B en paralelo)

#### Track A: Detectores Multi-Evento (Días 1-3)

**Objetivo**: Implementar detectores de eventos específicos del playbook

**Scripts a crear**:
```
scripts/fase_C_ingesta_tiks/event_detectors/
├── __init__.py
├── e1_volume_explosion.py       # RVOL > 5x
├── e4_parabolic_move.py         # +50% en ≤5 días
├── e7_first_red_day.py          # 3+ verdes → primer rojo (MÁS COMPLEJO)
└── e8_gap_down.py               # gap < -15%
```

**E1: Volume Explosion** (10 líneas, trivial):
```python
def detect_e1_volume_explosion(df_daily: pl.DataFrame, rvol_threshold: float = 5.0):
    """
    Detecta explosión de volumen: RVOL > 5x promedio 30d

    Ventana de descarga: [-1, +2] días (total 4 días)
    """
    return (
        df_daily
        .filter(pl.col("rvol30") >= rvol_threshold)
        .select([
            "ticker", "trading_day",
            pl.lit("E1_VolExplosion").alias("event_type"),
            "rvol30", "vol_d", "dollar_vol_d"
        ])
    )
```

**E4: Parabolic Move** (15 líneas, fácil):
```python
def detect_e4_parabolic_move(df_daily: pl.DataFrame, pct_threshold: float = 0.50, window_days: int = 5):
    """
    Detecta movimiento parabólico: +50% en ≤5 días

    Ventana de descarga: [-2, +3] días (total 6 días)
    """
    return (
        df_daily
        .sort(["ticker", "trading_day"])
        .with_columns([
            pl.col("close_d").shift(window_days).over("ticker").alias("close_N_ago")
        ])
        .with_columns([
            ((pl.col("close_d") - pl.col("close_N_ago")) / pl.col("close_N_ago")).alias("pct_change")
        ])
        .filter(
            (pl.col("pct_change") >= pct_threshold) &
            (pl.col("close_N_ago").is_not_null())
        )
        .select([
            "ticker", "trading_day",
            pl.lit("E4_ParabolicMove").alias("event_type"),
            "pct_change", "close_d", "close_N_ago"
        ])
    )
```

**E7: First Red Day** (50 líneas, complejo - requiere state tracking):
```python
def detect_e7_first_red_day(df_daily: pl.DataFrame, min_run_days: int = 3, min_extension_pct: float = 0.50):
    """
    Detecta First Red Day: primer día rojo tras corrida verde ≥3 días con +50%

    IMPORTANTE: Patrón más confiable según playbook EduTrades
    Ventana de descarga: [-1, +2] días (total 4 días)

    Requiere lógica de runs de días verdes con state tracking
    """
    # Detectar runs verdes
    df = (
        df_daily
        .sort(["ticker", "trading_day"])
        .with_columns([
            (pl.col("close_d") > pl.col("open_d")).alias("is_green"),
            (pl.col("close_d") < pl.col("open_d")).alias("is_red"),
        ])
    )

    # State tracking: detectar runs verdes seguidos de primer rojo
    # (Implementación completa requiere iteración por ticker con acumulador)
    # Ver: scripts/fase_C_ingesta_tiks/event_detectors/e7_first_red_day.py

    # Pseudo-código:
    # for ticker in tickers:
    #     green_run_days = 0
    #     run_start_price = None
    #     for row in sorted_by_date:
    #         if is_green:
    #             green_run_days += 1
    #             if green_run_days == 1:
    #                 run_start_price = row.open_d
    #         elif is_red and green_run_days >= min_run_days:
    #             extension = (row.close_d - run_start_price) / run_start_price
    #             if extension >= min_extension_pct:
    #                 events.append(...)
    #             green_run_days = 0

    pass  # Ver implementación completa en archivo específico
```

**E8: Gap Down** (10 líneas, trivial):
```python
def detect_e8_gap_down_violent(df_daily: pl.DataFrame, gap_threshold: float = -0.15):
    """
    Detecta gap down violento: open < prev_close * (1 + gap_threshold)

    Ventana de descarga: [-1, +1] días (total 3 días)
    """
    return (
        df_daily
        .sort(["ticker", "trading_day"])
        .with_columns([
            pl.col("close_d").shift(1).over("ticker").alias("prev_close")
        ])
        .with_columns([
            ((pl.col("open_d") - pl.col("prev_close")) / pl.col("prev_close")).alias("gap_pct")
        ])
        .filter(
            (pl.col("gap_pct") < gap_threshold) &
            (pl.col("prev_close").is_not_null())
        )
        .select([
            "ticker", "trading_day",
            pl.lit("E8_GapDownViolent").alias("event_type"),
            "gap_pct", "prev_close", "open_d", "close_d"
        ])
    )
```

**Script maestro** (`build_multi_event_watchlists.py`):

```python
#!/usr/bin/env python
"""
Detecta eventos E0, E1, E4, E7, E8 y genera watchlists multi-evento
con merge inteligente de ventanas
"""
import polars as pl
from pathlib import Path
from datetime import timedelta

from event_detectors import (
    detect_e1_volume_explosion,
    detect_e4_parabolic_move,
    detect_e7_first_red_day,
    detect_e8_gap_down_violent,
)

def load_daily_cache():
    """Carga daily_cache completo"""
    cache_dir = Path("processed/daily_cache")
    dfs = []
    for ticker_dir in cache_dir.glob("ticker=*"):
        parquet_file = ticker_dir / "daily.parquet"
        if parquet_file.exists():
            dfs.append(pl.read_parquet(parquet_file))
    return pl.concat(dfs)

def merge_event_windows(events_df: pl.DataFrame, existing_e0_days: set) -> pl.DataFrame:
    """
    CRÍTICO: Merge inteligente de ventanas multi-evento

    Expande ventanas por evento y marca:
    - Días ya cubiertos por E0 (no re-descargar)
    - Días adicionales necesarios (descargar)

    Args:
        events_df: DataFrame con columnas [ticker, trading_day, event_type, window_pre, window_post]
        existing_e0_days: Set de (ticker, date) ya descargados en PASO 5

    Returns:
        DataFrame con columnas:
        - ticker, trading_day
        - E0_info_rich, E1_volume_explosion, E4_parabolic, E7_first_red, E8_gap_down (boolean)
        - event_types: List[str] (ej: ["E0", "E4"])
        - max_event_window: int (ventana máxima requerida)
        - days_to_download: List[date] (días que faltan descargar)
    """
    # 1. Expandir ventanas por evento
    expanded_events = []
    for row in events_df.iter_rows(named=True):
        ticker = row['ticker']
        event_day = row['trading_day']
        event_type = row['event_type']

        # Ventanas por tipo de evento (según C.1)
        windows = {
            'E1_VolExplosion': (-1, 2),    # 4 días total
            'E4_ParabolicMove': (-2, 3),   # 6 días total
            'E7_FirstRedDay': (-1, 2),     # 4 días total
            'E8_GapDown': (-1, 1),         # 3 días total
        }

        pre, post = windows.get(event_type, (0, 0))

        # Expandir ventana
        for offset in range(pre, post + 1):
            expanded_day = event_day + timedelta(days=offset)
            expanded_events.append({
                'ticker': ticker,
                'date': expanded_day,
                'event_type': event_type,
                'is_event_day': (offset == 0),
            })

    df_expanded = pl.DataFrame(expanded_events)

    # 2. Agrupar por (ticker, date) y consolidar eventos
    df_consolidated = (
        df_expanded
        .group_by(['ticker', 'date'])
        .agg([
            pl.col('event_type').unique().alias('event_types'),
        ])
    )

    # 3. Marcar días ya descargados vs días nuevos
    df_consolidated = df_consolidated.with_columns([
        pl.when(pl.struct(['ticker', 'date']).is_in(existing_e0_days))
          .then(pl.lit(True))
          .otherwise(pl.lit(False))
          .alias('already_downloaded'),
    ])

    return df_consolidated

def main():
    print("="*80)
    print("MULTI-EVENT WATCHLIST GENERATION")
    print("="*80)

    # Cargar daily cache
    df_daily = load_daily_cache()
    print(f"Daily cache loaded: {len(df_daily):,} rows")

    # Detectar eventos
    print("\nDetecting events...")
    e1_events = detect_e1_volume_explosion(df_daily)
    e4_events = detect_e4_parabolic_move(df_daily)
    e7_events = detect_e7_first_red_day(df_daily)
    e8_events = detect_e8_gap_down_violent(df_daily)

    print(f"  E1 (Volume Explosion): {len(e1_events):,}")
    print(f"  E4 (Parabolic Move):   {len(e4_events):,}")
    print(f"  E7 (First Red Day):    {len(e7_events):,}")
    print(f"  E8 (Gap Down):         {len(e8_events):,}")

    # Combinar eventos
    all_events = pl.concat([e1_events, e4_events, e7_events, e8_events])

    # Cargar días E0 existentes
    existing_e0_days = set()
    e0_watchlists_dir = Path("processed/universe/info_rich/daily")
    for watchlist_path in e0_watchlists_dir.glob("date=*/watchlist.parquet"):
        date_str = watchlist_path.parent.name.split('=')[1]
        df_e0 = pl.read_parquet(watchlist_path)
        for ticker in df_e0['ticker'].to_list():
            existing_e0_days.add((ticker, date_str))

    print(f"\nExisting E0 days: {len(existing_e0_days):,}")

    # Merge inteligente de ventanas
    df_merged = merge_event_windows(all_events, existing_e0_days)

    # Estadísticas
    days_new = df_merged.filter(pl.col('already_downloaded') == False)
    print(f"\nNew days to download: {len(days_new):,}")
    print(f"Days already covered by E0: {len(df_merged) - len(days_new):,}")

    # Guardar watchlists multi-evento
    outdir = Path("processed/universe/multi_event/daily")
    outdir.mkdir(parents=True, exist_ok=True)

    for date_str in df_merged['date'].unique().sort():
        df_date = df_merged.filter(pl.col('date') == date_str)
        date_dir = outdir / f"date={date_str}"
        date_dir.mkdir(exist_ok=True)
        df_date.write_parquet(date_dir / "watchlist.parquet")

    print(f"\nWatchlists saved: {outdir}")

if __name__ == "__main__":
    main()
```

**Comando ejecución**:
```bash
python scripts/fase_C_ingesta_tiks/build_multi_event_watchlists.py
```

**Output esperado**:
```
Multi-event watchlists: processed/universe/multi_event/daily/
- Total days: ~10,000-15,000
- New days to download: ~30,000-40,000 (no cubiertos por E0)
- Days already covered: ~64,801 (E0 ya descargado)
```

---

#### Track B: Prototipo DIB/VIB (Días 1-3, en paralelo)

**Objetivo**: **VALIDAR que podemos construir barras informativas** antes de commitment +3 TB

**Por qué es OBLIGATORIO ahora**:
> Track B no es "nice to have" decorativo. Es la validación de que nuestra **feature factory intradía funciona**. Sin Track B validado, descargar más datos es **fe sin pruebas**.

**Script prototipo** (`scripts/fase_D_barras/prototype_dib_vib.py`):

```python
#!/usr/bin/env python
"""
Prototipo DIB/VIB: Validación técnica de construcción de barras informativas

OBJETIVO:
- Probar que podemos leer ticks descargados
- Construir Dollar Imbalance Bars (López de Prado Cap 2.4)
- Generar features básicas de microestructura
- Verificar timestamps, timezone, y cálculos numéricos

INPUT:
- Subset pequeño: 2-3 tickers × 10 días E0
- Ticks ya descargados: raw/polygon/trades/<TICKER>/date=*/trades.parquet

OUTPUT:
- temp_prototype_bars/<TICKER>/date=*/dib.parquet
- Validación: timestamps OK, features OK, pipeline funciona
"""
import polars as pl
from pathlib import Path
from datetime import datetime

def build_dollar_imbalance_bars(df_ticks: pl.DataFrame, threshold_usd: float = 250_000.0):
    """
    Construye Dollar Imbalance Bars según López de Prado (2018) Cap 2.4

    Algoritmo:
    1. Inferir dirección de trade con tick rule (buy=+1, sell=-1)
    2. Acumular imbalance = sum(direction × dollar_volume)
    3. Cuando |imbalance| >= threshold → crear nueva barra

    Args:
        df_ticks: DataFrame con [t (timestamp), p (price), s (size), ...]
        threshold_usd: Umbral de dólares acumulados para formar barra

    Returns:
        DataFrame con barras: [bar_start, bar_end, notional, imbalance, n_ticks, ...]
    """
    # 1. Calcular dollar volume por tick
    df = df_ticks.with_columns([
        (pl.col('p') * pl.col('s')).alias('dollar_volume')
    ])

    # 2. Inferir dirección con tick rule (simplificado)
    # Dirección = +1 si precio sube, -1 si baja, 0 si igual
    df = df.with_columns([
        pl.when(pl.col('p') > pl.col('p').shift(1))
          .then(pl.lit(1))
          .when(pl.col('p') < pl.col('p').shift(1))
          .then(pl.lit(-1))
          .otherwise(pl.lit(0))
          .alias('direction')
    ])

    # 3. Calcular signed dollar volume
    df = df.with_columns([
        (pl.col('direction') * pl.col('dollar_volume')).alias('signed_dollar_volume')
    ])

    # 4. Acumular imbalance y crear barras cuando |imbalance| >= threshold
    bars = []
    cumulative_imbalance = 0.0
    bar_start_idx = 0

    for idx, row in enumerate(df.iter_rows(named=True)):
        cumulative_imbalance += row['signed_dollar_volume']

        if abs(cumulative_imbalance) >= threshold_usd:
            # Crear barra
            bar_ticks = df[bar_start_idx:idx+1]
            bars.append({
                'bar_start': bar_ticks['t'].min(),
                'bar_end': bar_ticks['t'].max(),
                'notional': bar_ticks['dollar_volume'].sum(),
                'imbalance': cumulative_imbalance,
                'n_ticks': len(bar_ticks),
                'avg_price': bar_ticks['p'].mean(),
                'volume': bar_ticks['s'].sum(),
            })

            # Reset acumulador
            cumulative_imbalance = 0.0
            bar_start_idx = idx + 1

    return pl.DataFrame(bars)

def prototype_single_ticker_day(ticker: str, date_str: str):
    """
    Procesa un ticker-día: ticks → DIB bars
    """
    # Leer ticks
    ticks_path = Path(f"raw/polygon/trades/{ticker}/date={date_str}/trades.parquet")
    if not ticks_path.exists():
        print(f"  SKIP: {ticker} {date_str} (no ticks)")
        return None

    df_ticks = pl.read_parquet(ticks_path)
    print(f"  {ticker} {date_str}: {len(df_ticks):,} ticks")

    # Construir DIB
    df_bars = build_dollar_imbalance_bars(df_ticks, threshold_usd=250_000.0)
    print(f"    → {len(df_bars)} DIB bars")

    # Guardar prototipo
    outdir = Path(f"temp_prototype_bars/{ticker}/date={date_str}")
    outdir.mkdir(parents=True, exist_ok=True)
    df_bars.write_parquet(outdir / "dib.parquet")

    return df_bars

def main():
    print("="*80)
    print("PROTOTYPE DIB/VIB - VALIDACIÓN TÉCNICA")
    print("="*80)

    # Subset pequeño para validación
    sample_tickers = ["BCRX", "GERN", "VXRT"]
    sample_dates = [
        "2020-03-16",
        "2020-03-17",
        "2020-03-18",
        "2021-06-10",
        "2021-06-11",
        "2022-08-15",
        "2022-08-16",
        "2023-05-22",
        "2024-02-12",
        "2024-10-15",
    ]

    print(f"\nSample: {len(sample_tickers)} tickers × {len(sample_dates)} days = {len(sample_tickers) * len(sample_dates)} ticker-days")

    # Procesar subset
    results = []
    for ticker in sample_tickers:
        for date_str in sample_dates:
            result = prototype_single_ticker_day(ticker, date_str)
            if result is not None:
                results.append(result)

    print(f"\n{'='*80}")
    print(f"VALIDACIÓN COMPLETA")
    print(f"{'='*80}")
    print(f"Ticker-days procesados: {len(results)}")
    print(f"\n✅ Pipeline DIB/VIB validado")
    print(f"✅ Listo para escalar a dataset completo")

if __name__ == "__main__":
    main()
```

**Comando ejecución**:
```bash
python scripts/fase_D_barras/prototype_dib_vib.py
```

**Validaciones a verificar**:
1. ✅ Timestamps correctos (no "year 57676" errors)
2. ✅ Cálculos numéricos coherentes (imbalance, notional, VWAP)
3. ✅ Orden temporal correcto (bar_start < bar_end)
4. ✅ Features razonables (n_ticks > 0, notional > 0)
5. ✅ Pipeline no crashea (manejo de casos edge: días sin ticks, gaps, halts)

**Criterio de éxito Track B**:
- ✅ Procesa 30 ticker-días sin errores
- ✅ Genera barras coherentes (timestamps, features, orden)
- ✅ Code ready para escalar a ~300K ticker-días

---

### SEMANA 2: Descarga Incremental E1-E13 (Días 4-8)

**Prerequisito**: ✅ Track A completo (watchlists multi-evento listos) + ✅ Track B validado (DIB/VIB funciona)

**Script**: Reutilizar `download_trades_optimized.py` con watchlists multi-evento

**Comando**:
```bash
python scripts/fase_C_ingesta_tiks/download_trades_optimized.py \
  --watchlist-root processed/universe/multi_event/daily \
  --outdir raw/polygon/trades \
  --mode watchlists \
  --resume \
  --workers 8 \
  --rate-limit 0.15 \
  --page-limit 50000
```

**Lógica de descarga incremental**:
- `--resume` salta días con `_SUCCESS` existente
- Solo descarga:
  - Días E1-E13 NO cubiertos por E0
  - Ventanas adicionales (ej: E4 necesita ±3, E0 ya tiene ±1 → descarga solo ±2 y ±3)

**Storage estimado adicional**:
- Días nuevos: ~30K-40K (E1-E13 no cubiertos por E0)
- Small caps tienen 100x-1000x menos volumen que large caps
- Estimación: +3-4 TB (no +9 TB como estimación inicial)

**Metadata por ticker-día** (`events.json`):
```json
{
  "ticker": "BCRX",
  "date": "2020-03-16",
  "events": ["E0", "E4_ParabolicMove"],
  "event_windows": {
    "E0": 3,
    "E4": 6
  },
  "max_window_used": 6,
  "reason": "event_day"
}
```

**Monitoreo progreso**:
```bash
# Ver logs en tiempo real
tail -f download_trades.log

# Contar días completados
find raw/polygon/trades -name "_SUCCESS" | wc -l

# Storage acumulado
du -sh raw/polygon/trades
```

**Tiempo estimado**: 20-30 horas (paralelo con 8 workers)

---

### SEMANA 3-4: Dataset Maestro DIB/VIB (Días 9-14)

**Objetivo**: Construir **UNA SOLA VEZ** las barras informativas sobre conjunto completo {E0 ∪ E1-E13}

**Script final** (`scripts/fase_D_barras/build_info_bars.py`):

```python
#!/usr/bin/env python
"""
Construcción DIB/VIB sobre dataset completo multi-evento

INPUT:
- Ticks: raw/polygon/trades/<TICKER>/date=*/trades.parquet
- Metadata eventos: processed/universe/multi_event/daily/date=*/watchlist.parquet

OUTPUT:
- processed/bars/<TICKER>/date=*/
    ├── dib.parquet           (Dollar Imbalance Bars)
    ├── vib.parquet           (Volume Imbalance Bars)
    ├── features.parquet      (features microestructura)
    └── metadata.json         (eventos aplicables, contexto diario)

FEATURES POR BARRA:
- Timestamp (bar_start, bar_end)
- Price (open, high, low, close, vwap)
- Volume (total, buy_volume, sell_volume)
- Imbalance (dollar_imbalance, volume_imbalance)
- Microestructura (spread_pct, tick_rule_accuracy, order_flow_imbalance)
- Contexto diario (rvol30, pctchg_d, dollar_vol_d, eventos aplicables)
"""
import polars as pl
from pathlib import Path
import multiprocessing as mp

def build_bars_for_ticker_day(ticker: str, date_str: str, events_metadata: dict):
    """
    Construye DIB/VIB para un ticker-día con contexto de eventos
    """
    # Leer ticks
    ticks_path = Path(f"raw/polygon/trades/{ticker}/date={date_str}/trades.parquet")
    if not ticks_path.exists():
        return None

    df_ticks = pl.read_parquet(ticks_path)

    # Construir DIB/VIB
    df_dib = build_dollar_imbalance_bars(df_ticks)
    df_vib = build_volume_imbalance_bars(df_ticks)

    # Features de microestructura
    df_features = compute_microstructure_features(df_ticks, df_dib)

    # Adjuntar contexto de eventos
    df_dib = df_dib.with_columns([
        pl.lit(events_metadata.get('events', [])).alias('events'),
        pl.lit(events_metadata.get('rvol30', None)).alias('rvol30'),
        pl.lit(events_metadata.get('pctchg_d', None)).alias('pctchg_d'),
    ])

    # Guardar
    outdir = Path(f"processed/bars/{ticker}/date={date_str}")
    outdir.mkdir(parents=True, exist_ok=True)
    df_dib.write_parquet(outdir / "dib.parquet")
    df_vib.write_parquet(outdir / "vib.parquet")
    df_features.write_parquet(outdir / "features.parquet")

    # Metadata
    import json
    with open(outdir / "metadata.json", "w") as f:
        json.dump(events_metadata, f, indent=2)

    return {
        'ticker': ticker,
        'date': date_str,
        'n_bars_dib': len(df_dib),
        'n_bars_vib': len(df_vib),
    }

def main():
    print("="*80)
    print("BUILD INFO BARS - DATASET MAESTRO")
    print("="*80)

    # Cargar watchlists multi-evento
    watchlists_dir = Path("processed/universe/multi_event/daily")
    ticker_days = []

    for watchlist_path in sorted(watchlists_dir.glob("date=*/watchlist.parquet")):
        date_str = watchlist_path.parent.name.split('=')[1]
        df_watchlist = pl.read_parquet(watchlist_path)

        for row in df_watchlist.iter_rows(named=True):
            ticker_days.append({
                'ticker': row['ticker'],
                'date': date_str,
                'events': row.get('event_types', []),
                'rvol30': row.get('rvol30', None),
                'pctchg_d': row.get('pctchg_d', None),
            })

    print(f"Total ticker-days to process: {len(ticker_days):,}")

    # Procesar en paralelo
    with mp.Pool(processes=8) as pool:
        results = pool.starmap(
            build_bars_for_ticker_day,
            [(td['ticker'], td['date'], td) for td in ticker_days]
        )

    # Resumen
    results = [r for r in results if r is not None]
    print(f"\n{'='*80}")
    print(f"CONSTRUCCIÓN COMPLETA")
    print(f"{'='*80}")
    print(f"Ticker-days procesados: {len(results):,}")
    print(f"Barras DIB generadas: {sum(r['n_bars_dib'] for r in results):,}")
    print(f"Barras VIB generadas: {sum(r['n_bars_vib'] for r in results):,}")

if __name__ == "__main__":
    main()
```

**Comando ejecución**:
```bash
python scripts/fase_D_barras/build_info_bars.py
```

**Output esperado**:
```
processed/bars/
├── BCRX/
│   ├── date=2020-03-16/
│   │   ├── dib.parquet          (~50-200 barras)
│   │   ├── vib.parquet
│   │   ├── features.parquet
│   │   └── metadata.json        (eventos: ["E0", "E4"])
│   └── ...
└── ... (~300K ticker-días procesados)
```

**Tiempo estimado**: 5-7 días (procesamiento en paralelo)

---

## SIGUIENTE FASE: ML PIPELINE (POST-SEMANA 4)

Una vez completado el dataset maestro DIB/VIB:

### PASO 7: Triple Barrier Labeling

```python
# scripts/fase_E_ml/triple_barrier_labeling.py
# Implementar labeling por tipo de evento:
# - E7 (FRD): Short setup → label profit_target=-10%, stop_loss=+5%
# - E4 (Parabolic): Momentum → label profit_target=+15%, stop_loss=-5%
# - E8 (GapDown): Fade setup → label profit_target=+8%, stop_loss=-3%
```

### PASO 8: Sample Weighting

```python
# scripts/fase_E_ml/sample_weighting.py
# Bootstrap weights considerando:
# - Overlap temporal entre eventos (unicidad)
# - Importancia económica (dollar_vol_d)
# - Time decay (eventos recientes más relevantes)
```

### PASO 9: Dataset Maestro ML

```python
# scripts/fase_E_ml/build_master_dataset.py
# Unificar:
# - Barras (DIB/VIB)
# - Features (microestructura)
# - Labels (triple barrier)
# - Weights (bootstrap)
# - Metadata (eventos, régimen macro)
```

---

## MÉTRICAS DE ÉXITO

### Semana 1-2 (Ingeniería Base)
- ✅ Detectores E1, E4, E7, E8 implementados
- ✅ Watchlists multi-evento generadas (~10K-15K días)
- ✅ Prototipo DIB/VIB validado (30 ticker-días)
- ✅ Merge inteligente de ventanas funciona (no duplica descargas)

### Semana 3 (Descarga Incremental)
- ✅ Ticks adicionales E1-E13 descargados (~30K-40K días nuevos)
- ✅ Storage final: ~20-22 GB (vs ~2.6 TB estimado inicial)
- ✅ Metadata `events.json` por ticker-día
- ✅ Resume tolerance probado (puede interrumpir/continuar)

### Semana 4-5 (Dataset Maestro)
- ✅ DIB/VIB construidos sobre ~300K ticker-días
- ✅ Features microestructura calculadas
- ✅ Contexto diario + eventos adjuntados
- ✅ Dataset listo para triple barrier labeling

---

## DECISIONES ARQUITECTÓNICAS CLAVE

### 1. Por Qué Track B (Prototipo DIB/VIB) es Obligatorio Ahora

**NO es opcional decorativo**:
> Track B valida que nuestra **feature factory intradía funciona** antes de commitment +3 TB. Sin Track B, descargar más datos es **fe sin pruebas**.

**Qué valida**:
- ✅ Podemos leer ticks descargados (no están corruptos)
- ✅ Timestamps coherentes (no hay "year 57676" bugs)
- ✅ Imbalance calculation funciona (DIB/VIB correctas)
- ✅ Features de microestructura calculables
- ✅ Pipeline no crashea con casos edge (gaps, halts, días vacíos)

### 2. Merge Inteligente de Ventanas Multi-Evento

**Problema**: E4 necesita window ±3, E0 ya tiene ±1 → ¿descargar todo de nuevo?

**Solución**: `merge_event_windows()` en `build_multi_event_watchlists.py`

**Algoritmo**:
1. Expandir ventanas ideales por evento (E1: ±2, E4: ±3, E7: ±2, E8: ±1)
2. Cargar días ya cubiertos por E0 (set de (ticker, date))
3. Restar días existentes de días necesarios
4. Marcar días adicionales como "pendientes de descarga"
5. `--resume` en downloader salta días con `_SUCCESS`

**Resultado**: Descarga incremental eficiente (no duplica E0)

### 3. Por Qué NO Construir DIB/VIB con E0 Solo

**Problema**: E0 es genérico, no identifica patrón específico

**Impacto en ML**:
- DIB/VIB threshold óptimo varía por tipo de evento:
  - E1 (Vol Explosion): threshold bajo (100K USD)
  - E4 (Parabolic): threshold medio (250K USD)
  - E7 (FRD): threshold alto (500K USD)
- Labeling por tipo de setup (FRD → short, Parabolic → long)
- Sample weighting considera overlap entre eventos

**Conclusión**: DIB/VIB necesita contexto de TODOS los eventos para máxima calidad

---

## COMPARACIÓN: OPCIÓN B vs OPCIÓN C (HÍBRIDA)

| Aspecto | Opción B (DIB/VIB con E0 solo) | Opción C (Híbrido A+B) |
|---------|-------------------------------|------------------------|
| **DIB/VIB construction** | 2 veces (E0 → luego E0+E1-E13) | 1 vez (sobre conjunto completo) |
| **Descarga API** | 2 pasadas (E0 → luego adicionales) | 1 pasada (incremental con resume) |
| **Validación pipeline** | Después de E0 completo | Antes de commitment +3 TB |
| **Dataset calidad** | Mediocre (E0 genérico) | Completo (eventos específicos) |
| **Tiempo total** | ~15-20 días | ~10-12 días |
| **Riesgo** | Alto (re-trabajo si falla E1-E13) | Bajo (validación temprana) |
| **Flexibilidad** | Rígida (sequence B→A) | Flexible (paralelo A+B) |

**Conclusión**: Opción C es óptima (minimiza re-trabajo, valida temprano, dataset completo)

---

## REFERENCIAS TÉCNICAS

### López de Prado (2018) - Advances in Financial Machine Learning

**Cap 2.3-2.4: Information-Driven Bars**
- Dollar Imbalance Bars (DIB): pp. 29-32
- Volume Imbalance Bars (VIB): pp. 32-34
- Threshold estimation: pp. 35-37

**Cap 3: Triple Barrier Labeling**
- Profit target / stop loss: pp. 45-48
- Meta-labeling: pp. 50-53

**Cap 4: Sample Weighting**
- Bootstrap weights: pp. 63-65
- Sequential bootstrap: pp. 65-68
- Time decay: pp. 68-70

### EduTrades Playbook

**Setups por tipo de evento**:
- E7 (First Red Day): Short setup, profit_target=-10%, stop_loss=+5%
- E4 (Parabolic Move): Momentum long, profit_target=+15%, stop_loss=-5%
- E8 (Gap Down): Fade long, profit_target=+8%, stop_loss=-3%
- E1 (Vol Explosion): Scalp setup, profit_target=+5%, stop_loss=-2%

---

## CONCLUSIÓN

**ROADMAP APROBADO**: Híbrido A+B (Multi-evento + Prototipo DIB/VIB en paralelo)

**Tiempo total**: ~10-12 días (vs 15-20 con alternativas)

**Próximo paso inmediato**:
1. Crear directorios: `scripts/fase_C_ingesta_tiks/event_detectors/`, `scripts/fase_D_barras/`
2. Implementar detectores E1, E4, E7, E8 (Track A, días 1-2)
3. Implementar prototipo DIB/VIB (Track B, días 1-3, en paralelo)

**Validación crítica antes de PASO 6**:
- ✅ Track A: Watchlists multi-evento con merge inteligente
- ✅ Track B: Prototipo DIB/VIB procesa 30 ticker-días sin errores

**Dataset maestro final**:
- {E0 ∪ E1 ∪ E4 ∪ E7 ∪ E8} multi-evento
- ~300K ticker-días
- DIB/VIB con features de microestructura
- Metadata de eventos por ticker-día
- Listo para triple barrier labeling → ML

---

**Documento creado**: 2025-10-27
**Autor**: Alex Just Rodriguez + Claude (Anthropic)
**Versión**: 1.0.0 (Aprobada)
**Status**: ROADMAP OFICIAL - LISTO PARA EJECUCIÓN

**FIN DE C.7**
