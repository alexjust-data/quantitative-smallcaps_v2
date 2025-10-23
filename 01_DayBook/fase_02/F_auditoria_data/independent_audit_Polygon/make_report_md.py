import argparse, json, pathlib, datetime as dt

TEMPLATE = """
# {title}

Date: {date}
Vendor: {vendor}
Symbols: {symbols}
Dates: {dates}

## Summary
Overall match rate: {overall:.2%}
Price tolerance: {price_tol:.2%} | Volume tolerance: {vol_tol:.2%}

## Details by symbol/date
{details}

## Notes
- Times aligned at minute granularity in UTC.
- Differences may arise from vendor-specific filtering (odd lots, late corrections) and rounding.
- This audit is independent from the production pipeline and can be reproduced with the provided JSON and scripts.
"""

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="JSON report from verify_against_reference.py")
    ap.add_argument("--output", required=True, help="Markdown file to write")
    ap.add_argument("--title", default="Independent Verification Report")
    args = ap.parse_args()

    js = json.loads(pathlib.Path(args.input).read_text(encoding="utf-8"))
    lines = []
    for it in js.get("items", []):
        s = f"- {it['symbol']} {it['date']} -> rows={it.get('rows_compared',0)}, match_rate={it.get('match_rate',0.0):.2%}"
        if it.get("rows_compared",0)==0:
            s += " (no data)"
        lines.append(s)
    details = "\n".join(lines)
    md = TEMPLATE.format(
        title=args.title,
        date=dt.date.today().isoformat(),
        vendor=js.get("vendor","?"),
        symbols=", ".join(js.get("symbols", [])),
        dates=", ".join(js.get("dates", [])),
        overall=js.get("overall_match_rate", 0.0),
        price_tol=js.get("price_tol", 0.0),
        vol_tol=js.get("vol_tol", 0.0),
        details=details
    )
    pathlib.Path(args.output).write_text(md, encoding="utf-8")
    print(f"Wrote {args.output}")

if __name__ == "__main__":
    main()
