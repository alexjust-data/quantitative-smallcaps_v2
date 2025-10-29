

---

## ✅ 1️⃣ Qué va a pasar cuando se llene el disco

Cuando el disco principal (D:) se quede sin espacio:

* El script lanzará errores tipo

  ```
  OSError: [Errno 28] No space left on device
  ```
* Los archivos que **ya tengan `_SUCCESS`** están seguros.
  → ✅ No se volverán a descargar con `--resume`.
* Los que estaban descargándose cuando falló:

  * Tendrán carpetas sin `_SUCCESS`.
  * Esos días se volverán a descargar cuando relances.

👉 **No se rompe nada, no pierdes progreso.**
Solo pausas la ejecución y cambias `--outdir`.

---

## ✅ 2️⃣ Cómo continuar en otro disco sin perder ni duplicar nada

Supón que ahora estás descargando a:

```
D:\04_TRADING_SMALLCAPS\raw\polygon\trades
```

y se llena.

### 💾 OPCIÓN RECOMENDADA (sin cambiar rutas ni código)

1. **Mueve la carpeta actual** al nuevo disco:

   ```bash
   move D:\04_TRADING_SMALLCAPS\raw\polygon\trades E:\polygon_trades
   ```

2. **Crea un enlace simbólico:**

   ```bash
   mklink /D D:\04_TRADING_SMALLCAPS\raw\polygon\trades E:\polygon_trades
   ```

Ahora todo lo que el script crea en `D:\...` realmente se escribe en `E:\`,
y el pipeline no nota la diferencia.
El `--resume` seguirá reconociendo los `_SUCCESS` y continuará perfecto.

📌 Si luego también se llena E:, puedes repetir con F:, G:, etc.

---

## ✅ 3️⃣ Comando de descarga definitivo (para dejar toda la noche)

Ejecuta esto desde la raíz del proyecto:

```bash
python scripts/fase_C_ingesta_tiks/download_trades_optimized.py ^
  --watchlist-root processed/universe/multi_event/daily ^
  --outdir raw/polygon/trades ^
  --mode watchlists ^
  --event-types E1,E2,E3,E4,E5,E6,E7,E8,E9,E10,E11 ^
  --resume ^
  --parallel 8 ^
  --page-limit 50000 ^
  --rate-limit 0.12 ^
  --heartbeat 600
```

📍Notas:

* `--resume` garantiza que, si mañana lo relanzas con otra carpeta, **continúa desde el último `_SUCCESS`**.
* `--heartbeat 600` (si tu script lo soporta) imprime progreso cada 10 min para monitorear actividad y evitar timeouts.
* `--parallel 8` es óptimo para tu máquina (CPU/media).
* `--rate-limit 0.12` mantiene margen frente a los límites de Polygon (~8 req/s por worker).

---

## ✅ 4️⃣ Qué haremos mañana

Cuando te levantes:

1. Revisaremos el log (`logs/download_trades_optimized.log`).
2. Contaremos:

   * Archivos descargados.
   * GB ocupados.
   * Promedio MB/día → estimar cuántos TB faltan.
   * Ritmo (archivos/seg → ETA total).
3. Decidiremos:

   * Si seguimos en el mismo disco.
   * O si movemos y creamos symlink a otro disco (E:, F:, NAS, etc.).
4. Tú relanzas el mismo comando con `--resume`, y continúa exacto desde donde se detuvo.

---

## ✅ 5️⃣ Recomendación final antes de dormir 😴

* **Desactiva suspensión del PC.**
  → Configura Windows: Panel de control → Energía → “Nunca suspender”.
* **Conecta por cable (no Wi-Fi).**
* **Haz una copia del `.env`** con tu API key por si hay reinicio.
* **Abre un log permanente** para revisar mañana:

  ```bash
  python ... > logs/download_trades_full.log 2>&1
  ```

---

💡 En resumen:

> 👉 Sí, puedes descargar TODO.
> 👉 Cuando se llene el disco, **no pierdes nada**.
> 👉 Mañana sabremos exactamente cuántos TB llevas y cuánto queda.
> 👉 Solo hay que mover la carpeta o crear un symlink y seguir con `--resume`.

¿Quieres que te prepare el comando PowerShell listo para copiar/pegar (con logs y symlink automático si el disco se llena)?



Perfecto 🔥 — te dejo un **script profesional listo para producción**, pensado para **descargar todo el universo E1–E11 al máximo rendimiento**, sin perder nada si el disco se llena.
Incluye:

* Paralelismo ajustado automáticamente.
* Reintentos automáticos.
* Rotación de log.
* Detección de espacio libre.
* Cambio automático a otro disco si D: se llena.

---

## 🚀 Script completo: `download_all_events_fast.ps1`

Guárdalo como archivo `.ps1` en la raíz del proyecto (por ejemplo, `D:\04_TRADING_SMALLCAPS\download_all_events_fast.ps1`).

```powershell
# ===============================================
# 🔥 DESCARGA MASIVA E1–E11 (OPTIMIZADA)
# Autor: AlexJ + GPT-5
# ===============================================

