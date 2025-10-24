import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import polars as pl
import pandas as pd

# Cargar universo enriquecido
df = pl.read_parquet('processed/universe/cs_xnas_xnys_hybrid_enriched_2025-10-24.parquet')

# Separar activos e inactivos
activos = df.filter(pl.col('active') == True)
inactivos = df.filter(pl.col('active') == False)

print("="*80)
print("ANÁLISIS DE COLUMNAS: ACTIVOS vs INACTIVOS")
print("="*80)

# Analizar cada columna
analisis = []
for col in df.columns:
    # Activos
    activos_not_null = len(activos.filter(pl.col(col).is_not_null()))
    activos_pct = (activos_not_null / len(activos)) * 100 if len(activos) > 0 else 0

    # Inactivos
    inactivos_not_null = len(inactivos.filter(pl.col(col).is_not_null()))
    inactivos_pct = (inactivos_not_null / len(inactivos)) * 100 if len(inactivos) > 0 else 0

    analisis.append({
        'Columna': col,
        'Activos_Count': activos_not_null,
        'Activos_%': f'{activos_pct:.1f}%',
        'Inactivos_Count': inactivos_not_null,
        'Inactivos_%': f'{inactivos_pct:.1f}%',
        'Tiene_Activos': 'SI' if activos_pct > 0 else 'NO',
        'Tiene_Inactivos': 'SI' if inactivos_pct > 0 else 'NO'
    })

df_analisis = pd.DataFrame(analisis)
print(df_analisis.to_string(index=False))

# Resumen
print("\n" + "="*80)
print("RESUMEN")
print("="*80)

solo_activos = df_analisis[(df_analisis['Tiene_Activos'] == 'SI') & (df_analisis['Tiene_Inactivos'] == 'NO')]
solo_inactivos = df_analisis[(df_analisis['Tiene_Activos'] == 'NO') & (df_analisis['Tiene_Inactivos'] == 'SI')]
ambos = df_analisis[(df_analisis['Tiene_Activos'] == 'SI') & (df_analisis['Tiene_Inactivos'] == 'SI')]
ninguno = df_analisis[(df_analisis['Tiene_Activos'] == 'NO') & (df_analisis['Tiene_Inactivos'] == 'NO')]

print(f"\nColumnas SOLO con datos en ACTIVOS ({len(solo_activos)}):")
if len(solo_activos) > 0:
    print(solo_activos[['Columna', 'Activos_%']].to_string(index=False))

print(f"\nColumnas SOLO con datos en INACTIVOS ({len(solo_inactivos)}):")
if len(solo_inactivos) > 0:
    print(solo_inactivos[['Columna', 'Inactivos_%']].to_string(index=False))

print(f"\nColumnas con datos en AMBOS ({len(ambos)}):")
if len(ambos) > 0:
    print(ambos[['Columna', 'Activos_%', 'Inactivos_%']].to_string(index=False))

print(f"\nColumnas SIN datos en NINGUNO ({len(ninguno)}):")
if len(ninguno) > 0:
    print(ninguno[['Columna']].to_string(index=False))
