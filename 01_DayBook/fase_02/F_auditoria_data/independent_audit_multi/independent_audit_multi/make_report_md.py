import argparse, json, pathlib, datetime as dt

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--title", default="Independent Verification Report (Multi‑Vendor)")
    args = ap.parse_args()

    js = json.loads(pathlib.Path(args.input).read_text(encoding="utf-8"))
    vendors = js.get("vendors", [])
    overall = js.get("overall_match_rate", {})
    items = js.get("items", [])

    lines = []
    for it in items:
        s = [f"- {it['symbol']} {it['date']}"]
        for v in vendors:
            vi = it["vendors"].get(v, {})
            if "error" in vi:
                s.append(f"  · {v}: ERROR ({vi['error']})")
            else:
                s.append(f"  · {v}: rows={vi.get('rows_compared',0)}, match_rate={vi.get('match_rate',0.0):.2%}")
        lines.append("\n".join(s))
    details = "\n".join(lines)

    overall_lines = [f"- {v}: {overall.get(v,0.0):.2%}" for v in vendors]
    overall_txt = "\n".join(overall_lines)

    md = f"""# {args.title}

Date: {dt.date.today().isoformat()}
Vendors: {", ".join(vendors)}
Symbols: {", ".join(js.get("symbols", []))}
Dates: {", ".join(js.get("dates", []))}

## Overall Match Rates
{overall_txt}

## Details by symbol/date
{details}

## Notes
- Timezone: UTC, aligned to minute.
- Tolerances: price {js.get('price_tol',0.0):.2%}, volume {js.get('vol_tol',0.0):.2%}.
- Vendors included may have different eligibility rules; discrepancies should be investigated with sale-condition policies if needed.
"""
    pathlib.Path(args.output).write_text(md, encoding="utf-8")
    print(f"Wrote {args.output}")

if __name__ == "__main__":
    main()
