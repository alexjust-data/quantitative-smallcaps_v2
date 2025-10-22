# launch_wrapper.ps1 - Launcher PRINCIPAL (universo completo) - OPTIMIZADO
# Descarga el universo completo con configuracion balanceada
# APROVECHA: Descarga mensual + ZSTD + Rate-limit adaptativo + TLS heredado

# Cargar .env
$envPath = "D:\04_TRADING_SMALLCAPS\.env"
if (Test-Path $envPath) {
    Get-Content $envPath | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+?)\s*=\s*(.+)\s*$') {
            $key = $matches[1].Trim()
            $val = $matches[2].Trim()
            [System.Environment]::SetEnvironmentVariable($key, $val, [System.EnvironmentVariableTarget]::Process)
        }
    }
}

# Verificar API KEY
$apiKey = [System.Environment]::GetEnvironmentVariable("POLYGON_API_KEY")
if (-not $apiKey -or $apiKey -eq "") {
    Write-Host "ERROR: POLYGON_API_KEY no configurada en .env" -ForegroundColor Red
    exit 1
}

Write-Host "OK - POLYGON_API_KEY configurada" -ForegroundColor Green
Write-Host ""

# Configuracion del WRAPPER PRINCIPAL (optimizada para universo completo)
# Configuracion BALANCEADA que funciona bien para mix de tickers normales + elefantes
$tickersCsv = "processed/universe/cs_xnas_xnys_under2b_2025-10-21.csv"
$outdir = "raw/polygon/ohlcv_intraday_1m"
$dateFrom = "2004-01-01"
$dateTo = "2025-10-21"

# CONFIGURACION BALANCEADA (optimizada con descarga mensual):
# - Batches moderados (20 tickers)
# - Concurrencia media (8 batches)
# - Rate limit balanceado (adaptativo ajustara segun necesidad)
$batchSize = 20          # Balance entre throughput y estabilidad
$maxConcurrent = 8       # Balance entre velocidad y recursos
$rateLimit = 0.22        # Balanceado (adaptativo: 0.12-0.35s)
$ingestScript = "scripts/fase_1_Bloque_B/ingest_ohlcv_intraday_minute.py"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  WRAPPER PRINCIPAL - OPTIMIZADO (Universo Completo)" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Configuracion:"
Write-Host "  Universo:        $tickersCsv (3,107 tickers)"
Write-Host "  Periodo:         $dateFrom -> $dateTo"
Write-Host "  Batch size:      $batchSize tickers/batch"
Write-Host "  Concurrencia:    $maxConcurrent batches simultaneos"
Write-Host "  Rate limit:      $rateLimit s/pag (adaptativo 0.12-0.35s)"
Write-Host "  PAGE_LIMIT:      50,000 rows/request (5x mejora)"
Write-Host "  Compresion:      ZSTD level 2"
Write-Host "  Descarga:        Por MESES (evita JSONs gigantes)"
Write-Host "  Resume:          Activado (excluye tickers con datos)"
Write-Host ""
Write-Host "Optimizaciones activas:"
Write-Host "  - Descarga mensual: JSON pequenos, menos RAM"
Write-Host "  - Rate-limit adaptativo: acelera/frena automaticamente"
Write-Host "  - PAGE_LIMIT 50K: reduce requests ~80%"
Write-Host "  - TLS heredado a subprocesos"
Write-Host "  - Compresion ZSTD: archivos 40-60% mas pequenos"
Write-Host ""
Write-Host "NOTA: Para dual-lane (normal/heavy separados), usar:"
Write-Host "  - launch_normal.ps1 (10 batches, agresivo)"
Write-Host "  - launch_heavy.ps1 (4 batches, conservador)"
Write-Host ""
Write-Host "Iniciando descarga..."
Write-Host ""

# Configurar SSL/TLS certs (heredado a subprocesos via env=env)
$cert = & python -c "import certifi; print(certifi.where())" 2>$null
if ($LASTEXITCODE -eq 0 -and $cert) {
    $env:SSL_CERT_FILE = $cert
    $env:REQUESTS_CA_BUNDLE = $cert
    Write-Host "SSL_CERT_FILE: $cert" -ForegroundColor Green
} else {
    Write-Host "Warning: certifi no encontrado, usando certs del sistema" -ForegroundColor Yellow
}
Write-Host ""

# Ejecutar wrapper Python
python scripts/fase_1_Bloque_B/tools/batch_intraday_wrapper.py `
  --tickers-csv $tickersCsv `
  --outdir $outdir `
  --from $dateFrom `
  --to $dateTo `
  --batch-size $batchSize `
  --max-concurrent $maxConcurrent `
  --rate-limit $rateLimit `
  --ingest-script $ingestScript `
  --resume

$exitCode = $LASTEXITCODE

Write-Host ""
Write-Host "============================================================" -ForegroundColor $(if ($exitCode -eq 0) {"Green"} else {"Red"})
if ($exitCode -eq 0) {
    Write-Host "  DESCARGA COMPLETA (exit code: $exitCode)" -ForegroundColor Green
} else {
    Write-Host "  DESCARGA TERMINO CON ERRORES (exit code: $exitCode)" -ForegroundColor Red
}
Write-Host "============================================================" -ForegroundColor $(if ($exitCode -eq 0) {"Green"} else {"Red"})
Write-Host ""
Write-Host "Logs de batches: $outdir\_batch_temp\"

exit $exitCode
