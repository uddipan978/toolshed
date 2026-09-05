#!/usr/bin/env python3
"""Validate delivery scope and freeze sprint commitments before dispatch."""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
import time
from pathlib import Path

from foreman_lib import all_tasks, atomic_write, critique_problems, load_json, save_json
from ops import WorkflowError, identifier, lock, read_document, task_index


def plan(root: Path) -> dict:
    return read_document(root / "delivery.json")


def dependency_ids(task: dict) -> list[str]:
    return re.findall(r"T-\d+-\d+", task.get("depends_on", ""))


def scope_digest(root: Path, sprint: dict) -> str:
    """Progress fields can change; the agreed Build/Acceptance/Verify cannot drift."""
    from ops import set_field
    tasks = task_index(root)
    bodies = []
    for tid in sorted(sprint["tasks"]):
        text = tasks[tid]["path"].read_text().split("\n## Activity log", 1)[0]
        text = set_field(set_field(text, "Status", "`[ ]`"), "Session", "—")
        text = re.sub(r"(?m)^(\s*-\s+)\[[xX]\]", r"\1[ ]", text)
        bodies.append("\n".join(line.rstrip() for line in text.splitlines()).strip())
    for name in ("REQUIREMENTS.md", "constitution.md", "design.md", "contracts.md"):
        path = root / name
        bodies.append(path.read_text() if path.is_file() else "")
    return hashlib.sha256("\n\0\n".join(bodies).encode()).hexdigest()


