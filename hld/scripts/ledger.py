#!/usr/bin/env python3
"""ledger.py — the path-pinned effort ledger (.hld/ledger.json, TRACKED — H4 replays it).

The H1 walk logs every step it actually took. Once pinned, H4's replay must reproduce
the path; divergence is a DIVERGED-PATH verdict, not a silent pass.

Usage:
  ledger.py init  [--root DIR]
  ledger.py log   "<step>" [--root DIR]        (refused after pin)
  ledger.py pin   [--root DIR]
  ledger.py verify --against FILE [--root DIR]  (one replayed step per line)
  ledger.py show  [--root DIR]

Exit 0 ok · 2 error/DIVERGED-PATH. Stdlib only.
"""
import json
import sys
from pathlib import Path


def ledger_path(root):
    p = Path(root)
    hld = p if p.name == ".hld" else p / ".hld"
    return hld / "ledger.json"


def load(lp):
    return json.loads(lp.read_text()) if lp.is_file() else {"pinned": False, "steps": []}


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    args = dict(zip(argv, argv[1:]))
    lp = ledger_path(args.get("--root", "."))
    cmd = argv[0]
    led = load(lp)
    if cmd == "init":
        if led["pinned"] and "--force" not in argv:
            print(f"REFUSED: {lp} is pinned evidence — H4 replays it. "
                  "Pass --force only if you truly mean to destroy the pinned path.")
            return 2
        lp.parent.mkdir(parents=True, exist_ok=True)
        lp.write_text(json.dumps({"pinned": False, "steps": []}, indent=2))
        print(f"ledger initialized at {lp}")
        return 0
    if cmd == "log":
        if led["pinned"]:
            print("ledger is pinned — the path is frozen; a changed path at H4 is a "
                  "DIVERGED-PATH verdict, not a new log entry")
            return 2
        # the step is the first non-flag argument (flags may come first)
        rest = argv[1:]
        step = None
        i = 0
        while i < len(rest):
            if rest[i].startswith("--"):
                i += 2  # skip the flag and its value
                continue
            step = rest[i]
            break
        if not step:
            print("log needs a step description")
            return 2
        led["steps"].append(step)
        lp.write_text(json.dumps(led, indent=2))
        print(f"step {len(led['steps'])}: {step}")
        return 0
    if cmd == "pin":
        led["pinned"] = True
        lp.write_text(json.dumps(led, indent=2))
        print(f"pinned {len(led['steps'])} steps")
        return 0
    if cmd == "verify":
        if "--against" not in args:
            print("verify needs --against <file> (one replayed step per line)")
            return 2
        replay = [ln.strip() for ln in
                  Path(args["--against"]).read_text().splitlines() if ln.strip()]
        pinned = led["steps"]
        for i, (a, b) in enumerate(zip(pinned, replay), 1):
            if a != b:
                print(f"DIVERGED-PATH at step {i}:\n  pinned: {a}\n  replay: {b}")
                return 2
        if len(pinned) != len(replay):
            print(f"DIVERGED-PATH: pinned {len(pinned)} steps, replay {len(replay)}")
            return 2
        print(f"PATH-MATCH: {len(pinned)} steps")
        return 0
    if cmd == "show":
        print(json.dumps(led, indent=2))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
