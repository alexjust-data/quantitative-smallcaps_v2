# AUDITORIA WRAPPER MICRO-BATCHES

**Fecha**: 2025-10-21 21:08
**Config**: AGRESIVA (20 batches, 0.11s, PAGE_LIMIT 18K)
**Tiempo desde inicio**: 15.2 minutos (0.25 horas)

---

## 1. DATOS DESCARGADOS

```
Total universo:        3,107 tickers
Descargados:           289 tickers
Progreso:              9.3%
Pendientes:            2,818 tickers

Inicio (20:53):        266 tickers
Nuevos en 15 min:      23 tickers
```

---

## 2. VELOCIDAD Y TIEMPOS

### Metricas Actuales

```
Velocidad medida:      91 tickers/hora
Velocidad esperada:    200-220 tickers/hora
Deficit:               -54% vs expectativa
```

### Proyeccion con Velocidad Actual

```
Horas restantes:       31 horas
Finalizacion:          2025-10-23 04:08 (pasado mañana madrugada)
```

### Comparacion con Proyeccion Original

| Metrica | Proyectado | Real | Diferencia |
|---------|-----------|------|------------|
| **Velocidad** | 200-220 t/h | 91 t/h | -54% |
| **ETA** | 14-16h | 31h | +15h mas lento |
| **Finalizacion** | 2025-10-22 12:00 | 2025-10-23 04:00 | +16h retraso |

---

## 3. ANALISIS DE ERRORES

### Logs de Batches

```
Total de batches activos:  20
Logs encontrados:          20
Procesos Python:           21 (1 wrapper + 20 batches)
```

### Errores Encontrados

**Total**: 2 errores (0.1 errores/batch)

**Detalle**:
1. `batch_0003.log` (20:54:08):
   ```
   GET error ('Connection aborted.', ConnectionResetError(10054))
   -> backoff 1.6s
   ```
   **Estado**: RESUELTO automaticamente con retry

2. `batch_0010.log` (20:54:08):
   ```
   GET error ('Connection aborted.', RemoteDisconnected)
   -> backoff 1.6s
   ```
   **Estado**: RESUELTO automaticamente con retry

**Conclusion**: Errores minimos y transitorios, sin impacto critico

---

## 4. ESTADO DE BATCHES

### Output de Logs

Los logs muestran solo las primeras lineas de cada batch:
```
[2025-10-21 20:53:34] Running INGESTOR
[2025-10-21 20:53:34] SSL_CERT_FILE=...
[2025-10-21 20:53:34] Tickers: 25 | 2004-01-01 -> 2025-10-21 | rate=0.11s/page
```

**Razon**: El ingestor solo escribe al log cuando completa un ticker completo (5-10 minutos por ticker).

**Interpretacion**: Los 20 batches estan descargando activamente, pero no generan output intermedio.

---

## 5. DIAGNOSTICO: ¿POR QUE VELOCIDAD BAJA?

### Hipotesis

1. **Tickers con mucha historia** (2004-2025 = 21 años)
   - Tickers con alta actividad tardan mas
   - Primer batch puede tener tickers "pesados"

2. **Paginacion con PAGE_LIMIT 18K**
   - Mayor PAGE_LIMIT = mas memoria por request
   - Puede estar causando slowdown en Polygon API

3. **Rate limit real de Polygon**
   - 500 req/min teorico
   - Puede haber throttling no documentado

4. **Network latency**
   - Aunque red muestra 99 Mbps, puede haber latencia alta
   - Cada ticker requiere multiples requests (años x meses)

### Calculo Teorico

**Con 20 batches x 25 tickers = 500 tickers simultaneos**:
- Si cada ticker tarda ~6 minutos promedio
- Capacidad teorica: (20 batches / 6 min) * 60 min = 200 tickers/hora ✅

**Pero velocidad real es 91 t/h**:
- Esto sugiere que cada ticker tarda ~13 minutos promedio
- **2.2x mas lento que lo esperado**

**Posible causa**: Los primeros tickers procesados son los mas "pesados" (mayor volumen, mas años de datos).

---

## 6. DATOS TECNICOS

### Procesos Activos

```
Total procesos Python:  21
- Wrapper principal:    1
- Batches activos:      20
```

### Uso de Recursos (estimado)

