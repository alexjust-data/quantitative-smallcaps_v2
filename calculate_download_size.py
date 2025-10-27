#!/usr/bin/env python3
"""
Calcula el tamaño actual y proyectado de la descarga de ticks.
"""
from pathlib import Path

def get_dir_size(path: Path) -> int:
    """Calcula tamaño total de un directorio recursivamente."""
    total = 0
    try:
        for item in path.rglob('*'):
            if item.is_file():
                total += item.stat().st_size
    except Exception as e:
        print(f"Error: {e}")
    return total

def format_size(bytes_size: int) -> str:
    """Formatea bytes a unidades legibles."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} PB"

# Paths
trades_dir = Path('raw/polygon/trades')

print("=" * 80)
print("CÁLCULO DE TAMAÑO DE DESCARGA TICKS")
print("=" * 80)
print()

# Contar archivos completados
success_files = list(trades_dir.rglob('_SUCCESS'))
completed_days = len(success_files)

print(f"Días completados: {completed_days:,}")
print()

# Calcular tamaño actual
print("Calculando tamaño actual...")
current_size_bytes = get_dir_size(trades_dir)
current_size_gb = current_size_bytes / (1024**3)

print(f"Tamaño actual: {format_size(current_size_bytes)} ({current_size_gb:.2f} GB)")
print()

# Parámetros de la descarga
total_days = 82_012  # Según PASO 5
eventos_e0 = 29_555  # Eventos E0 reales
event_window = 1     # ±1 día

print("PROYECCIÓN:")
print(f"  Total días objetivo: {total_days:,}")
print(f"  Eventos E0: {eventos_e0:,}")
print(f"  Event window: ±{event_window} día")
print()

if completed_days > 0:
    # Calcular tamaño promedio por día
    avg_size_per_day = current_size_bytes / completed_days

    print(f"Tamaño promedio por día: {format_size(avg_size_per_day)}")
    print()

    # Proyectar tamaño final
    projected_total_bytes = avg_size_per_day * total_days
    projected_total_gb = projected_total_bytes / (1024**3)
    projected_total_tb = projected_total_gb / 1024

    print("TAMAÑO FINAL PROYECTADO:")
    print(f"  {format_size(projected_total_bytes)}")
    print(f"  {projected_total_gb:,.2f} GB")
    print(f"  {projected_total_tb:.2f} TB")
    print()

    # Calcular progreso
    progress_pct = (completed_days / total_days) * 100
    remaining_days = total_days - completed_days
    remaining_bytes = projected_total_bytes - current_size_bytes
    remaining_gb = remaining_bytes / (1024**3)

    print("PROGRESO:")
    print(f"  Completado: {progress_pct:.1f}%")
    print(f"  Días restantes: {remaining_days:,}")
    print(f"  Tamaño restante: {format_size(remaining_bytes)} ({remaining_gb:.2f} GB)")
    print()

    # Comparar con estimación original
    original_estimate_gb = 2_600  # 2.6 TB según C.5
    difference = projected_total_gb - original_estimate_gb
    difference_pct = (difference / original_estimate_gb) * 100

    print("VS. ESTIMACIÓN ORIGINAL:")
    print(f"  Estimación C.5: 2,600 GB (2.6 TB)")
    print(f"  Proyección real: {projected_total_gb:,.0f} GB ({projected_total_tb:.2f} TB)")
    print(f"  Diferencia: {difference:+,.0f} GB ({difference_pct:+.1f}%)")
else:
    print("No hay datos suficientes para proyectar.")

print()
print("=" * 80)