def validate(root: Path) -> list[str]:
    try:
        data, tasks = plan(root), task_index(root)
    except WorkflowError as exc:
        return [str(exc)]
    problems = []
    requirements = root / "REQUIREMENTS.md"
    if not requirements.is_file() or not requirements.read_text().strip() or "[NEEDS CLARIFICATION]" in requirements.read_text():
        problems.append("G0 requirements are missing, empty or contain unresolved clarification markers")
    if data.get("version") != 1:
        problems.append("delivery.json requires version 1")
    if data.get("mode") not in ("product", "targeted"):
        problems.append("mode must be product or targeted")
    if data.get("surface") not in ("ui", "no-ui"):
        problems.append("surface must be ui or no-ui")
    milestones = data.get("milestones", [])
    sprints = data.get("sprints", [])
    if not isinstance(milestones, list) or not milestones or not isinstance(sprints, list) or not sprints:
        return problems + ["define at least one milestone and sprint"]
    if any(not isinstance(m, dict) for m in milestones + sprints):
        return problems + ["milestones and sprints must contain objects"]
    mids = [m.get("id") for m in milestones]
    sids = [s.get("id") for s in sprints]
    if any(not isinstance(value, str) for value in mids + sids):
        return problems + ["milestone and sprint IDs must be strings"]
    if len(set(mids)) != len(mids) or len(set(sids)) != len(sids):
        problems.append("duplicate milestone or sprint IDs")
    for value in mids + sids:
        try:
            identifier(value or "")
        except WorkflowError as exc:
            problems.append(str(exc))
    if data.get("mode") == "product" and not any(m.get("kind") == "mvp" for m in milestones):
        problems.append("one milestone must have kind=mvp")
    if data.get("mode") == "product" and not any(m.get("kind") == "production" for m in milestones):
        problems.append("product mode requires a production milestone after the MVP")
    for m in milestones:
        if not m.get("outcome") or not m.get("exit_criteria"):
            problems.append(f"{m.get('id')}: record a user outcome and exit_criteria")
        if m.get("kind") == "production" and not m.get("release_checks"):
            problems.append(f"{m.get('id')}: production needs release_checks (commands for release readiness)")
    limits = data.get("limits", {})
    if not isinstance(limits, dict):
        return problems + ["limits must be a JSON object"]
    for key, lo, hi in (("workers", 1, 5), ("test_reserve", 1, 5), ("max_fix_rounds", 1, 10)):
        n = limits.get(key)
        if type(n) is not int or not lo <= n <= hi:
            problems.append(f"limits.{key} must be an integer in {lo}..{hi}")
    if type(limits.get("test_reserve")) is int and type(limits.get("workers")) is int and limits["test_reserve"] > limits["workers"]:
        problems.append("test_reserve cannot exceed workers")
    for field, low, high in (("cpu_pause_pct", 1, 100), ("min_available_pct", 1, 99), ("min_available_mb", 1, 1024**2)):
        if field in limits and (type(limits[field]) not in (int, float) or not low <= limits[field] <= high):
            problems.append(f"limits.{field} must be in {low}..{high}")
    scheduled = {}
    for pos, sprint in enumerate(sprints):
        sid = sprint.get("id")
        if sprint.get("milestone") not in mids:
            problems.append(f"{sid}: unknown milestone")
        if not sprint.get("goal") or not sprint.get("demo"):
            problems.append(f"{sid}: goal and runnable demo command are required")
        if type(sprint.get("turn_budget")) is not int or sprint["turn_budget"] <= 0:
            problems.append(f"{sid}: positive turn_budget is required (includes G4/G5)")
        ids = sprint.get("tasks", [])
        if not isinstance(ids, list) or not ids or any(not isinstance(t, str) for t in ids):
            problems.append(f"{sid}: tasks must be a nonempty list of task IDs")
            continue
        if len(set(ids)) != len(ids):
            problems.append(f"{sid}: duplicate task IDs")
        if sprint.get("tracer") not in ids:
            problems.append(f"{sid}: tracer must name the first demonstrable vertical slice")
        if pos == 0 and data.get("mode") == "product" and data.get("surface") == "ui":
            preview = sprint.get("preview")
            if preview not in ids or tasks.get(preview, {}).get("track") != "frontend":
                problems.append(f"{sid}: a frontend preview task is required in the first sprint")
            else:
                seen_deps = set()
                def needs_backend(tid):
                    if tid in seen_deps or tid not in tasks:
                        return False
                    seen_deps.add(tid)
                    return tasks[tid]["track"] in ("backend", "integration") or any(needs_backend(dep) for dep in dependency_ids(tasks[tid]))
                if any(needs_backend(dep) for dep in dependency_ids(tasks[preview])):
                    problems.append(f"{preview}: static frontend preview cannot wait on backend dependencies")
            contract = root / "contracts.md"
            if not contract.is_file() or not contract.read_text().strip():
                problems.append("parallel frontend/backend work requires contracts.md (API, fixtures, states)")
        for tid in ids:
            if tid not in tasks:
                problems.append(f"{sid}: unknown task {tid}")
            if tid in scheduled:
                problems.append(f"{tid}: scheduled in more than one sprint")
            scheduled[tid] = pos
            if tid in tasks:
                for field, expected in (("sprint", sid), ("milestone", sprint.get("milestone"))):
                    if tasks[tid].get(field) and tasks[tid][field] != expected:
                        problems.append(f"{tid}: {field} label disagrees with delivery.json")
    for tid, task in tasks.items():
        if task["needs_clarification"]:
            problems.append(f"{tid}: unresolved clarification blocks dispatch")
        if tid not in scheduled:
            if task.get("milestone") != "later":
                problems.append(f"{tid}: assign to a sprint or explicitly mark **Milestone** later")
        if task.get("surface") not in ("ui", "no-ui"):
            problems.append(f"{tid}: **Surface** ui|no-ui is required; an unset URL does not mean no UI")
        if task.get("surface") == "ui" and task.get("validation") != "browser":
            problems.append(f"{tid}: UI work requires **Validation** browser")
        if not task.get("files"):
            problems.append(f"{tid}: **Files** must declare the write scope")
        if not task["acceptance_total"]:
            problems.append(f"{tid}: at least one acceptance criterion is required")
        body = task["path"].read_text()
        if not re.search(r"^\*\*Traces to\*\*\s*\S", body, re.M):
            problems.append(f"{tid}: **Traces to** must identify the requirement")
        verify = re.search(r"^## Verify\s*\n```(?:bash|sh)?\n(.*?)\n```", body, re.M | re.S)
        if not verify or not verify[1].strip() or verify[1].strip().startswith("#"):
            problems.append(f"{tid}: runnable Verify command is required")
        for dep in dependency_ids(task):
            if dep not in tasks:
                problems.append(f"{tid}: unknown dependency {dep}")
            elif tid in scheduled and tasks[dep]["status"] != "done" and scheduled.get(dep, 10**9) > scheduled[tid]:
                problems.append(f"{tid}: dependency {dep} is in a later sprint or unscheduled")
    visiting, visited = set(), set()
    def visit(tid):
        if tid in visiting:
            problems.append(f"dependency cycle at {tid}")
            return
        if tid in visited:
            return
        visiting.add(tid)
        for dep in dependency_ids(tasks[tid]):
            if dep in tasks:
                visit(dep)
        visiting.remove(tid)
        visited.add(tid)
    for tid in tasks:
        visit(tid)
    return problems


