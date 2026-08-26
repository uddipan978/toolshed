#!/usr/bin/env python3
"""Foreman dependency preflight: probe, install, report.

Foreman assumes nothing is present. Every run probes each dependency, installs
what is missing from a verified source, and prints exactly what changed.

  preflight.py [--dry-run] [--quiet] [--json]

Policy:
  - Install silently, report after. Never block the run to ask.
  - Never install from an unverified source. A dependency whose upstream could
    not be confirmed is reported to the user as a decision, not silently skipped.
  - Never write a semver constraint for impeccable or ui-ux-pro-max. Version
    resolution needs {plugin-name}--v{version} git tags; those repos tag as
    skill-v4.1.2 and v2.15.0, so a constrained install hard-fails with
    "has no git tag satisfying ...".
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from foreman_lib import load_json, run, save_json  # noqa: E402

OK, MISSING, FAILED, SKIPPED = "ok", "missing", "failed", "skipped"

# Marketplaces that must exist before their plugins can resolve.
MARKETPLACES = {
    "claude-plugins-official": "anthropics/claude-plugins-official",
    "claude-community": "anthropics/claude-plugins-community",
    "ui-ux-pro-max-skill": "nextlevelbuilder/ui-ux-pro-max-skill",
    "mattpocock": "mattpocock/skills",
}

# Every entry here has a verified upstream. See reference/troubleshooting.md for
# the sources that were rejected and why.
PLUGINS = [
    ("impeccable",        "claude-community",         "G5 design audit, critique and a11y vocabulary"),
    ("ui-ux-pro-max",     "ui-ux-pro-max-skill",      "G5 design-system lookup (3k+ rows of design data)"),
    ("mattpocock-skills", "mattpocock",               "G0 grilling, G1 ticket shape, handover rules, TDD"),
    ("frontend-design",   "claude-plugins-official",  "preventative anti-slop design direction"),
    ("skill-creator",     "claude-plugins-official",  "evals for Foreman's own skills"),
    ("pr-review-toolkit", "claude-plugins-official",  "G3 silent-failure and type-design reviewers"),
    ("session-report",    "claude-plugins-official",  "cost accounting for multi-session runs"),
]

# playwright is deliberately absent: Foreman bundles its own .mcp.json so it can
# pass --caps=testing, which the flagless marketplace plugin cannot.
MCP_SERVERS = [
    ("playwright",      None,                                          "G4 E2E — browser_generate_locator"),
    ("chrome-devtools", ["npx", "chrome-devtools-mcp@latest"],         "G5 Lighthouse, perf traces, a11y"),
]

BINARIES = [("git", None), ("claude", None), ("python3", None), ("node", (22, 18))]


def node_version() -> tuple[int, int] | None:
    rc, out, _ = run(["node", "--version"], timeout=15)
    if rc != 0:
        return None
    m = re.match(r"v(\d+)\.(\d+)", out.strip())
    return (int(m.group(1)), int(m.group(2))) if m else None


def probe_binaries() -> list[dict]:
    rows = []
    for name, minver in BINARIES:
        if not shutil.which(name):
            rows.append({"kind": "binary", "name": name, "status": MISSING,
                         "note": "not on PATH — install it manually"})
            continue
        note = ""
        status = OK
        if name == "node" and minver:
            v = node_version()
            if v and v < minver:
                status = FAILED
                note = (f"v{v[0]}.{v[1]} is below the required "
                        f"{minver[0]}.{minver[1]} — impeccable's hooks silently no-op below it")
            elif v:
                note = f"v{v[0]}.{v[1]}"
        rows.append({"kind": "binary", "name": name, "status": status, "note": note})
    return rows


def installed_plugins() -> set[str]:
    """Parse `claude plugin list`. Entries render as "  ❯ name@marketplace"."""
    rc, out, _ = run(["claude", "plugin", "list"], timeout=90)
    if rc != 0:
        return set()
    return {m.group(1) for m in re.finditer(r"([a-z0-9][a-z0-9._-]*)@[a-z0-9][a-z0-9._-]*", out)}


def known_marketplaces() -> set[str]:
    """Parse `claude plugin marketplace list`. Entries render as "  ❯ name"."""
    rc, out, _ = run(["claude", "plugin", "marketplace", "list"], timeout=90)
    if rc != 0:
        return set()
    return {m.group(1) for m in re.finditer(r"^\s*❯\s+([a-z0-9][a-z0-9._-]*)\s*$", out, re.M)}


def connected_mcp() -> set[str]:
    rc, out, _ = run(["claude", "mcp", "list"], timeout=120)
    if rc != 0:
        return set()
    return {m.group(1).strip() for m in re.finditer(r"^(.+?):\s+.*[✔✓]\s*Connected", out, re.M)}


def ensure_settings_timeout(dry: bool) -> dict:
    """Foreman's 5-minute auto-select needs the question dialog to actually close."""
    path = Path.home() / ".claude" / "settings.json"
    settings = load_json(path, default={})
    current = settings.get("askUserQuestionTimeout")
    if current == "5m":
        return {"kind": "setting", "name": "askUserQuestionTimeout", "status": OK, "note": "already 5m"}
    if dry:
        return {"kind": "setting", "name": "askUserQuestionTimeout", "status": MISSING,
                "note": f"would set to 5m (currently {current or 'unset'})"}
    settings["askUserQuestionTimeout"] = "5m"
    save_json(path, settings)
    return {"kind": "setting", "name": "askUserQuestionTimeout", "status": OK,
            "note": f"set to 5m (was {current or 'unset'})"}


