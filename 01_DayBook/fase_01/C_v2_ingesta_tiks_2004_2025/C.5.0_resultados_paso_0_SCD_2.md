```sh
PS D:\04_TRADING_SMALLCAPS> python 01_DayBook/fase_01/C_v2_ingesta_tiks_2004_2025/verificar_paso0_scd2.py
================================================================================
VERIFICACIÓN PASO 0: SCD-2 MARKET CAP DIMENSION
================================================================================
Working directory: D:\04_TRADING_SMALLCAPS

[1] VERIFICACIÓN DE ARCHIVOS GENERADOS
--------------------------------------------------------------------------------
[OK] market_cap_dim.parquet: EXISTS
[OK] MANIFEST.json: EXISTS
[OK] _SUCCESS: EXISTS

[OK] Todos los archivos existen

[2] VERIFICACIÓN DE MANIFEST.JSON
--------------------------------------------------------------------------------
Timestamp generación: 2025-10-25T18:32:00.095322
Total tickers: 10,482
Total periodos SCD-2: 10,482
Rango temporal: 2025-10-19 -> 2099-12-31

Cobertura global:
  - market_cap: 5,608 / 10,482 (53.5%)
  - shares_outstanding: 9,485 / 10,482 (90.5%)

[3] CARGA Y VALIDACIÓN DE DIMENSIÓN SCD-2
--------------------------------------------------------------------------------
Shape: (10482, 5)

Schema:
  ticker                    String          (nulls: 0 = 0.0%)
  effective_from            Date            (nulls: 0 = 0.0%)
  effective_to              Date            (nulls: 0 = 0.0%)
  market_cap                Float64         (nulls: 4,874 = 46.5%)
  shares_outstanding        Float64         (nulls: 997 = 9.5%)

[4] VERIFICACIÓN INTEGRIDAD SCD-2
--------------------------------------------------------------------------------
[OK] Rangos válidos (effective_from < effective_to): True
[OK] Sin gaps/overlaps entre periodos: True
[OK] Periodos abiertos (effective_to=2099-12-31): 10,482

[5] VERIFICACIÓN COBERTURA UNIVERSO HÍBRIDO
--------------------------------------------------------------------------------
Tickers en daily_cache (universo actual): 4,943
Tickers en SCD-2 (universo): 2,945

[NOTA] 1998 tickers en cache NO están en SCD-2
       Estos fueron delistados antes de 2025-10-19 (ESPERADO)
       Representan 40.4% del universo

Cobertura UNIVERSO HÍBRIDO:
  [OK] market_cap: 2,942 / 2,945 (99.9%)
  [OK] shares_outstanding: 2,944 / 2,945 (100.0%)

  [WARN] 3 tickers sin market_cap:
shape: (3, 3)
┌────────┬────────────────┬──────────────┐
│ ticker ┆ effective_from ┆ effective_to │
│ ---    ┆ ---            ┆ ---          │
│ str    ┆ date           ┆ date         │
╞════════╪════════════════╪══════════════╡
│ CPN    ┆ 2025-10-19     ┆ 2099-12-31   │
│ FVN    ┆ 2025-10-19     ┆ 2099-12-31   │
│ JACS   ┆ 2025-10-19     ┆ 2099-12-31   │
└────────┴────────────────┴──────────────┘

[6] DISTRIBUCIÓN DE MARKET CAP (UNIVERSO HÍBRIDO)
--------------------------------------------------------------------------------
Estadísticas market_cap (USD):
  min       : $413,489
  p25       : $49,551,040
  median    : $223,973,523
  p75       : $660,179,818
  max       : $2,260,604,541

Distribución por rango:
shape: (4, 2)
┌────────────────────┬───────┐
│ cap_range          ┆ count │
│ ---                ┆ ---   │
│ str                ┆ u32   │
╞════════════════════╪═══════╡
│ $300M-$2B (Small)  ┆ 1255  │
│ $50M-$300M (Micro) ┆ 944   │
│ < $50M (Nano)      ┆ 741   │
│ $2B-$10B (Mid)     ┆ 2     │
└────────────────────┴───────┘

[7] MUESTRA DE TICKERS ESPECÍFICOS
--------------------------------------------------------------------------------
Tickers seleccionados: SILO, ESPR, XPON, PETZ, SCYX

Detalle:

  SILO:
    effective_from: 2025-10-19
    effective_to: 2099-12-31
    market_cap: $7,455,569
    shares_outstanding: 9,461,128

  ESPR:
    effective_from: 2025-10-19
    effective_to: 2099-12-31
    market_cap: $636,962,769
    shares_outstanding: 201,622,825

  XPON:
    effective_from: 2025-10-19
    effective_to: 2099-12-31
    market_cap: $12,697,566
    shares_outstanding: 3,474,720

  PETZ:
    effective_from: 2025-10-19
    effective_to: 2099-12-31
    market_cap: $10,737,231
    shares_outstanding: 10,323,268

  SCYX:
    effective_from: 2025-10-19
    effective_to: 2099-12-31
    market_cap: $31,636,560
    shares_outstanding: 41,924,941

[8] SIMULACIÓN JOIN TEMPORAL SCD-2
--------------------------------------------------------------------------------
Fecha de prueba: 2025-10-21
Tickers con market_cap válido en 2025-10-21: 2,945
Cobertura: 100.0%
[OK] Sin duplicados en join temporal

Muestra join (10 tickers):
shape: (10, 5)
┌────────┬────────────────┬──────────────┬─────────────┬────────────────────┐
│ ticker ┆ effective_from ┆ effective_to ┆ market_cap  ┆ shares_outstanding │
│ ---    ┆ ---            ┆ ---          ┆ ---         ┆ ---                │
│ str    ┆ date           ┆ date         ┆ f64         ┆ f64                │
╞════════╪════════════════╪══════════════╪═════════════╪════════════════════╡
│ SIDU   ┆ 2025-10-19     ┆ 2099-12-31   ┆ 4.2297e7    ┆ 3.5147483e7        │
│ ESOA   ┆ 2025-10-19     ┆ 2099-12-31   ┆ 1.6834e8    ┆ 1.6650538e7        │
│ XOMA   ┆ 2025-10-19     ┆ 2099-12-31   ┆ 4.1932e8    ┆ 1.2087719e7        │
│ PERF   ┆ 2025-10-19     ┆ 2099-12-31   ┆ 1.9759e8    ┆ 8.5059953e7        │
│ SCOR   ┆ 2025-10-19     ┆ 2099-12-31   ┆ 3.6909e7    ┆ 5.01478e6          │
│ MLAB   ┆ 2025-10-19     ┆ 2099-12-31   ┆ 4.0202e8    ┆ 5.501454e6         │
│ BIYA   ┆ 2025-10-19     ┆ 2099-12-31   ┆ 1.0261e7    ┆ 1.252e7            │
│ MTEN   ┆ 2025-10-19     ┆ 2099-12-31   ┆ 3.2693288e7 ┆ 6.8396e6           │
│ CLPR   ┆ 2025-10-19     ┆ 2099-12-31   ┆ 6.4748e7    ┆ 1.6146546e7        │
│ VBTX   ┆ 2025-10-19     ┆ 2099-12-31   ┆ 1.6576e9    ┆ 5.4745471e7        │
└────────┴────────────────┴──────────────┴─────────────┴────────────────────┘

================================================================================
VERIFICACIÓN FINAL - PASO 0
================================================================================
[OK] Archivos generados
[OK] Rangos SCD-2 válidos
[OK] Sin gaps/overlaps
[OK] Cobertura SCD-2 >95%

================================================================================
[SUCCESS] PASO 0 COMPLETADO EXITOSAMENTE
Dimensión SCD-2 lista para uso en PASO 1 (daily_cache)
================================================================================
```