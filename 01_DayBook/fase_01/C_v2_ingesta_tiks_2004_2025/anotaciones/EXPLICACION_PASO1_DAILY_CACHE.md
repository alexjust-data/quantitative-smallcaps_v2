# PASO 1: Agregación OHLCV 1m → Daily Cache - Explicación Técnica

**Fecha**: 2025-10-30
**Script**: `scripts/fase_C_ingesta_tiks/build_daily_cache.py`
**Objetivo**: Transformar barras 1-minuto en agregación diaria con features para filtrado E0

---

## 📊 FLUJO DE DATOS

### INPUT: Barras 1-minuto (Fase B)

```
raw/polygon/ohlcv_intraday_1m/AAM/
├── date=2024-01-01/data.parquet  ← 390 barras (9:30-16:00 RTH)
├── date=2024-01-02/data.parquet  ← 390 barras
└── ...
```

**Schema barras 1-min**:
- `ticker`: Símbolo
- `date`: Fecha trading
- `t`: Timestamp Unix
- `o`, `h`, `l`, `c`: Open, High, Low, Close
- `v`: Volume (acciones)
- `n`: Number of trades
- `vw`: VWAP (Volume-Weighted Average Price)

---

## 🔄 TRANSFORMACIÓN: Agregación Diaria

### 1️⃣ Agregación Básica (Código líneas 140-165)

```python
daily = (
    df_1m.group_by(["ticker", "trading_day"])
    .agg([
        pl.col("c").last().alias("close_d"),              # Close del día
        pl.col("v").sum().alias("vol_d"),                 # Volumen total
        (pl.col("v") * pl.col("vw")).sum().alias("dollar_vol_d_raw"),
        pl.col("n").count().alias("session_rows"),        # Nro barras 1m
    ])
    .with_columns([
        # VWAP diario = sum(v*vw) / sum(v)
        (pl.col("dollar_vol_d_raw") / pl.col("vol_sum")).alias("vwap_d"),
        # Dollar volume final
        pl.col("dollar_vol_d_raw").alias("dollar_vol_d"),
        # Has gaps? (faltan barras 1-min)
        (pl.col("session_rows") < 390).alias("has_gaps"),
    ])
)
```

**Ejemplo visual**:

```
AAM 2024-01-02 - Barras 1-min:
┌────────┬───────┬────────┐
│ Time   │ v     │ vw     │
├────────┼───────┼────────┤
│ 09:30  │10,000 │ $25.50 │
│ 09:31  │ 5,000 │ $25.60 │
│ ...    │   ... │    ... │
│ 16:00  │ 8,000 │ $26.00 │ ← c = $26.00
└────────┴───────┴────────┘

Agregación diaria →
┌──────────────┬───────────────┐
│ close_d      │ $26.00        │ ← Último c del día
│ vol_d        │ 2,500,000     │ ← Σ(v)
│ dollar_vol_d │ $64,750,000   │ ← Σ(v × vw)
│ vwap_d       │ $25.90        │ ← dollar_vol_d / vol_d
│ session_rows │ 390           │ ← Cuenta de barras
│ has_gaps     │ False         │ ← 390 == 390 (completo)
└──────────────┴───────────────┘
```

---

### 2️⃣ Features Calculados (Código líneas 167-204)

#### **pctchg_d** - Cambio Porcentual Diario

```python
# Línea 184: Close del día anterior
close_prev = pl.col("close_d").shift(1).over("ticker")

# Línea 191: % change
pctchg_d = (close_d / close_prev) - 1.0
```

**Ejemplo**:
```
AAM:
┌────────────┬──────────┬───────────┐
│ Date       │ close_d  │ pctchg_d  │
├────────────┼──────────┼───────────┤
│ 2024-01-01 │ $25.00   │ N/A       │ ← Primer día
│ 2024-01-02 │ $28.75   │ +0.15     │ ← +15% 🚨 CALIFICA E0
│ 2024-01-03 │ $24.44   │ -0.15     │ ← -15% 🚨 CALIFICA E0
└────────────┴──────────┴───────────┘

Formula: (28.75 / 25.00) - 1.0 = 0.15 = +15%
```

