import os, subprocess, pathlib, sys

def run(cmd):
    print("\n==>", " ".join(cmd))
    return subprocess.call(cmd, shell=False)

def main():
    root = os.environ.get("SC_ROOT", "D:/04_TRADING_SMALLCAPS")
    reports = os.environ.get("SC_REPORTS", f"{root}/reports/audits")
    pathlib.Path(reports).mkdir(parents=True, exist_ok=True)

    cmds = [
        ["python","checks/a01_inventory.py","--root",root,"--out",f"{reports}/a01_inventory.json"],
        ["python","checks/a02_schema.py","--root",root,"--out",f"{reports}/a02_schema.json"],
        ["python","checks/a03_tick2bar_conservation.py","--root",root,"--out",f"{reports}/a03_tick2bar.json","--sample","500","--tol","0.001"],
        ["python","checks/a04_labels_logic.py","--root",root,"--out",f"{reports}/a04_labels.json"],
        ["python","checks/a05_weights_stats.py","--root",root,"--out",f"{reports}/a05_weights.json"],
        ["python","checks/a06_universe_pti.py","--root",root,"--out",f"{reports}/a06_universe_pti.json"],
        ["python","checks/a06b_filings_dilution.py","--root",root,"--out",f"{reports}/a06b_filings.json"],
        ["python","checks/a07_reproducibility.py","--root",root,"--out",f"{reports}/a07_repro.json"],
        ["python","checks/a08_split_purging.py","--root",root,"--out",f"{reports}/a08_split.json","--purge","50"],
        ["python","checks/a09_events_schema.py","--root",root,"--out",f"{reports}/a09_events_schema.json"],
        ["python","checks/a10_events_lineage.py","--root",root,"--out",f"{reports}/a10_events_lineage.json"],
        ["python","checks/a11_events_consistency.py","--root",root,"--out",f"{reports}/a11_events_consistency.json"]
    ]

    fail = 0
    for c in cmds:
        rc = run(c)
        if rc != 0: fail += 1

    print("\nSummary: Failures =", fail)
    sys.exit(fail)

if __name__ == "__main__":
    main()
