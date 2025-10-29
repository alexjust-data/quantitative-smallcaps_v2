import argparse, json, pathlib, sys
from datetime import datetime

REQUIRED = [
  "a01_inventory.json",
  "a02_schema.json",
  "a03_tick2bar.json",
  "a04_labels.json",
  "a05_weights.json",
  "a06_universe_pti.json",
  "a06b_filings.json",
  "a07_repro.json",
  "a08_split.json",
  "a09_events_schema.json",
  "a10_events_lineage.json",
  "a11_events_consistency.json",
]

def status_of(obj):
    # Our check scripts include a "status" key, but we also accept implicit pass/fail by presence of fields.
    if isinstance(obj, dict) and obj.get("status"):
        return obj["status"]
    # Fallback: if 'violations' key exists and is non-empty => FAIL
    if isinstance(obj, dict) and "violations" in obj:
        return "FAIL" if obj["violations"] else "PASS"
    return "PASS"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reports", required=True, help="Carpeta con los JSON de auditoría")
    ap.add_argument("--out-md", default=None, help="Ruta de salida para SUMMARY.md (opcional)")
    args = ap.parse_args()

    reports = pathlib.Path(args.reports)
    found = {}
    passes = []
    fails = []

    for name in REQUIRED:
        p = reports / name
        if not p.exists():
            fails.append((name, "MISSING"))
            continue
        try:
            with open(p, "r", encoding="utf-8") as f:
                obj = json.load(f)
            st = status_of(obj)
            found[name] = obj
            if st == "PASS":
                passes.append(name)
            else:
                fails.append((name, st))
        except Exception as e:
            fails.append((name, f"ERROR: {e}"))

    go = (len(fails) == 0)

    # Build Markdown
    lines = []
    lines.append(f"# Data Certification Summary — {datetime.utcnow().isoformat(timespec='seconds')}Z")
    lines.append("")
    lines.append(f"**GO/NO-GO:** {'✅ GO' if go else '❌ NO-GO'}")
    lines.append("")
    lines.append("## Resultados por check")
    lines.append("")
    for name in REQUIRED:
        badge = "🟢 PASS" if name in passes else "🔴 FAIL"
        lines.append(f"- {badge} `{name}`")
    lines.append("")
    if fails:
        lines.append("## Detalles de fallos")
        lines.append("")
        for name, why in fails:
            lines.append(f"- `{name}` — {why}")
    lines.append("")
    lines.append("## Recomendaciones GO")
    lines.append("1. Asegura A03 con error relativo <0.1% en volumen y dólar.")
    lines.append("2. A06/A06b sin violaciones (universo point-in-time + filings).")
    lines.append("3. A08 sin leakage (purge ≥ 50).")
    lines.append("4. A05 con Σweights=1 y Gini ≤ 0.9.")
    lines.append("5. A09–A11 válidos si usas eventos ML.")
    md = "\\n".join(lines)

    # Output
    if args.out_md:
        pathlib.Path(args.out_md).write_text(md, encoding="utf-8")
    print(md)
    sys.exit(0 if go else 1)

if __name__ == "__main__":
    main()