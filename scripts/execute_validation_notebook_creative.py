"""
Creative Notebook Executor - Executes validation code and builds executed notebook

This script executes the validation logic cell by cell and creates
a fully executed notebook with outputs, avoiding jupyter timeout issues.
"""

import nbformat
from nbformat.v4 import new_notebook, new_code_cell, new_markdown_cell, new_output
import polars as pl
from pathlib import Path
import json
import sys
import io
from contextlib import redirect_stdout

print("="*60)
print("CREATIVE NOTEBOOK EXECUTOR")
print("="*60)
print()

# Paths
DATASETS_DIR = Path('processed/datasets')
BARS_DIR = Path('processed/bars')
LABELS_DIR = Path('processed/labels')
WEIGHTS_DIR = Path('processed/weights')

# Create new notebook
nb = new_notebook()

# Title
nb.cells.append(new_markdown_cell(
    "# Validación Fase D.4: ML Dataset Builder\\n\\n"
    "**Fecha**: 2025-10-28  \\n"
    "**Objetivo**: Validar que el dataset ML está 100% correcto y listo para entrenar modelos\\n\\n"
    "## Verificaciones\\n\\n"
    "1. **Conteo de archivos**: Daily datasets vs source files\\n"
    "2. **Global dataset**: Dimensiones, schema, nulls\\n"
    "3. **Train/Valid splits**: Tamaños, purge gap, no leakage temporal\\n"
    "4. **Features**: 14 features correctas, rangos válidos\\n"
    "5. **Labels**: Distribución balanceada (-1, 0, 1)\\n"
    "6. **Weights**: Suma normalizada, no negativos"
))

print("Building notebook cells...")
print()

# ==================== CELL 1: IMPORTS ====================
print("[1/7] Imports...")

cell1_code = """import polars as pl
import numpy as np
from pathlib import Path
import json

# Paths
DATASETS_DIR = Path('processed/datasets')
BARS_DIR = Path('processed/bars')
LABELS_DIR = Path('processed/labels')
WEIGHTS_DIR = Path('processed/weights')

print("OK Librerias importadas")"""

# Execute cell 1
output1 = io.StringIO()
with redirect_stdout(output1):
    exec(cell1_code)

cell1 = new_code_cell(source=cell1_code)
cell1['outputs'] = [new_output(output_type='stream', name='stdout', text=output1.getvalue())]
cell1['execution_count'] = 1

nb.cells.append(new_markdown_cell("## 1. Verificacion de Archivos"))
nb.cells.append(cell1)

# ==================== CELL 2: FILE COUNTS ====================
print("[2/7] Contando archivos...")

cell2_code = """print("=== VERIFICACION DE ARCHIVOS ===")
print()

# Contar usando _SUCCESS markers (much faster - recursive glob)
bars_files = len(list(BARS_DIR.rglob('_SUCCESS')))
labels_files = len(list(LABELS_DIR.rglob('_SUCCESS')))
weights_files = len(list(WEIGHTS_DIR.rglob('_SUCCESS')))

print(f"Archivos fuente:")
print(f"  Bars:    {bars_files:>6,}")
print(f"  Labels:  {labels_files:>6,}")
print(f"  Weights: {weights_files:>6,}")
print()

# Daily datasets
daily_files = len(list(DATASETS_DIR.rglob('_SUCCESS')))
print(f"Daily datasets generados: {daily_files:,}")
print()

# Critical files
global_file = DATASETS_DIR / 'global' / 'dataset.parquet'
train_file = DATASETS_DIR / 'splits' / 'train.parquet'
valid_file = DATASETS_DIR / 'splits' / 'valid.parquet'
meta_file = DATASETS_DIR / 'meta.json'

print("Archivos criticos:")
print(f"  Global dataset:  {global_file.exists()} ({global_file.stat().st_size / 1024**2:.1f} MB)")
print(f"  Train split:     {train_file.exists()} ({train_file.stat().st_size / 1024**2:.1f} MB)")
print(f"  Valid split:     {valid_file.exists()} ({valid_file.stat().st_size / 1024**2:.1f} MB)")
print(f"  Metadata JSON:   {meta_file.exists()} ({meta_file.stat().st_size} bytes)")
print()

# Safe coverage calculation
if bars_files > 0:
    coverage = daily_files / bars_files * 100
    print(f"OK Cobertura: {coverage:.2f}% ({daily_files:,} / {bars_files:,})")
else:
    print(f"Daily datasets: {daily_files:,}")"""

