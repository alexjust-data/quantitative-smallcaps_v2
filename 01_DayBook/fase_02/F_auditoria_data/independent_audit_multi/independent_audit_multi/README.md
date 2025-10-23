# Independent Data Audit — Multi‑Vendor

Verifica tu dataset de forma independiente comparándolo con múltiples proveedores:
- Polygon (1‑min)
- IEX Cloud (1‑min, token)
- Finnhub (1‑min, token)
- CSV genérico (por ejemplo, agregados desde TAQ/SIP/WRDS que hayas preparado)

No depende de tu suite interna. Produce un JSON con métricas por proveedor y un Markdown legible.

## Instalación
```bash
python -m venv .venv
. .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Variables de entorno (según vendor)
- POLYGON_API_KEY=...
- IEX_API_TOKEN=...
- FINNHUB_API_KEY=...

## Ejecutar (ejemplos)

### 1) Comparación doble: Polygon + IEX (contra tus minute bars)
```bash
python verify_against_references.py   --symbols AMC,AAPL   --dates 2024-05-17   --vendors polygon,iex   --our-minute-root "D:/04_TRADING_SMALLCAPS/processed/minute"   --out reports/report_multi_minute.json
```

### 2) Comparación triple: Polygon + Finnhub + CSV (TAQ agregado propio)
```bash
python verify_against_references.py   --symbols AMC   --dates 2024-05-17   --vendors polygon,finnhub,csv   --csv-root "D:/references/taq_minute"   --our-dib-root "D:/04_TRADING_SMALLCAPS/processed/bars"   --out reports/report_multi_from_dib.json
```

### 3) Informe Markdown
```bash
python make_report_md.py   --input reports/report_multi_minute.json   --output reports/INDEPENDENT_DATA_REPORT.md   --title "Independent Verification vs Multiple Vendors"
```

## Notas
- Tiempos en UTC. El comparador alinea por minuto.
- Tolerancias por defecto: precio 0.2%, volumen 5% (configurables).
- IEX/Finnhub requieren claves de API (free tiers existen, con límites).
- El vendor `csv` lee archivos locales `symbol/date=YYYY-MM-DD/minute.csv` con columnas `t,open,high,low,close,volume`.