**Uso en Filtros E0**: `|pctchg_d| ≥ 0.15` (15%)
- Detecta movimientos extremos
- Captura runners (+15%) y crashes (-15%)
- Basado en EduTrades Playbook (Gap&Go, FRD)

---

#### **rvol30** - Volumen Relativo 30 Sesiones

```python
# Línea 187: MA móvil 30 sesiones (FILAS, no días calendario)
vol_30s_ma = pl.col("vol_d").rolling_mean(window_size=30, min_periods=1).over("ticker")

# Línea 195: RVOL = volumen hoy / promedio 30 días
rvol30 = vol_d / vol_30s_ma
```

**Ejemplo**:
```
AAM - Historial últimos 30 días:
┌────────────┬───────────┬────────────┬─────────┐
│ Date       │ vol_d     │ vol_30s_ma │ rvol30  │
├────────────┼───────────┼────────────┼─────────┤
│ 2024-01-01 │ 1,000,000 │ 1,000,000  │ 1.0     │ ← Normal
│ 2024-01-02 │ 2,500,000 │ 1,000,000  │ 2.5     │ ← 🚨 ACTIVIDAD 2.5x SUPERIOR
│ 2024-01-03 │   800,000 │ 1,000,000  │ 0.8     │ ← Bajo
└────────────┴───────────┴────────────┴─────────┘

MA30 = promedio móvil últimas 30 SESIONES (no días calendario)
min_periods=1 → Permite calcular desde el primer día disponible
```

**Uso en Filtros E0**: `rvol30 ≥ 2.0`
- Detecta actividad anómala (2x superior a media)
- Captura inicio de pumps, bounces, first red days
- Fundamento: López de Prado (2018, Ch.1) - Event-based sampling

---

#### **dollar_vol_d** - Volumen en Dólares (VWAP-weighted)

```python
# Línea 145: Suma ponderada por VWAP de cada barra 1-min
dollar_vol_d = (pl.col("v") * pl.col("vw")).sum()
```

**Ejemplo**:
```
AAM 2024-01-02 - Barras 1-min:
┌────────┬───────┬────────┬──────────────┐
│ Time   │ v     │ vw     │ v × vw       │
├────────┼───────┼────────┼──────────────┤
│ 09:30  │10,000 │ $25.50 │ $255,000     │
│ 09:31  │ 5,000 │ $25.60 │ $128,000     │
│ ...    │   ... │    ... │      ...     │
│ 16:00  │ 8,000 │ $26.00 │ $208,000     │
└────────┴───────┴────────┴──────────────┘
                    Σ(v×vw) = $64,750,000

Dollar Volume ≠ close_d × vol_d
Dollar Volume = Σ(volumen_barra × vwap_barra) ← MÁS PRECISO
```

**Uso en Filtros E0**: `dollar_vol_d ≥ $5,000,000`
- Filtra micro-caps zombis sin liquidez
- Solo activos con flujo real e interés institucional
- Fundamento: Easley, López de Prado & O'Hara (2012) - Flow toxicity

---

## 📂 OUTPUT: Daily Cache Enriquecido

```
processed/daily_cache/ticker=AAM/daily.parquet

Schema final (11 columnas):
┌───────────────┬──────────┬─────────────────────────────────────┐
│ Columna       │ Tipo     │ Descripción                         │
├───────────────┼──────────┼─────────────────────────────────────┤
│ ticker        │ String   │ Símbolo                             │
│ trading_day   │ Date     │ Fecha trading                       │
│ close_d       │ Float64  │ Close del día (última barra)        │
│ vol_d         │ Int64    │ Volumen total acciones              │
│ dollar_vol_d  │ Float64  │ Volumen en dólares (VWAP-weighted)  │
│ vwap_d        │ Float64  │ VWAP del día                        │
│ pctchg_d      │ Float64  │ % change vs día anterior            │
│ return_d      │ Float64  │ Log return                          │
│ rvol30        │ Float64  │ Volumen relativo 30 sesiones        │
│ session_rows  │ Int64    │ Cantidad de barras 1-min            │
│ has_gaps      │ Boolean  │ ¿Faltan barras? (<390)              │
└───────────────┴──────────┴─────────────────────────────────────┘
```