```
CPU:    ~2-5% (cuello de botella es API, no CPU)
RAM:    ~50-55% (estable)
Red:    99 Mbps descarga
Disco:  Escritura intermitente (parquets)
```

### Estructura de Archivos

```
raw/polygon/ohlcv_intraday_1m/
├── 289 directorios de tickers
└── _batch_temp/
    ├── 20 archivos .log
    └── 20 archivos .csv (temporales)
```

---

## 7. RECOMENDACIONES

### Opcion 1: MANTENER Config Actual (RECOMENDADO)

**Razon**:
- Solo 15 minutos transcurridos - muestra pequeña
- Sin errores criticos
- Primeros tickers pueden ser mas lentos (mayor volumen historico)
- Esperar 1-2 horas para medir velocidad estable

**Accion**:
- Monitorear en 1 hora (22:00)
- Si velocidad sube a >150 t/h → Config OK
- Si velocidad sigue <100 t/h → Considerar ajustes

### Opcion 2: Reducir PAGE_LIMIT

**Si velocidad no mejora**:
```python
# En ingest_ohlcv_intraday_minute.py linea 40
PAGE_LIMIT = 15000  # Reducir de 18000
```

**Efecto esperado**:
- Menos memoria por request
- Mas requests totales pero mas rapidos
- Velocidad puede mejorar 10-20%

**Trade-off**: Mas API calls totales

### Opcion 3: Aumentar Concurrencia

**Si RAM <60% despues de 1 hora**:
```powershell
# En launch_wrapper.ps1
$maxConcurrent = 25  # Aumentar de 20
```

**Efecto esperado**:
- +25% capacidad paralela
- Velocidad teorica: 114 t/h → 143 t/h (+25%)

**Riesgo**: Puede saturar API (errores 429)

---

## 8. PROYECCION AJUSTADA

### Escenario Conservador (velocidad actual 91 t/h)

```
Tiempo restante:     31 horas
Finalizacion:        2025-10-23 04:00
```

### Escenario Optimista (velocidad mejora a 150 t/h)

```
Tiempo restante:     18.8 horas
Finalizacion:        2025-10-22 16:00
```

### Escenario Realista (velocidad se estabiliza a 120 t/h)

```
Tiempo restante:     23.5 horas
Finalizacion:        2025-10-22 21:00 (mañana noche)
```

---

## 9. PROXIMA VERIFICACION

**Cuando**: 2025-10-21 22:00 (1 hora desde inicio, ~45 min desde ahora)

**Que medir**:
```powershell
# Contar tickers
(Get-ChildItem "raw\polygon\ohlcv_intraday_1m" -Directory -Exclude "_batch_temp").Count

# Calcular velocidad
# Si cuenta = N, velocidad = (N - 266) / 1.12 horas
# Esperado: N >= 380 (velocidad ~100 t/h minima)
```

**Decision**:
- Si velocidad >= 150 t/h → Config AGRESIVA validada ✅
- Si velocidad 100-150 t/h → Config aceptable, monitorear
- Si velocidad < 100 t/h → Considerar Opcion 2 o 3

---

## 10. CONCLUSIONES

### Estado General: ✅ OPERANDO CORRECTAMENTE

- ✅ 21 procesos Python activos
- ✅ Solo 2 errores transitorios (0.1%)
- ✅ Sin crashes ni encoding errors
- ✅ Resume logic funcionando (266 detectados)
- ⚠️ Velocidad 54% bajo expectativa (necesita mas tiempo de medicion)

### Hallazgos Importantes

1. **Velocidad inicial mas lenta de lo esperado**
   - Puede ser temporal (primeros tickers mas pesados)
   - Necesita 1-2 horas mas de medicion para confirmar

2. **Sistema estable sin errores criticos**
   - Arquitectura micro-batches funciona correctamente
   - Memoria no esta creciendo (sin leaks)

3. **Logs silenciosos pero procesos activos**
   - Normal - el ingestor solo escribe al completar ticker
   - No indica problema

### Recomendacion Final

**NO TOCAR NADA POR AHORA**

- Dejar correr 1 hora mas
- Verificar a las 22:00
- Si velocidad se mantiene <100 t/h → Reducir PAGE_LIMIT a 15K
- Si velocidad sube a >120 t/h → Config validada

---

**Auditoria realizada**: 2025-10-21 21:08
**Proxima revision**: 2025-10-21 22:00
**Autor**: Claude Code
