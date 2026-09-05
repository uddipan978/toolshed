#!/usr/bin/env python3
"""Guarded manager task transitions, evidence receipts, and automatic projections."""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
import time
from pathlib import Path

from foreman_lib import LEGEND, append_log, atomic_write, load_json, run, save_json
from ops import (WorkflowError, brief_task, identifier, lock, mark_views_dirty,
                 read_document, session_alive, set_field, task_index, update_session)

TRANSITIONS = {
    "backlog": {"planned", "in_progress", "blocked", "awaiting_human"},
    "planned": {"backlog", "in_progress", "blocked", "awaiting_human"},
    "in_progress": {"in_test", "blocked", "awaiting_human"},
    "in_test": {"in_progress", "beta", "blocked", "awaiting_human"},
    "beta": {"in_progress", "done", "blocked", "awaiting_human"},
    "done": {"in_progress"},
    "blocked": {"backlog", "planned", "in_progress", "in_test", "beta", "awaiting_human"},
    "awaiting_human": {"backlog", "planned", "in_progress", "in_test", "beta", "blocked"},
}


def receipt_path(root: Path, name: str) -> Path:
    return root / "evidence" / identifier(name) / "receipt.json"


def archive(root: Path, sdir: Path, *, gate: str, task_ids: list[str], integrated: str = "",
            tested_head: str = "") -> dict:
    """Call only after pass validation and before deleting a tested worktree."""
    status = read_document(sdir / "status.json")
    dest = receipt_path(root, sdir.name).parent
    files = {}
    for name in ("brief.md", "testcases.md", "results.md", "beta-review.md", "integration-verify.md", "verification.json", "verify-output.md"):
        source = sdir / name
        if source.is_file():
            text = source.read_text()
            atomic_write(dest / name, text)
            files[name] = hashlib.sha256(text.encode()).hexdigest()
    receipt = {"version": 1, "gate": gate, "session": sdir.name, "tasks": task_ids,
               "recorded_at": time.time(), "tested_head": tested_head or status.get("start_commit"),
               "integrated_head": integrated, "files": files}
    save_json(dest / "receipt.json", receipt)
    return receipt


def check_receipt(root: Path, name: str, gate: str, tid: str) -> dict:
    path = receipt_path(root, name)
    receipt = read_document(path)
    if receipt.get("gate") != gate or tid not in receipt.get("tasks", []):
        raise WorkflowError(f"{name} has no {gate} receipt for {tid}")
    for filename, digest in receipt.get("files", {}).items():
        data = (path.parent / filename).read_bytes()
        if hashlib.sha256(data).hexdigest() != digest:
            raise WorkflowError(f"{name}: archived evidence changed: {filename}")
    if gate == "G4":
        commit = receipt.get("integrated_head")
        if not commit or run(["git", "-C", str(root.parent), "merge-base", "--is-ancestor", commit, "HEAD"])[0]:
            raise WorkflowError(f"{name}: integrated commit is not on the current branch")
    elif gate == "G5":
        tested = receipt.get("tested_head")
        rc, changed, _ = run(["git", "-C", str(root.parent), "diff", "--name-only", tested or "", "--", ".", ":(exclude).foreman"])
        if rc or changed.strip():
            raise WorkflowError(f"{name}: product changed after G5; review the current product before closing")
    return receipt


