Write-Host '================================================' -ForegroundColor Cyan
Write-Host '  AUDITORIA POST-OPTIMIZACIONES' -ForegroundColor Cyan
Write-Host '  Fecha: ' -NoNewline; Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
Write-Host '================================================' -ForegroundColor Cyan
Write-Host ''

# 1. Progreso de tickers
Write-Host '=== PROGRESO DE TICKERS ===' -ForegroundColor Yellow
$tickersAhora = (Get-ChildItem 'raw\polygon\ohlcv_intraday_1m' -Directory -Exclude '_batch_temp').Count
Write-Host "Tickers descargados: $tickersAhora / 3,107"
$pct = [math]::Round(($tickersAhora / 3107) * 100, 2)
Write-Host "Porcentaje completado: $pct%"
Write-Host "Pendientes: $(3107 - $tickersAhora)"
Write-Host ''

# 2. Comparativa con inicio de sesion
Write-Host '=== COMPARATIVA SESION ===' -ForegroundColor Yellow
Write-Host 'Inicio sesion (antes optimizaciones): 330 tickers'
Write-Host "Ahora (con optimizaciones): $tickersAhora tickers"
$ganancia = $tickersAhora - 330
Write-Host "Ganancia total: +$ganancia tickers"
Write-Host ''

# 3. Comparativa optimizaciones
Write-Host '=== IMPACTO OPTIMIZACIONES ===' -ForegroundColor Yellow
Write-Host 'Antes de aplicar patches (22:56): 352 tickers'
Write-Host 'Despues de relanzar optimizado (23:03): 417 tickers'
Write-Host "Ahora: $tickersAhora tickers"
$gananciaOptimizado = $tickersAhora - 417
$inicioOptimizado = Get-Date '2025-10-21 23:03:40'
$minutos = [math]::Round(((Get-Date) - $inicioOptimizado).TotalMinutes, 1)
Write-Host "Ganancia desde lanzamiento optimizado: +$gananciaOptimizado tickers en $minutos min"
if ($minutos -gt 0) {
    $velocidad = [math]::Round(($gananciaOptimizado / $minutos) * 60, 1)
    Write-Host "Velocidad estimada: $velocidad tickers/hora"
}
Write-Host ''

# 4. Procesos activos
Write-Host '=== PROCESOS ACTIVOS ===' -ForegroundColor Yellow
$pythonProcs = Get-Process python -ErrorAction SilentlyContinue
if ($pythonProcs) {
    Write-Host "Procesos Python: $($pythonProcs.Count)"
    Write-Host 'Configuracion esperada: 9 (1 wrapper + 8 batches)'
} else {
    Write-Host 'ALERTA: No hay procesos Python corriendo!' -ForegroundColor Red
}
Write-Host ''

# 5. Archivos recientes
Write-Host '=== ACTIVIDAD RECIENTE ===' -ForegroundColor Yellow
Write-Host 'Ultimos 5 tickers modificados:'
Get-ChildItem 'raw\polygon\ohlcv_intraday_1m' -Directory -Exclude '_batch_temp' |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 5 |
    ForEach-Object {
        $diff = [math]::Round(((Get-Date) - $_.LastWriteTime).TotalMinutes, 1)
        Write-Host "  $($_.Name) - hace $diff minutos"
    }
Write-Host ''

# 6. Proyeccion
Write-Host '=== PROYECCION DE COMPLETADO ===' -ForegroundColor Yellow
if ($minutos -gt 0 -and $gananciaOptimizado -gt 0) {
    $velocidad = ($gananciaOptimizado / $minutos) * 60
    $pendientes = 3107 - $tickersAhora
    $horasRestantes = $pendientes / $velocidad
    $velocidadStr = [math]::Round($velocidad, 1)
    Write-Host "Velocidad actual: $velocidadStr t/h"
    Write-Host "Tickers pendientes: $pendientes"
    $horasStr = [math]::Round($horasRestantes, 1)
    Write-Host "Tiempo estimado restante: $horasStr horas"
    $eta = (Get-Date).AddHours($horasRestantes)
    Write-Host "ETA completado: $($eta.ToString('yyyy-MM-dd HH:mm'))"
}
Write-Host ''

Write-Host '================================================' -ForegroundColor Cyan
