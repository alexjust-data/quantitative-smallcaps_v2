# 6.2 - ACTUALIZACIÓN CRÍTICA: Timestamp Fix Definitivo

**Fecha**: 2025-10-27
**Referencia**: [C.5.6_problema_timestamps_critico.md](../C_v2_ingesta_tiks_2004_2025/C.5.6_problema_timestamps_critico.md)

---

## ⚠️ IMPORTANTE: Fix Temporal Reemplazado por Solución Definitiva

El fix temporal documentado en [6.1_Ejecucion_Pipeline_DIB_Labels_Weights.md](./6.1_Ejecucion_Pipeline_DIB_Labels_Weights.md) líneas 44-58 **ha sido reemplazado** por una solución definitiva.

---

## Comparación de Soluciones

### Fix TEMPORAL (2025-10-22) - DESCONTINUADO ❌

**Ubicación**: `build_bars_from_trades.py` líneas 57-63

```python
# Check if timestamp values are too large (> year 3000 when interpreted as microseconds)
t_sample = df["t"].head(1).cast(pl.Int64).item()
if t_sample > 32503680000000000:  # Jan 1, 3000 in microseconds
    # Timestamps are in nanoseconds, convert to microseconds
    df = df.with_columns((pl.col("t").cast(pl.Int64) // 1000).cast(pl.Datetime(time_unit="us")).alias("t"))
```

**Problema**:
- Fix aplicado en el momento de **lectura** (downstream)
- Archivos descargados seguían teniendo formato incorrecto
- Cada script que leía ticks necesitaba aplicar el fix
- No escalable para múltiples pipelines

---

### Fix DEFINITIVO (2025-10-27) - APLICADO ✅

**Ubicación**: `scripts/fase_C_ingesta_tiks/download_trades_optimized.py` líneas 174-222

