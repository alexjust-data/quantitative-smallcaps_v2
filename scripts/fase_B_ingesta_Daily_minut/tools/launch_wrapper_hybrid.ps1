# launch_wrapper_hybrid.ps1
# Launcher para descarga intradía 1m - Config OPTIMIZADA probada en Fase B
# Usa el wrapper micro-batches con las optimizaciones que resolvieron el problema de elefantes

Write-Host "============================================================"
Write-Host "  WRAPPER INTRADAY 1M - CONFIG OPTIMIZADA (Universo Híbrido)"
Write-Host "============================================================"
Write-Host ""

# Cargar API key desde .env
$envPath = "D:\04_TRADING_SMALLCAPS\.env"
if (Test-Path $envPath) {
    Get-Content $envPath | ForEach-Object {
        if ($_ -match '^\s*POLYGON_API_KEY\s*=\s*(.+)$') {
            $env:POLYGON_API_KEY = $matches[1].Trim()
        }
    }
}

if (-not $env:POLYGON_API_KEY) {
    Write-Host "ERROR: POLYGON_API_KEY no encontrada en .env" -ForegroundColor Red
    exit 1
}

# Configuración OPTIMIZADA (basada en éxitos de Fase B)
$tickersCsv = "processed\universe\cs_xnas_xnys_hybrid_2025-10-24.csv"  # 8,686 tickers
$outdir = "raw\polygon\ohlcv_intraday_1m"
$dateFrom = "2004-01-01"
$dateTo = "2025-10-24"

# Config OPTIMIZADA - Probada exitosamente en Fase B
$batchSize = 20           # Tickers por batch (balance)
$maxConcurrent = 8        # Batches simultáneos (balance)
$rateLimit = 0.22         # Adaptativo 0.12-0.35s

$ingestScript = "scripts\fase_B_ingesta_Daily_minut\ingest_ohlcv_intraday_minute.py"
$wrapperScript = "scripts\fase_B_ingesta_Daily_minut\tools\batch_intraday_wrapper.py"

Write-Host "Configuración:"
Write-Host "  Universo:        $tickersCsv"
Write-Host "  Output:          $outdir"
Write-Host "  Período:         $dateFrom -> $dateTo"
Write-Host "  Batch size:      $batchSize tickers/batch"
Write-Host "  Concurrencia:    $maxConcurrent batches simultáneos"
Write-Host "  Rate limit:      $rateLimit s/página (adaptativo 0.12-0.35s)"
Write-Host "  PAGE_LIMIT:      50,000 rows/request (5x optimización)"
Write-Host "  Compresión:      ZSTD level 2"
Write-Host "  Descarga:        Por MESES (evita JSONs gigantes)"
Write-Host ""

Write-Host "Optimizaciones activas (éxitos Fase B):"
Write-Host "  - Descarga mensual: JSON pequeños, menos RAM"
Write-Host "  - Rate-limit adaptativo: acelera/frena automáticamente"
Write-Host "  - PAGE_LIMIT 50K: reduce requests ~80%"
Write-Host "  - TLS heredado a subprocesos"
Write-Host "  - Compresión ZSTD: archivos 40-60% más pequeños"
Write-Host "  - Resume inteligente: salta tickers ya descargados"
Write-Host ""

$logFile = "logs\intraday_wrapper_optimized_$(Get-Date -Format 'yyyyMMdd_HHmmss').log"

Write-Host "Lanzando wrapper en background..."
Write-Host "Log: $logFile"
Write-Host ""

# Lanzar wrapper con PowerShell Start-Process para mejor control
$cmd = "python"
$arguments = @(
    $wrapperScript,
    "--tickers-csv", $tickersCsv,
    "--outdir", $outdir,
    "--from", $dateFrom,
    "--to", $dateTo,
    "--batch-size", $batchSize,
    "--max-concurrent", $maxConcurrent,
    "--rate-limit", $rateLimit,
    "--ingest-script", $ingestScript,
    "--resume"
)

# Lanzar en background
$process = Start-Process -FilePath $cmd -ArgumentList $arguments -NoNewWindow -PassThru -RedirectStandardOutput $logFile -RedirectStandardError "${logFile}.err"

Write-Host "✓ Wrapper lanzado exitosamente" -ForegroundColor Green
Write-Host "  PID: $($process.Id)"
Write-Host ""
Write-Host "Monitoreo:"
Write-Host "  tail -f $logFile"
Write-Host "  Get-Process -Id $($process.Id)"
Write-Host ""
Write-Host "Estado:"
Write-Host "  (Get-ChildItem '$outdir' -Directory -Exclude '_batch_temp').Count"
Write-Host ""
Write-Host "Velocidad esperada: aproximadamente 297 tickers por hora (medida en Fase B)"
Write-Host "Tickers pendientes: aproximadamente 5579 de 8686 total (3107 ya descargados)"
Write-Host "ETA: aproximadamente 19 horas"
Write-Host ""
Write-Host "El wrapper lanzara 8 batches simultaneos de 20 tickers cada uno."
Write-Host "Cada batch es un proceso independiente que descarga secuencialmente."
Write-Host ""