def preflight(dry: bool) -> list[dict]:
    rows = probe_binaries()

    have_mp = known_marketplaces()
    have_pl = installed_plugins()
    for mp_name, source in MARKETPLACES.items():
        if mp_name in have_mp:
            continue
        if dry:
            rows.append({"kind": "marketplace", "name": mp_name, "status": MISSING,
                         "note": f"would add from {source}"})
            continue
        rc, _, err = run(["claude", "plugin", "marketplace", "add", source], timeout=180)
        rows.append({"kind": "marketplace", "name": mp_name,
                     "status": OK if rc == 0 else FAILED,
                     "note": f"added from {source}" if rc == 0 else err.strip()[:160]})

    for name, marketplace, purpose in PLUGINS:
        if name in have_pl:
            rows.append({"kind": "plugin", "name": name, "status": OK, "note": purpose})
            continue
        if dry:
            rows.append({"kind": "plugin", "name": name, "status": MISSING,
                         "note": f"would install from {marketplace} — {purpose}"})
            continue
        # Bare name@marketplace, never a version constraint.
        rc, _, err = run(["claude", "plugin", "install", f"{name}@{marketplace}",
                          "--scope", "user"], timeout=300)
        rows.append({"kind": "plugin", "name": name,
                     "status": OK if rc == 0 else FAILED,
                     "note": purpose if rc == 0 else err.strip()[:160]})

    live = connected_mcp()
    for name, add_cmd, purpose in MCP_SERVERS:
        if name in live:
            rows.append({"kind": "mcp", "name": name, "status": OK, "note": purpose})
        elif add_cmd is None:
            rows.append({"kind": "mcp", "name": name, "status": OK,
                         "note": f"{purpose} (bundled by foreman/.mcp.json)"})
        elif dry:
            rows.append({"kind": "mcp", "name": name, "status": MISSING,
                         "note": f"would add: claude mcp add {name} -- {' '.join(add_cmd)}"})
        else:
            rc, _, err = run(["claude", "mcp", "add", name, "--"] + add_cmd, timeout=180)
            rows.append({"kind": "mcp", "name": name,
                         "status": OK if rc == 0 else FAILED,
                         "note": purpose if rc == 0 else err.strip()[:160]})

    rows.append(ensure_settings_timeout(dry))
    return rows


def report(rows: list[dict], dry: bool) -> int:
    icons = {OK: "ok  ", MISSING: "MISS", FAILED: "FAIL", SKIPPED: "skip"}
    print(f"\nForeman preflight{' (dry run — nothing changed)' if dry else ''}\n")
    width = max((len(r["name"]) for r in rows), default=10)
    for r in rows:
        print(f"  [{icons[r['status']]}] {r['kind']:<11} {r['name']:<{width}}  {r['note']}")

    failed = [r for r in rows if r["status"] == FAILED]
    missing = [r for r in rows if r["status"] == MISSING]
    print()
    if failed:
        print(f"  {len(failed)} dependency/dependencies could not be satisfied. "
              "Foreman needs a decision before continuing:")
        for r in failed:
            print(f"    - {r['name']}: {r['note']}")
        return 1
    if dry and missing:
        print(f"  {len(missing)} would be installed. Re-run without --dry-run.")
        return 0
    print("  All dependencies satisfied." if not missing else f"  {len(missing)} still missing.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--quiet", action="store_true", help="only print when something is wrong")
    a = ap.parse_args()

    try:
        rows = preflight(a.dry_run)
    except Exception as exc:  # noqa: BLE001
        print(f"[foreman] preflight error: {exc}", file=sys.stderr)
        sys.exit(0)  # never take a session down

    if a.json:
        print(json.dumps(rows, indent=2))
        sys.exit(0)
    if a.quiet and all(r["status"] == OK for r in rows):
        sys.exit(0)
    sys.exit(report(rows, a.dry_run))
