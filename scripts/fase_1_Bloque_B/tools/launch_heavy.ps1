# launch_heavy.ps1 - Carril PESADO (elefantes)
# Descarga tickers pesados (elefantes) con configuracion conservadora

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

# Configuracion del CARRIL PESADO (elefantes)
$tickersCsv = "processed/reports/heavy_tickers.csv"
$outdir = "raw/polygon/ohlcv_intraday_1m"
$dateFrom = "2004-01-01"
$dateTo = "2025-10-21"
$batchSize = 10
$maxConcurrent = 2
$rateLimit = 0.30
$ingestScript = "scripts/fase_1_Bloque_B/ingest_ohlcv_intraday_minute.py"

Write-Host "============================================================" -ForegroundColor Magenta
Write-Host "  CARRIL PESADO - ELEFANTES (95 tickers)" -ForegroundColor Magenta
Write-Host "============================================================" -ForegroundColor Magenta
Write-Host ""
Write-Host "Configuracion:"
Write-Host "  Universo:        $tickersCsv"
Write-Host "  Periodo:         $dateFrom -> $dateTo"
Write-Host "  Batch size:      $batchSize tickers/batch"
Write-Host "  Concurrencia:    $maxConcurrent batches simultaneos"
Write-Host "  Rate limit:      $rateLimit segundos entre paginas"
Write-Host "  Resume:          Activado (excluye tickers con datos)"
Write-Host ""
Write-Host "Iniciando descarga..."
Write-Host ""

# Configurar SSL/TLS certs
$cert = & python -c "import certifi; print(certifi.where())"
$env:SSL_CERT_FILE = $cert
$env:REQUESTS_CA_BUNDLE = $cert

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

exit $exitCode
