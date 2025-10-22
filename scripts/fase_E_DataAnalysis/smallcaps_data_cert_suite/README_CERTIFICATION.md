# SmallCaps Data Certification Suite

**Objetivo:** certificar científicamente que tus datasets cumplen los **pensamientos fundacionales** y son **aptos para backtesting** sin sesgos ni leakage.

## Contenido

```
smallcaps_data_cert_suite/
├── checks/
│   ├── _utils.py
│   ├── a01_inventory.py
│   ├── a02_schema.py
│   ├── a03_tick2bar_conservation.py
│   ├── a04_labels_logic.py
│   ├── a05_weights_stats.py
│   ├── a06_universe_pti.py
│   ├── a06b_filings_dilution.py
│   ├── a07_reproducibility.py
│   ├── a08_split_purging.py
│   ├── a09_events_schema.py
│   ├── a10_events_lineage.py
│   └── a11_events_consistency.py
├── schemas/
│   ├── events_schema.json
│   └── reference_schema.json
├── config/
│   └── example_paths.yaml
└── README_CERTIFICATION.md
```

## Requisitos

- Python 3.10+
- `pip install polars pyarrow numpy`

## Ejecución (PowerShell ejemplo)

```powershell
$env:SC_ROOT="D:/04_TRADING_SMALLCAPS"
$env:SC_REPORTS="$env:SC_ROOT/reports/audits"
mkdir $env:SC_REPORTS

python checks/a01_inventory.py --root "$env:SC_ROOT" --out "$env:SC_REPORTS/a01_inventory.json"
python checks/a02_schema.py --root "$env:SC_ROOT" --out "$env:SC_REPORTS/a02_schema.json"
python checks/a03_tick2bar_conservation.py --root "$env:SC_ROOT" --out "$env:SC_REPORTS/a03_tick2bar.json" --sample 500 --tol 0.001
python checks/a04_labels_logic.py --root "$env:SC_ROOT" --out "$env:SC_REPORTS/a04_labels.json"
python checks/a05_weights_stats.py --root "$env:SC_ROOT" --out "$env:SC_REPORTS/a05_weights.json" --gini_max 0.9 --eps_sum 1e-6
python checks/a06_universe_pti.py --root "$env:SC_ROOT" --out "$env:SC_REPORTS/a06_universe_pti.json" --mc_max 2000000000 --float_max 100000000 --pmin 0.5 --pmax 20.0 --volmin 500000 --chgmin 0.15
python checks/a06b_filings_dilution.py --root "$env:SC_ROOT" --out "$env:SC_REPORTS/a06b_filings.json" --window_days 10
python checks/a07_reproducibility.py --root "$env:SC_ROOT" --out "$env:SC_REPORTS/a07_repro.json"
python checks/a08_split_purging.py --root "$env:SC_ROOT" --out "$env:SC_REPORTS/a08_split.json" --purge 50
python checks/a09_events_schema.py --root "$env:SC_ROOT" --out "$env:SC_REPORTS/a09_events_schema.json"
python checks/a10_events_lineage.py --root "$env:SC_ROOT" --out "$env:SC_REPORTS/a10_events_lineage.json"
python checks/a11_events_consistency.py --root "$env:SC_ROOT" --out "$env:SC_REPORTS/a11_events_consistency.json"
```

## GO/NO-GO

**GO** si:
1. A01–A11 = PASS
2. Conservación tick→barra < 0.1%
3. Universo *point‑in‑time* cumple marketcap/float/precio/vol/%chg/exchange
4. Filings de dilución trazados
5. Σ weights = 1 y Gini < 0.9
6. Split sin leakage (purge ≥ 50)
7. Eventos ML (esquema/lineage/consistencia) OK




# 3 maneras de ejecutar la suite **a tope de rápido**, sin tocar los scripts.

# 0) Preparación (una vez)

* Pon los datos y la carpeta `smallcaps_data_cert_suite/` en **SSD/NVMe local** (evita discos de red).
* Instala deps: `pip install polars pyarrow numpy`
* Variables para usar **todos tus cores**:

* PowerShell:

```sh
$env:SC_ROOT="D:/04_TRADING_SMALLCAPS"
$env:SC_REPORTS="$env:SC_ROOT/reports/audits"
$env:POLARS_MAX_THREADS=[Environment]::ProcessorCount
mkdir $env:SC_REPORTS -Force | Out-Null
```
* Bash (WSL/Git Bash):

```sh
export SC_ROOT="D:/04_TRADING_SMALLCAPS"
export SC_REPORTS="$SC_ROOT/reports/audits"
export POLARS_MAX_THREADS=$(nproc)
mkdir -p "$SC_REPORTS"
```

---

### 1) PowerShell 7 — **Paralelo real** (rápido y simple)

Copia/pega y ejecuta (usa 8 tareas simultáneas; ajusta `-ThrottleLimit`):

