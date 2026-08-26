#!/usr/bin/env python3
"""Stop-hook gate: refuse to let a Foreman worker finish on an unearned claim.

Anthropic's documented failure mode for multi-agent systems is the early-victory
problem — a worker declaring success after minimal verification. Prompt wording
does not fix it; a hook that blocks the stop does.

Exit 2 on a Stop hook prevents the stop and feeds stderr back to the agent, so it
keeps working. Exit 0 lets it finish.

Only acts on sessions spawned by spawn.sh (FOREMAN_SESSION_DIR is set). Every
other session is untouched.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from foreman_lib import load_json, save_json  # noqa: E402

# A blocking hook that can never be satisfied would trap the agent in a loop.
MAX_BLOCKS = 3


def main() -> int:
    sdir_env = os.environ.get("FOREMAN_SESSION_DIR")
    if not sdir_env:
        return 0
    sdir = Path(sdir_env)
    if not sdir.is_dir():
        return 0

    status = load_json(sdir / "status.json")
    if status.get("agent") not in ("foreman-developer", "foreman-tester"):
        return 0

    blocks = int(status.get("gate_blocks", 0))
    if blocks >= MAX_BLOCKS:
        # Stop insisting; the manager will catch it at the gate instead.
        return 0

    brief = (sdir / "brief.md").read_text(errors="replace") if (sdir / "brief.md").exists() else ""
    m = re.search(r"^\*\*Task file\*\*\s*(.+)$", brief, re.M)
    if not m:
        return 0
    task_path = Path(m.group(1).strip())
    if not task_path.is_absolute():
        task_path = Path(status.get("cwd", ".")) / task_path
    if not task_path.exists():
        return 0

    text = task_path.read_text(errors="replace")
    acc = re.search(r"^##\s+Acceptance.*?$(.*?)(?=^##\s|\Z)", text, re.M | re.S)
    if not acc:
        return 0
    boxes = re.findall(r"^\s*-\s+\[([ xX])\]", acc.group(1), re.M)
    if not boxes:
        return 0

    unchecked = sum(1 for b in boxes if b == " ")
    log = re.search(r"^##\s+Activity log(.*)$", text, re.M | re.S)
    log_body = (log.group(1).strip() if log else "")

    problems = []
    if unchecked:
        problems.append(
            f"{unchecked} of {len(boxes)} acceptance criteria in {task_path.name} are still "
            f"unchecked. Either satisfy them or report a blocker — do not stop in between."
        )
    if not log_body:
        problems.append(
            f"The Activity log in {task_path.name} is empty. Record the Verify command you "
            f"ran and paste its real output; a claim of success without it is not evidence."
        )

    if not problems:
        return 0

    status["gate_blocks"] = blocks + 1
    save_json(sdir / "status.json", status)
    print("[foreman gate] Not done yet:\n- " + "\n- ".join(problems), file=sys.stderr)
    return 2


if __name__ == "__main__":
    try:
        sys.stdin.read()  # drain the payload; we read state from disk
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001 — a broken hook must never trap a session
        print(f"[foreman] verify_gate error: {exc}", file=sys.stderr)
        sys.exit(0)
