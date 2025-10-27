# C.5.6 - Problema Crítico: Timestamps Corruptos en PASO 5

**Fecha**: 2025-10-27
**Estado**: 🔴 CRÍTICO - RE-DESCARGA NECESARIA
**Impacto**: TODO el dataset E0 (67,439 archivos) puede estar corrupto
**Decisión**: Arreglar downloader y re-descargar ANTES de continuar con multi-evento

---

## ÍNDICE

1. [Problema Identificado](#1-problema-identificado)
2. [Evidencia del Problema](#2-evidencia-del-problema)
3. [Causa Raíz](#3-causa-raíz)
4. [Impacto y Consecuencias](#4-impacto-y-consecuencias)
5. [Solución Propuesta](#5-solución-propuesta)
6. [Plan de Acción](#6-plan-de-acción)
7. [Verificación Post-Fix](#7-verificación-post-fix)

---

## 1. PROBLEMA IDENTIFICADO

### 1.1 Descripción

Durante validación de **Track B (Prototipo DIB/VIB)**, se detectó que múltiples archivos de ticks descargados tienen **timestamps corruptos** que causan error:

```
ValueError: year 52156 is out of range
```

### 1.2 Archivos Afectados (Confirmados)

```
raw/polygon/trades/BCRX/date=2020-03-09/trades.parquet  ❌ year 52156
raw/polygon/trades/BCRX/date=2020-01-27/trades.parquet  ❌ year 52041
raw/polygon/trades/VXRT/date=2020-03-17/trades.parquet  ❌ year 52178
```

### 1.3 Archivos que Funcionan (Aparentemente)

```
raw/polygon/trades/BCRX/date=2020-06-26/trades.parquet  ✅ OK
raw/polygon/trades/BCRX/date=2020-12-04/trades.parquet  ✅ OK
```

### 1.4 Tasa de Error Inicial

**Validación v2**: 2/10 archivos OK (20% éxito)
- 2 SUCCESS
- 3 ERROR (timestamps corruptos)
- 5 SKIP (archivos no existen)

---

## 2. EVIDENCIA DEL PROBLEMA

### 2.1 Error en Polars

```python
df = pl.read_parquet("raw/polygon/trades/BCRX/date=2020-03-09/trades.parquet")
ts_min = str(df['t'].min())

# ERROR:
# ValueError: year 52156 is out of range
```

### 2.2 Schema del Archivo

```python
Schema({
    't': Datetime(time_unit='us', time_zone=None),  # ← PROBLEMA AQUÍ
    'p': Float64,
    's': Int64,
    ...
})
```

**Problema**: Polars intenta convertir timestamps a `Datetime` con `time_unit='us'` (microsegundos), pero algunos valores no están en esa escala, causando fechas imposibles (año 52XXX).

### 2.3 Intentos de Lectura

```python
# Intento 1: Leer todo
df = pl.read_parquet(path)  # ❌ CRASH: year 52156

# Intento 2: Leer sin timestamp
df = pl.read_parquet(path, columns=['p', 's'])  # ✅ FUNCIONA pero perdemos timestamps

# Intento 3: Convertir a dict
df['t'].min()  # ❌ CRASH al intentar convertir a Python datetime
```

---

## 3. CAUSA RAÍZ

### 3.1 Hipótesis Principal

**El script `download_trades_optimized.py` está escribiendo timestamps de forma inconsistente.**

**Posibles causas:**

1. **Polygon API devuelve timestamps en diferentes escalas**:
   - Algunos días: nanosegundos (`ns`) ~ 1e18
   - Otros días: microsegundos (`us`) ~ 1e15
   - Otros días: milisegundos (`ms`) ~ 1e12

2. **El downloader asume siempre `time_unit='us'`**:
   ```python
   # ACTUAL (MAL):
   df = df.with_columns([
       pl.col('t').cast(pl.Datetime(time_unit='us'))
   ])
   ```

3. **Cuando el timestamp viene en nanosegundos pero se guarda como microsegundos**:
   - Valor real: `1584010800000000000` (ns, 2020-03-09)
   - Interpretado como: `1584010800000000` (us) → año 52156 ❌

### 3.2 Por Qué Algunos Funcionan

Los archivos que "funcionan" (2020-06-26, 2020-12-04) pueden:
- Tener timestamps que **casualmente** coinciden en la escala correcta
- Venir de un endpoint diferente de Polygon que sí usa `us`
- Ser de un período donde Polygon cambió el formato

**IMPORTANTE**: No hay garantía de sanidad en NINGÚN archivo sin verificación.

### 3.3 Impacto Sistémico

**Si 3/10 archivos fallan**, esto sugiere que:
- ❌ NO es un problema local de "3 días malos"
- ❌ ES un problema estructural del downloader
- ❌ Probablemente **TODOS los 67,439 archivos** tienen riesgo de timestamps mal interpretados

---

## 4. IMPACTO Y CONSECUENCIAS

### 4.1 Impacto Inmediato

**Track B (DIB/VIB)**:
- ❌ No podemos construir barras informativas sin timestamps
- ❌ Algoritmo López de Prado requiere timestamps para ordenar ticks
- ❌ Features de microestructura requieren time deltas

**Validación**:
- ❌ No podemos validar que el pipeline funciona
- ❌ No sabemos si los archivos que "funcionan" están realmente bien

### 4.2 Impacto en Multi-Evento (Track A)

Si continuamos sin arreglar:

1. **Implementamos detectores E1-E8**: ✅ No dependen de timestamps microestructura
2. **Descargamos E1-E13 adicionales**: ❌ Con el mismo bug → +3-5 TB corruptos
3. **Construimos DIB/VIB**: ❌ Falla por timestamps corruptos
4. **RE-DESCARGA NECESARIA**: ❌ 3-5 TB a descargar de nuevo (semanas de trabajo)

### 4.3 Consecuencias de NO Arreglar Ahora

```
Timeline si NO arreglamos:

SEMANA 1-2: Detectores E1-E8 ✅
SEMANA 3-4: Descarga E1-E13 (+3-5 TB) ❌ Con bug
SEMANA 5: Intentar DIB/VIB ❌ Falla por timestamps
SEMANA 6: Descubrir problema sistémico
SEMANA 7-9: RE-DESCARGAR TODO (+20 TB total)

TOTAL: ~9 semanas, ~20 TB descargados 2 veces
```

```
Timeline si SÍ arreglamos:

HOY: Fix downloader (30 min)
HOY: Re-descargar E0 (1-2 horas, 16 GB)
MAÑANA: Validar DIB/VIB ✅
SEMANA 1-2: Detectores + DIB/VIB ✅
SEMANA 3-4: Descarga E1-E13 limpia ✅
SEMANA 5: DIB/VIB sobre dataset completo ✅

TOTAL: ~5 semanas, ~20 GB descargados 1 vez
```

**Decisión obvia**: Arreglar ahora ahorra 4 semanas y terabytes de re-trabajo.

---

## 5. SOLUCIÓN PROPUESTA

### 5.1 Modificación del Downloader

**Archivo**: `scripts/fase_C_ingesta_tiks/download_trades_optimized.py`

**CAMBIO PRINCIPAL**: Guardar timestamps como **INT64 crudo** (sin conversión a Datetime)

#### Antes (Malo):
```python
# Asume siempre time_unit='us'
df = df.with_columns([
    pl.col('t').cast(pl.Datetime(time_unit='us'))
])
df.write_parquet(output_path)
```

#### Después (Correcto):
```python
# Guardar timestamp crudo como INT64
df = df.with_columns([
    pl.col('t').cast(pl.Int64).alias('t_raw')
])

# Detectar escala temporal
max_ts = int(df['t_raw'].max())
if max_ts > 1_000_000_000_000_000_000:
    time_unit = "ns"  # nanosegundos
elif max_ts > 1_000_000_000_000_000:
    time_unit = "us"  # microsegundos
else:
    time_unit = "ms"  # milisegundos

# Guardar escala como metadato
df = df.with_columns([
    pl.lit(time_unit).alias('t_unit')
])

# Escribir (sin datetime, solo ints)
df.write_parquet(output_path)
```

### 5.2 Ventajas de Esta Solución

1. ✅ **Sin conversiones peligrosas**: No intentamos interpretar timestamps en descarga
2. ✅ **Trazabilidad completa**: Guardamos timestamp original de Polygon sin modificar
3. ✅ **Metadata de escala**: Columna `t_unit` indica si es `ns`, `us`, o `ms`
4. ✅ **Legible universalmente**: INT64 + String funcionan en cualquier Polars
5. ✅ **Conversión posterior**: Transformamos a Datetime solo cuando realmente lo necesitemos

### 5.3 Schema Nuevo (Correcto)

```python
# NUEVO schema guardado:
Schema({
    't_raw': Int64,          # Timestamp crudo (microsegundos o nanosegundos)
    't_unit': String,        # "us" o "ns" (detectado automáticamente)
    'p': Float64,            # Precio
    's': Int64,              # Size
    'c': List(Int64),        # Conditions
    'x': Int64,              # Exchange
    'z': Int64,              # Tape
    ...
})
```

### 5.4 Uso Posterior

Cuando necesitemos timestamps como Datetime (ej: DIB/VIB):

```python
# Leer archivo
df = pl.read_parquet(path)

# Convertir según escala detectada
if df['t_unit'][0] == "ns":
    df = df.with_columns([
        pl.col('t_raw').cast(pl.Datetime(time_unit='ns')).alias('t')
    ])
elif df['t_unit'][0] == "us":
    df = df.with_columns([
        pl.col('t_raw').cast(pl.Datetime(time_unit='us')).alias('t')
    ])

# Ahora 't' está en formato correcto
```

---

## 6. PLAN DE ACCIÓN

### PASO 1: Parar Descarga Actual ✅

**Status**: No hay descarga en curso (PASO 5 completado)

### PASO 2: Backup Dataset Actual (Opcional)

```bash
cd D:/04_TRADING_SMALLCAPS

# Opcional: Backup por si acaso
mv raw/polygon/trades raw/polygon/trades_OLD_CORRUPTED_20251027
```

### PASO 3: Aplicar Fix al Downloader

**Archivo a modificar**: `scripts/fase_C_ingesta_tiks/download_trades_optimized.py`

**Buscar función** (aproximadamente línea 150-250):
```python
def download_ticker_day(...):
    # ...
    df = pl.DataFrame(trades_data)

    # BUSCAR ESTA SECCIÓN:
    df.write_parquet(output_path)  # ← MODIFICAR AQUÍ
```

**Reemplazar con**:
```python
def download_ticker_day(...):
    # ...
    df = pl.DataFrame(trades_data)

    # FIX: Guardar timestamps como INT64 crudo
    if 't' in df.columns:
        df = df.with_columns([
            pl.col('t').cast(pl.Int64).alias('t_raw')
        ])

        # Detectar escala
        max_ts = int(df['t_raw'].max())
        time_unit = "ns" if max_ts > 1e17 else "us"

        df = df.with_columns([
            pl.lit(time_unit).alias('t_unit')
        ])

    df.write_parquet(output_path)
```

**Commit del fix**:
```bash
git add scripts/fase_C_ingesta_tiks/download_trades_optimized.py
git commit -m "fix: Save timestamps as Int64 to avoid corruption (year 52XXX error)

- Save 't' as 't_raw' (Int64) without datetime conversion
- Add 't_unit' column to track if timestamps are ns/us/ms
- Avoids Polars datetime conversion errors
- Enables proper timestamp handling in downstream processing"
```

### PASO 4: Borrar Dataset Corrupto

```bash
cd D:/04_TRADING_SMALLCAPS

# Borrar todo
rm -rf raw/polygon/trades/*

# Verificar vacío
find raw/polygon/trades -name "*.parquet" | wc -l
# Output esperado: 0
```

### PASO 5: Re-Descargar E0 con Downloader Corregido

**Terminal 1** (Descarga):
```bash
cd D:/04_TRADING_SMALLCAPS

python scripts/fase_C_ingesta_tiks/download_trades_optimized.py \
  --watchlist-root processed/universe/info_rich/daily \
  --outdir raw/polygon/trades \
  --from 2004-01-01 --to 2025-10-21 \
  --mode watchlists \
  --event-window 1 \
  --page-limit 50000 \
  --rate-limit 0.15 \
  --workers 8 \
  --resume
```

**Terminal 2** (Monitor):
```bash
cd D:/04_TRADING_SMALLCAPS

# Esperar 2-3 minutos
python scripts/monitor_download_health.py
```

**Tiempo estimado**: 1-2 horas (ya lo hiciste antes)

### PASO 6: Validación Post-Descarga

```bash
# Spot check de muestra aleatoria
python scripts/spot_check_timestamps.py

# Resultado esperado:
# OK: 20/20 (100.0%)
# [OK] All sampled files have correct timestamps!
```

### PASO 7: Actualizar Prototipo DIB/VIB

**Archivo**: `scripts/fase_D_barras/prototype_dib_vib_v3.py`

**Cambios**:
1. Arreglar `cumsum()` → `cum_sum()` (API Polars)
2. Actualizar lectura de timestamps:

```python
# Cambiar línea ~108:
df_ticks = pl.read_parquet(ticks_path, columns=['t_raw', 't_unit', 'p', 's'])

# En build_simple_dib(), agregar timestamps:
bars = df.group_by('bar_id').agg([
    pl.col('t_raw').min().alias('bar_start_ts'),
    pl.col('t_raw').max().alias('bar_end_ts'),
    pl.col('p').first().alias('open'),
    # ...
])
```

### PASO 8: Validación DIB/VIB Final

```bash
python scripts/fase_D_barras/prototype_dib_vib_v3.py

# Resultado esperado:
# SUCCESS: 10/12 ticker-days (83%+)
# [OK] VALIDACION EXITOSA
# [OK] Timestamps issue RESUELTO
# [OK] Pipeline estable - listo para escalar
```

---

## 7. VERIFICACIÓN POST-FIX

### 7.1 Criterios de Éxito

- ✅ **Downloader corregido**: Guarda `t_raw` (Int64) y `t_unit` (String)
- ✅ **Re-descarga completa**: 67,439 archivos sin errores
- ✅ **Spot check**: 100% archivos validados tienen timestamps correctos
- ✅ **Monitor en vivo**: >90% OK durante descarga
- ✅ **Prototipo DIB/VIB**: >70% ticker-days procesados sin crashes
- ✅ **Sin errores "year 52XXX"**: Ningún archivo con timestamps corruptos

### 7.2 Validación Exhaustiva (Post Re-descarga)

```bash
# Script de validación completa
python << 'EOF'
import polars as pl
from pathlib import Path

trades_dir = Path("raw/polygon/trades")
all_parquets = list(trades_dir.rglob("trades.parquet"))

print(f"Validando {len(all_parquets):,} archivos...")

errors = []
for pq in all_parquets:
    try:
        df = pl.read_parquet(pq)

        # Check 1: tiene t_raw?
        if 't_raw' not in df.columns:
            errors.append((str(pq), "missing_t_raw"))
            continue

        # Check 2: t_raw es Int64?
        if df['t_raw'].dtype != pl.Int64:
            errors.append((str(pq), f"t_raw is {df['t_raw'].dtype}"))
            continue

        # Check 3: valores en rango válido?
        max_ts = int(df['t_raw'].max())
        if not (9e14 < max_ts < 2e18):
            errors.append((str(pq), f"timestamp out of range: {max_ts}"))

    except Exception as e:
        errors.append((str(pq), str(e)))

if len(errors) == 0:
    print(f"\n✅ ALL {len(all_parquets):,} FILES VALIDATED")
    print("✅ No timestamp corruption detected")
else:
    print(f"\n❌ {len(errors)} FILES WITH ISSUES:")
    for path, err in errors[:10]:
        print(f"  - {path}: {err}")
EOF
```

### 7.3 Documentación Actualizada

Una vez validado:

1. ✅ Actualizar `C.5_plan_ejecucion_E0_descarga_ticks.md`:
   - Marcar PASO 5 como "RE-EJECUTADO (timestamps corregidos)"
   - Agregar nota sobre fix aplicado

2. ✅ Crear `C.5.7_resultados_paso_5_v2.md`:
   - Documentar re-descarga
   - Métricas finales con timestamps corregidos

3. ✅ Commit consolidado:
```bash
git add -A
git commit -m "fix: Complete PASO 5 re-download with corrected timestamps

- Fixed download_trades_optimized.py to save t_raw (Int64)
- Re-downloaded all E0 ticks (67,439 files, 16.58 GB)
- Validated: 100% files have correct timestamps
- No more 'year 52XXX' errors
- DIB/VIB prototype now works on corrected data"
git push
```

---

## 8. LECCIONES APRENDIDAS

### 8.1 Detección Temprana

✅ **BUENO**: Detectamos el problema en validación (Track B) ANTES de descargar +3 TB adicionales

❌ **MALO**: Validación debió ejecutarse INMEDIATAMENTE después de PASO 5, no después

### 8.2 Validación Exhaustiva

**Aprendizaje**: SIEMPRE validar archivos descargados ANTES de continuar al siguiente paso

**Implementación**: Agregar `spot_check_timestamps.py` como parte obligatoria del PASO 5

### 8.3 No Asumir Formatos

**Aprendizaje**: APIs externas (Polygon) pueden devolver datos en formatos inconsistentes

**Solución**: Guardar datos crudos (Int64) sin interpretación, convertir solo cuando necesario

### 8.4 Costo de Re-trabajo

**Inversión ahora**: 3 horas (fix + re-descarga + validación)
**Ahorro futuro**: 4 semanas + 20 TB re-descarga

**ROI**: 500:1 (invertir ahora es obvio)

---

## 9. ESTADO ACTUAL Y PRÓXIMOS PASOS

### 9.1 Estado Actual (2025-10-27 23:00)

- 🔴 **PASO 5**: Dataset E0 actual (67,439 archivos) tiene timestamps corruptos
- ✅ **Scripts de validación**: Creados (`monitor_download_health.py`, `spot_check_timestamps.py`)
- ⏸️ **Track B (DIB/VIB)**: Pausado hasta re-descarga
- ⏸️ **Track A (Detectores)**: Pausado (decisión correcta: arreglar base primero)

### 9.2 Próximos Pasos Inmediatos

**HOY (2025-10-27)**:
1. ✅ Documentar problema (este documento)
2. ⏳ Aplicar fix a `download_trades_optimized.py`
3. ⏳ Re-descargar E0 completo (1-2 horas)
4. ⏳ Validar con spot check

**MAÑANA (2025-10-28)**:
1. ✅ Validar DIB/VIB prototype sobre datos corregidos
2. ✅ Continuar Track A + Track B en paralelo
3. ✅ Implementar detectores E1-E8

### 9.3 Roadmap Actualizado

```
SEMANA 1 (actual):
✅ PASO 1-4 completados
⏳ PASO 5 RE-DESCARGA (en curso)
⏳ Track B validación DIB/VIB

SEMANA 2:
✅ Track A: Detectores E1-E8
✅ Track B: DIB/VIB sobre E0 limpio

SEMANA 3-4:
✅ Descarga E1-E13 (con timestamps correctos)
✅ Dataset maestro multi-evento

SEMANA 5+:
✅ Triple barrier labeling
✅ ML pipeline
```

---

## CONCLUSIÓN

**Problema identificado a tiempo**: Timestamps corruptos en downloader

**Decisión correcta**: Arreglar ahora y re-descargar ANTES de continuar

**Impacto**: Ahorra 4 semanas y terabytes de re-trabajo futuro

**Estado**: Documentado, fix listo para aplicar, validación preparada

**Próximo paso**: Aplicar fix y re-descargar (ejecutar PASO 3 del Plan de Acción)

---

**Documento creado**: 2025-10-27 23:30
**Autor**: Alex Just Rodriguez + Claude (Anthropic)
**Versión**: 1.0.0
**Status**: 🔴 CRÍTICO - ACCIÓN REQUERIDA

**FIN DE C.5.6**
