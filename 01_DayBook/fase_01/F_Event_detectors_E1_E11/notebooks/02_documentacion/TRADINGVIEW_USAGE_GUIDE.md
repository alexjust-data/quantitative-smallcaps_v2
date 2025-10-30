# Guía de Uso: Visualización de Eventos en TradingView

## 📊 ARCHIVOS GENERADOS

Se han exportado **11 archivos CSV** con **44,189 eventos** detectados:

| Evento | Archivo | Eventos | Descripción |
|--------|---------|---------|-------------|
| E6_MultipleGreenDays | `tradingview_E6_MultipleGreenDays.csv` | 16,776 | Múltiples días verdes consecutivos |
| E10_FirstGreenBounce | `tradingview_E10_FirstGreenBounce.csv` | 8,494 | Primer rebote verde tras caída |
| E1_VolExplosion | `tradingview_E1_VolExplosion.csv` | 7,686 | Explosión de volumen |
| E5_BreakoutATH | `tradingview_E5_BreakoutATH.csv` | 4,633 | Breakout a máximo histórico |
| E3_PriceSpikeIntraday | `tradingview_E3_PriceSpikeIntraday.csv` | 1,901 | Spike de precio intradía |
| E4_Parabolic | `tradingview_E4_Parabolic.csv` | 1,265 | Movimiento parabólico |
| E11_VolumeBounce | `tradingview_E11_VolumeBounce.csv` | 1,256 | Rebote con volumen |
| E2_GapUp | `tradingview_E2_GapUp.csv` | 1,070 | Gap alcista |
| E8_GapDownViolent | `tradingview_E8_GapDownViolent.csv` | 455 | Gap bajista violento |
| E9_CrashIntraday | `tradingview_E9_CrashIntraday.csv` | 420 | Crash intradía |
| E7_FirstRedDay | `tradingview_E7_FirstRedDay.csv` | 233 | Primer día rojo tras subida |

**Ubicación**: `01_DayBook/fase_01/F_Event_detectors_E1_E11/notebooks/tradingview_exports/`

---

## 📋 FORMATO DE DATOS

Cada CSV contiene las siguientes columnas:

```csv
ticker,datetime,close_price,event_code,window_suggested,date
NAII,2004-01-08 14:27:42.000000,6.3,E10_FirstGreenBounce,"[-3,+3]",2004-01-08
GRIL,2004-01-12 15:34:16.000000,2.75,E10_FirstGreenBounce,"[-3,+3]",2004-01-12
```

### Columnas:

- **ticker**: Símbolo del activo (ej: AAPL, TSLA, NAII)
- **datetime**: Timestamp exacto del evento (fecha + hora del primer bar del día)
- **close_price**: Precio de cierre en el momento del evento
- **event_code**: Código del evento (E1-E11)
- **window_suggested**: Ventana óptima sugerida por análisis MI (ej: [-3,+3])
- **date**: Fecha del evento (sin hora)

---

## 🎯 CÓMO USAR EN TRADINGVIEW

### Método 1: Pine Script Custom Indicator (RECOMENDADO)

**Paso 1**: Crea un nuevo indicador Pine Script en TradingView

**Paso 2**: Copia y pega este código:

```pinescript
//@version=5
indicator("Event Markers - E10_FirstGreenBounce", overlay=true)

// INSTRUCCIONES:
// 1. Modifica la tabla CSV_DATA con los datos del evento que quieres visualizar
// 2. Copia las filas del CSV correspondiente (filtrando por ticker si es necesario)
// 3. El script dibujará triángulos verdes en los eventos

// Datos del evento (REEMPLAZAR con datos reales del CSV)
var table_data = array.new_string()

// Ejemplo de cómo parsear eventos (debes adaptarlo a tus eventos)
// Formato: "YYYY-MM-DD HH:MM:SS,PRICE"
array.push(table_data, "2004-01-08 14:27:42,6.3")
array.push(table_data, "2004-01-12 15:34:16,2.75")
// ... (añade más eventos aquí)

// Dibujar marcadores en los eventos
if barstate.islast
    for i = 0 to array.size(table_data) - 1
        event_str = array.get(table_data, i)
        // Parse timestamp y precio
        // (Necesitarás implementar parsing aquí)
        // label.new(...) para marcar el evento
```

### Método 2: Importación Manual (Para pocos eventos)

**Paso 1**: Filtra el CSV por ticker

```bash
# En terminal
cd 01_DayBook/fase_01/F_Event_detectors_E1_E11/notebooks/tradingview_exports/
grep "AAPL" tradingview_E10_FirstGreenBounce.csv > aapl_events.csv
```

**Paso 2**: Abre TradingView y carga el ticker (AAPL)

**Paso 3**: Marca manualmente los eventos usando "Drawing Tools" → "Vertical Line"

---

## 🔧 MÉTODO ALTERNATIVO: Python Script para Generar Pine Script

Usa este script Python para generar automáticamente el código Pine Script:

