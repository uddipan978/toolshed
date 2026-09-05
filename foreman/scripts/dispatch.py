#!/usr/bin/env python3
"""One guarded launch path shared by manual dispatch and the scheduler."""
from __future__ import annotations

import argparse
import fnmatch
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from delivery import active_sprint, launch_problems, plan
from foreman_lib import all_sessions, atomic_write, detect_harness, load_json, save_json
from ops import (WorkflowError, brief_task, identifier, lock, read_document,
                 session_alive, set_field, task_index, update_session)
from resources import admission, sample
from state import transition


def overlaps(left: list[str], right: list[str]) -> bool:
    for a in left:
        for b in right:
            if fnmatch.fnmatch(a, b) or fnmatch.fnmatch(b, a):
                return True
            # Wildcard prefixes that nest are conservatively considered shared.
            pa, pb = re.split(r"[*?\[]", a)[0], re.split(r"[*?\[]", b)[0]
            if (pa != a or pb != b) and (pa.startswith(pb) or pb.startswith(pa)):
                return True
    return False


def check_brief(text: str) -> None:
    for field in ("Objective", "Output format", "Tools and sources", "Boundaries"):
        block = re.search(r"^## " + re.escape(field) + r"\s*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
        if not block or not block[1].strip():
            raise WorkflowError(f"brief requires a nonempty {field} section")


def legacy_launch(root: Path, argv: list[str], args, text: str, harness: str | None) -> dict:
    """Keep already-running pre-sprint installations usable during migration.

    Never activate this for a fresh project or after a managed sprint existed.
    Existing work still uses ancestry/evidence gates, runner recovery and views.
    """
    print("foreman: legacy run compatibility; migrate remaining scope to delivery.json for managed scheduling", file=sys.stderr)
    sdir = root / "work" / "sessions" / identifier(args.name)
    with lock(root, "launch"):
        if (sdir / "status.json").exists():
            raise WorkflowError("existing session evidence must be preserved; use a new successor name")
        try:
            task = brief_task(root, text)
        except WorkflowError:
            task = None  # old manager fix/review briefs may not name a task
        original = task["path"].read_text() if task else ""
        if task and args.agent.split(":")[-1] == "foreman-developer":
            with lock(root):
                body = set_field(original, "Session", args.name)
                if task["status"] in ("backlog", "planned", "in_progress"):
                    body = set_field(body, "Status", "`[~]`")
                atomic_write(task["path"], body)
        env = {**os.environ, "FOREMAN_MANAGED_LAUNCH": "1", "FOREMAN_TASK_IDS": "", "FOREMAN_SPRINT": ""}
        adapter = Path(__file__).parent / "adapters" / (harness or detect_harness(root)) / "spawn.sh"
        result = subprocess.run(["bash", str(adapter), *argv], env=env, capture_output=True, text=True)
        status = load_json(sdir / "status.json")
        if result.returncode and not status.get("runner_pid") and task:
            with lock(root):
                atomic_write(task["path"], original)
    from refresh import refresh
    refresh(root)
    if result.returncode:
        raise WorkflowError(result.stderr or result.stdout)
    print(result.stdout.strip())
    return status


def capacity(root: Path, limits: dict, agent: str, task: dict | None) -> None:
    live = [s for s in all_sessions(root) if session_alive(s) or (
        s.get("state") == "starting" and time.time() - s.get("started_at", 0) < 60)]
    if len(live) >= limits["workers"]:
        raise WorkflowError(f"worker capacity reached ({len(live)}/{limits['workers']})")
    tasks = task_index(root)
    sprint_ids = active_sprint(root)["tasks"]
    if agent == "foreman-developer" and any(tasks[t]["status"] == "in_test" for t in sprint_ids):
        developers = sum(s.get("agent", "").split(":")[-1] == "foreman-developer" for s in live)
        # With one slot, drain tests before adding development. Otherwise reserve
        # configured capacity for tests whenever developed work is waiting.
        if developers >= max(0, limits["workers"] - limits["test_reserve"]):
            raise WorkflowError("capacity reserved for G4; drain developed work before adding developers")
    if task:
        for status in live:
            other_ids = status.get("task_ids", [])
            if task["id"] in other_ids:
                raise WorkflowError(f"{task['id']} already has a live worker")
            if agent == "foreman-developer" and status.get("agent", "").split(":")[-1] == "foreman-developer":
                if not other_ids:
                    raise WorkflowError(f"live developer {status['name']} has unknown file scope; wait or reconcile it")
                for tid in other_ids:
                    other = tasks.get(tid)
                    if not other or not task["parallel"] or not other["parallel"] or overlaps(task["files"], other["files"]):
                        raise WorkflowError(f"parallel scope is not disjoint from {status['name']}")


def launch(root: Path, argv: list[str], *, harness: str | None = None) -> dict:
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--name", required=True)
    ap.add_argument("--agent", default="foreman-developer")
    ap.add_argument("--brief", required=True)
    ap.add_argument("--root", default=str(root))
    ap.add_argument("--reason", default="")
    ap.add_argument("--base", default="")
    args, _ = ap.parse_known_args(argv)
    name = identifier(args.name)
    agent = args.agent.split(":")[-1]
    if agent not in ("foreman-developer", "foreman-tester", "foreman-beta-tester", "foreman-critic"):
        raise WorkflowError(f"unknown gated worker role: {agent}")
    text = Path(args.brief).resolve().read_text()
    if (not (root / "delivery.json").exists() and all_sessions(root)
            and not any((root / "sprints").glob("*.json"))):
        return legacy_launch(root, argv, args, text, harness)
    check_brief(text)
    task = None
    task_ids = []
    with lock(root, "launch"):
        sdir = root / "work" / "sessions" / name
        if (sdir / "status.json").exists() or (sdir / "launch.json").exists():
            raise WorkflowError(f"session {name} already has launch history; preserve it and use a new successor name")
        if agent in ("foreman-developer", "foreman-tester"):
            task = brief_task(root, text)
            task_ids = [task["id"]]
        if agent != "foreman-critic":
            problems = launch_problems(root, task, agent)
            if problems:
                raise WorkflowError("; ".join(problems))
            data = plan(root)
            limits = data["limits"]
            sprint = active_sprint(root)
            if agent == "foreman-beta-tester":
                match = re.search(r"^\*\*Tasks\*\*\s*([^\n]+)", text, re.M)
                task_ids = re.findall(r"T-\d+-\d+", match[1]) if match else []
                tasks = task_index(root)
                if not task_ids or any(t not in sprint["tasks"] or tasks[t]["status"] != "beta" for t in task_ids):
                    raise WorkflowError("beta brief must name **Tasks** from this sprint that all passed G4")
            elif agent == "foreman-tester":
                from foreman_lib import session_for_branch
                from verify_gate import session_pass_problems
                base = args.base or ("foreman/dev-" + name[5:] if name.startswith("test-") else "")
                predecessor = session_for_branch(root, base)
                if not predecessor or task["id"] not in predecessor.get("task_ids", []):
                    raise WorkflowError("tester must use a recorded predecessor for this task; a main/HEAD base cannot bypass G3")
                pred_dir = root / "work" / "sessions" / predecessor["name"]
                problems = session_pass_problems(pred_dir, predecessor)
                if session_alive(predecessor) or problems:
                    raise WorkflowError("G3 predecessor is not ready: " + "; ".join(problems))
            capacity(root, limits, agent, task)
            resource_state = admission(sample(), limits, load_json(root / "work" / "resources.json"))
            save_json(root / "work" / "resources.json", resource_state)
            if resource_state["paused"]:
                raise WorkflowError(resource_state["reason"])
            if task and agent == "foreman-developer":
                attempts = sum(task["id"] in s.get("task_ids", []) and s.get("agent", "").split(":")[-1] == agent
                               for s in all_sessions(root))
                if attempts >= limits["max_fix_rounds"] + 1:
                    raise WorkflowError(f"{task['id']}: fix-round limit reached; diagnose/replan instead of another blind retry")
                if task["status"] in ("in_test", "beta", "done") and not args.reason:
                    raise WorkflowError("reopening passed work requires --reason and a new successor session")
        else:
            sprint = {}
        original = task["path"].read_text() if task else ""
        save_json(sdir / "launch.json", {"reserved_at": time.time(), "name": name,
                  "task_ids": task_ids, "previous_task": original, "phase": "reserved"})
        if task and agent == "foreman-developer":
            transition(root, task["id"], "in_progress", session=name, reason=args.reason,
                       regenerate=False, _launch=True)
        env = os.environ.copy()
        env.update(FOREMAN_MANAGED_LAUNCH="1", FOREMAN_TASK_IDS=",".join(task_ids),
                   FOREMAN_SPRINT=sprint.get("id", ""))
        adapter_args = list(argv)
        if "--reason" in adapter_args:
            pos = adapter_args.index("--reason")
            del adapter_args[pos:pos + 2]
        adapter = Path(__file__).parent / "adapters" / (harness or detect_harness(root)) / "spawn.sh"
        result = subprocess.run(["bash", str(adapter), *adapter_args], env=env, capture_output=True, text=True)
        status = load_json(sdir / "status.json")
        if result.returncode and not status.get("runner_pid"):
            if task and agent == "foreman-developer":
                with lock(root):
                    atomic_write(task["path"], original)
            update_session(sdir, state="launch-failed", name=name, agent=agent, root=str(root), task_ids=task_ids)
        record = read_document(sdir / "launch.json")
        record.update(phase="launched" if status.get("runner_pid") else "failed", error=result.stderr[-4000:])
        save_json(sdir / "launch.json", record)
    from refresh import refresh
    refresh(root)
    if result.returncode:
        raise WorkflowError(result.stderr or result.stdout or "worker launch failed")
    print(result.stdout.strip())
    return read_document(sdir / "status.json")


if __name__ == "__main__":
    argv = sys.argv[1:]
    root = Path(argv[argv.index("--root") + 1] if "--root" in argv else ".foreman").resolve()
    try:
        launch(root, argv)
    except (WorkflowError, OSError, ValueError) as exc:
        sys.exit(f"spawn: {exc}")
