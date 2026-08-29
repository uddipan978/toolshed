#!/usr/bin/env python3
"""lookup.py — runtime lookup into ui-ux-pro-max's tables WHEN PRESENT. HLD never
copies those CSVs (no license in their tree); it queries them on machines that have
the skill installed, and records COULD-NOT-RUN where they're absent.

Usage: lookup.py palette|type|ux|style <query terms...>
Exit 0 (results or a recorded absence). Stdlib only.
"""
import csv
import os
import sys
from pathlib import Path

HOMES = [os.environ.get("HLD_PROMAX_DATA", ""),
         "~/.agents/skills/ui-ux-pro-max/data",
         "~/.claude/skills/ui-ux-pro-max/data"]
FILES = {"palette": "colors.csv", "type": "typography.csv",
         "ux": "ux-guidelines.csv", "style": "styles.csv"}


def data_dir():
    for h in HOMES:
        if h and Path(h).expanduser().is_dir():
            return Path(h).expanduser()
    return None


def main(argv):
    if len(argv) < 2 or argv[0] not in FILES:
        print(__doc__)
        return 0
    d = data_dir()
    if d is None:
        print("COULD-NOT-RUN: ui-ux-pro-max not installed on this host "
              "(lookups are optional; the contract still rules)")
        return 0
    path = d / FILES[argv[0]]
    if not path.is_file():
        print(f"COULD-NOT-RUN: {path.name} not found in {d}")
        return 0
    terms = [t.lower() for t in argv[1:]]
    hits = 0
    with open(path, newline="", encoding="utf-8", errors="replace") as fh:
        for row in csv.reader(fh):
            joined = " ".join(row).lower()
            if all(t in joined for t in terms):
                print(" | ".join(row)[:300])
                hits += 1
                if hits >= 12:
                    print("... (capped at 12 rows)")
                    break
    if not hits:
        print(f"no rows in {path.name} match: {' '.join(terms)}")
    print(f"[source: {path} — third-party data, cite as 'pro-max lookup' with grade heuristic]")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
