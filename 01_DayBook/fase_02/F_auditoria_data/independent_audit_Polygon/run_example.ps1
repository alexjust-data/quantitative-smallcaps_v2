$env:POLYGON_API_KEY="REPLACE_WITH_YOUR_KEY"
$ROOT="D:/04_TRADING_SMALLCAPS"

python verify_against_reference.py `
  --symbols AMC `
  --dates 2024-05-17 `
  --vendor polygon `
  --our-minute-root "$ROOT/processed/minute" `
  --out "reports/report_polygon_minute.json"

python make_report_md.py `
  --input "reports/report_polygon_minute.json" `
  --output "reports/INDEPENDENT_DATA_REPORT.md" `
  --title "Independent Verification vs Polygon (Minute)"