def active_sprint(root: Path) -> dict:
    data = plan(root)
    sid = data.get("active_sprint")
    sprint = next((s for s in data.get("sprints", []) if s.get("id") == sid), None)
    if not sprint:
        raise WorkflowError("no active sprint; validate the plan and run delivery.py start SNN")
    record = read_document(root / "sprints" / f"{identifier(sid)}.json")
    if record.get("closed_at"):
        raise WorkflowError(f"sprint {sid} is closed")
    if record.get("commitment") != sprint:
        raise WorkflowError(f"{sid} changed after start; scope is frozen. Record changes with delivery.py amend")
    if record.get("scope_digest") and record["scope_digest"] != scope_digest(root, sprint):
        raise WorkflowError(f"{sid} task/contract scope changed after start; re-critique and record delivery.py amend")
    return sprint


def launch_problems(root: Path, task: dict | None, agent: str) -> list[str]:
    problems = validate(root) + critique_problems(root, require_clear=True)
    if problems:
        return problems
    try:
        sprint = active_sprint(root)
    except WorkflowError as exc:
        return [str(exc)]
    if task and task["id"] not in sprint["tasks"]:
        problems.append(f"{task['id']} is outside active sprint {sprint['id']}")
    if task and agent == "foreman-developer":
        tasks = task_index(root)
        for dep in dependency_ids(task):
            if tasks[dep]["status"] not in ("beta", "done"):
                problems.append(f"{task['id']} waits for {dep} to pass G4 and integrate")
        tracer = tasks[sprint["tracer"]]
        prerequisites = set()
        def collect(tid):
            for dep in dependency_ids(tasks[tid]):
                if dep not in prerequisites:
                    prerequisites.add(dep)
                    collect(dep)
        collect(tracer["id"])
        preview = tasks.get(sprint.get("preview"), {})
        early_parallel = bool(preview) and task.get("track") in ("frontend", "backend")
        if not early_parallel and task["id"] != tracer["id"] and task["id"] not in prerequisites and tracer["status"] not in ("beta", "done"):
            problems.append(f"demonstrate tracer {tracer['id']} through G4 before expanding this sprint")
        if task.get("track") == "integration" and preview and preview["status"] not in ("beta", "done"):
            problems.append("wiring waits for the static frontend preview to pass browser G4")
        if task["surface"] == "ui":
            design = root / "design.md"
            text = design.read_text() if design.is_file() else ""
            if not re.search(r"^\*\*Status\*\* accepted\s*$", text, re.M):
                problems.append("UI work needs an accepted design.md direction before development")
            for section in ("Journey", "Layout", "States", "Accessibility"):
                if not re.search(r"^## " + section + r"\s*\n+\S", text, re.M):
                    problems.append(f"design.md needs a concrete {section} section")
    return problems


def summary(root: Path) -> dict:
    if not (root / "delivery.json").is_file():
        return {"mode": "legacy", "message": "No MVP/sprint plan recorded"}
    data = plan(root)
    sid = data.get("active_sprint")
    sprint = next((s for s in data.get("sprints", []) if s.get("id") == sid), None)
    if not sprint:
        return {"mode": "planning", "message": "No active sprint"}
    tasks = {t["id"]: t for t in all_tasks(root)}
    record = load_json(root / "sprints" / f"{identifier(sid)}.json")
    baseline = record.get("baseline", sprint["tasks"])
    ids = sprint["tasks"]
    return {"mode": "sprint", "id": sid, "milestone": sprint["milestone"],
            "goal": sprint["goal"], "demo": sprint["demo"], "preview": sprint.get("preview", ""),
            "committed": len(baseline), "current": len(ids),
            "added": len(set(ids) - set(baseline)), "removed": len(set(baseline) - set(ids)),
            "done": sum(tasks.get(t, {}).get("status") == "done" for t in ids),
            "in_test": sum(tasks.get(t, {}).get("status") == "in_test" for t in ids),
            "beta": sum(tasks.get(t, {}).get("status") == "beta" for t in ids)}


