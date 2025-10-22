# Bloque B - OHLCV y Bar Construction

Descarga de datos de mercado (diario, intradía, trades) y construcción de barras avanzadas para small-caps.

---

## Componentes

### 1. Selección de Universo

**Script:** `select_universe_cs.py`

Filtra universo a Common Stocks de NASDAQ/NYSE. Excluye ARCX (principalmente ETFs).

```bash
python select_universe_cs.py \
  --snapdir raw/polygon/reference/tickers_snapshot/snapshot_date=2025-10-19 \
  --details raw/polygon/reference/ticker_details \
  --cap-max 2000000000 \
  --out-csv processed/universe/cs_xnas_xnys_under2b.csv
```

**Parámetros:**
- `--snapdir`: Snapshot de tickers (requerido)
- `--details`: Directorio de ticker details (opcional, para filtro market cap)
- `--cap-max`: Market cap máximo en USD (opcional)
- `--out-csv`: Archivo CSV de salida (requerido)
- `--out-parquet`: Archivo Parquet con metadatos (opcional)

**Output:** ~3,626 tickers CS de NASDAQ/NYSE con market cap < $2B

---

### 2. OHLCV Diario

**Script:** `ingest_ohlcv_daily.py`

Descarga barras diarias (1 day). 20+ años de historia disponible.

```bash
python ingest_ohlcv_daily.py \
  --tickers-csv processed/universe/cs_xnas_xnys_under2b.csv \
  --outdir raw/polygon/ohlcv_daily \
  --from 2004-01-01 --to 2025-10-20 \
  --max-workers 12
```

**Parámetros:**
- `--tickers-csv`: CSV con columna 'ticker'
- `--outdir`: Directorio de salida
- `--from`, `--to`: Rango de fechas (YYYY-MM-DD)
- `--max-workers`: Workers paralelos (default: 12)

**Output:** `ticker/year=YYYY/daily.parquet`

**Launcher:** `tools/launch_daily_smallcaps.py`

```bash
python tools/launch_daily_smallcaps.py start \
  --tickers-csv processed/universe/cs_xnas_xnys_under2b.csv \
  --outdir raw/polygon/ohlcv_daily \
  --from 2004-01-01 --to 2025-10-20 \
  --shards 12 --per-shard-workers 4 \
  --workdir runs/daily_2025-10-20 \
  --ingest-script scripts/fase_1_Bloque_B/ingest_ohlcv_daily.py

# Monitoreo
python tools/launch_daily_smallcaps.py status --workdir runs/daily_2025-10-20
python tools/launch_daily_smallcaps.py stop --workdir runs/daily_2025-10-20
```

---

### 3. OHLCV Intradía 1-minuto

**Script:** `ingest_ohlcv_intraday_minute.py`

Descarga barras de 1 minuto. 20+ años de historia (plan Advanced).

**Parámetros clave:**
- `--rate-limit`: Segundos entre páginas (default: 0.125)
- `--max-tickers-per-process`: Limita tickers por proceso antes de salir (para wrapper)

**Output:** `ticker/year=YYYY/month=MM/minute.parquet`

**Wrapper Micro-batches (RECOMENDADO):**

Usa el wrapper de micro-batches para descargas estables sin fugas de memoria:

```bash
export POLYGON_API_KEY=tu_api_key

python tools/batch_intraday_wrapper.py \
  --tickers-csv processed/universe/cs_xnas_xnys_under2b_2025-10-21.csv \
  --outdir raw/polygon/ohlcv_intraday_1m \
  --from 2004-01-01 --to 2010-12-31 \
  --batch-size 25 \
  --max-concurrent 6 \
  --rate-limit 0.20 \
  --ingest-script scripts/fase_1_Bloque_B/ingest_ohlcv_intraday_minute.py \
  --resume
```

**Ventajas del wrapper:**
- Procesos desechables que viven ~10-30 min (no horas)
- Libera RAM automáticamente al morir cada batch
- Reintentos automáticos (2 intentos por batch)
- Si falla un batch, solo pierdes 25 tickers (no cientos)
- Log separado por batch para diagnóstico fácil
- Control de concurrencia (solo N batches simultáneos)

**Ver:** [docs/wrapper_micro_batches_explicacion.md](../../docs/wrapper_micro_batches_explicacion.md) para detalles completos

**Parámetros wrapper:**
- `--batch-size`: Tickers por batch (default: 30, recomendado: 25)
- `--max-concurrent`: Batches paralelos (default: 6)
- `--resume`: Excluye tickers que ya tienen datos

---

### 4. Trades (tick-level)

