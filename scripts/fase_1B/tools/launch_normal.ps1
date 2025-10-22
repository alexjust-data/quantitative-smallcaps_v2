# launch_normal.ps1 - Carril NORMAL (tickers rapidos) - OPTIMIZADO
# Descarga tickers normales (sin elefantes) con configuracion optimizada
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

# Configuracion del CARRIL NORMAL (optimizada para tickers rapidos)
# Con descarga mensual podemos ser MAS AGRESIVOS sin romper nada
$tickersCsv = "processed/reports/normal_tickers.csv"
$outdir = "raw/polygon/ohlcv_intraday_1m"
$dateFrom = "2004-01-01"
$dateTo = "2025-10-21"

# CONFIGURACION OPTIMIZADA para tickers normales:
# - Mas batches concurrentes (10 vs 8)
# - Rate limit inicial mas bajo (el adaptativo lo ajustara)
# - Batches medianos (15 tickers) para velocidad sin saturar
$batchSize = 15          # Reducido para mayor throughput
$maxConcurrent = 10      # Aumentado gracias a descarga mensual
$rateLimit = 0.18        # Mas agresivo (adaptativo: 0.12-0.35s)
$ingestScript = "scripts/fase_1_Bloque_B/ingest_ohlcv_intraday_minute.py"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  CARRIL NORMAL - OPTIMIZADO (Mensual + ZSTD + RL Adaptativo)" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Configuracion:"
Write-Host "  Universo:        $tickersCsv"
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
Write-Host "  - Descarga mensual reduce pico de RAM"
Write-Host "  - Rate-limit adaptativo acelera si puede"
Write-Host "  - PAGE_LIMIT 50K reduce requests ~80%"
Write-Host "  - TLS heredado a subprocesos"
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
    Write-Host "  CARRIL NORMAL COMPLETO (exit code: $exitCode)" -ForegroundColor Green
} else {
    Write-Host "  CARRIL NORMAL TERMINO CON ERRORES (exit code: $exitCode)" -ForegroundColor Red
}
Write-Host "============================================================" -ForegroundColor $(if ($exitCode -eq 0) {"Green"} else {"Red"})

exit $exitCode