def start(root: Path, sid: str) -> None:
    with lock(root):
        problems = validate(root) + critique_problems(root, require_clear=True)
        if problems:
            raise WorkflowError("\n".join(problems))
        data = plan(root)
        if data.get("active_sprint"):
            raise WorkflowError("close the current sprint before starting another")
        sprint = next((s for s in data["sprints"] if s["id"] == sid), None)
        if not sprint:
            raise WorkflowError(f"unknown sprint {sid}")
        target = root / "sprints" / f"{identifier(sid)}.json"
        if target.exists():
            raise WorkflowError("sprint already has a commitment record; use a new sprint ID")
        save_json(target, {"started_at": time.time(), "baseline": sprint["tasks"],
                           "commitment": sprint, "changes": [], "scope_digest": scope_digest(root, sprint),
                           "critique_digest": hashlib.sha256((root / "CRITIQUE.md").read_bytes()).hexdigest()})
        data["active_sprint"] = sid
        save_json(root / "delivery.json", data)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=("check", "start", "close", "amend", "summary"))
    ap.add_argument("sprint", nargs="?")
    ap.add_argument("--root", default=".foreman")
    ap.add_argument("--reason")
    ap.add_argument("--demo-evidence", help="file containing actual demo output and outcome")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    try:
        if args.command == "check":
            problems = validate(root)
            if problems:
                raise WorkflowError("\n".join(problems))
            print("delivery plan is valid")
        elif args.command == "summary":
            import json
            print(json.dumps(summary(root), indent=2))
        elif args.command == "start":
            start(root, args.sprint or "")
        else:
            with lock(root):
                data = plan(root)
                sid = identifier(data.get("active_sprint") or "")
                record_path = root / "sprints" / f"{sid}.json"
                record = read_document(record_path)
                sprint = next(s for s in data["sprints"] if s["id"] == sid)
                if args.command == "amend":
                    if not args.reason or validate(root):
                        raise WorkflowError("amend requires --reason and a valid delivery plan")
                    digest = scope_digest(root, sprint)
                    critique_digest = hashlib.sha256((root / "CRITIQUE.md").read_bytes()).hexdigest()
                    if digest != record.get("scope_digest"):
                        if critique_problems(root, require_clear=True) or critique_digest == record.get("critique_digest"):
                            raise WorkflowError("task/contract scope changed; a new cleared critique is required before amendment")
                    record["changes"].append({"at": time.time(), "reason": args.reason,
                                              "before": record["commitment"], "after": sprint})
                    record["commitment"] = sprint
                    record["scope_digest"] = digest
                    record["critique_digest"] = critique_digest
                else:
                    active_sprint(root)
                    tasks = task_index(root)
                    if any(tasks[t]["status"] != "done" for t in sprint["tasks"]):
                        raise WorkflowError("sprint has unfinished G3/G4/G5 work")
                    from state import check_receipt
                    for tid in sprint["tasks"]:
                        check_receipt(root, tasks[tid]["session"], "G5", tid)
                    if not args.demo_evidence or not Path(args.demo_evidence).read_text().strip():
                        raise WorkflowError("close requires --demo-evidence with the executed journey result")
                    evidence = Path(args.demo_evidence).read_text()
                    if not re.search(r"^\*\*Verdict\*\* pass\s*$", evidence, re.M):
                        raise WorkflowError("demo evidence must have **Verdict** pass")
                    milestone = next(m for m in data["milestones"] if m["id"] == sprint["milestone"])
                    if milestone.get("kind") == "production":
                        import subprocess
                        outputs = []
                        for command in milestone["release_checks"]:
                            result = subprocess.run(["bash", "-c", command], cwd=root.parent,
                                                    capture_output=True, text=True, timeout=600)
                            outputs.append(f"$ {command}\nexit={result.returncode}\n{result.stdout}\n{result.stderr}")
                            atomic_write(root / "sprints" / f"{sid}-release.md", "\n\n".join(outputs))
                            if result.returncode:
                                raise WorkflowError(f"production release check failed: {command}")
                    atomic_write(root / "sprints" / f"{sid}-demo.md", evidence)
                    record["closed_at"] = time.time()
                    data["active_sprint"] = None
                    save_json(root / "delivery.json", data)
                save_json(record_path, record)
        if args.command not in ("check", "summary"):
            from refresh import refresh
            refresh(root)
        return 0
    except (WorkflowError, OSError, KeyError, TypeError) as exc:
        print(f"delivery: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