**Script:** `ingest_trades_day.py`

Descarga trades individuales por día. Voluminoso - usar ventanas pequeñas para prototipar.

```bash
python ingest_trades_day.py \
  --tickers-csv processed/universe/top_100_runners.csv \
  --outdir raw/polygon/trades \
  --from 2024-01-01 --to 2024-12-31 \
  --max-workers 8
```

**Output:** `ticker/year=YYYY/month=MM/day=YYYY-MM-DD/trades.parquet`

**Campos:** `ticker`, `day`, `sip_ts` (timestamp), `price`, `size`

**Nota:** No necesitas todos los años de trades. Con 1-2 años tienes base suficiente para Bar Construction.

---

### 5. Bar Construction

**Script:** `build_bars.py`

Construye barras avanzadas desde trades tick-level.

**Tipos de barras:**
- **DB** (Dollar Bars): Cierra al acumular X dólares
- **VB** (Volume Bars): Cierra al acumular X volumen
- **DIB** (Dollar Imbalance Bars): Cierra por desequilibrio buy/sell en dólares
- **VIB** (Volume Imbalance Bars): Cierra por desequilibrio buy/sell en volumen

**Ejemplos:**

Dollar Bars:
```bash
python build_bars.py \
  --trades-root raw/polygon/trades \
  --ticker GPRO \
  --from 2024-01-01 --to 2024-12-31 \
  --outdir processed/bars \
  --mode DB --target 50000
```

Dollar Imbalance Bars:
```bash
python build_bars.py \
  --trades-root raw/polygon/trades \
  --ticker GPRO \
  --from 2024-01-01 --to 2024-12-31 \
  --outdir processed/bars \
  --mode DIB --target 50000 --alpha 0.2
```

Fallback desde 1m aggregates (si no hay trades):
```bash
python build_bars.py \
  --agg1m-root raw/polygon/ohlcv_intraday_1m \
  --ticker GPRO \
  --from 2024-01-01 --to 2024-12-31 \
  --outdir processed/bars \
  --mode VB --target 100000
```

**Parámetros:**

| Parámetro | Descripción | Default |
|-----------|-------------|---------|
| `--trades-root` | Directorio de trades | - |
| `--agg1m-root` | Directorio 1m (fallback) | - |
| `--ticker` | Ticker a procesar | - |
| `--from`, `--to` | Rango de fechas | - |
| `--outdir` | Directorio de salida | - |
| `--mode` | DB, VB, DIB, VIB | - |
| `--target` | USD o volumen objetivo | 50000 |
| `--alpha` | EWMA alpha (solo imbalance) | 0.2 |

**Output:** `ticker/[dollar|volume|dollar_imbalance|volume_imbalance]/year=YYYY/bars.parquet`

**Parámetros recomendados:**

Dollar Bars/DIB:
- Small-caps activos: `--target 50000` ($50K/barra)
- Small-caps menos líquidos: `--target 25000` ($25K/barra)

Volume Bars/VIB:
- Base: `0.5% * avg_daily_volume / bars_per_session`

Alpha (Imbalance):
- Agresivo: `0.15`
- Balanceado: `0.20` (default)
- Conservador: `0.30`

---

## Schema de Datos

### OHLCV Diario/Intradía

| Columna | Tipo | Descripción |
|---------|------|-------------|
| ticker | string | Símbolo |
| date | string | Fecha YYYY-MM-DD |
| minute | string | Timestamp YYYY-MM-DD HH:MM (solo intradía) |
| t | int64 | Timestamp Unix (ms) |
| o | float64 | Open |
| h | float64 | High |
| l | float64 | Low |
| c | float64 | Close |
| v | float64 | Volume |
| n | int64 | Number of transactions |
| vw | float64 | VWAP |

### Trades

| Columna | Tipo | Descripción |
|---------|------|-------------|
| ticker | string | Símbolo |
| day | string | Fecha YYYY-MM-DD |
| sip_ts | int64 | Timestamp Unix (ns) |
| price | float64 | Precio del trade |
| size | float64 | Tamaño del trade |

### Barras Construidas

| Columna | Tipo | Descripción |
|---------|------|-------------|
| t | int64 | Timestamp apertura barra (ns) |
| open | float64 | Precio apertura |
| high | float64 | Precio máximo |
| low | float64 | Precio mínimo |
| close | float64 | Precio cierre |
| v | float64 | Volumen total |
| dollar | float64 | Dólares totales |

---

## Notas Técnicas

### Paginación

Todos los scripts usan extracción correcta del cursor desde `next_url`. Evita el bug de truncamiento detectado en splits/dividends.

