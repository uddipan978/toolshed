"""Behavioral regressions for delivery, dispatch, recovery and convergence."""
from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import delivery
import dispatch
import scheduler
from checkpoint import preserve
from events import acknowledge, pending, publish
from findings import record
from foreman_lib import all_tasks, atomic_write, load_json, parse_task, save_json
from ops import WorkflowError, lock, session_alive, set_field, task_index
from refresh import refresh
from resources import admission
from state import archive, check_receipt, finish_beta, transition
from supervise import assess, sweep
from verify_gate import beta_evidence_problems, tester_evidence_problems

HEALTHY = {"known": True, "cpu_pct": 20, "available_mb": 4096, "available_pct": 50}
CRITIQUE = """# Critique
**Verdict** fit
**Re-critique** not-required
**Round** 1
**Date** 2026-09-05

## Attacks that did not land
- Task scope and dependencies are disjoint and complete.
"""
TASK = """# {tid} — Example
**Module** M01 · **Status** `[{status}]` · **Parallel** [P] · **Depends on** {depends}
**Session** — · **Est** 12 turns
**Traces to** REQUIREMENTS.md §1
**Files** {files}
**Surface** {surface} · **Validation** {validation} · **Track** {track}

## Build
Implement the documented behavior.

## Acceptance
- [ ] WHEN requested THE SYSTEM SHALL show a result

## Verify
```bash
printf 'verified\n'
```

## Out of scope
Unrelated features.

## Activity log
"""


