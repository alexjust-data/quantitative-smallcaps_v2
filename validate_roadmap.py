#!/usr/bin/env python
"""
Validación completa del roadmap post-PASO 5
"""
import json
from pathlib import Path
import sys

def validate_documentation():
    """Valida que la documentación esté correcta"""
    print("="*80)
    print("VALIDACIÓN DOCUMENTACIÓN")
    print("="*80)
    
    docs = {
        'C.5': '01_DayBook/fase_01/C_v2_ingesta_tiks_2004_2025/C.5_plan_ejecucion_E0_descarga_ticks.md',
        'C.6': '01_DayBook/fase_01/C_v2_ingesta_tiks_2004_2025/C.6_roadmap_multi_evento.md',
        'C.7': '01_DayBook/fase_01/C_v2_ingesta_tiks_2004_2025/C.7_roadmap_post_paso5.md'
    }
    
    for name, path in docs.items():
        file_path = Path(path)
        if file_path.exists():
            size_kb = file_path.stat().st_size / 1024
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = len(f.readlines())
            print(f"✅ {name}: {lines:,} líneas, {size_kb:.1f} KB")
            
            # Validar que tenga enlaces a otros docs
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            if name == 'C.5':
                has_c6_link = 'C.6_roadmap_multi_evento.md' in content
                has_c7_link = 'C.7_roadmap_post_paso5.md' in content
                has_index = '## ÍNDICE' in content
                print(f"   - Índice: {'✅' if has_index else '❌'}")
                print(f"   - Link a C.6: {'✅' if has_c6_link else '❌'}")
                print(f"   - Link a C.7: {'✅' if has_c7_link else '❌'}")
                
            elif name == 'C.6':
                has_c1_link = 'C.1_estrategia_descarga_ticks_eventos.md' in content
                has_c5_link = 'C.5_plan_ejecucion_E0_descarga_ticks.md' in content
                has_track_ab = 'Track A' in content and 'Track B' in content
                print(f"   - Track A+B: {'✅' if has_track_ab else '❌'}")
                print(f"   - Link a C.1: {'✅' if has_c1_link else '❌'}")
                print(f"   - Link a C.5: {'✅' if has_c5_link else '❌'}")
                
            elif name == 'C.7':
                has_code = 'def build_dollar_imbalance_bars' in content
                has_detectors = 'def detect_e1_volume_explosion' in content
                print(f"   - Algoritmo DIB: {'✅' if has_code else '❌'}")
                print(f"   - Detectores E1-E8: {'✅' if has_detectors else '❌'}")
        else:
            print(f"❌ {name}: NO ENCONTRADO")
            return False
    
    return True

def validate_paso5_completion():
    """Valida que PASO 5 esté completado"""
    print("\n" + "="*80)
    print("VALIDACIÓN PASO 5 (TICKS DESCARGADOS)")
    print("="*80)
    
    trades_dir = Path('raw/polygon/trades')
    if not trades_dir.exists():
        print("❌ Directorio raw/polygon/trades no existe")
        return False
    
    # Contar archivos _SUCCESS
    success_files = list(trades_dir.rglob('_SUCCESS'))
    num_success = len(success_files)
    print(f"✅ Archivos descargados: {num_success:,} _SUCCESS")
    
    # Verificar storage
    import subprocess
    result = subprocess.run(['du', '-sh', 'raw/polygon/trades'], 
                          capture_output=True, text=True, shell=True)
    if result.returncode == 0:
        storage = result.stdout.split()[0]
        print(f"✅ Storage total: {storage}")
    
    # Verificar que tenemos los TOP tickers
    top_tickers = ['BCRX', 'GERN', 'VXRT', 'SRNE', 'BLDP']
    for ticker in top_tickers:
        ticker_dir = trades_dir / ticker
        if ticker_dir.exists():
            days = len(list(ticker_dir.glob('date=*')))
            print(f"✅ {ticker}: {days} días descargados")
        else:
            print(f"⚠️  {ticker}: No encontrado")
    
    # Validar cobertura esperada
    expected_min = 60000  # 92.2% de ~70K días trading
    if num_success >= expected_min:
        coverage_pct = (num_success / 70290) * 100
        print(f"\n✅ Cobertura: {coverage_pct:.1f}% (>{expected_min:,} archivos)")
        return True
    else:
        print(f"\n⚠️  Cobertura baja: {num_success:,} archivos (<{expected_min:,} esperados)")
        return False

def validate_data_structure():
    """Valida estructura completa de datos"""
    print("\n" + "="*80)
    print("VALIDACIÓN ESTRUCTURA DE DATOS")
    print("="*80)
    
    paths = {
        'Daily Cache': 'processed/daily_cache',
        'Watchlists E0': 'processed/universe/info_rich/daily',
        'Ticks E0': 'raw/polygon/trades',
        'Auditorías': '01_DayBook/fase_01/C_v2_ingesta_tiks_2004_2025/audits',
    }
    
    all_ok = True
    for name, path_str in paths.items():
        path = Path(path_str)
        if path.exists():
            if path.is_dir():
                files = list(path.rglob('*'))
                print(f"✅ {name}: {len(files):,} archivos")
            else:
                print(f"✅ {name}: Existe")
        else:
            print(f"❌ {name}: NO ENCONTRADO")
            all_ok = False
    
    return all_ok

def validate_next_steps():
    """Valida que los directorios para próximos pasos estén listos"""
    print("\n" + "="*80)
    print("VALIDACIÓN PREPARACIÓN PRÓXIMOS PASOS")
    print("="*80)
    
    # Verificar que NO existen directorios de implementación (no comenzados aún)
    future_dirs = {
        'Event Detectors': 'scripts/fase_C_ingesta_tiks/event_detectors',
        'Barras DIB/VIB': 'scripts/fase_D_barras',
        'Multi-event watchlists': 'processed/universe/multi_event',
    }
    
    for name, path_str in future_dirs.items():
        path = Path(path_str)
        if path.exists():
            print(f"⚠️  {name}: YA EXISTE (pendiente implementación)")
        else:
            print(f"✅ {name}: Listo para crear")
    
    return True

def main():
    print("\n🔍 VALIDACIÓN COMPLETA POST-PASO 5\n")
    
    results = {
        'Documentación': validate_documentation(),
        'PASO 5 Completado': validate_paso5_completion(),
        'Estructura de Datos': validate_data_structure(),
        'Preparación': validate_next_steps(),
    }
    
    print("\n" + "="*80)
    print("RESUMEN VALIDACIÓN")
    print("="*80)
    
    all_passed = True
    for category, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {category}")
        if not passed:
            all_passed = False
    
    print("\n" + "="*80)
    if all_passed:
        print("🎉 VALIDACIÓN COMPLETA: TODO OK")
        print("="*80)
        print("\n📋 PRÓXIMOS PASOS (según C.6):")
        print("   1. Track A: Implementar detectores E1, E4, E7, E8")
        print("   2. Track B: Prototipo DIB/VIB en subset pequeño")
        print("   3. Ejecutar en paralelo (Semana 1-2)")
        print("\n📖 Ver roadmap completo: C.6_roadmap_multi_evento.md")
        return 0
    else:
        print("⚠️  VALIDACIÓN FALLÓ: Revisar errores arriba")
        print("="*80)
        return 1

if __name__ == '__main__':
    sys.exit(main())