### Idempotencia

Todos los scripts son idempotentes. Pueden relanzarse sin problemas:
- Merge por `date` (diario)
- Merge por `minute` (intradía)
- Merge por `t` (barras)

### Rate Limiting

Plan Advanced: ~500 req/min práctico

Configuraciones recomendadas:
- Diario: 12 shards × 4 workers = 48 threads
- Intradía: 12 shards × 4 workers + rate-limit 0.125s

### Resume

Launchers soportan `--resume`:
- Excluye tickers con carpeta existente en outdir
- No requiere estado adicional
- Útil para continuar descargas interrumpidas

---

## Workflow Típico

```bash
# 1. Universo
python scripts/fase_1_Bloque_B/select_universe_cs.py \
  --snapdir raw/polygon/reference/tickers_snapshot/snapshot_date=2025-10-19 \
  --details raw/polygon/reference/ticker_details \
  --cap-max 2000000000 \
  --out-csv processed/universe/cs_xnas_xnys_under2b.csv

# 2. OHLCV Diario
python tools/launch_daily_smallcaps.py start \
  --tickers-csv processed/universe/cs_xnas_xnys_under2b.csv \
  --outdir raw/polygon/ohlcv_daily \
  --from 2004-01-01 --to 2025-10-20 \
  --shards 12 --per-shard-workers 4 \
  --workdir runs/daily_2025-10-20 \
  --ingest-script scripts/fase_1_Bloque_B/ingest_ohlcv_daily.py

# 3. OHLCV Intradía (con wrapper micro-batches)
export POLYGON_API_KEY=tu_api_key

python tools/batch_intraday_wrapper.py \
  --tickers-csv processed/universe/cs_xnas_xnys_under2b_2025-10-21.csv \
  --outdir raw/polygon/ohlcv_intraday_1m \
  --from 2004-01-01 --to 2010-12-31 \
  --batch-size 25 \
  --max-concurrent 6 \
  --rate-limit 0.20 \
  --ingest-script scripts/fase_1_Bloque_B/ingest_ohlcv_intraday_minute.py \
  --resume

# 4. Trades (subset para prototipar)
python scripts/fase_1_Bloque_B/ingest_trades_day.py \
  --tickers-csv processed/universe/top_100_runners.csv \
  --outdir raw/polygon/trades \
  --from 2024-01-01 --to 2024-12-31 \
  --max-workers 8

# 5. Barras
python scripts/fase_1_Bloque_B/build_bars.py \
  --trades-root raw/polygon/trades \
  --ticker GPRO \
  --from 2024-01-01 --to 2024-12-31 \
  --outdir processed/bars \
  --mode DIB --target 50000 --alpha 0.2
```

---

## Troubleshooting

### Error: POLYGON_API_KEY no establecida
```bash
export POLYGON_API_KEY="tu_api_key"
```

### Error 429 (Rate Limit)
- Aumentar `--rate-limit` (0.125 → 0.167 o 0.25)
- Reducir `--max-workers` o `--shards`

### Monitorear batches en ejecución
```bash
# Ver progreso del wrapper
tail -f raw/polygon/ohlcv_intraday_1m/_batch_temp/batch_0001.log

# Contar batches completados
ls raw/polygon/ohlcv_intraday_1m/_batch_temp/*.log | wc -l

# Ver últimas líneas de todos los logs
for log in raw/polygon/ohlcv_intraday_1m/_batch_temp/*.log; do
    echo "=== $log ==="
    tail -n 3 "$log"
done
```

### Relanzar con resume (completar faltantes)
```bash
export POLYGON_API_KEY=tu_api_key

python tools/batch_intraday_wrapper.py \
  --tickers-csv processed/universe/cs_xnas_xnys_under2b_2025-10-21.csv \
  --outdir raw/polygon/ohlcv_intraday_1m \
  --from 2004-01-01 --to 2010-12-31 \
  --batch-size 25 \
  --max-concurrent 6 \
  --rate-limit 0.20 \
  --ingest-script scripts/fase_1_Bloque_B/ingest_ohlcv_intraday_minute.py \
  --resume
```

### Errores SSL/TLS (Windows)
Si ves errores de certificados SSL, instala certifi en tu entorno virtual:
```bash
.venv-smallcap\Scripts\activate
pip install certifi
```

El ingestor ya está configurado para usar certifi automáticamente.

---

## Referencias

- Polygon.io API: https://polygon.io/docs/stocks
- López de Prado, Advances in Financial Machine Learning (2018)
- Bloque A: `../fase_1_Bloque_A/`