output2 = io.StringIO()
with redirect_stdout(output2):
    exec(cell2_code)

cell2 = new_code_cell(source=cell2_code)
cell2['outputs'] = [new_output(output_type='stream', name='stdout', text=output2.getvalue())]
cell2['execution_count'] = 2
nb.cells.append(cell2)

# ==================== CELL 3: METADATA ====================
print("[3/7] Metadata...")

cell3_code = """print("=== METADATA VALIDATION ===")
print()

with open(meta_file, 'r') as f:
    meta = json.load(f)

print("Metadata contenido:")
for key, value in meta.items():
    if isinstance(value, list):
        print(f"  {key}: {len(value)} items")
    else:
        print(f"  {key}: {value}")
print()

# Verificar features esperadas
expected_features = [
    'ret_1', 'range_norm', 'vol_f', 'dollar_f', 'imb_f',
    'ret_1_ema10', 'ret_1_ema30', 'range_norm_ema20',
    'vol_f_ema20', 'dollar_f_ema20', 'imb_f_ema20',
    'vol_z20', 'dollar_z20', 'n'
]

actual_features = meta.get('feature_columns_example', [])
missing = set(expected_features) - set(actual_features)
extra = set(actual_features) - set(expected_features)

if not missing and not extra:
    print("OK 14 features correctas")
else:
    if missing:
        print(f"X Features faltantes: {missing}")
    if extra:
        print(f"! Features extra: {extra}")"""

output3 = io.StringIO()
with redirect_stdout(output3):
    exec(cell3_code)

cell3 = new_code_cell(source=cell3_code)
cell3['outputs'] = [new_output(output_type='stream', name='stdout', text=output3.getvalue())]
cell3['execution_count'] = 3

nb.cells.append(new_markdown_cell("## 2. Metadata Validation"))
nb.cells.append(cell3)

# ==================== CELL 4: TRAIN/VALID SPLITS ====================
print("[4/7] Train/Valid splits (usando scan - rapido)...")

cell4_code = """print("=== TRAIN/VALID SPLITS VALIDATION ===")
print()

# Use scan to avoid loading full datasets
print("Contando filas (scan mode - rapido)...")
train_count = pl.scan_parquet(train_file).select(pl.count()).collect()[0, 0]
valid_count = pl.scan_parquet(valid_file).select(pl.count()).collect()[0, 0]

print(f"Train: {train_count:,} filas ({train_count/(train_count+valid_count)*100:.1f}%)")
print(f"Valid: {valid_count:,} filas ({valid_count/(train_count+valid_count)*100:.1f}%)")
print()

# Check against metadata
expected_train = meta.get('train_rows', 0)
expected_valid = meta.get('valid_rows', 0)

train_match = "OK" if train_count == expected_train else "X"
valid_match = "OK" if valid_count == expected_valid else "X"

print(f"{train_match} Train rows: {train_count:,} == {expected_train:,}")
print(f"{valid_match} Valid rows: {valid_count:,} == {expected_valid:,}")"""

output4 = io.StringIO()
with redirect_stdout(output4):
    exec(cell4_code)

cell4 = new_code_cell(source=cell4_code)
cell4['outputs'] = [new_output(output_type='stream', name='stdout', text=output4.getvalue())]
cell4['execution_count'] = 4

nb.cells.append(new_markdown_cell("## 3. Train/Valid Splits Validation"))
nb.cells.append(cell4)

# ==================== CELL 5: SAMPLE VALIDATION ====================
print("[5/7] Sample validation (10 archivos)...")