class Project(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)
        self.root = self.project / ".foreman"
        (self.root / "work" / "sessions").mkdir(parents=True)
        (self.root / ".gitignore").write_text("work/\n")
        (self.project / ".gitignore").write_text(".claude/worktrees/\n.grok/worktrees/\n")
        (self.root / "REQUIREMENTS.md").write_text("# Requirements\n\nDeliver a result.\n")
        (self.root / "CRITIQUE.md").write_text(CRITIQUE)
        self.git("init", "-b", "main")
        self.git("config", "user.email", "foreman@example.test")
        self.git("config", "user.name", "Foreman Tests")
        self.task()
        self.data = {"version": 1, "mode": "targeted", "surface": "no-ui", "active_sprint": None,
                     "limits": {"workers": 3, "test_reserve": 1, "max_fix_rounds": 3},
                     "milestones": [{"id": "FIX", "kind": "change", "outcome": "A working result", "exit_criteria": ["The journey passes"]}],
                     "sprints": [{"id": "S01", "milestone": "FIX", "goal": "Deliver a result", "demo": "printf demo", "turn_budget": 300,
                                  "tracer": "T-01-01", "tasks": ["T-01-01"]}]}
        self.save_plan()
        self.git("add", ".")
        self.git("commit", "-m", "initial plan")

    def git(self, *args, cwd=None):
        p = subprocess.run(["git", "-C", str(cwd or self.project), *args], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        return p.stdout.strip()

    def task(self, tid="T-01-01", status=" ", depends="—", files="src/example.py", surface="no-ui", validation="command", track="general"):
        p = self.root / "modules" / "M01" / "tasks" / f"{tid}-example.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(TASK.format(tid=tid, status=status, depends=depends, files=files, surface=surface, validation=validation, track=track))
        return p

    def save_plan(self):
        save_json(self.root / "delivery.json", self.data)

    def start(self):
        self.assertEqual(delivery.validate(self.root), [])
        delivery.start(self.root, "S01")

    def brief(self, name="dev-one", tid="T-01-01"):
        sdir = self.root / "work" / "sessions" / name
        sdir.mkdir(parents=True, exist_ok=True)
        task = task_index(self.root)[tid]["path"].relative_to(self.project)
        (sdir / "brief.md").write_text(f"**Task file** {task}\n\n## Objective\nImplement the result.\n\n## Output format\nScoped code and tests.\n\n## Tools and sources\nUse constitution commands.\n\n## Boundaries\nOnly task paths.\n")
        return sdir


class TaskStateTests(Project):
    def test_unreadable_task_is_visible_and_blocks_mutations(self):
        with patch("foreman_lib.parse_task", side_effect=OSError("cannot read task")):
            tasks = all_tasks(self.root)
            self.assertEqual(len(tasks), 1)
            self.assertEqual(tasks[0]["status"], "blocked")
            with self.assertRaisesRegex(WorkflowError, "cannot read task"):
                task_index(self.root)

    def test_field_update_preserves_other_fields(self):
        original = self.task().read_text()
        result = set_field(original, "Status", "`[~]`")
        result = set_field(result, "Session", "dev-one")
        p = self.task()
        p.write_text(result)
        task = parse_task(p)
        self.assertEqual(task["status"], "in_progress")
        self.assertEqual(task["session"], "dev-one")
        self.assertEqual(task["module"], "M01")
        self.assertTrue(task["parallel"])
        self.assertEqual(task["problems"], [])

    def test_duplicate_header_rejected_without_counting_it_twice(self):
        p = self.task()
        p.write_text(p.read_text().replace("# T-01-01 — Example", "# T-01-01 — Example\n# T-01-01 — Example"))
        self.assertEqual(len(all_tasks(self.root)), 1)
        with self.assertRaisesRegex(WorkflowError, "exactly one task heading"):
            task_index(self.root)
        refresh(self.root)
        self.assertIn("counts are provisional", (self.root / "STATUS.md").read_text())

    def test_duplicate_id_across_files_fails_closed(self):
        p = self.task()
        (p.parent / "duplicate.md").write_text(p.read_text())
        with self.assertRaisesRegex(WorkflowError, "duplicate task ID"):
            transition(self.root, "T-01-01", "planned")

    def test_cannot_skip_gates_or_invent_spawn(self):
        for to in ("done", "beta", "in_test", "in_progress"):
            with self.assertRaises(WorkflowError):
                transition(self.root, "T-01-01", to)
        self.assertEqual(parse_task(self.task())["status"], "backlog")

    def test_status_and_all_views_change_in_one_operation(self):
        transition(self.root, "T-01-01", "planned")
        p = task_index(self.root)["T-01-01"]["path"]
        self.assertEqual(parse_task(p)["status"], "planned")
        for rel in ("STATUS.md", "board.md", "board.html", "work/dashboard.html"):
            self.assertTrue((self.root / rel).is_file(), rel)
            self.assertIn("T-01-01", (self.root / rel).read_text())
        self.assertFalse((self.root / "work" / "views-dirty").exists())

    def test_refresh_failure_leaves_repair_marker(self):
        with patch("dashboard.write_html", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                transition(self.root, "T-01-01", "planned")
        self.assertTrue((self.root / "work" / "views-dirty").is_file())
        refresh(self.root)
        self.assertFalse((self.root / "work" / "views-dirty").exists())

    def test_receipt_cannot_be_used_for_other_task_or_tampered_evidence(self):
        sdir = self.brief()
        save_json(sdir / "status.json", {"name": sdir.name, "start_commit": self.git("rev-parse", "HEAD")})
        (sdir / "results.md").write_text("**Verdict** pass\n")
        archive(self.root, sdir, gate="G4", task_ids=["T-01-01"], integrated=self.git("rev-parse", "HEAD"))
        check_receipt(self.root, sdir.name, "G4", "T-01-01")
        with self.assertRaises(WorkflowError):
            check_receipt(self.root, sdir.name, "G4", "T-01-02")
        (self.root / "evidence" / sdir.name / "results.md").write_text("altered")
        with self.assertRaisesRegex(WorkflowError, "changed"):
            check_receipt(self.root, sdir.name, "G4", "T-01-01")


class DeliveryTests(Project):
    def test_acceptance_scope_cannot_change_silently_after_start(self):
        self.start()
        p = task_index(self.root)["T-01-01"]["path"]
        p.write_text(p.read_text().replace("show a result", "show any placeholder"))
        with self.assertRaisesRegex(WorkflowError, "task/contract scope changed"):
            delivery.active_sprint(self.root)

    def test_progress_checkmarks_do_not_invalidate_frozen_scope(self):
        self.start()
        p = task_index(self.root)["T-01-01"]["path"]
        p.write_text(set_field(p.read_text().replace("- [ ] WHEN", "- [x] WHEN"), "Status", "`[t]`"))
        self.assertEqual(delivery.active_sprint(self.root)["id"], "S01")

    def test_sprint_commitment_is_frozen(self):
        self.start()
        data = delivery.plan(self.root)
        data["sprints"][0]["goal"] = "different goal"
        save_json(self.root / "delivery.json", data)
        with self.assertRaisesRegex(WorkflowError, "scope is frozen"):
            delivery.active_sprint(self.root)

    def test_cycles_and_unknown_dependencies_block(self):
        self.task(depends="T-01-02")
        self.task("T-01-02", depends="T-01-01", files="src/second.py")
        self.data["sprints"][0]["tasks"].append("T-01-02")
        self.save_plan()
        self.assertTrue(any("cycle" in p for p in delivery.validate(self.root)))

    def test_ui_product_preview_and_backend_are_ready_together(self):
        self.task(track="frontend", surface="ui", validation="browser", files="web/**")
        self.task("T-01-02", track="backend", files="server/**")
        self.task("T-01-03", track="integration", depends="T-01-01, T-01-02", files="adapters/**", surface="ui", validation="browser")
        self.data.update(mode="product", surface="ui")
        self.data["milestones"] = [
            {"id": "MVP", "kind": "mvp", "outcome": "First real journey", "exit_criteria": ["Journey passes"]},
            {"id": "PROD", "kind": "production", "outcome": "Ready to operate", "exit_criteria": ["Release checks pass"], "release_checks": ["true"]}]
        self.data["sprints"][0].update(milestone="MVP", preview="T-01-01", tracer="T-01-03", tasks=["T-01-01", "T-01-02", "T-01-03"])
        (self.root / "contracts.md").write_text("GET /result: {value: string}; fixtures use the same response.")
        (self.root / "design.md").write_text("**Status** accepted\n\n## Journey\nView result.\n\n## Layout\nList and detail.\n\n## States\nEmpty and error.\n\n## Accessibility\nVisible keyboard focus.\n")
        self.save_plan()
        self.start()
        tasks = task_index(self.root)
        self.assertEqual(delivery.launch_problems(self.root, tasks["T-01-01"], "foreman-developer"), [])
        self.assertEqual(delivery.launch_problems(self.root, tasks["T-01-02"], "foreman-developer"), [])
        self.assertTrue(delivery.launch_problems(self.root, tasks["T-01-03"], "foreman-developer"))
        self.task(depends="T-01-02", track="frontend", surface="ui", validation="browser")
        self.assertTrue(any("cannot wait" in p for p in delivery.validate(self.root)))

    def test_missing_ui_url_cannot_select_no_browser(self):
        self.task(surface="ui", validation="command")
        self.assertTrue(any("requires **Validation** browser" in p for p in delivery.validate(self.root)))


class ResourceTests(unittest.TestCase):
    def test_disjoint_filenames_do_not_collide_but_glob_scopes_do(self):
        self.assertFalse(dispatch.overlaps(["src/item.py"], ["src/item.pyx"]))
        self.assertTrue(dispatch.overlaps(["src/**"], ["src/item.py"]))
        self.assertFalse(dispatch.overlaps(["frontend/**"], ["backend/**"]))

    def test_memory_and_cpu_pause_launches_with_hysteresis(self):
        limits = {"workers": 3}
        self.assertFalse(admission(HEALTHY, limits)["paused"])
        pressure = admission({**HEALTHY, "available_mb": 700}, limits)
        self.assertTrue(pressure["paused"])
        self.assertTrue(admission({**HEALTHY, "available_mb": 1100}, limits, pressure)["paused"])
        self.assertFalse(admission(HEALTHY, limits, pressure)["paused"])
        self.assertTrue(admission({**HEALTHY, "cpu_pct": 90}, limits)["paused"])
        self.assertTrue(admission({"known": False}, limits)["paused"])


class EventTests(Project):
    def test_runner_pid_reuse_is_detected_without_exit_marker(self):
        status = {"name": "worker", "root": str(self.root), "pid": os.getpid(),
                  "runner_pid": os.getpid(), "runner_identity": "original process start"}
        with patch("ops.process_identity", return_value="different process start"):
            self.assertFalse(session_alive(status))

    def test_completion_survives_missing_notification_and_supervisor_restart(self):
        sdir = self.brief("old-worker")
        save_json(sdir / "status.json", {"name": sdir.name, "agent": "generic", "root": str(self.root), "pid": 0,
                  "state": "running", "started_at": time.time() - 100, "max_turns": 10})
        (sdir / "stream.jsonl").write_text('{"type":"result","subtype":"success","num_turns":10}\n')
        first, second = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(first):
            sweep(self.root, once=True, regenerate=False)
        with contextlib.redirect_stdout(second):
            sweep(self.root, once=True, regenerate=False)
        self.assertIn("DONE old-worker", first.getvalue())
        self.assertNotIn("TURNS", first.getvalue())
        self.assertNotIn("DONE", second.getvalue())
        events = pending(self.root)
        self.assertEqual(len(events), 1)
        acknowledge(self.root, events[0]["id"], "completion inspected")
        self.assertEqual(pending(self.root), [])

    def test_exit_marker_overrides_recycled_pid(self):
        sdir = self.brief()
        status = {"name": sdir.name, "root": str(self.root), "pid": os.getpid()}
        save_json(sdir / "exit.json", {"returncode": 0})
        self.assertFalse(session_alive(status))

    def test_final_stream_does_not_retire_live_worker(self):
        sdir = self.brief()
        save_json(sdir / "status.json", {"name": sdir.name, "root": str(self.root), "agent": "generic", "pid": os.getpid(), "started_at": time.time()})
        (sdir / "stream.jsonl").write_text('{"type":"result","subtype":"success"}\n')
        self.assertEqual(assess(sdir, time.time())["state"], "running")

    def test_retired_worktree_does_not_reappear_as_review(self):
        sdir = self.brief()
        save_json(sdir / "status.json", {"name": sdir.name, "agent": "foreman-developer", "pid": 0, "cwd": "/missing", "integrated_at": time.time()})
        self.assertEqual(assess(sdir, time.time()), {})


class FindingsTests(Project):
    def test_nits_do_not_refill_task_backlog(self):
        fields = dict(severity=1, place="table widths", description="Align numeric column widths", evidence="43 duplicate width declarations")
        first = record(self.root, **fields)
        second = record(self.root, **fields, source="another tester")
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(second["route"], "known")
        self.assertEqual(len(load_json(self.root / "findings.json")["findings"]), 1)
        self.assertEqual(len(all_tasks(self.root)), 1)

    def test_acceptance_failure_blocks_at_any_severity(self):
        finding = record(self.root, severity=1, place="dialog", description="Focus escapes via iframe", evidence="Positive control button wraps; iframe escapes", acceptance=True)
        self.assertEqual(finding["route"], "fix-task")


class EvidenceConsistencyTests(unittest.TestCase):
    def test_browser_pass_needs_real_artifact_paths(self):
        from verify_gate import session_gate_problems
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            sdir = cwd / "session"
            sdir.mkdir()
            task = cwd / "task.md"
            task.write_text(TASK.format(tid="T-01-01", status="t", depends="—", files="src/**", surface="ui", validation="browser", track="frontend").replace("- [ ] WHEN", "- [x] WHEN"))
            (sdir / "brief.md").write_text("**Task file** task.md\n")
            (sdir / "testcases.md").write_text("## TC-01 — focus\n**Expected** Visible outline\n")
            (sdir / "results.md").write_text("**Verdict** pass\n**Browser** Chromium\n**Viewport** 1440x900\n**Browser evidence** focus-trace.txt\n\n## TC-01 — focus\n**Outcome** pass\n**Evidence** Measured after settling\n")
            status = {"agent": "foreman-tester", "cwd": str(cwd)}
            self.assertTrue(any("missing/empty" in p for p in session_gate_problems(sdir, status)))
            (sdir / "focus-trace.txt").write_text("Observed computed outline width: 2px; after transition completion.\n")
            self.assertEqual(session_gate_problems(sdir, status), [])

    def test_contradictory_and_duplicate_case_reports_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            sdir = Path(tmp)
            (sdir / "testcases.md").write_text("## TC-01 — case\n**Expected** result\n")
            for outcome in ("fail", "could-not-run"):
                (sdir / "results.md").write_text(f"**Verdict** pass\n\n## TC-01 — case\n**Outcome** {outcome}\n**Evidence** observed result\n")
                self.assertTrue(any("contradicts" in p for p in tester_evidence_problems(sdir)))
            (sdir / "results.md").write_text("**Verdict** pass\n\n" + "## TC-01 — case\n**Outcome** pass\n**Evidence** result\n" * 2)
            self.assertTrue(any("duplicate" in p for p in tester_evidence_problems(sdir)))

    def test_beta_cannot_pass_with_blocking_finding(self):
        with tempfile.TemporaryDirectory() as tmp:
            sdir = Path(tmp)
            (sdir / "beta-review.md").write_text("**Surface** no-ui\n**Verdict** pass\n\n## Findings\n### B-01 — role gate\n**Severity** 4\n**Place** release reservation\n**Fix** Check the role\n\n## What worked\nClear output.\n")
            self.assertTrue(any("contradicts" in p for p in beta_evidence_problems(sdir)))


class QueueTests(Project):
    def test_g4_capacity_is_reserved_while_maintaining_total_worker_cap(self):
        self.task(status="t")
        self.task("T-01-02", files="src/second.py")
        self.data["sprints"][0]["tasks"].append("T-01-02")
        self.save_plan()
        self.start()
        for name in ("dev-a", "dev-b"):
            sdir = self.brief(name)
            save_json(sdir / "status.json", {"name": name, "root": str(self.root), "agent": "foreman-developer", "pid": os.getpid(), "task_ids": ["T-01-01"]})
        with self.assertRaisesRegex(WorkflowError, "reserved for G4"):
            dispatch.capacity(self.root, self.data["limits"], "foreman-developer", task_index(self.root)["T-01-02"])
        dispatch.capacity(self.root, self.data["limits"], "foreman-tester", None)

    def test_corrupt_queue_is_not_replaced_with_an_empty_one(self):
        path = self.root / "work" / "queue.json"
        path.write_text("{interrupted edit")
        sdir = self.brief()
        with self.assertRaises(WorkflowError):
            scheduler.enqueue(self.root, sdir.name, "foreman-developer", str(sdir / "brief.md"))
        self.assertEqual(path.read_text(), "{interrupted edit")

    def test_queue_keeps_failed_launch_and_recovers_crash_reservation(self):
        self.start()
        sdir = self.brief()
        scheduler.enqueue(self.root, sdir.name, "foreman-developer", str(sdir / "brief.md"))
        def fail(*args, **kwargs):
            save_json(sdir / "launch.json", {"phase": "failed"})
            raise WorkflowError("adapter failed")
        with patch("scheduler.sample", return_value=HEALTHY), patch("scheduler.launch", side_effect=fail):
            scheduler.tick(self.root)
        job = load_json(self.root / "work" / "queue.json")["jobs"][0]
        self.assertEqual(job["state"], "failed")
        self.assertIn("adapter failed", job["error"])
        queue = load_json(self.root / "work" / "queue.json")
        queue["jobs"][0]["state"] = "launching"
        save_json(self.root / "work" / "queue.json", queue)
        with patch("scheduler.sample", return_value=HEALTHY), patch("scheduler.launch") as spawn:
            scheduler.tick(self.root)
            spawn.assert_not_called()
        self.assertEqual(load_json(self.root / "work" / "queue.json")["jobs"][0]["state"], "interrupted")

    def test_resource_pause_keeps_queue_and_refreshes_views(self):
        self.start()
        sdir = self.brief()
        scheduler.enqueue(self.root, sdir.name, "foreman-developer", str(sdir / "brief.md"))
        with patch("scheduler.sample", return_value={**HEALTHY, "available_mb": 300}), patch("scheduler.launch") as spawn:
            scheduler.tick(self.root)
            spawn.assert_not_called()
        self.assertEqual(load_json(self.root / "work" / "queue.json")["jobs"][0]["state"], "pending")
        self.assertIn("RAM available", (self.root / "work" / "dashboard.html").read_text())

    def test_single_instance_lock_prevents_competing_scheduler(self):
        with lock(self.root, "scheduler"):
            with self.assertRaises(WorkflowError):
                with lock(self.root, "scheduler", blocking=False):
                    self.fail("second scheduler obtained the lock")


class RecoveryTests(Project):
    def test_uncommitted_files_are_copied_without_committing_or_removing_them(self):
        sdir = self.brief()
        (self.project / "unfinished.py").write_text("valuable work\n")
        head = self.git("rev-parse", "HEAD")
        recovery = preserve(sdir, {"cwd": str(self.project)})
        saved = Path(recovery["location"]) / "files" / "unfinished.py"
        self.assertEqual(saved.read_text(), "valuable work\n")
        self.assertEqual((self.project / "unfinished.py").read_text(), "valuable work\n")
        self.assertEqual(self.git("rev-parse", "HEAD"), head)
        again = preserve(sdir, {"cwd": str(self.project)})
        self.assertEqual(again["location"], recovery["location"])


class ManagedLifecycleTests(Project):
    def test_verify_record_is_invalidated_when_product_changes(self):
        from verify import evidence_problems, record as record_verify
        sdir = self.brief()
        save_json(sdir / "status.json", {"cwd": str(self.project)})
        source = self.project / "src" / "example.py"
        source.parent.mkdir()
        source.write_text("RESULT = 42\n")
        self.assertEqual(record_verify(sdir), 0)
        self.assertEqual(evidence_problems(sdir, {"cwd": str(self.project)}), [])
        source.write_text("RESULT = 0\n")
        self.assertTrue(any("changed after Verify" in p for p in evidence_problems(sdir, {"cwd": str(self.project)})))

    def test_existing_run_can_launch_while_awaiting_sprint_migration(self):
        (self.root / "delivery.json").unlink()
        old = self.brief("old-session")
        save_json(old / "status.json", {"name": old.name, "agent": "generic", "state": "done", "pid": 0})
        sdir = self.brief("legacy-dev")
        with patch.dict(os.environ, {"PATH": self.fake_harness()}):
            status = dispatch.launch(self.root, ["--name", sdir.name, "--brief", str(sdir / "brief.md"), "--root", str(self.root)])
            self.wait_exit(sdir)
        self.assertEqual(status["task_ids"], [])
        self.assertEqual(task_index(self.root)["T-01-01"]["status"], "in_progress")

    def test_fresh_project_cannot_enter_legacy_mode_without_a_plan(self):
        (self.root / "delivery.json").unlink()
        sdir = self.brief()
        with self.assertRaisesRegex(WorkflowError, "delivery.json"):
            dispatch.launch(self.root, ["--name", sdir.name, "--brief", str(sdir / "brief.md"), "--root", str(self.root)])

    def fake_harness(self, harness="claude"):
        bindir = self.project / "fakebin"
        bindir.mkdir()
        cli = bindir / harness
        cli.write_text(f"#!{sys.executable}\n" + r'''
import json, os, pathlib, subprocess, sys
sdir = pathlib.Path(os.environ['FOREMAN_SESSION_DIR'])
cwd = pathlib.Path.cwd()
agent = sys.argv[sys.argv.index('--agent') + 1].split(':')[-1]
task = cwd / '.foreman/modules/M01/tasks/T-01-01-example.md'
if agent == 'foreman-developer':
    source = cwd / 'src/example.py'
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text('RESULT = 42\n')
    subprocess.run([sys.executable, '__VERIFY_SCRIPT__', '--session-dir', str(sdir)], check=True, stdout=subprocess.DEVNULL)
    text = task.read_text().replace('**Status** `[~]`', '**Status** `[t]`').replace('- [ ] WHEN', '- [x] WHEN')
    task.write_text(text + '\n- Verify: printf verified -> verified (exit 0)\n')
    subprocess.run(['git', 'add', '--', 'src/example.py', str(task.relative_to(cwd))], check=True)
    subprocess.run(['git', 'commit', '-m', 'implement result'], check=True, stdout=subprocess.DEVNULL)
elif agent == 'foreman-beta-tester':
    (sdir / 'beta-review.md').write_text('**Surface** no-ui\n**Verdict** pass\n\n## Findings\n- None.\n\n## What worked\nThe result is clear.\n')
else:
    (sdir / 'testcases.md').write_text('## TC-01 — result\n**Expected** 42\n')
    (sdir / 'results.md').write_text('**Verdict** pass\n\n## TC-01 — result\n**Outcome** pass\n**Evidence** RESULT = 42 observed\n')
print(json.dumps({'type': 'result', 'subtype': 'success', 'num_turns': 1}))
'''.replace('__VERIFY_SCRIPT__', str(SCRIPTS / 'verify.py')))
        cli.chmod(0o755)
        # Keep the harness outside product commits while still using a real child process.
        with (self.project / ".gitignore").open("a") as fh:
            fh.write("fakebin/\n")
        return str(bindir) + os.pathsep + os.environ["PATH"]

    def wait_exit(self, sdir):
        deadline = time.monotonic() + 8
        while not (sdir / "exit.json").is_file() and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertTrue((sdir / "exit.json").is_file(), (sdir / "stderr.log").read_text())
        self.assertEqual(load_json(sdir / "exit.json")["returncode"], 0, (sdir / "stderr.log").read_text())

    def test_dispatch_test_integrate_and_archive_with_manager_reconciliation(self):
        self.start()
        dev = self.brief("dev-one")
        env_path = self.fake_harness()
        with patch.dict(os.environ, {"PATH": env_path}), patch("dispatch.sample", return_value=HEALTHY):
            dispatch.launch(self.root, ["--name", dev.name, "--brief", str(dev / "brief.md"), "--root", str(self.root)])
            self.assertEqual(task_index(self.root)["T-01-01"]["status"], "in_progress")
            self.wait_exit(dev)
            sweep(self.root, once=True, regenerate=False)
            scheduler.reconcile(self.root)
            self.assertEqual(task_index(self.root)["T-01-01"]["status"], "in_test")
            tester = self.brief("test-one")
            dispatch.launch(self.root, ["--name", tester.name, "--agent", "foreman-tester", "--brief", str(tester / "brief.md"),
                                       "--root", str(self.root), "--base", "foreman/dev-one"])
            self.wait_exit(tester)
        sweep(self.root, once=True, regenerate=False)
        p = subprocess.run(["bash", str(SCRIPTS / "integrate.sh"), "--name", tester.name, "--root", str(self.root)],
                           cwd=self.project, capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual((self.project / "src/example.py").read_text(), "RESULT = 42\n")
        self.assertEqual(task_index(self.root)["T-01-01"]["status"], "beta")
        check_receipt(self.root, tester.name, "G4", "T-01-01")
        self.assertTrue((self.root / "evidence" / tester.name / "results.md").is_file())
        self.assertEqual(assess(tester, time.time()), {})
        beta = self.brief("beta-one")
        with (beta / "brief.md").open("a") as fh:
            fh.write("\n**Tasks** T-01-01\n")
        with patch.dict(os.environ, {"PATH": env_path}), patch("dispatch.sample", return_value=HEALTHY):
            dispatch.launch(self.root, ["--name", beta.name, "--agent", "foreman-beta-tester", "--brief", str(beta / "brief.md"), "--root", str(self.root)])
            self.wait_exit(beta)
        finish_beta(self.root, beta.name)
        self.assertEqual(task_index(self.root)["T-01-01"]["status"], "done")
        demo = self.root / "work" / "demo.md"
        demo.write_text("**Verdict** pass\n\nCommand: printf demo\nOutput: demo\n")
        p = subprocess.run([sys.executable, str(SCRIPTS / "delivery.py"), "close", "--root", str(self.root), "--demo-evidence", str(demo)], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertTrue(load_json(self.root / "sprints" / "S01.json")["closed_at"])

    def test_grok_uses_the_same_managed_lifecycle(self):
        self.start()
        sdir = self.brief()
        with patch.dict(os.environ, {"PATH": self.fake_harness("grok")}), patch("dispatch.sample", return_value=HEALTHY):
            dispatch.launch(self.root, ["--name", sdir.name, "--brief", str(sdir / "brief.md"), "--root", str(self.root)], harness="grok")
            self.wait_exit(sdir)
        status = load_json(sdir / "status.json")
        self.assertEqual(status["harness"], "grok")
        self.assertEqual(status["task_ids"], ["T-01-01"])
        self.assertEqual(assess(sdir, time.time())["state"], "done")

    def test_tester_cannot_bypass_developer_with_main_base(self):
        self.start()
        sdir = self.brief("test-one")
        with patch("dispatch.sample", return_value=HEALTHY):
            with self.assertRaisesRegex(WorkflowError, "cannot bypass G3"):
                dispatch.launch(self.root, ["--name", sdir.name, "--agent", "foreman-tester", "--brief", str(sdir / "brief.md"),
                                           "--root", str(self.root), "--base", "main"])
        self.assertFalse((sdir / "status.json").exists())

    def test_failed_adapter_rolls_back_in_progress(self):
        self.start()
        sdir = self.brief()
        original = task_index(self.root)["T-01-01"]["path"].read_text()
        with patch("dispatch.sample", return_value=HEALTHY), patch("dispatch.subprocess.run", return_value=subprocess.CompletedProcess([], 2, "", "adapter refused")):
            with self.assertRaisesRegex(WorkflowError, "adapter refused"):
                dispatch.launch(self.root, ["--name", sdir.name, "--brief", str(sdir / "brief.md"), "--root", str(self.root)])
        self.assertEqual(task_index(self.root)["T-01-01"]["path"].read_text(), original)
        self.assertTrue((sdir / "launch.json").is_file())


if __name__ == "__main__":
    unittest.main()