---

## 🎯 USO DE FEATURES EN PASO 3: Filtros E0

### Fórmula E0 (Generic Info-Rich)

```python
E0_generic_info_rich = (
    rvol30 >= 2.0 AND                     # Volumen relativo 30 sesiones
    |pctchg_d| >= 0.15 AND                # 15% cambio absoluto
    dollar_vol_d >= 5_000_000 AND         # $5M volumen dólares
    close_d >= 0.20 AND                   # Precio mínimo $0.20
    close_d <= 20.00 AND                  # Precio máximo $20.00
    market_cap_d < 2_000_000_000          # Market cap < $2B
)
```

### Tabla de Uso

| Feature | Threshold E0 | Propósito | Fundamento |
|---------|--------------|-----------|------------|
| **rvol30** | ≥ 2.0 | Detectar actividad anómala | López de Prado (2018, Ch.1) - Event-based sampling |
| **pctchg_d** | \|x\| ≥ 15% | Identificar movimientos extremos | EduTrades Playbook - Gap&Go +15%, FRD -15% |
| **dollar_vol_d** | ≥ $5M | Filtrar zombis sin liquidez | Easley et al. (2012) - Flow toxicity |
| **close_d** | $0.20-$20 | Enfoque small caps | Proxy small caps + penny stocks válidos |

---

## 📈 EJEMPLO REAL COMPLETO

### AAM 2024-01-02 (Día Info-Rich)

**Barras 1-min agregadas**:
```
390 barras 1-min (9:30-16:00 RTH)
Close día anterior: $25.00
Close hoy: $28.75
Volumen total: 2,500,000 acciones
Dollar volume: $64,750,000
Promedio 30 días: 1,000,000 acciones/día
```

**Features calculados**:
```
close_d      = $28.75
vol_d        = 2,500,000 acciones
dollar_vol_d = $64,750,000
vwap_d       = $25.90
pctchg_d     = +0.15 (+15%)
rvol30       = 2.5
session_rows = 390
has_gaps     = False
```

**Evaluación Filtros E0**:
```
✅ rvol30 = 2.5        → PASA (≥2.0)   ← Volumen 2.5x superior
✅ pctchg_d = +15%     → PASA (≥15%)   ← Movimiento extremo
✅ dollar_vol_d = $64M → PASA (≥$5M)   ← Liquidez suficiente
✅ close_d = $28.75    → PASA ($0.20-$20) ← Rango small caps

→ Día CALIFICA como E0 (info-rich)
→ PASO 3 lo agregará a watchlist
→ PASO 5 descargará trades tick-by-tick para este día
```

---

## 🔍 DETALLES TÉCNICOS IMPORTANTES

### 1. RVOL30: Rolling por FILAS, no días calendario

```python
# Línea 187
pl.col("vol_d").rolling_mean(window_size=30, min_periods=1).over("ticker")
```

- **Window=30**: Últimas 30 SESIONES (días con trading)
- **min_periods=1**: Permite calcular desde el primer día disponible
- **NO días calendario**: Si hay gaps (fines de semana, feriados), solo cuenta días con datos

**Ejemplo**:
```
2024-01-01 Mon → sesión 1
2024-01-02 Tue → sesión 2
2024-01-03 Wed → sesión 3
2024-01-04 Thu → (no trading, holiday)
2024-01-05 Fri → sesión 4

MA30 en 2024-01-05 = promedio de últimas 30 SESIONES (ignora 2024-01-04)
```

