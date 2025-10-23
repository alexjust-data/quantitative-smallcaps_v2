# Independent Data Audit (SmallCaps)

This package verifies your dataset independently, by downloading reference data from an external vendor (e.g., Polygon) and comparing it with your own bars (minute or DIB-aggregated-to-minute). It does not depend on your internal certification suite.

## What it checks
- Minute-by-minute alignment of OHLCV between your data and a reference feed
- Absolute relative differences for price and volume
- Match rates and a list of outliers ("breaks") for investigation
- Markdown report you can publish as an independent audit

## Install
```bash
python -m venv .venv
. .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Quick start (Polygon vendor)
1) Export an environment variable with your key:
   - Linux/Mac: `export POLYGON_API_KEY=XXXX`
   - Windows PowerShell: `$env:POLYGON_API_KEY="XXXX"`

2) Run the verifier. Example comparing your minute bars:
```bash
python verify_against_reference.py   --symbols AMC,AAPL   --dates 2024-05-17,2024-05-20   --vendor polygon   --our-minute-root "D:/04_TRADING_SMALLCAPS/processed/minute"   --out reports/report_polygon_minute.json
```

3) Or, if you only have DIB bars, aggregate them to minute on-the-fly:
```bash
python verify_against_reference.py   --symbols AMC   --dates 2024-05-17   --vendor polygon   --our-dib-root "D:/04_TRADING_SMALLCAPS/processed/bars"   --out reports/report_polygon_from_dib.json
```

4) Produce a Markdown report:
```bash
python make_report_md.py   --input reports/report_polygon_minute.json   --output reports/INDEPENDENT_DATA_REPORT.md   --title "Independent Verification vs Polygon (Minute)"
```

Open the Markdown in VSCode/GitHub to read it clearly.

## Notes
- Times are handled in UTC by default; the script aligns vendor and your data consistently.
- Default tolerances: price 0.2%, volume 5%.
- You can switch vendor stubs or extend to IEX/Tiingo by adding vendor clients in `vendors/`.