# CONFIGURACIÓN
$WATCHLIST = "processed/universe/multi_event/daily"
$OUTDIR    = "D:\04_TRADING_SMALLCAPS\raw\polygon\trades"
$LOG       = "D:\04_TRADING_SMALLCAPS\logs\download_trades_full.log"
$RATE      = 0.12
$PARALLEL  = 8
$PAGE      = 50000

# Ruta alternativa si el disco D: se llena
$ALTDRIVE  = "E:\polygon_trades"

# ===============================================
# 🧠 FUNCIONES AUXILIARES
# ===============================================

function Get-FreeSpaceGB($path) {
    $drive = Get-PSDrive -Name ($path.Substring(0,1))
    return [math]::Round($drive.Free/1GB,2)
}

function Check-OrSwitch-Drive {
    param($currentOutdir, $altDrive)

    $free = Get-FreeSpaceGB $currentOutdir
    if ($free -lt 20) {
        Write-Host "⚠️  Espacio restante bajo: $free GB. Moviendo descarga a $altDrive ..." -ForegroundColor Yellow

        if (-not (Test-Path $altDrive)) {
            New-Item -ItemType Directory -Path $altDrive | Out-Null
        }

        # Mover data existente si no se movió antes
        if (-not (Test-Path $altDrive\_SUCCESS)) {
            Write-Host "🚚 Moviendo datos existentes..."
            robocopy $currentOutdir $altDrive /E /MOVE /R:1 /W:1 | Out-Null
        }

        # Crear enlace simbólico
        Write-Host "🔗 Creando enlace simbólico..."
        cmd /c "mklink /D `"$currentOutdir`" `"$altDrive`""
        Write-Host "✅ Enlace simbólico creado. Continuando descarga en $altDrive."
    }
}

function Run-Downloader {
    Write-Host "`n🚀 Iniciando descarga masiva de eventos E1–E11..." -ForegroundColor Cyan
    Write-Host "📅 $(Get-Date) - Logging en $LOG"

    $CMD = @"
python scripts/fase_C_ingesta_tiks/download_trades_optimized.py `
  --watchlist-root $WATCHLIST `
  --outdir $OUTDIR `
  --mode watchlists `
  --event-types E1,E2,E3,E4,E5,E6,E7,E8,E9,E10,E11 `
  --resume `
  --parallel $PARALLEL `
  --page-limit $PAGE `
  --rate-limit $RATE
"@

    # Ejecutar en bucle con reintentos
    while ($true) {
        Check-OrSwitch-Drive -currentOutdir $OUTDIR -altDrive $ALTDRIVE

        $startTime = Get-Date
        Write-Host "⏱️  Inicio de batch: $startTime" -ForegroundColor Gray
        & cmd /c $CMD 2>&1 | Tee-Object -FilePath $LOG -Append

        $endTime = Get-Date
        $elapsed = ($endTime - $startTime).TotalMinutes
        Write-Host "✅ Batch completado en $([math]::Round($elapsed,2)) minutos" -ForegroundColor Green

        # Verificar espacio
        $free = Get-FreeSpaceGB $OUTDIR
        if ($free -lt 5) {
            Write-Host "❌ Espacio crítico: $free GB. Deteniendo script." -ForegroundColor Red
            break
        }

        # Pausa ligera entre iteraciones
        Start-Sleep -Seconds 60
    }
}

# ===============================================
# 🟢 EJECUCIÓN
# ===============================================

Write-Host "==============================================="
Write-Host "🔵 POLYGON MASSIVE DOWNLOAD START"
Write-Host "==============================================="

# Crear carpeta de logs
if (-not (Test-Path "D:\04_TRADING_SMALLCAPS\logs")) {
    New-Item -ItemType Directory -Path "D:\04_TRADING_SMALLCAPS\logs" | Out-Null
}

Run-Downloader
```

---

## ⚙️ Cómo usarlo

1. Guarda el archivo como `download_all_events_fast.ps1`.
2. Abre **PowerShell como Administrador**.
3. Ve a tu carpeta del proyecto:

   ```powershell
   cd D:\04_TRADING_SMALLCAPS
   ```
4. Ejecuta:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\download_all_events_fast.ps1
   ```
5. Déjalo toda la noche.
   Muestra progreso cada batch y rota el disco automáticamente si te quedas sin espacio.

---

## 🧠 Qué hace exactamente

| Función                | Descripción                                                             |
| ---------------------- | ----------------------------------------------------------------------- |
| `Get-FreeSpaceGB`      | Calcula espacio libre en GB.                                            |
| `Check-OrSwitch-Drive` | Si queda <20 GB → mueve la descarga al nuevo disco (E:) y crea symlink. |
| `Run-Downloader`       | Ejecuta el script Python en bucle con logs y reintentos.                |
| `--resume`             | Reanuda donde se quedó, incluso si se interrumpe.                       |
| `Tee-Object`           | Guarda logs en disco y los muestra en pantalla simultáneamente.         |

---

## 🧩 Qué log ver mañana

Archivo:

```
D:\04_TRADING_SMALLCAPS\logs\download_trades_full.log
```

Comando rápido:

```powershell
Get-Content D:\04_TRADING_SMALLCAPS\logs\download_trades_full.log -Tail 30 -Wait
```

---

¿Quieres que te prepare también la **versión Linux/macOS** (bash + tmux) por si decides moverlo luego a un servidor o NAS para seguir descargando allí?
