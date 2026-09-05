#!/usr/bin/env python3
"""Resolve only structured task bookkeeping conflicts during an integration rebase."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from foreman_lib import atomic_write, parse_task, run
from ops import WorkflowError, set_field


def merge_text(ours: str, base: str, theirs: str) -> str:
    with tempfile.TemporaryDirectory(prefix="foreman-task-merge-") as tmp:
        paths = [Path(tmp) / name for name in ("ours.md", "base.md", "theirs.md")]
        for path, body in zip(paths, (ours, base, theirs)):
            path.write_text(body)
        p = subprocess.run(["git", "merge-file", "-p", *map(str, paths)], capture_output=True, text=True)
        if p.returncode:
            raise WorkflowError("task content conflict requires review")
        return p.stdout


def merge_task(ours: str, base: str, theirs: str) -> str:
    with tempfile.TemporaryDirectory(prefix="foreman-task-schema-") as tmp:
        parsed = []
        for i, body in enumerate((ours, base, theirs)):
            path = Path(tmp) / f"{i}.md"
            path.write_text(body)
            task = parse_task(path)
            if task["problems"]:
                raise WorkflowError("task schema conflict: " + "; ".join(task["problems"]))
            parsed.append(task)
        if len({p["id"] for p in parsed}) != 1:
            raise WorkflowError("task IDs differ across merge stages")
    # Only these manager-owned header fields are normalized. Changes to task
    # scope, requirements and acceptance remain a real three-way merge.
    normalized = []
    logs = []
    for text in (ours, base, theirs):
        text = set_field(set_field(text, "Status", "`[t]`"), "Session", "merge")
        body, sep, activity = text.partition("\n## Activity log")
        if not sep:
            raise WorkflowError("task has no Activity log")
        normalized.append(body)
        logs.append(activity)
    body = merge_text(*normalized)
    main_log, base_log, worker_log = logs
    if main_log.startswith(base_log) and worker_log.startswith(base_log):
        extra_main, extra_worker = main_log[len(base_log):], worker_log[len(base_log):]
        activity = base_log + extra_main
        if extra_worker != extra_main:
            activity += extra_worker
    else:
        activity = merge_text(main_log, base_log, worker_log)
    text = body.rstrip() + "\n## Activity log" + activity
    text = set_field(text, "Session", parsed[0]["session"] or "—")
    # A manager may have falsified an acceptance criterion while G4 ran. Keep
    # that change, and refuse the merge rather than restoring a stale checkmark.
    with tempfile.TemporaryDirectory(prefix="foreman-task-check-") as tmp:
        path = Path(tmp) / "merged.md"
        path.write_text(text)
        merged = parse_task(path)
        if merged["problems"] or merged["acceptance_done"] != merged["acceptance_total"]:
            raise WorkflowError("merged task has invalid or unchecked acceptance; re-test it")
    return text


def resolve_rebase(cwd: Path) -> None:
    while True:
        rc, raw, _ = run(["git", "-C", str(cwd), "diff", "--name-only", "--diff-filter=U"])
        paths = raw.splitlines()
        if rc or not paths:
            raise WorkflowError("rebase failed without a resolvable task conflict")
        if any(not (p.startswith(".foreman/modules/") and "/tasks/" in p and p.endswith(".md")) for p in paths):
            raise WorkflowError("conflicts include non-task files; preserve for review")
        outputs = {}
        for path in paths:
            stages = []
            for stage in (2, 1, 3):
                rc, body, err = run(["git", "-C", str(cwd), "show", f":{stage}:{path}"])
                if rc:
                    raise WorkflowError(err)
                stages.append(body)
            outputs[path] = merge_task(*stages)
        for path, body in outputs.items():
            atomic_write(cwd / path, body)
        p = subprocess.run(["git", "-C", str(cwd), "add", "--", *paths], capture_output=True, text=True)
        if p.returncode:
            raise WorkflowError(p.stderr)
        p = subprocess.run(["git", "-C", str(cwd), "rebase", "--continue"],
                           capture_output=True, text=True, env={**os.environ, "GIT_EDITOR": "true"})
        if p.returncode == 0:
            return


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--worktree", required=True)
    args = ap.parse_args()
    try:
        resolve_rebase(Path(args.worktree))
    except (WorkflowError, OSError) as exc:
        sys.exit(f"task merge: {exc}")
