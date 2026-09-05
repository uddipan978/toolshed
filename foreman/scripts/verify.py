#!/usr/bin/env python3
"""Execute the task's Verify command and bind real output to its product files."""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys
import time

from foreman_lib import atomic_write, parse_task, run, save_json
from ops import WorkflowError, read_document


def task_for_session(sdir: Path, status: dict) -> Path:
    text = (sdir / "brief.md").read_text()
    matches = re.findall(r"^\*\*Task file\*\*[ \t]*([^\n]+)$", text, re.M)
    if len(matches) != 1:
        raise WorkflowError("Verify requires exactly one Task file")
    cwd = Path(status["cwd"]).resolve()
    path = Path(matches[0].strip().strip("`"))
    path = path if path.is_absolute() else cwd / path
    if not path.resolve().is_relative_to(cwd):
        raise WorkflowError("task must be in worker checkout")
    return path


def command_for_task(path: Path) -> str:
    match = re.search(r"^## Verify\s*\n```(?:bash|sh)?\n(.*?)\n```", path.read_text(), re.M | re.S)
    if not match or not match[1].strip() or match[1].strip().startswith("#"):
        raise WorkflowError("task requires a runnable Verify command")
    return match[1].strip()


def product_digest(cwd: Path, task: dict) -> str:
    rc, raw, err = run(["git", "-C", str(cwd), "ls-files", "-z", "--cached", "--others", "--exclude-standard"])
    if rc:
        raise WorkflowError(err)
    entries = []
    for name in sorted(set(raw.split("\0"))):
        if not name or name.startswith(".foreman/") or not any(fnmatch.fnmatch(name, pattern) for pattern in task.get("files", [])):
            continue
        path = cwd / name
        if path.is_symlink():
            content = os.readlink(path).encode()
        elif path.is_file():
            content = path.read_bytes()
        elif not path.exists():
            content = b"<deleted>"
        else:
            continue
        entries.append(name + "\0" + hashlib.sha256(content).hexdigest())
    return hashlib.sha256("\n".join(entries).encode()).hexdigest()


def record(sdir: Path) -> int:
    status = read_document(sdir / "status.json")
    path = task_for_session(sdir, status)
    task = parse_task(path)
    command = command_for_task(path)
    started = time.time()
    try:
        result = subprocess.run(["bash", "-c", command], cwd=status["cwd"], capture_output=True, text=True, timeout=600)
        rc, output = result.returncode, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        rc, output = 124, "Verify command timed out after 600 seconds"
    body = f"# Verify output\n\n$ {command}\n\nExit: {rc}\n\n{output}\n"
    atomic_write(sdir / "verify-output.md", body)
    save_json(sdir / "verification.json", {"task": task["id"], "command": command,
              "started_at": started, "finished_at": time.time(), "returncode": rc,
              "product_digest": product_digest(Path(status["cwd"]), task),
              "output_digest": hashlib.sha256(body.encode()).hexdigest()})
    print(output, end="" if output.endswith("\n") else "\n")
    return rc


def evidence_problems(sdir: Path, status: dict) -> list[str]:
    try:
        evidence = read_document(sdir / "verification.json")
        path = task_for_session(sdir, status)
        task = parse_task(path)
        problems = []
        if evidence.get("returncode") != 0:
            problems.append("recorded Verify did not pass")
        if evidence.get("task") != task["id"] or evidence.get("command") != command_for_task(path):
            problems.append("Verify record belongs to a different task/command")
        if evidence.get("product_digest") != product_digest(Path(status["cwd"]), task):
            problems.append("product changed after Verify; rerun verify.py")
        if hashlib.sha256((sdir / "verify-output.md").read_bytes()).hexdigest() != evidence.get("output_digest"):
            problems.append("Verify output changed after recording")
        return problems
    except (OSError, WorkflowError) as exc:
        return [f"run verify.py to record actual Verify evidence: {exc}"]


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--session-dir", default=os.environ.get("FOREMAN_SESSION_DIR"))
    args = ap.parse_args()
    if not args.session_dir:
        ap.error("--session-dir or FOREMAN_SESSION_DIR is required")
    try:
        sys.exit(record(Path(args.session_dir)))
    except (WorkflowError, OSError) as exc:
        sys.exit(f"verify: {exc}")
