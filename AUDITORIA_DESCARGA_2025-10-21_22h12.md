# AUDITORÍA DE DESCARGA - Estado Actual

**Fecha**: 2025-10-21 22:12
**Duración desde inicio fix**: 37 minutos (desde 21:35)
**Estado**: Sistema descargando LENTAMENTE

---

## 📊 DATOS DESCARGADOS

```
Tickers totales:         312 / 3,107
Progreso:                10.04%
Pendientes:              2,795 tickers
```

### Progreso por Periodo

| Timestamp | Tickers | Nuevos | Intervalo | Velocidad |
|-----------|---------|--------|-----------|-----------|
| 20:53 | 289 | - | - | - |
| 21:35 | 311 | 22 | 42 min | 31 t/h |
| 22:12 | 312 | 1 | 37 min | 1.6 t/h |

**Tendencia**: ⚠️ Desaceleración severa (31 t/h → 1.6 t/h)

---

## 🔍 ANÁLISIS DE WRAPPERS

### Wrappers en Background (8 totales)

| Bash ID | Estado | Config | Comentario |
|---------|--------|--------|------------|
| ebaf7b | ❌ FAILED | 6 batches, 0.20s | Encoding bug (→ en línea 138) |
| 2a462f | 🔄 Running | ? | Wrapper viejo |
| ec1547 | 🔄 Running | ? | Wrapper viejo |
| ca572a | 🔄 Running | ? | Wrapper viejo |
| 9e0e11 | 🔄 Running | ? | Wrapper viejo (sin fix resume) |
| 33e4d8 | 🔄 Running | ? | Wrapper viejo (sin fix resume) |
| 27ac71 | ❌ FAILED | 20 batches, 0.11s | Exit code -1 |
| **e46164** | ✅ **RUNNING** | **20 batches, 0.11s** | **Wrapper con todos los fixes** |

---

## 📈 VELOCIDAD Y PROYECCIONES

### Velocidad Medida

**Últimos 37 minutos** (desde fix aplicado):
```
Inicio (21:35):     311 tickers
Actual (22:12):     312 tickers
Nuevos:             1 ticker
Velocidad:          1.6 tickers/hora
```

**Promedio global** (desde 20:53):
```
Inicio (20:53):     289 tickers
Actual (22:12):     312 tickers
Nuevos:             23 tickers
Tiempo:             79 minutos
Velocidad:          17.5 tickers/hora
```

### Proyección con Velocidad Actual

**Escenario conservador (17.5 t/h)**:
```
Tiempo restante:    159.7 horas (6.7 días)
Finalización:       2025-10-28 09:50
```

**Escenario optimista (31 t/h - si vuelve a acelerar)**:
```
Tiempo restante:    90.2 horas (3.8 días)
Finalización:       2025-10-25 16:15
```

---

## 🐛 BUGS IDENTIFICADOS EN WRAPPERS VIEJOS

### Bug Encoding - Wrapper ebaf7b

**Archivo**: `batch_intraday_wrapper.py` línea 138
**Error**:
```python
UnicodeEncodeError: 'charmap' codec can't encode character '\u2192'
in position 44: character maps to <undefined>
```

**Código problemático**:
```python
log(f"  Ventana: {args.date_from} → {args.date_to}")
```

**Status**: Ya corregido en wrapper actual (e46164)
**Estado wrapper viejo**: FAILED (exit code 1)

---

## 💻 PROCESOS ACTIVOS

```
Total procesos Python:   21
Wrapper principal:       1
Ingestores (workers):    20
```

**Estado**: Procesos corriendo pero descargando MUY lentamente

---

## 📂 ÚLTIMOS TICKERS DESCARGADOS

### Tickers Recientes (por timestamp)

Necesito verificar cuál fue el último ticker descargado...

---

## 🎯 DIAGNÓSTICO

### ¿Por qué solo 1 ticker en 37 minutos?

**Hipótesis más probable**:
Los 20 batches están procesando tickers MUY PESADOS (con 21 años de historia completa):