```powershell
$checks = @(
  "python checks/a01_inventory.py --root `"$env:SC_ROOT`" --out `"$env:SC_REPORTS/a01_inventory.json`"",
  "python checks/a02_schema.py --root `"$env:SC_ROOT`" --out `"$env:SC_REPORTS/a02_schema.json`"",
  "python checks/a03_tick2bar_conservation.py --root `"$env:SC_ROOT`" --out `"$env:SC_REPORTS/a03_tick2bar.json`" --sample 300 --tol 0.001",
  "python checks/a04_labels_logic.py --root `"$env:SC_ROOT`" --out `"$env:SC_REPORTS/a04_labels.json`"",
  "python checks/a05_weights_stats.py --root `"$env:SC_ROOT`" --out `"$env:SC_REPORTS/a05_weights.json`"",
  "python checks/a06_universe_pti.py --root `"$env:SC_ROOT`" --out `"$env:SC_REPORTS/a06_universe_pti.json`" --mc_max 2000000000 --float_max 100000000 --pmin 0.5 --pmax 20.0 --volmin 500000 --chgmin 0.15",
  "python checks/a06b_filings_dilution.py --root `"$env:SC_ROOT`" --out `"$env:SC_REPORTS/a06b_filings.json`" --window_days 10",
  "python checks/a07_reproducibility.py --root `"$env:SC_ROOT`" --out `"$env:SC_REPORTS/a07_repro.json`"",
  "python checks/a08_split_purging.py --root `"$env:SC_ROOT`" --out `"$env:SC_REPORTS/a08_split.json`" --purge 50",
  "python checks/a09_events_schema.py --root `"$env:SC_ROOT`" --out `"$env:SC_REPORTS/a09_events_schema.json`"",
  "python checks/a10_events_lineage.py --root `"$env:SC_ROOT`" --out `"$env:SC_REPORTS/a10_events_lineage.json`"",
  "python checks/a11_events_consistency.py --root `"$env:SC_ROOT`" --out `"$env:SC_REPORTS/a11_events_consistency.json`""
)

$checks |
  ForEach-Object -Parallel { & cmd.exe /c $_ } -ThrottleLimit 8 |
  Out-Host
```

✔️ Esto lanza **todas** las verificaciones en paralelo.
💡 Para un *smoke test* ultra-rápido, baja el muestreo de A03: `--sample 100`.

---

### 2) Git Bash / WSL + GNU Parallel (también muy rápido)

Si tienes `parallel`, ejecuta:

```bash
cat > /tmp/checks.list <<'EOF'
python checks/a01_inventory.py --root "$SC_ROOT" --out "$SC_REPORTS/a01_inventory.json"
python checks/a02_schema.py --root "$SC_ROOT" --out "$SC_REPORTS/a02_schema.json"
python checks/a03_tick2bar_conservation.py --root "$SC_ROOT" --out "$SC_REPORTS/a03_tick2bar.json" --sample 300 --tol 0.001
python checks/a04_labels_logic.py --root "$SC_ROOT" --out "$SC_REPORTS/a04_labels.json"
python checks/a05_weights_stats.py --root "$SC_ROOT" --out "$SC_REPORTS/a05_weights.json"
python checks/a06_universe_pti.py --root "$SC_ROOT" --out "$SC_REPORTS/a06_universe_pti.json" --mc_max 2000000000 --float_max 100000000 --pmin 0.5 --pmax 20.0 --volmin 500000 --chgmin 0.15
python checks/a06b_filings_dilution.py --root "$SC_ROOT" --out "$SC_REPORTS/a06b_filings.json" --window_days 10
python checks/a07_reproducibility.py --root "$SC_ROOT" --out "$SC_REPORTS/a07_repro.json"
python checks/a08_split_purging.py --root "$SC_ROOT" --out "$SC_REPORTS/a08_split.json" --purge 50
python checks/a09_events_schema.py --root "$SC_ROOT" --out "$SC_REPORTS/a09_events_schema.json"
python checks/a10_events_lineage.py --root "$SC_ROOT" --out "$SC_REPORTS/a10_events_lineage.json"
python checks/a11_events_consistency.py --root "$SC_ROOT" --out "$SC_REPORTS/a11_events_consistency.json"
EOF

parallel -j $(nproc) < /tmp/checks.list
```

---

### 3) Runner incluido + multi-proceso del SO (rápido y ordenado)

Usa el runner que ya te dejé y permite que el SO paralelice E/S entre procesos Python:

```powershell
python run_all_checks.py
```

Si quieres **paralelizar por lotes**, abre 2–3 consolas y reparte comandos (p.ej. en una A01–A05, en otra A06–A08, en otra A09–A11).

---

### Ajustes prácticos para “modo turbo”

* **Baja muestreo de A03** si solo quieres *smoke test*: `--sample 100` (luego subes a 300–500 para certificación).
* **Cierra antivirus** para la carpeta del proyecto (o exclúyela) si tu equipo lo permite — reduce E/S bloqueante.
* **Evita subprocesos innecesarios** abiertos en el mismo disco (copias, compresiones, etc.).
* Mantén `POLARS_MAX_THREADS` al número de cores físicos o lógicos disponibles.
* Si el disco es NVMe, pon **datos y scripts en el mismo volumen**.

`summary_semáforo.py` que lea todos los JSON de `reports/audits` y te imprima el **GO/NO-GO** con los umbrales.