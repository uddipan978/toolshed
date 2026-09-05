#!/usr/bin/env python3
"""Durable, deduplicated G4/G5 triage. Findings do not automatically grow scope."""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
import time
from pathlib import Path

from foreman_lib import atomic_write, load_json, save_json
from ops import WorkflowError, lock, read_document


def record(root: Path, *, severity: int, place: str, description: str, evidence: str,
           acceptance: bool = False, source: str = "", task: str = "") -> dict:
    if type(severity) is not int or severity not in range(5):
        raise WorkflowError("severity must be 0..4")
    if not all(x.strip() for x in (place, description, evidence)):
        raise WorkflowError("place, description and concrete evidence are required")
    # The same issue from another tester updates the ledger; it is not another task.
    key = hashlib.sha256((place.strip().lower() + "\n" + description.strip().lower()).encode()).hexdigest()[:16]
    with lock(root):
        path = root / "findings.json"
        data = read_document(path) if path.is_file() else {"version": 1, "findings": []}
        existing = next((f for f in data["findings"] if f["id"] == key), None)
        route = "fix-task" if severity >= 3 or acceptance else "known"
        if existing:
            existing["severity"] = max(existing["severity"], severity)
            existing["acceptance"] = existing.get("acceptance", False) or acceptance
            if route == "fix-task":
                existing["route"] = route
            existing["observations"].append({"source": source, "evidence": evidence})
            result = existing
        else:
            result = {"id": key, "severity": severity, "acceptance": acceptance,
                      "place": place, "description": description, "route": route,
                      "task": task, "status": "open", "created_at": time.time(),
                      "observations": [{"source": source, "evidence": evidence}]}
            data["findings"].append(result)
        save_json(path, data)
        rows = ["# Known issues", "", "Deferred does not mean accepted by the user.", ""]
        for f in data["findings"]:
            rows += [f"## {f['id']} — {f['description']}", "",
                     f"Severity {f['severity']} · {f['route']} · {f['status']}", "",
                     f"Place: {f['place']}", f"Task: {f.get('task') or 'unassigned'}", "",
                     f"Evidence: {f['observations'][-1]['evidence']}", ""]
        atomic_write(root / "KNOWN-ISSUES.md", "\n".join(rows))
    return result


def ingest_beta(root: Path, sdir: Path) -> list[dict]:
    from verify_gate import BETA_FINDING, FIELD_LINE
    text = (sdir / "beta-review.md").read_text()
    heads = list(BETA_FINDING.finditer(text))
    findings = []
    for i, head in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        fields = {k.lower(): v.strip() for k, v in FIELD_LINE.findall(text[head.end():end])}
        findings.append(record(root, severity=int(fields["severity"]), place=fields["place"],
                               description=fields["fix"], evidence=fields.get("evidence", f"{sdir.name}/{head[1]}: {fields['place']}"),
                               source=f"{sdir.name}/{head[1]}", acceptance=fields.get("acceptance", "").lower() == "yes"))
    return findings


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=".foreman")
    ap.add_argument("--severity", type=int, required=True)
    ap.add_argument("--place", required=True)
    ap.add_argument("--description", required=True)
    ap.add_argument("--evidence", required=True)
    ap.add_argument("--acceptance", action="store_true")
    ap.add_argument("--source", default="")
    ap.add_argument("--task", default="")
    args = ap.parse_args()
    try:
        values = vars(args).copy()
        root = Path(values.pop("root")).resolve()
        finding = record(root, **values)
        from refresh import refresh
        refresh(root)
        print(f"{finding['id']}: {finding['route']} (no task created automatically)")
    except (WorkflowError, OSError) as exc:
        sys.exit(f"findings: {exc}")
