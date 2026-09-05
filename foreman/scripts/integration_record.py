#!/usr/bin/env python3
"""Archive verified G4 evidence and reconcile state before worktree retirement."""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from foreman_lib import atomic_write, run
from ops import WorkflowError, identifier, lock, read_document, session_alive, update_session
from state import archive, transition


def verify_replay(root: Path, name: str) -> None:
    sdir = root / "work" / "sessions" / identifier(name)
    status = read_document(sdir / "status.json")
    if not status.get("task_ids"):
        return  # pre-managed legacy compatibility; documented in the receipt
    brief = (sdir / "brief.md").read_text()
    match = re.search(r"^\*\*Task file\*\*\s*([^\n]+)", brief, re.M)
    if not match:
        raise WorkflowError("integration needs a task file and runnable Verify")
    path = Path(match[1].strip().strip("`"))
    path = path if path.is_absolute() else Path(status["cwd"]) / path
    command = re.search(r"^## Verify\s*\n```(?:bash|sh)?\n(.*?)\n```", path.read_text(), re.M | re.S)
    if not command or not command[1].strip() or command[1].strip().startswith("#"):
        raise WorkflowError("integration needs a runnable Verify command")
    result = subprocess.run(["bash", "-c", command[1]], cwd=status["cwd"],
                            capture_output=True, text=True, timeout=600)
    atomic_write(sdir / "integration-verify.md", f"# Integration verification\n\n**Verdict** {'pass' if result.returncode == 0 else 'fail'}\n\n"
                 f"```bash\n{command[1]}\n```\n\nExit: {result.returncode}\n\n{result.stdout}\n{result.stderr}\n")
    if result.returncode:
        raise WorkflowError("verification failed after replay; main branch was not advanced. Original tested commit is retained under refs/foreman/tested/" + name)


def finish(root: Path, name: str) -> None:
    sdir = root / "work" / "sessions" / identifier(name)
    status = read_document(sdir / "status.json")
    head = run(["git", "-C", str(root.parent), "rev-parse", "HEAD"])[1].strip()
    tested = run(["git", "-C", str(root.parent), "rev-parse", f"refs/foreman/tested/{name}"])[1].strip()
    ids = status.get("task_ids", [])
    archive(root, sdir, gate="G4" if status.get("agent", "").split(":")[-1] == "foreman-tester" else "G3-legacy",
            task_ids=ids, integrated=head, tested_head=tested)
    # The worker task is already [t] in the integrated tree. The receipt is
    # durable before [b], so an interrupted finish can be repaired idempotently.
    for tid in ids:
        transition(root, tid, "beta", session=name, regenerate=False)
    update_session(sdir, integrated_at=time.time(), integrated_head=head, tested_head=tested)
    predecessor = status.get("base_session")
    if predecessor:
        pred_dir = root / "work" / "sessions" / identifier(predecessor)
        pred = read_document(pred_dir / "status.json")
        archive(root, pred_dir, gate="G3" if pred.get("task_ids") else "G3-legacy", task_ids=pred.get("task_ids", []))
        from foreman_lib import git_status_paths
        included = pred.get("branch") and run(["git", "-C", str(root.parent), "merge-base", "--is-ancestor", pred["branch"], tested])[0] == 0
        if included and not session_alive(pred) and not git_status_paths(Path(pred.get("cwd") or root.parent)):
            update_session(pred_dir, retired_at=time.time(), disposition=f"tested and integrated by {name}")
    from refresh import refresh
    refresh(root)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=("verify", "finish", "run"))
    ap.add_argument("--root", default=".foreman")
    ap.add_argument("--name", required=True)
    ap.add_argument("--base")
    ap.add_argument("--keep-worktree", action="store_true")
    args = ap.parse_args()
    try:
        root = Path(args.root).resolve()
        if args.command == "run":
            command = ["bash", str(Path(__file__).with_name("integrate.sh")), "--root", str(root), "--name", args.name]
            if args.base:
                command += ["--base", args.base]
            if args.keep_worktree:
                command += ["--keep-worktree"]
            with lock(root, "launch"):
                sys.exit(subprocess.run(command, env={**os.environ, "FOREMAN_INTEGRATION_LOCK": "1"}).returncode)
        (verify_replay if args.command == "verify" else finish)(root, args.name)
    except (WorkflowError, OSError, subprocess.TimeoutExpired) as exc:
        sys.exit(f"integration: {exc}")