### 2. Dollar Volume: VWAP-weighted vs Simple

```python
# ❌ INCORRECTO (simple):
dollar_vol_simple = close_d × vol_d

# ✅ CORRECTO (VWAP-weighted):
dollar_vol_d = Σ(volumen_barra_1m × vwap_barra_1m)
```

**Por qué VWAP-weighted es mejor**:
- Captura el precio promedio REAL al que se negociaron las acciones
- No asume que todo el volumen se negoció al close
- Más preciso para detectar flujo institucional real

**Ejemplo**:
```
AAM 2024-01-02:
close_d = $28.75
vol_d = 2,500,000
vwap_d = $25.90 (promedio ponderado real)

Simple:    $28.75 × 2,500,000 = $71,875,000  ← SOBRESTIMA
Correcto:  Σ(v×vw) = $64,750,000             ← REAL
Diferencia: +$7.1M (+11% error)
```

### 3. Has Gaps: Detección de datos incompletos

```python
# Línea 156
has_gaps = (session_rows < 390)
```

- **RTH (Regular Trading Hours)**: 9:30-16:00 = 390 minutos
- **has_gaps=True**: Faltan barras 1-min (datos incompletos, halts, etc.)
- **Uso futuro**: Potencial filtro adicional para calidad de datos

---

## 📚 REFERENCIAS

**Código fuente**: `scripts/fase_C_ingesta_tiks/build_daily_cache.py`
- Agregación diaria: líneas 140-165
- Features calculados: líneas 167-204

**Documentación**:
- [C.3.3_Contrato_E0.md](fase_01/C_v2_ingesta_tiks_2004_2025/C.3.3_Contrato_E0.md) - Especificación técnica inmutable (líneas 74-228)
- [C.5_plan_ejecucion_E0_descarga_ticks.md](fase_01/C_v2_ingesta_tiks_2004_2025/C.5_plan_ejecucion_E0_descarga_ticks.md) - PASO 1 completo

**Fundamentos teóricos**:
- López de Prado (2018, Ch.1): Event-based sampling
- Easley, López de Prado & O'Hara (2012): Flow toxicity and imbalance
- EduTrades Playbook: Gap&Go +15%, FRD -15%

---

## 🔄 TRADE-OFF RVOL: E0 vs E1

### E0 (Generic Info-Rich): RVOL ≥ 2.0

```
Filosofía: Máximo recall (cobertura amplia)
Objetivo: Capturar TODO evento con volumen anómalo
Cobertura: Pumps, bounces, reclaims, continuaciones, first red days
Resultado: 29,555 eventos detectados (14.76M días → 0.2%)
```

### E1 (VolExplosion): RVOL ≥ 5.0

```
Filosofía: Máxima precisión (eventos extremos)
Objetivo: Solo explosiones EXTREMAS de volumen
Cobertura: Inicio de pumps grandes (no bounces menores)
Resultado: 7,686 eventos detectados (más selectivo)
```

**Fuente**: [C.0_comparacion_enfoque_anterior_vs_nuevo.md](fase_01/C_v2_ingesta_tiks_2004_2025/C.0_comparacion_enfoque_anterior_vs_nuevo.md) líneas 120-141

---

## 📊 ESTADÍSTICAS PASO 1

**Ejecución real** (2025-10-26):
```
Input:  8,618 tickers × ~1,700 días promedio = 14.76M ticker-días
Output: processed/daily_cache/ (8,618 tickers cached)
Tiempo: ~4.8 horas
Formato: Parquet + ZSTD compression
```

**Resultado final**:
- ✅ 8,618 tickers procesados
- ✅ 14,763,368 ticker-días agregados
- ✅ Features calculados: rvol30, pctchg_d, dollar_vol_d, return_d
- ✅ Ready para PASO 3 (filtrado E0)

---

**STATUS**: ✅ PASO 1 COMPLETADO
**Última actualización**: 2025-10-30