def transition(root: Path, tid: str, to: str, *, session: str = "", reason: str = "",
               regenerate: bool = True, _launch: bool = False) -> None:
    if to in LEGEND:
        to = LEGEND[to]
    if to not in TRANSITIONS:
        raise WorkflowError(f"unknown task status {to}")
    with lock(root):
        task = task_index(root).get(tid)
        if not task:
            raise WorkflowError(f"unknown task {tid}")
        old = task["status"]
        if to != old and to not in TRANSITIONS[old]:
            raise WorkflowError(f"illegal transition {tid}: {old} -> {to}")
        if to in ("blocked", "awaiting_human") or (to == "in_progress" and old in ("in_test", "beta", "done")):
            if not reason.strip():
                raise WorkflowError("blocking/reopening a task requires a recorded --reason")
        if to == "in_progress" and not _launch:
            raise WorkflowError("in-progress is recorded by spawn.sh only after a validated launch reservation")
        if to == "in_test":
            if not session:
                raise WorkflowError("G3 evidence session is required")
            from verify_gate import session_pass_problems
            sdir = root / "work" / "sessions" / identifier(session)
            status = read_document(sdir / "status.json")
            if status.get("agent", "").split(":")[-1] != "foreman-developer" or session_alive(status):
                raise WorkflowError("G3 needs a stopped developer")
            evidence_task = brief_task(root, (sdir / "brief.md").read_text(), Path(status["cwd"]))
            problems = session_pass_problems(sdir, status)
            if evidence_task["id"] != tid or problems:
                raise WorkflowError("G3 evidence does not pass for this task: " + "; ".join(problems))
        elif to == "beta":
            check_receipt(root, session, "G4", tid)
        elif to == "done":
            check_receipt(root, session, "G5", tid)
        text = task["path"].read_text()
        token = next(k for k, v in LEGEND.items() if v == to)
        text = set_field(text, "Status", f"`[{token}]`")
        if session:
            text = set_field(text, "Session", identifier(session))
        if "\n## Activity log" not in text:
            text += "\n## Activity log\n"
        text += f"\n- {time.strftime('%Y-%m-%d %H:%M:%S')} {old} -> {to}; session={session or 'manager'}; {reason or 'gate verified'}\n"
        mark_views_dirty(root)
        atomic_write(task["path"], text)
        append_log(root, f"{tid}: {old} -> {to}; {reason or session}")
    if regenerate:
        from refresh import refresh
        refresh(root)


def finish_beta(root: Path, name: str) -> None:
    with lock(root, "launch"):
        _finish_beta(root, name)


def _finish_beta(root: Path, name: str) -> None:
    from delivery import active_sprint
    from findings import ingest_beta
    from verify_gate import session_pass_problems
    sdir = root / "work" / "sessions" / identifier(name)
    status = read_document(sdir / "status.json")
    if status.get("agent", "").split(":")[-1] != "foreman-beta-tester" or session_alive(status):
        raise WorkflowError("G5 requires a stopped beta tester")
    problems = session_pass_problems(sdir, status)
    if problems:
        raise WorkflowError("; ".join(problems))
    ids = status.get("task_ids", [])
    if not ids:
        raise WorkflowError("beta session has no recorded task scope")
    sprint = active_sprint(root)
    tasks = task_index(root)
    if any(t not in sprint["tasks"] or tasks[t]["status"] != "beta" for t in ids):
        raise WorkflowError("beta scope must consist of active sprint tasks that passed G4")
    current_tree = run(["git", "-C", str(root.parent), "rev-parse", "HEAD^{tree}"])[1].strip()
    # Only product paths matter: manager task/status writes are expected during G5.
    base = status.get("base_commit")
    rc, diff, _ = run(["git", "-C", str(root.parent), "diff", "--name-only", base or "", "--", ".", ":(exclude).foreman"])
    if rc or diff.strip():
        raise WorkflowError("product changed since beta launch; re-run G5 against the current product")
    ingest_beta(root, sdir)
    archive(root, sdir, gate="G5", task_ids=ids, integrated=current_tree)
    for tid in ids:
        transition(root, tid, "done", session=name, regenerate=False)
    update_session(sdir, retired_at=time.time(), disposition="G5 passed")
    cwd = Path(status.get("cwd") or root.parent)
    if cwd.resolve() != root.parent.resolve() and status.get("branch"):
        run(["git", "-C", str(root.parent), "update-ref", f"refs/foreman/beta/{name}", status["start_commit"]])
        rc, _, error = run(["git", "-C", str(root.parent), "worktree", "remove", str(cwd)])
        if rc:
            update_session(sdir, cleanup_warning=error)
    from refresh import refresh
    refresh(root)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("task", nargs="?")
    ap.add_argument("--to")
    ap.add_argument("--session", default="")
    ap.add_argument("--reason", default="")
    ap.add_argument("--finish-beta")
    ap.add_argument("--root", default=".foreman")
    args = ap.parse_args()
    try:
        root = Path(args.root).resolve()
        if args.finish_beta:
            finish_beta(root, args.finish_beta)
        elif args.task and args.to:
            transition(root, args.task, args.to, session=args.session, reason=args.reason)
        else:
            ap.error("provide TASK --to STATUS, or --finish-beta SESSION")
    except (WorkflowError, OSError) as exc:
        sys.exit(f"state: {exc}")
