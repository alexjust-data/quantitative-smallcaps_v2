@echo off
REM launch_wrapper_hybrid.cmd
REM Launcher CMD para descarga intraday - Config OPTIMIZADA probada en Fase B

echo ============================================================
echo   WRAPPER INTRADAY 1M - CONFIG OPTIMIZADA (Universo Hibrido)
echo ============================================================
echo.

cd /d D:\04_TRADING_SMALLCAPS

REM Cargar API key desde .env
for /f "tokens=1,2 delims==" %%a in ('findstr /r "^POLYGON_API_KEY=" .env') do set %%a=%%b

if "%POLYGON_API_KEY%"=="" (
    echo ERROR: POLYGON_API_KEY no encontrada en .env
    pause
    exit /b 1
)

REM Configuracion OPTIMIZADA
set TICKERS_CSV=processed\universe\cs_xnas_xnys_hybrid_2025-10-24.csv
set OUTDIR=raw\polygon\ohlcv_intraday_1m
set DATE_FROM=2004-01-01
set DATE_TO=2025-10-24
set BATCH_SIZE=20
set MAX_CONCURRENT=8
set RATE_LIMIT=0.22
set INGEST_SCRIPT=scripts\fase_B_ingesta_Daily_minut\ingest_ohlcv_intraday_minute.py
set WRAPPER_SCRIPT=scripts\fase_B_ingesta_Daily_minut\tools\batch_intraday_wrapper.py

echo Configuracion:
echo   Universo:        %TICKERS_CSV%
echo   Output:          %OUTDIR%
echo   Periodo:         %DATE_FROM% - %DATE_TO%
echo   Batch size:      %BATCH_SIZE% tickers/batch
echo   Concurrencia:    %MAX_CONCURRENT% batches simultaneos
echo   Rate limit:      %RATE_LIMIT% s/pagina (adaptativo 0.12-0.35s)
echo.
echo Optimizaciones activas (exitos Fase B):
echo   - Descarga mensual (JSON pequenos, menos RAM)
echo   - Rate-limit adaptativo
echo   - PAGE_LIMIT 50K (reduce requests 80%%)
echo   - TLS heredado a subprocesos
echo   - Compresion ZSTD (archivos 40-60%% mas pequenos)
echo   - Resume inteligente (salta tickers ya descargados)
echo.
echo Lanzando wrapper...
echo.

REM Crear directorio de logs si no existe
if not exist logs mkdir logs

REM Generar nombre de log con timestamp
for /f "tokens=2 delims==" %%a in ('wmic OS Get localdatetime /value') do set "dt=%%a"
set "YY=%dt:~2,2%" & set "YYYY=%dt:~0,4%" & set "MM=%dt:~4,2%" & set "DD=%dt:~6,2%"
set "HH=%dt:~8,2%" & set "Min=%dt:~10,2%" & set "Sec=%dt:~12,2%"
set "timestamp=%YYYY%%MM%%DD%_%HH%%Min%%Sec%"

set LOG_FILE=logs\intraday_wrapper_optimized_%timestamp%.log

REM Lanzar wrapper
python %WRAPPER_SCRIPT% --tickers-csv %TICKERS_CSV% --outdir %OUTDIR% --from %DATE_FROM% --to %DATE_TO% --batch-size %BATCH_SIZE% --max-concurrent %MAX_CONCURRENT% --rate-limit %RATE_LIMIT% --ingest-script %INGEST_SCRIPT% --resume > %LOG_FILE% 2>&1

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================
    echo   WRAPPER COMPLETADO EXITOSAMENTE
    echo ========================================
    echo.
    echo Log: %LOG_FILE%
    echo.
) else (
    echo.
    echo ========================================
    echo   WRAPPER TERMINO CON ERRORES
    echo ========================================
    echo.
    echo Log: %LOG_FILE%
    echo Error code: %ERRORLEVEL%
    echo.
)

echo Presiona cualquier tecla para salir...
pause > nul
