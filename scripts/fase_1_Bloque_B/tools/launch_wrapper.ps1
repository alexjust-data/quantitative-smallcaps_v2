# Script para lanzar el wrapper de descarga intradia
# Configura tu API key y lanza el proceso

# Leer API key del archivo de configuracion si existe
$apiKeyFile = "D:\04_TRADING_SMALLCAPS\.env"
if (Test-Path $apiKeyFile) {
    Get-Content $apiKeyFile | ForEach-Object {
        if ($_ -match '^POLYGON_API_KEY=(.+)$') {
            $env:POLYGON_API_KEY = $matches[1]
        }
    }
}

# Verificar que existe la API key
if (-not $env:POLYGON_API_KEY) {
    Write-Host "ERROR: POLYGON_API_KEY no esta configurada" -ForegroundColor Red
    Write-Host ""
    Write-Host "Por favor, crea un archivo .env con tu API key:" -ForegroundColor Yellow
    Write-Host "  POLYGON_API_KEY=tu_api_key_aqui"
    Write-Host ""
    Write-Host "O configurala manualmente:" -ForegroundColor Yellow
    Write-Host '  $env:POLYGON_API_KEY = "tu_api_key_aqui"' -ForegroundColor Cyan
    Write-Host ""
    exit 1
}

Write-Host "OK - POLYGON_API_KEY configurada" -ForegroundColor Green
Write-Host ""

# Configuracion del wrapper (DESATASCADA - evita "atasco de elefantes")
$tickersCsv = "processed/universe/cs_xnas_xnys_under2b_2025-10-21.csv"
$outdir = "raw/polygon/ohlcv_intraday_1m"
$dateFrom = "2004-01-01"
$dateTo = "2025-10-21"
$batchSize = 20
$maxConcurrent = 8
$rateLimit = 0.25
$ingestScript = "scripts/fase_1_Bloque_B/ingest_ohlcv_intraday_minute.py"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  WRAPPER MICRO-BATCHES - DESCARGA INTRADIA 1M" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Configuracion:" -ForegroundColor Yellow
Write-Host "  Universo:        $tickersCsv"
Write-Host "  Periodo:         $dateFrom -> $dateTo"
Write-Host "  Batch size:      $batchSize tickers/batch"
Write-Host "  Concurrencia:    $maxConcurrent batches simultaneos"
Write-Host "  Rate limit:      $rateLimit segundos entre paginas"
Write-Host "  Resume:          Activado (excluye tickers con datos)"
Write-Host ""
Write-Host "Iniciando descarga..." -ForegroundColor Green
Write-Host ""

# Lanzar wrapper
python "scripts/fase_1_Bloque_B/tools/batch_intraday_wrapper.py" --tickers-csv $tickersCsv --outdir $outdir --from $dateFrom --to $dateTo --batch-size $batchSize --max-concurrent $maxConcurrent --rate-limit $rateLimit --ingest-script $ingestScript --resume

# Capturar exit code
$exitCode = $LASTEXITCODE

if ($exitCode -eq 0) {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "  DESCARGA COMPLETADA EXITOSAMENTE" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Red
    Write-Host "  DESCARGA TERMINO CON ERRORES (exit code: $exitCode)" -ForegroundColor Red
    Write-Host "============================================================" -ForegroundColor Red
}

exit $exitCode
