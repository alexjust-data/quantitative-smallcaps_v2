# launch_heavy.ps1 - Carril PESADO (elefantes) - OPTIMIZADO
# Descarga tickers elefantes con configuracion conservadora pero optimizada
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

# Configuracion del CARRIL PESADO (optimizada para elefantes)
# Con descarga mensual los elefantes NO colapsan el sistema
$tickersCsv = "processed/reports/heavy_tickers.csv"
$outdir = "raw/polygon/ohlcv_intraday_1m"
$dateFrom = "2004-01-01"
$dateTo = "2025-10-21"

# CONFIGURACION CONSERVADORA pero OPTIMIZADA para elefantes:
# - Menos batches concurrentes (4 vs 10)
# - Rate limit mas alto (mas conservador)
# - Batches pequenos (10 tickers) para evitar saturacion
# PERO: Descarga mensual permite manejar elefantes sin problemas
$batchSize = 10          # Pequeno para evitar multiples elefantes simultaneos
$maxConcurrent = 4       # Conservador (4 batches a la vez)
$rateLimit = 0.28        # Mas lento (adaptativo: 0.12-0.35s)
$ingestScript = "scripts/fase_1_Bloque_B/ingest_ohlcv_intraday_minute.py"

Write-Host "============================================================" -ForegroundColor DarkYellow
Write-Host "  CARRIL PESADO - OPTIMIZADO (Elefantes bajo control)" -ForegroundColor DarkYellow
Write-Host "============================================================" -ForegroundColor DarkYellow
Write-Host ""
Write-Host "Configuracion:"
Write-Host "  Universo:        $tickersCsv (95 elefantes)"
Write-Host "  Periodo:         $dateFrom -> $dateTo"
Write-Host "  Batch size:      $batchSize tickers/batch (pequeno)"
Write-Host "  Concurrencia:    $maxConcurrent batches simultaneos (conservador)"
Write-Host "  Rate limit:      $rateLimit s/pag (adaptativo 0.12-0.35s)"
Write-Host "  PAGE_LIMIT:      50,000 rows/request"
Write-Host "  Compresion:      ZSTD level 2"
Write-Host "  Descarga:        Por MESES (CLAVE para elefantes)"
Write-Host "  Resume:          Activado (excluye tickers con datos)"
Write-Host ""
Write-Host "Optimizaciones para elefantes:"
Write-Host "  - Descarga mensual EVITA JSONs gigantes (20GB -> 500MB por mes)"
Write-Host "  - Rate-limit adaptativo se frena si detecta problemas"
Write-Host "  - PAGE_LIMIT 50K funciona bien por mes"
Write-Host "  - TLS heredado a subprocesos"
Write-Host "  - Batches pequenos evitan saturar CPU/RAM"
Write-Host ""
Write-Host "Iniciando descarga de elefantes..."
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
    Write-Host "  CARRIL PESADO COMPLETO (exit code: $exitCode)" -ForegroundColor Green
} else {
    Write-Host "  CARRIL PESADO TERMINO CON ERRORES (exit code: $exitCode)" -ForegroundColor Red
}
Write-Host "============================================================" -ForegroundColor $(if ($exitCode -eq 0) {"Green"} else {"Red"})

exit $exitCode