```python
import pandas as pd
from pathlib import Path

def generate_pine_script(csv_file: Path, ticker_filter: str = None):
    """
    Genera código Pine Script desde CSV de eventos.

    Args:
        csv_file: Path al CSV (ej: tradingview_E10_FirstGreenBounce.csv)
        ticker_filter: Filtrar por ticker específico (ej: "AAPL")
    """
    df = pd.read_csv(csv_file)

    # Filtrar por ticker si se especifica
    if ticker_filter:
        df = df[df['ticker'] == ticker_filter]

    event_code = df['event_code'].iloc[0]

    print(f"//@version=5")
    print(f"indicator(\"{event_code} - {ticker_filter or 'All Tickers'}\", overlay=true)")
    print()
    print("// Event timestamps")
    print("var event_times = array.new_int()")
    print()

    for idx, row in df.iterrows():
        ts = pd.Timestamp(row['datetime'])
        unix_ts = int(ts.timestamp())
        print(f"array.push(event_times, {unix_ts}000)  // {row['ticker']} - {row['datetime']}")

    print()
    print("// Draw markers")
    print("if barstate.islast")
    print("    for i = 0 to array.size(event_times) - 1")
    print("        event_time = array.get(event_times, i)")
    print("        if time == event_time")
    print("            label.new(bar_index, high, \"⭐\", ")
    print("                     style=label.style_label_down, ")
    print("                     color=color.green, ")
    print("                     textcolor=color.white)")


# Uso:
csv_path = Path("tradingview_exports/tradingview_E10_FirstGreenBounce.csv")
generate_pine_script(csv_path, ticker_filter="AAPL")
```

---

## 📈 EJEMPLO DE USO COMPLETO

### Caso: Visualizar E10_FirstGreenBounce en ticker NAII

**Paso 1**: Filtrar eventos del ticker

```bash
grep "NAII" tradingview_E10_FirstGreenBounce.csv | head -5
```

Salida:
```
NAII,2004-01-08 14:27:42.000000,6.3,E10_FirstGreenBounce,"[-3,+3]",2004-01-08
NAII,2005-03-10 14:39:01.000000,5.15,E10_FirstGreenBounce,"[-3,+3]",2005-03-10
...
```

**Paso 2**: Abrir TradingView con NAII (4H o Daily chart)

**Paso 3**: Buscar las fechas manualmente:
- 2004-01-08 → Marcar con línea vertical
- 2005-03-10 → Marcar con línea vertical

**Paso 4**: Verificar que el evento coincide con el patrón esperado

---

## 🎨 VENTANAS SUGERIDAS

Cada evento incluye la ventana óptima detectada por el análisis de Mutual Information:

| Evento | Ventana Sugerida | Significado |
|--------|------------------|-------------|
| E10_FirstGreenBounce | [-3, +3] | 3 días antes + 3 días después |
| E11_VolumeBounce | [-3, +3] | 3 días antes + 3 días después |
| E1_VolExplosion | [-3, +3] | 3 días antes + 3 días después |
| ... | ... | ... |

**Nota**: Phase 2 (LightGBM) sugiere que ventanas más pequeñas [0,0] o [1,1] tienen mejor performance económico.

---

## 📊 VALIDACIÓN RECOMENDADA

Para cada evento visualizado:

1. **Verificar patrón**: ¿El gráfico muestra el patrón esperado?
2. **Verificar ventana**: ¿La ventana [-3,+3] captura el movimiento?
3. **Comparar con Phase2**: ¿Ventanas más pequeñas funcionan mejor?
4. **Anotar observaciones**: Crear tabla con validación visual

Ejemplo de tabla de validación:

| Ticker | Fecha | Evento | Patrón Correcto? | Ventana Óptima Visual | Notas |
|--------|-------|--------|------------------|-----------------------|-------|
| NAII | 2004-01-08 | E10 | ✅ Sí | [0,1] | Rebote claro, día siguiente sube |
| GRIL | 2004-01-12 | E10 | ❌ No | - | Falso positivo |

---

## 🚀 PRÓXIMOS PASOS

1. **Validar 10-20 eventos** por tipo visualmente en TradingView
2. **Documentar falsos positivos** y patrones incorrectos
3. **Ajustar detectores** en `event_detectors.py` si es necesario
4. **Repetir análisis Phase1/Phase2** con detectores mejorados

---

## 📝 NOTAS TÉCNICAS

- **Timestamps exactos**: Corresponden al primer bar DIB del día del evento
- **Pilot50**: Datos de 50 tickers representativos (2004-2025)
- **Periodo**: 21 años de historia
- **Formato hora**: UTC (verificar timezone en TradingView)

---

## ❓ TROUBLESHOOTING

**Problema**: No veo el evento en la fecha indicada

**Soluciones**:
1. Verificar que el timeframe en TradingView sea Daily o inferior (4H, 1H)
2. Verificar timezone (CSV usa UTC)
3. El ticker puede no tener datos históricos en TradingView para esa fecha

**Problema**: Muchos falsos positivos

**Soluciones**:
1. Revisar lógica del detector en `event_detectors.py`
2. Ajustar thresholds (ej: vol_threshold, price_threshold)
3. Añadir filtros adicionales (market cap, spread, etc.)

---

**Última actualización**: 2025-10-30
**Generado por**: Phase1 Information Theory Notebook
**Total eventos exportados**: 44,189
