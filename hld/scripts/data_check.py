#!/usr/bin/env python3
"""data_check.py — dataset schema + provenance check. Ships in the same commit as the
data it validates. Exit 0 ok / 2 fail. Stdlib only."""
import csv
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
GRADES = {"replicated", "contested", "null-result", "heuristic", "my-inference"}
HLT_FILES = ["principles.csv", "symptoms.csv", "conflicts.csv", "effort-weights.csv"]
AUTHORED = {
    "slop-rules.csv": ["id", "family", "requires_contract", "pattern_kind",
                       "pattern", "severity", "note", "provenance", "grade"],
    "effort-cases.csv": ["id", "size", "expected_bands", "expected_test_kinds",
                         "note", "provenance", "grade"],
}


def rows(name):
    with open(DATA / name, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def main():
    errs = []
    for name in HLT_FILES:
        p = DATA / name
        if not p.is_file():
            errs.append(f"{name}: missing (absorbed from human-like-thinking)")
            continue
        if not rows(name):
            errs.append(f"{name}: no data rows")
    for name, cols in AUTHORED.items():
        p = DATA / name
        if not p.is_file():
            errs.append(f"{name}: missing")
            continue
        rws = rows(name)
        if not rws:
            errs.append(f"{name}: no data rows")
            continue
        got = list(rws[0].keys())
        if got != cols:
            errs.append(f"{name}: columns {got} != expected {cols}")
            continue
        for r in rws:
            if not (r["provenance"] or "").strip():
                errs.append(f"{name} {r['id']}: empty provenance")
            if r["grade"] not in GRADES:
                errs.append(f"{name} {r['id']}: grade '{r['grade']}' not in {sorted(GRADES)}")
    if errs:
        print("data_check FAIL:")
        for e in errs:
            print(f"  - {e}")
        return 2
    print(f"data_check: ok ({len(HLT_FILES) + len(AUTHORED)} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