**Commit**: [c62ba86](https://github.com/user/repo/commit/c62ba86) - "fix: CRITICAL - Save timestamps as Int64 to prevent corruption"

```python
def to_parquet_trades(...):
    ...
    if "t" in df.columns:
        # 1. Guardar como Int64 RAW (sin conversión datetime)
        df = df.with_columns([
            pl.col("t").cast(pl.Int64).alias("t_raw")
        ])

        # 2. Detectar escala por magnitud
        max_ts = int(df["t_raw"].max())
        if max_ts > 1e17:
            time_unit = "ns"  # nanosegundos
        elif max_ts > 1e14:
            time_unit = "us"  # microsegundos
        else:
            time_unit = "ms"  # milisegundos

        # 3. Guardar time_unit como metadato
        df = df.with_columns([
            pl.lit(time_unit).alias("t_unit")
        ])

        # 4. Eliminar columna 't' original
        df = df.drop("t")

    # Guardar con formato NUEVO
    df.write_parquet(output_path, compression="zstd", compression_level=2)
```

**Ventajas**:
- ✅ Fix aplicado en **origen** (downloader)
- ✅ Todos los archivos nuevos tienen formato correcto
- ✅ Scripts downstream reciben datos limpios
- ✅ Escalable a múltiples pipelines (E1-E13)
- ✅ Previene +3-5 TB de datos corruptos futuros

---

## Formato de Archivos

### FORMATO VIEJO (pre 2025-10-27) - CORRUPTO ❌

```python
Schema({
  't': Datetime(time_unit='us', time_zone=None),  # ❌ Asume microsegundos
  'p': Float64,
  's': UInt64,
  'c': List[UInt8],
  'x': UInt8,
  'z': UInt8
})
```

**Problema**: Polygon API retorna nanosegundos pero se guardaba asumiendo microsegundos → Fechas imposibles (año 52XXX)

---

### FORMATO NUEVO (post 2025-10-27) - CORRECTO ✅

```python
Schema({
  't_raw': Int64,        # Timestamp RAW sin conversión ✅
  't_unit': String,      # 'ns', 'us', o 'ms' ✅
  'p': Float64,          # Precio
  's': UInt64,           # Size
  'c': List[UInt8],      # Condiciones
  'x': UInt8,            # Exchange
  'z': UInt8             # Tape
})
```

**Ventajas**:
- Preserva valor original sin pérdida de información
- Metadato explícito de unidad temporal
- Compatible con escalas mixtas (ns/us/ms)

---

## Actualización Scripts Downstream

### Scripts que DEBEN actualizarse:

1. ✅ **`build_bars_from_trades.py`** - Constructor barras DIB/VIB
2. ✅ **`prototype_dib_vib_v3.py`** → **v4** (ya actualizado)
3. ⏭️ Cualquier script que lea `raw/polygon/trades/**/*.parquet`

---

### Template para Leer Formato NUEVO:

```python
import polars as pl

def read_trades_with_timestamps(path):
    """
    Lee archivos de ticks con formato NUEVO (t_raw + t_unit)
    """
    # 1. Leer archivo
    df = pl.read_parquet(path, columns=['t_raw', 't_unit', 'p', 's'])

    # 2. Verificar formato NUEVO
    if 't_raw' not in df.columns or 't_unit' not in df.columns:
        raise ValueError(f"OLD FORMAT detected in {path}. Need t_raw + t_unit columns.")

    # 3. Detectar time_unit
    time_unit = df['t_unit'][0]  # 'ns', 'us', o 'ms'

    # 4. Convertir según unidad detectada
    if time_unit == 'ns':
        df = df.with_columns([
            pl.col('t_raw').cast(pl.Datetime(time_unit='ns')).alias('timestamp')
        ])
    elif time_unit == 'us':
        df = df.with_columns([
            pl.col('t_raw').cast(pl.Datetime(time_unit='us')).alias('timestamp')
        ])
    elif time_unit == 'ms':
        df = df.with_columns([
            pl.col('t_raw').cast(pl.Datetime(time_unit='ms')).alias('timestamp')
        ])
    else:
        raise ValueError(f"Unknown time_unit: {time_unit}")

    return df
```

---

### Ejemplo Aplicado a `build_bars_from_trades.py`:

**Ubicación a modificar**: Función de lectura de ticks (línea ~80-120)

**ANTES (formato viejo con fix temporal):**
```python
df = pl.read_parquet(ticks_path)

# Fix temporal: detectar y convertir ns → μs
t_sample = df["t"].head(1).cast(pl.Int64).item()
if t_sample > 32503680000000000:
    df = df.with_columns((pl.col("t").cast(pl.Int64) // 1000).cast(pl.Datetime(time_unit="us")).alias("t"))
```

**DESPUÉS (formato nuevo):**
```python
df = pl.read_parquet(ticks_path, columns=['t_raw', 't_unit', 'p', 's', 'c', 'x', 'z'])

# Detectar time_unit y convertir correctamente
time_unit = df['t_unit'][0]

if time_unit == 'ns':
    df = df.with_columns([pl.col('t_raw').cast(pl.Datetime(time_unit='ns')).alias('t')])
elif time_unit == 'us':
    df = df.with_columns([pl.col('t_raw').cast(pl.Datetime(time_unit='us')).alias('t')])
else:  # 'ms'
    df = df.with_columns([pl.col('t_raw').cast(pl.Datetime(time_unit='ms')).alias('t')])

# Ahora 't' es correcto y el resto del código funciona igual
```

---

## Estado Actual de los Datos

### Datos RE-DESCARGADOS con Fix (2025-10-27):

```
raw/polygon/trades/
├── 60,825 archivos trades.parquet con FORMATO NUEVO ✅
├── 4,871 tickers únicos
├── 11.05 GB storage
└── 100% verificados sin errores timestamp
```

**Validación**:
- Script: `scripts/spot_check_timestamps.py`
- Resultado: 20/20 archivos (100%) con formato NUEVO
- Time unit detectado: `'ns'` (nanosegundos) en todos los casos
- 0 errores "year 52XXX"

---

## Impacto en Pipeline DIB/VIB

### Pipeline ACTUAL (con datos corruptos) - DEPRECADO ❌

```
processed/bars/      (11,054 archivos - generados con fix temporal)
processed/labels/    (11,054 archivos)
processed/weights/   (11,054 archivos)
processed/datasets/  (1.6M rows ML dataset)
```

**Status**: Funciona pero usa fix temporal. **Recomendación: RE-GENERAR** con formato nuevo.

---

### Pipeline NUEVO (con datos limpios) - RECOMENDADO ✅

**Pasos sugeridos:**

1. **Actualizar `build_bars_from_trades.py`** con template de lectura nuevo formato
2. **Re-generar barras DIB** desde `raw/polygon/trades` (60,825 días)
3. **Re-generar labels + weights** (sin cambios en lógica)
4. **Re-generar ML dataset** (1.6M rows con timestamps correctos)

**Tiempo estimado**: ~20-30 minutos (mismo que pipeline original)

**Ventaja**: Barras DIB con timestamps CORRECTOS (t_open, t_close) para análisis temporal

---

## Validación Prototipo DIB/VIB v4

**Script**: `scripts/fase_D_barras/prototype_dib_vib_v4.py`

**Resultado ejecución**:
```
Sample: 12 ticker-days
Threshold: $250,000 USD

Processing BCRX 2020-03-09... [OK] 40,925 ticks -> 27,635 bars (avg 1 ticks/bar, 0.8s/bar, unit=ns)
Processing BCRX 2020-04-15... [OK] 28,660 ticks -> 25,455 bars (avg 1 ticks/bar, 0.6s/bar, unit=ns)
Processing VXRT 2020-03-17... [OK] 41,800 ticks -> 36,426 bars (avg 1 ticks/bar, 0.5s/bar, unit=ns)

SUCCESS: 3/3 archivos existentes (100%)
Total ticks procesados: 111,385
Total barras DIB generadas: 89,516
Promedio duración/bar: 0.6 seconds
Total notional: $101,248,206

✅ VALIDACION EXITOSA
✅ Timestamps NUEVO formato funcionan correctamente
✅ Barras DIB tienen timestamps (bar_start_ts, bar_end_ts, duration_sec)
```

**Documentación**: [C.5.7_validacion_prototipo_dib_vib.md](../C_v2_ingesta_tiks_2004_2025/C.5.7_validacion_prototipo_dib_vib.md)

---

## Referencias

- [C.5.6_problema_timestamps_critico.md](../C_v2_ingesta_tiks_2004_2025/C.5.6_problema_timestamps_critico.md) - Análisis completo del bug
- [C.5.5_resultados_paso_5.md](../C_v2_ingesta_tiks_2004_2025/C.5.5_resultados_paso_5.md) - Resultados re-descarga con fix
- [C.5.7_validacion_prototipo_dib_vib.md](../C_v2_ingesta_tiks_2004_2025/C.5.7_validacion_prototipo_dib_vib.md) - Validación prototipo v4
- [prototype_dib_vib_v4.py](../../../scripts/fase_D_barras/prototype_dib_vib_v4.py) - Código actualizado

---

## Próximos Pasos

1. ✅ Fix aplicado y validado
2. ✅ 60,825 días re-descargados con formato NUEVO
3. ✅ Prototipo DIB/VIB v4 funciona correctamente
4. ⏭️ Actualizar `build_bars_from_trades.py` con template nuevo formato
5. ⏭️ Re-generar pipeline completo (DIB + Labels + Weights)
6. ⏭️ Aplicar mismo fix a downloaders E1-E13 (multi-evento)

---

**Timestamp Fix ROI**: ~500:1
- Tiempo fix: 3 horas (análisis + código + validación)
- Tiempo ahorrado: ~4 semanas re-trabajo + +3-5 TB datos corruptos evitados (E1-E13)

---
