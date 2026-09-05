#!/usr/bin/env python3
"""Managed loop: reconcile, measure resources, dispatch ready jobs, refresh views."""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from delivery import active_sprint, plan
from dispatch import launch
from events import publish
from foreman_lib import all_sessions, load_json, save_json
from ops import WorkflowError, identifier, lock, read_document, task_index
from resources import admission, sample
from state import transition
from supervise import sweep


def load_queue(root: Path) -> dict:
    path = root / "work" / "queue.json"
    data = read_document(path) if path.is_file() else {"version": 1, "jobs": []}
    if data.get("version") != 1 or not isinstance(data.get("jobs"), list):
        raise WorkflowError("queue.json has an invalid schema; preserved for repair")
    for job in data["jobs"]:
        if not isinstance(job, dict) or not all(isinstance(job.get(k), str) for k in ("name", "agent", "brief", "state")):
            raise WorkflowError("queue.json has an invalid job; preserved for repair")
        identifier(job["name"])
    return data


def enqueue(root: Path, name: str, agent: str, brief: str, base: str = "", reason: str = "") -> None:
    identifier(name)
    path = Path(brief).resolve()
    if not path.is_file():
        raise WorkflowError(f"brief not found: {path}")
    with lock(root, "queue"):
        queue = load_queue(root)
        if any(j["name"] == name for j in queue["jobs"]):
            raise WorkflowError(f"{name} is already queued; inspect its recorded outcome")
        queue["jobs"].append({"name": name, "agent": agent, "brief": str(path),
                              "base": base, "reason": reason, "state": "pending", "created_at": time.time()})
        save_json(root / "work" / "queue.json", queue)


def reconcile(root: Path) -> None:
    """Completion notifications can be lost; current evidence remains authoritative."""
    tasks = task_index(root)
    for status in all_sessions(root):
        if status.get("integrated_at") or status.get("retired_at"):
            continue
        if status.get("state", "").split(":")[0] not in ("done", "ready"):
            continue
        if status.get("agent", "").split(":")[-1] == "foreman-developer":
            for tid in status.get("task_ids", []):
                if tid in tasks and tasks[tid]["status"] == "in_progress":
                    transition(root, tid, "in_test", session=status["name"], regenerate=False)


def tick(root: Path) -> None:
    with lock(root, "supervisor", blocking=False):
        sweep(root, once=True, regenerate=False)
    try:
        reconcile(root)
        data = plan(root)
        sprint = active_sprint(root)
        previous = load_json(root / "work" / "resources.json")
        resources = admission(sample(), data["limits"], previous)
        resources["sampled_at"] = time.time()
        save_json(root / "work" / "resources.json", resources)
        if resources["paused"] != previous.get("paused"):
            publish(root, "scheduler", "RESOURCE", resources["reason"], str(resources["sampled_at"]))
            print(f"RESOURCE scheduler — {resources['reason']}", flush=True)
        if resources["paused"]:
            return
        spent = sum(int(s.get("turns") or 0) for s in all_sessions(root) if s.get("sprint") == sprint["id"])
        if spent >= sprint["turn_budget"]:
            publish(root, "scheduler", "SPRINT_BUDGET", "Sprint turn budget reached; review scope and remaining gates", sprint["id"])
            return
        with lock(root, "queue"):
            queue = load_queue(root)
            # G4/G5 first; the static frontend preview wins the first developer slot.
            preview = sprint.get("preview")
            tasks = task_index(root)
            def priority(job):
                if job["agent"].split(":")[-1] != "foreman-developer":
                    return 0
                text = Path(job["brief"]).read_text() if Path(job["brief"]).is_file() else ""
                return 1 if preview and preview in text else 2
            for job in sorted(queue["jobs"], key=priority):
                sdir = root / "work" / "sessions" / job["name"]
                status = load_json(sdir / "status.json")
                if job["state"] == "launching":
                    # A crash between spawn and queue acknowledgement never
                    # consumes the job or starts a duplicate worker.
                    job["state"] = "launched" if status.get("runner_pid") else "interrupted"
                    job["error"] = "recovered launch reservation; inspect session before retrying"
                if job["state"] != "pending":
                    continue
                if not Path(job["brief"]).is_file():
                    job.update(state="failed", error="brief is missing; queue entry preserved")
                    continue
                # Launch checks are rerun immediately before mutation; a held
                # dependency or resource condition keeps the job pending.
                argv = ["--name", job["name"], "--agent", job["agent"],
                        "--brief", job["brief"], "--root", str(root)]
                if job.get("base"):
                    argv += ["--base", job["base"]]
                if job.get("reason"):
                    argv += ["--reason", job["reason"]]
                job["state"] = "launching"
                save_json(root / "work" / "queue.json", queue)
                try:
                    launch(root, argv)
                    job.update(state="launched", launched_at=time.time(), error="")
                except (WorkflowError, OSError) as exc:
                    status = load_json(sdir / "status.json")
                    state = "launched" if status.get("runner_pid") else "failed" if (sdir / "launch.json").exists() else "pending"
                    job.update(state=state, error=str(exc))
                    if state == "failed":
                        publish(root, job["name"], "LAUNCH_FAILED", str(exc))
                save_json(root / "work" / "queue.json", queue)
            save_json(root / "work" / "queue.json", queue)
    finally:
        from refresh import refresh
        refresh(root)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=("enqueue", "run"))
    ap.add_argument("--root", default=".foreman")
    ap.add_argument("--name")
    ap.add_argument("--agent", default="foreman-developer")
    ap.add_argument("--brief")
    ap.add_argument("--base", default="")
    ap.add_argument("--reason", default="")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--interval", type=int, default=30)
    args = ap.parse_args()
    root = Path(args.root).resolve()
    try:
        if args.command == "enqueue":
            if not args.name or not args.brief:
                ap.error("enqueue needs --name and --brief")
            enqueue(root, args.name, args.agent, args.brief, args.base, args.reason)
        else:
            with lock(root, "scheduler", blocking=False):
                while True:
                    tick(root)
                    if args.once:
                        break
                    time.sleep(max(1, args.interval))
    except (WorkflowError, OSError) as exc:
        sys.exit(f"scheduler: {exc}")
    except KeyboardInterrupt:
        pass