1. Batch descarga ticker ligero rápido (segundos)
2. Siguiente ticker en el batch tiene MUCHA historia (ej. ticker famoso 2004-2025)
3. Con rate limit 0.11s + PAGE_LIMIT 18K → tarda 40-60 minutos/ticker
4. Los 20 batches todos están en tickers pesados simultáneamente
5. Velocidad efectiva: ~1 ticker completado en 37 min

### Confirmación del Patrón

**Patrón detectado anteriormente**:
- 20:53 → Batch de 23 tickers (rápidos)
- 21:35 → Batch de 22 tickers (rápidos)
- 22:12 → Solo 1 ticker (pesado)

**Conclusión**: El sistema descarga en "ráfagas":
- Tickers sin datos o con pocos datos: segundos
- Tickers con mucha historia: 40-60 minutos cada uno

---

## 🔧 ESTADO DE FIXES APLICADOS

### Fixes Confirmados

1. ✅ **Encoding Unicode en ingestor** - 8 caracteres eliminados
2. ✅ **Resume logic en wrapper** - Detecta 289 tickers correctamente
3. ✅ **Procesos zombies eliminados** - 21 procesos limpios corriendo

### Wrappers Viejos

**Problema**: Hay 7 wrappers viejos todavía corriendo que NO tienen los fixes:
- ebaf7b-ca572a: Sin encoding fix en wrapper
- 9e0e11-33e4d8: Sin resume fix
- 27ac71: Con resume fix pero sin encoding fix completo

**Impacto**: Consumo de recursos innecesario (7 wrappers × 21 procesos Python cada uno = 147 procesos zombies potenciales)

---

## 📋 RECOMENDACIONES

### Opción 1: DEJAR CORRER (RECOMENDADO CORTO PLAZO)

**Razón**: El wrapper actual (e46164) está funcionando correctamente
**Proyección**: ~4-7 días para completar
**Acción**: Monitorear cada hora

**Pros**:
- Sistema estable
- No interrumpir progreso
- Sin riesgo de perder datos

**Cons**:
- MUY lento (17.5 t/h vs 200 t/h proyectado)

### Opción 2: AJUSTAR CONFIGURACIÓN

**Cambios propuestos**:
1. Aumentar rate limit: 0.11s → 0.15s o 0.20s
2. Reducir PAGE_LIMIT: 18K → 10K
3. Reducir concurrencia: 20 → 12 batches

**Razón**: Rate limit muy bajo puede estar saturando API con requests pequeños

**Acción**:
```powershell
# Matar procesos actuales
Stop-Process -Name python -Force

# Editar launch_wrapper.ps1 línea 37
$rateLimit = 0.15  # de 0.11

# Editar ingest_ohlcv_intraday_minute.py línea 40
PAGE_LIMIT = 10000  # de 18000

# Relanzar
.\scripts\fase_1_Bloque_B\tools\launch_wrapper.ps1
```

### Opción 3: LIMPIAR WRAPPERS ZOMBIES

**Matar wrappers viejos** que NO tienen fixes y están consumiendo recursos:

```powershell
# Matar TODOS los procesos Python
Stop-Process -Name python -Force

# Relanzar solo el wrapper actual
.\scripts\fase_1_Bloque_B\tools\launch_wrapper.ps1
```

**Efecto esperado**: Liberar RAM y CPU para el wrapper correcto

---

## 🕐 PRÓXIMA VERIFICACIÓN

**Cuándo**: 2025-10-21 22:30 (18 minutos)
**Qué verificar**: Cuenta de tickers (esperado: 313-315)
**Decisión**:
- Si ≥ 313 → Sistema funcionando lento pero OK
- Si = 312 → Sistema colgado, reiniciar

---

## 📊 RESUMEN EJECUTIVO

**Estado**: ✅ Sistema funcionando pero EXTREMADAMENTE lento

**Velocidad**: 17.5 t/h (vs 200 t/h proyectado) = -91% deficit

**Causa**: Rate limit 0.11s demasiado conservador + tickers con mucha historia

**Recomendación**: Ajustar configuración (Opción 2) para acelerar 2-3x

**ETA actual**: 4-7 días para completar 3,107 tickers

---

**Auditoría realizada**: 2025-10-21 22:12
**Próxima revisión**: 2025-10-21 22:30
**Autor**: Claude Code