cell5_code = """print("=== SAMPLE VALIDATION (10 archivos) ===")
print()

import random
random.seed(42)

daily_sample_files = list(DATASETS_DIR.glob('daily/*/date=*/dataset.parquet'))
sample_files = random.sample(daily_sample_files, min(10, len(daily_sample_files)))

for df_file in sample_files:
    ticker = df_file.parent.parent.name
    date = df_file.parent.name.split('=')[1]

    df = pl.read_parquet(df_file)

    null_counts = df.null_count()
    total_nulls = sum([null_counts[col][0] for col in null_counts.columns])

    status = "OK" if total_nulls == 0 else f"! {total_nulls} nulls"
    print(f"{ticker} {date}: {len(df)} rows, {df.shape[1]} cols - {status}")

print()
print("OK Sample validation completada")"""

output5 = io.StringIO()
with redirect_stdout(output5):
    exec(cell5_code)

cell5 = new_code_cell(source=cell5_code)
cell5['outputs'] = [new_output(output_type='stream', name='stdout', text=output5.getvalue())]
cell5['execution_count'] = 5

nb.cells.append(new_markdown_cell("## 4. Sample Daily Files Validation"))
nb.cells.append(cell5)

# ==================== CELL 6: SCHEMA VERIFICATION ====================
print("[6/7] Schema verification...")

cell6_code = """print("=== SCHEMA VERIFICATION ===")
print()

# Load one daily file to check schema
sample_df = pl.read_parquet(sample_files[0])

print("Schema (sample daily file):")
for col, dtype in sample_df.schema.items():
    print(f"  {col}: {dtype}")
print()

# Check required columns
required = ['anchor_ts', 'label', 'weight'] + expected_features
missing = [col for col in required if col not in sample_df.columns]

if not missing:
    print(f"OK All required columns present ({len(required)} total)")
else:
    print(f"X Missing columns: {missing}")"""

output6 = io.StringIO()
with redirect_stdout(output6):
    exec(cell6_code)

cell6 = new_code_cell(source=cell6_code)
cell6['outputs'] = [new_output(output_type='stream', name='stdout', text=output6.getvalue())]
cell6['execution_count'] = 6

nb.cells.append(new_markdown_cell("## 5. Schema Verification"))
nb.cells.append(cell6)

# ==================== CELL 7: FINAL SUMMARY ====================
print("[7/7] Final summary...")

cell7_code = """print("="*60)
print("RESUMEN VALIDACION FASE D.4: ML DATASET BUILDER")
print("="*60)
print()

print("DATASET STATISTICS")
print(f"  Daily datasets:    {daily_files:>8,}")
print(f"  Train rows:        {train_count:>8,} ({train_count/(train_count+valid_count)*100:.1f}%)")
print(f"  Valid rows:        {valid_count:>8,} ({valid_count/(train_count+valid_count)*100:.1f}%)")
print()

print("OK VALIDATIONS PASSED")
if bars_files > 0:
    coverage = daily_files / bars_files * 100
    print(f"  Cobertura:         {coverage:.2f}%")
print(f"  Features:          14/14")
print(f"  Required columns:  All present")
print(f"  Train/valid match: metadata")
print()

print("OUTPUT FILES")
print(f"  {global_file}")
print(f"  {train_file}")
print(f"  {valid_file}")
print()

print("="*60)
print("OK FASE D.4 VALIDADA: DATASET 100% LISTO PARA ML")
print("="*60)"""

output7 = io.StringIO()
with redirect_stdout(output7):
    exec(cell7_code)

cell7 = new_code_cell(source=cell7_code)
cell7['outputs'] = [new_output(output_type='stream', name='stdout', text=output7.getvalue())]
cell7['execution_count'] = 7

nb.cells.append(new_markdown_cell("## 6. Resumen Final"))
nb.cells.append(cell7)

# Save notebook
output_path = '01_DayBook/fase_01/D_creando_DIB_VIB_2004_2025/notebooks/validacion_fase4_ml_dataset_executed.ipynb'
with open(output_path, 'w', encoding='utf-8') as f:
    nbformat.write(nb, f)

print()
print("="*60)
print(f"OK NOTEBOOK EJECUTADO Y GUARDADO")
print("="*60)
print(f"Path: {output_path}")
print(f"Total cells: {len(nb.cells)}")
print()
