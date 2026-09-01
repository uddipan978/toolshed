#!/usr/bin/env python3
"""Foreman gate, stream, evidence, and git-handoff regression tests."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from foreman_lib import (  # noqa: E402
    MAX_G2A_ROUNDS,
    MAX_G2A_SCHEMA_RETRIES,
    WorktreeError,
    critique_is_clear,
    critique_is_well_formed,
    critique_problems,
    critique_round,
    detect_harness,
    finding_forces_recritique,
    has_ui,
    infer_gate,
    load_g2_state,
    may_set_pending,
    memory_problems,
    parse_critique,
    parse_memory,
    parse_stream_activity,
    parse_task,
    prepare_worker_worktree,
    read_stream,
    should_spawn_critic,
    worktree_snapshot,
)
from verify_gate import (  # noqa: E402
    beta_evidence_problems,
    session_gate_problems,
    stop_hook,
    task_gate_problems,
    tester_evidence_problems,
)
from supervise import assess  # noqa: E402
from dashboard import (  # noqa: E402
    render as render_dashboard,
    render_feed,
    render_markdown,
)


FIT_CRITIQUE = """# Critique

**Verdict** fit
**Re-critique** not-required
**Date** 2026-08-26

## Attacks that did not land

- Traceability: every requirement has a task.
"""

NOTFIT_OPEN = """# Critique

**Verdict** not-fit
**Re-critique** not-required
**Date** 2026-08-26

## F-01 — two [P] tasks share src/lib/session.ts
**Severity** 3
**Attack** decomposition
**Evidence** T-01-02 and T-01-03 both name src/lib/session.ts
**Change** drop [P] on T-01-03
**Status** open
**Disposition**

## Attacks that did not land

- Over-engineering: no speculative layer.
"""

NOTFIT_CLOSED = """# Critique

**Verdict** not-fit
**Re-critique** done
**Date** 2026-08-26

## F-01 — two [P] tasks share src/lib/session.ts
**Severity** 3
**Attack** decomposition
**Evidence** T-01-02 and T-01-03 both name src/lib/session.ts
**Change** drop [P] on T-01-03
**Status** fixed
**Disposition** T-01-03 now depends on T-01-02; [P] removed.

## Attacks that did not land

- Over-engineering: no speculative layer.
"""

PENDING = """# Critique

**Verdict** not-fit
**Re-critique** pending
**Date** 2026-08-26

## F-01 — two [P] tasks share src/lib/session.ts
**Severity** 3
**Attack** decomposition
**Evidence** T-01-02 and T-01-03 both name src/lib/session.ts
**Change** drop [P] on T-01-03
**Status** fixed
**Disposition** plan edited; waiting on re-critique.
"""

THIN = """# Critique

looks reasonable
"""

TASK_DEV_DONE = """# T-01-01 — Session cookie
**Module** M01 · **Status** `[x]` · **Parallel** — · **Depends on** —
**Session** dev-m01-01 · **Est** 12 turns / ~40 tool calls / medium
**Traces to** REQUIREMENTS.md §2

## Why
x

## Build
- src/lib/session.ts

## Acceptance
- [x] WHEN the user reloads THE SYSTEM SHALL restore the session

## Verify
```bash
npm test -- session
```

## Out of scope
Reset.

## Activity log
- 2026-08-26 npm test -- session → 4 passed
"""

TASK_DEV_T = TASK_DEV_DONE.replace("**Status** `[x]`", "**Status** `[t]`")

TASK_UNCHECKED = TASK_DEV_T.replace("- [x] WHEN", "- [ ] WHEN")

BRIEF = "**Task file** {path}\n\n## Objective\ndone\n"


class CritiqueTests(unittest.TestCase):
    def _write(self, body: str) -> Path:
        d = Path(tempfile.mkdtemp())
        p = d / "CRITIQUE.md"
        p.write_text(body)
        return p

    def test_missing(self):
        p = Path(tempfile.mkdtemp()) / "CRITIQUE.md"
        d = parse_critique(p)
        self.assertFalse(d["exists"])
        self.assertFalse(critique_is_well_formed(d))
        self.assertFalse(critique_is_clear(d))
        self.assertTrue(any("missing" in x.lower() for x in d["problems"]))

    def test_thin_fails_schema(self):
        d = parse_critique(self._write(THIN))
        self.assertFalse(critique_is_well_formed(d))
        self.assertFalse(critique_is_clear(d))

    def test_fit_with_attacks_held_is_clear(self):
        d = parse_critique(self._write(FIT_CRITIQUE))
        self.assertEqual(d["verdict"], "fit")
        self.assertTrue(critique_is_well_formed(d), d["problems"])
        self.assertTrue(critique_is_clear(d))

    def test_open_finding_is_not_clear(self):
        d = parse_critique(self._write(NOTFIT_OPEN))
        self.assertTrue(critique_is_well_formed(d), d["problems"])
        self.assertFalse(critique_is_clear(d))
        self.assertEqual(d["findings"][0]["status"], "open")
        self.assertEqual(d["findings"][0]["severity"], 3)

    def test_closed_findings_are_clear(self):
        d = parse_critique(self._write(NOTFIT_CLOSED))
        self.assertTrue(critique_is_well_formed(d), d["problems"])
        self.assertTrue(critique_is_clear(d))

    def test_pending_re_critique_is_not_clear(self):
        d = parse_critique(self._write(PENDING))
        self.assertTrue(critique_is_well_formed(d), d["problems"])
        self.assertFalse(critique_is_clear(d))

    def test_g2_clear_cli_problems(self):
        root = Path(tempfile.mkdtemp())
        self.assertTrue(critique_problems(root, require_clear=True))
        (root / "CRITIQUE.md").write_text(NOTFIT_OPEN)
        probs = critique_problems(root, require_clear=False)
        self.assertEqual(probs, [])
        probs = critique_problems(root, require_clear=True)
        self.assertTrue(any("open" in p for p in probs))

    def test_existence_is_not_clearance(self):
        """The old router treated file presence as G2. A not-fit file must not clear."""
        d = parse_critique(self._write(NOTFIT_OPEN))
        self.assertTrue(d["exists"])
        self.assertFalse(critique_is_clear(d))

    def test_missing_round_defaults_to_one(self):
        d = parse_critique(self._write(NOTFIT_OPEN))
        self.assertEqual(d["round"], 1)
        self.assertEqual(critique_round(d), 1)

    def test_done_without_round_defaults_to_two(self):
        """Pre-Round files that already recritiqued must not reset the cap."""
        d = parse_critique(self._write(NOTFIT_CLOSED))
        self.assertEqual(d["round"], 2)


ROUND2_CITED = """# Critique

**Verdict** not-fit
**Re-critique** done
**Round** 2
**Date** 2026-08-26

## F-01 — two [P] tasks share src/lib/session.ts
**Severity** 3
**Attack** decomposition
**Evidence** T-01-02 and T-01-03 both name src/lib/session.ts
**Change** drop [P] on T-01-03
**Status** fixed
**Disposition** [P] dropped.

## F-02 — the [P] drop did not land; T-01-03 is still parallel
**Severity** 3
**Attack** decomposition
**Evidence** T-01-03 still reads **Parallel** [P]
**Change** drop [P] on T-01-03; add Depends on T-01-02
**Status** open
**Cites** F-01
**Disposition**

## Attacks that did not land

- Over-engineering: no speculative layer.
"""

ROUND2_NO_CITES = ROUND2_CITED.replace("**Cites** F-01\n", "")

ROUND2_BAD_CITES = ROUND2_CITED.replace("**Cites** F-01", "**Cites** F-99")

ROUND4_PENDING = """# Critique

**Verdict** not-fit
**Re-critique** pending
**Round** 4
**Date** 2026-08-26

## F-01 — two [P] tasks share src/lib/session.ts
**Severity** 3
**Attack** decomposition
**Evidence** T-01-02 and T-01-03 both name src/lib/session.ts
**Change** drop [P] on T-01-03
**Status** fixed
**Disposition** plan edited; cap reached.

## Attacks that did not land

- Over-engineering: no speculative layer.
"""

ROUND4_DONE_CLOSED = ROUND4_PENDING.replace(
    "**Re-critique** pending", "**Re-critique** done"
)

ACCEPTANCE_FIXED = """# Critique

**Verdict** not-fit
**Re-critique** done
**Round** 1
**Date** 2026-08-26

## F-01 — Verify command cannot fail
**Severity** 3
**Attack** acceptance
**Evidence** T-07-01 ends npm test with no file argument
**Change** name the test file in Verify
**Status** fixed
**Disposition** Verify now names src/foo.test.ts

## Attacks that did not land

- Over-engineering: no speculative layer.
"""


class G2LoopTests(unittest.TestCase):
    def _root(self, body: str | None) -> Path:
        d = Path(tempfile.mkdtemp())
        if body is not None:
            (d / "CRITIQUE.md").write_text(body)
        return d

    def test_round2_open_requires_cites(self):
        d = parse_critique(self._root(ROUND2_NO_CITES) / "CRITIQUE.md")
        self.assertFalse(critique_is_well_formed(d), d["problems"])
        self.assertTrue(any("Cites" in p for p in d["problems"]))

    def test_round2_open_with_cites_is_well_formed(self):
        d = parse_critique(self._root(ROUND2_CITED) / "CRITIQUE.md")
        self.assertTrue(critique_is_well_formed(d), d["problems"])
        self.assertEqual(d["findings"][1]["cites"], ["F-01"])
        self.assertFalse(critique_is_clear(d))

    def test_empty_disposition_does_not_swallow_cites(self):
        body = ROUND2_CITED.replace(
            "**Cites** F-01\n**Disposition**",
            "**Disposition**\n**Cites** F-01",
        )
        d = parse_critique(self._root(body) / "CRITIQUE.md")
        self.assertEqual(d["findings"][1]["cites"], ["F-01"])
        self.assertTrue(critique_is_well_formed(d), d["problems"])

    def test_round2_cites_must_exist(self):
        d = parse_critique(self._root(ROUND2_BAD_CITES) / "CRITIQUE.md")
        self.assertFalse(critique_is_well_formed(d))
        self.assertTrue(any("F-99" in p for p in d["problems"]))

    def test_round1_open_does_not_need_cites(self):
        d = parse_critique(self._root(NOTFIT_OPEN) / "CRITIQUE.md")
        self.assertTrue(critique_is_well_formed(d), d["problems"])

    def test_spawn_missing_file(self):
        root = self._root(None)
        spawn, reason = should_spawn_critic(root, count=False)
        self.assertTrue(spawn)
        self.assertIn("missing", reason)

    def test_spawn_pending_under_cap(self):
        root = self._root(PENDING)
        spawn, reason = should_spawn_critic(root, count=False)
        self.assertTrue(spawn, reason)
        self.assertIn("pending", reason)

    def test_spawn_skips_open_findings_when_not_pending(self):
        """The loop: well-formed + done + open is G2b, not another G2a."""
        root = self._root(ROUND2_CITED)
        spawn, reason = should_spawn_critic(root, count=False)
        self.assertFalse(spawn)
        self.assertIn("G2b", reason)

    def test_pre_round_done_with_open_is_g2b_not_malformed_spawn(self):
        """In-flight files from before **Round** existed must not fail Cites
        and fork again. They go to G2b."""
        body = NOTFIT_OPEN.replace("not-required", "done")
        root = self._root(body)
        d = parse_critique(root / "CRITIQUE.md")
        self.assertEqual(d["round"], 2)
        self.assertFalse(d["round_explicit"])
        self.assertTrue(critique_is_well_formed(d), d["problems"])
        spawn, reason = should_spawn_critic(root, count=False)
        self.assertFalse(spawn)
        self.assertIn("G2b", reason)

    def test_spawn_skips_pending_at_round_cap(self):
        root = self._root(ROUND4_PENDING)
        d = parse_critique(root / "CRITIQUE.md")
        self.assertTrue(critique_is_well_formed(d), d["problems"])
        self.assertFalse(critique_is_clear(d))
        spawn, reason = should_spawn_critic(root, count=False)
        self.assertFalse(spawn)
        self.assertIn("round cap", reason)
        probs = critique_problems(root, require_clear=True)
        self.assertTrue(any("round cap" in p for p in probs))

    def test_round4_closed_done_is_clear_and_does_not_spawn(self):
        root = self._root(ROUND4_DONE_CLOSED)
        d = parse_critique(root / "CRITIQUE.md")
        self.assertTrue(critique_is_clear(d), d["problems"])
        spawn, _ = should_spawn_critic(root, count=False)
        self.assertFalse(spawn)
        allowed, reason = may_set_pending(d)
        self.assertFalse(allowed)
        self.assertIn("round cap", reason)

    def test_may_pending_graph_changing_sev3(self):
        # Round 1 just closed — Re-critique is still not-required.
        body = NOTFIT_CLOSED.replace("**Re-critique** done", "**Re-critique** not-required")
        body = body.replace("**Date**", "**Round** 1\n**Date**")
        d = parse_critique(self._root(body) / "CRITIQUE.md")
        self.assertEqual(d["round"], 1)
        self.assertTrue(finding_forces_recritique(d["findings"][0]))
        allowed, reason = may_set_pending(d)
        self.assertTrue(allowed, reason)

    def test_may_pending_ignores_historical_fixes(self):
        """A done file with no new cited findings must not keep forking."""
        d = parse_critique(self._root(NOTFIT_CLOSED) / "CRITIQUE.md")
        allowed, reason = may_set_pending(d)
        self.assertFalse(allowed)
        self.assertIn("this round", reason)

    def test_may_pending_round2_cited_fix(self):
        body = ROUND2_CITED.replace("**Status** open", "**Status** fixed", 1)
        body = body.replace(
            "**Cites** F-01\n**Disposition**",
            "**Cites** F-01\n**Disposition** still parallel; [P] dropped now.",
        )
        d = parse_critique(self._root(body) / "CRITIQUE.md")
        self.assertTrue(critique_is_well_formed(d), d["problems"])
        self.assertEqual(d["findings"][1]["status"], "fixed")
        allowed, reason = may_set_pending(d)
        self.assertTrue(allowed, reason)
        self.assertIn("F-02", reason)

    def test_may_pending_rejects_acceptance_sev3(self):
        d = parse_critique(self._root(ACCEPTANCE_FIXED) / "CRITIQUE.md")
        self.assertTrue(critique_is_clear(d), d["problems"])
        self.assertFalse(finding_forces_recritique(d["findings"][0]))
        allowed, reason = may_set_pending(d)
        self.assertFalse(allowed)
        self.assertIn("do not set pending", reason)

    def test_may_pending_rejects_open_findings(self):
        d = parse_critique(self._root(NOTFIT_OPEN) / "CRITIQUE.md")
        allowed, reason = may_set_pending(d)
        self.assertFalse(allowed)
        self.assertIn("open findings", reason)

    def test_counted_spawns_cap_at_four(self):
        root = self._root(None)
        for i in range(MAX_G2A_ROUNDS):
            spawn, reason = should_spawn_critic(root, count=True)
            self.assertTrue(spawn, f"spawn {i + 1}: {reason}")
        spawn, reason = should_spawn_critic(root, count=True)
        self.assertFalse(spawn)
        self.assertIn("spawn cap", reason)
        self.assertEqual(load_g2_state(root)["spawns"], MAX_G2A_ROUNDS)

    def test_schema_retries_cap(self):
        root = self._root(THIN)
        for i in range(MAX_G2A_SCHEMA_RETRIES):
            spawn, reason = should_spawn_critic(root, count=True)
            self.assertTrue(spawn, f"retry {i + 1}: {reason}")
        spawn, reason = should_spawn_critic(root, count=True)
        self.assertFalse(spawn)
        self.assertIn("schema retry cap", reason)

    def test_g2_spawn_cli(self):
        import subprocess
        root = self._root(ROUND2_CITED)
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "verify_gate.py"),
             "--g2-spawn", "--no-count", "--root", str(root)],
            capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertIn("G2b", proc.stderr)

        root2 = self._root(PENDING)
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "verify_gate.py"),
             "--g2-spawn", "--no-count", "--root", str(root2)],
            capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("pending", proc.stdout)

    def test_g2_may_pending_cli(self):
        import subprocess
        body = NOTFIT_CLOSED.replace(
            "**Re-critique** done", "**Re-critique** not-required"
        ).replace("**Date**", "**Round** 1\n**Date**")
        root = self._root(body)
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "verify_gate.py"),
             "--g2-may-pending", "--root", str(root)],
            capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("may set pending", proc.stdout)

        root2 = self._root(ROUND4_DONE_CLOSED)
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "verify_gate.py"),
             "--g2-may-pending", "--root", str(root2)],
            capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 1)
        self.assertIn("round cap", proc.stderr)


REQ_CLEAN = "Factory OS requirements. No open questions.\n"
REQ_DIRTY = "Scope still [NEEDS CLARIFICATION] on tenancy.\n"


def _memory(gate: str) -> str:
    return (
        f"# Working memory\n\n**Last updated** 2026-08-31\n**Gate** {gate}\n\n"
        "## 0. Immediate attention\n\n| | Item | Where |\n"
    )


class MemoryTests(unittest.TestCase):
    def _root(self, *, req=None, tasks=None, critique=None, memory=None) -> Path:
        d = Path(tempfile.mkdtemp())
        if req is not None:
            (d / "REQUIREMENTS.md").write_text(req)
        if tasks:
            tdir = d / "modules" / "M01" / "tasks"
            tdir.mkdir(parents=True)
            for i, body in enumerate(tasks, 1):
                (tdir / f"T-01-{i:02d}.md").write_text(body)
        if critique is not None:
            (d / "CRITIQUE.md").write_text(critique)
        if memory is not None:
            (d / "work").mkdir(parents=True, exist_ok=True)
            (d / "work" / "memory.md").write_text(memory)
        return d

    def test_infer_g0_missing_requirements(self):
        self.assertEqual(infer_gate(self._root()), "G0")

    def test_infer_g0_clarification(self):
        self.assertEqual(infer_gate(self._root(req=REQ_DIRTY)), "G0")

    def test_infer_g1_clean_no_tasks(self):
        self.assertEqual(infer_gate(self._root(req=REQ_CLEAN)), "G1")

    def test_infer_g2_tasks_no_critique(self):
        root = self._root(req=REQ_CLEAN, tasks=[TASK_DEV_T])
        self.assertEqual(infer_gate(root), "G2")

    def test_infer_g3_g2_clear_work_remaining(self):
        root = self._root(
            req=REQ_CLEAN, tasks=[TASK_DEV_T], critique=FIT_CRITIQUE,
        )
        self.assertEqual(infer_gate(root), "G3")

    def test_infer_g6_all_done(self):
        root = self._root(
            req=REQ_CLEAN, tasks=[TASK_DEV_DONE], critique=FIT_CRITIQUE,
        )
        self.assertEqual(infer_gate(root), "G6")

    def test_stale_g0_label_after_plan(self):
        """The FactoryOS failure: memory still says G0 after task files exist."""
        root = self._root(
            req=REQ_CLEAN, tasks=[TASK_DEV_T], memory=_memory("G0"),
        )
        self.assertEqual(infer_gate(root), "G2")
        probs = memory_problems(root)
        self.assertTrue(any("G0" in p and "G2" in p for p in probs), probs)

    def test_current_gate_is_ok(self):
        root = self._root(
            req=REQ_CLEAN, tasks=[TASK_DEV_T], critique=FIT_CRITIQUE,
            memory=_memory("G3"),
        )
        self.assertEqual(memory_problems(root), [])

    def test_g3_g5_alias(self):
        root = self._root(
            req=REQ_CLEAN, tasks=[TASK_DEV_T], critique=FIT_CRITIQUE,
            memory=_memory("G3–G5"),
        )
        self.assertEqual(memory_problems(root), [])

    def test_missing_file(self):
        root = self._root(req=REQ_CLEAN)
        probs = memory_problems(root)
        self.assertTrue(any("missing" in p for p in probs), probs)

    def test_none_placeholder_is_stale(self):
        root = self._root(req=REQ_CLEAN, memory=_memory("_none_"))
        d = parse_memory(root / "work" / "memory.md")
        self.assertIsNone(d["gate"])
        self.assertTrue(memory_problems(root))

    def test_check_memory_cli(self):
        import subprocess
        root = self._root(
            req=REQ_CLEAN, tasks=[TASK_DEV_T], memory=_memory("G0"),
        )
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "verify_gate.py"),
             "--check-memory", "--root", str(root)],
            capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 1)
        self.assertIn("stale", proc.stderr)
        self.assertIn("expected **Gate** G2", proc.stderr)

        root2 = self._root(
            req=REQ_CLEAN, tasks=[TASK_DEV_T], critique=FIT_CRITIQUE,
            memory=_memory("G3"),
        )
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "verify_gate.py"),
             "--check-memory", "--root", str(root2)],
            capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("G3", proc.stdout)


class HasUiTests(unittest.TestCase):
    def _const(self, url: str) -> Path:
        d = Path(tempfile.mkdtemp())
        (d / "constitution.md").write_text(
            f"| Purpose | Command |\n|---|---|\n| app URL | {url} |\n"
        )
        return d

    def test_placeholder_is_no_ui(self):
        self.assertFalse(has_ui(self._const("_not yet recorded_")))
        self.assertFalse(has_ui(self._const("n/a")))
        self.assertFalse(has_ui(Path(tempfile.mkdtemp())))

    def test_http_is_ui(self):
        self.assertTrue(has_ui(self._const("http://localhost:3000")))
        self.assertTrue(has_ui(self._const("https://example.test")))
        self.assertTrue(has_ui(self._const("localhost:8080")))


class TaskParseTests(unittest.TestCase):
    def test_status_tokens(self):
        d = Path(tempfile.mkdtemp())
        p = d / "T-01-01.md"
        p.write_text(TASK_DEV_DONE)
        self.assertEqual(parse_task(p)["status"], "done")
        p.write_text(TASK_DEV_T)
        self.assertEqual(parse_task(p)["status"], "in_test")


class DashboardProgressTests(unittest.TestCase):
    def test_primary_progress_uses_criteria_before_post_g5_done(self):
        root = Path(tempfile.mkdtemp()) / ".foreman"
        task = root / "modules" / "M01" / "tasks" / "T-01-01.md"
        task.parent.mkdir(parents=True)
        task.write_text(TASK_DEV_T)
        html = render_dashboard(root, static=True)
        self.assertIn('<div class="pct">100%</div>', html)
        self.assertIn("1/1 criteria met", html)
        self.assertIn(">Shipped</div><div class=\"v\">0/1", html)


class DashboardTranscriptTests(unittest.TestCase):
    def test_markdown_renders_common_blocks_and_escapes_raw_html(self):
        rendered = render_markdown(
            "# Plan\n\n**Bold** and `code`\n\n"
            "- [x] done\n- pending\n\n"
            "| File | State |\n| --- | :---: |\n| app.py | ready |\n\n"
            "```python\nprint('<unsafe>')\n```\n\n"
            "<script>alert(1)</script> [bad](javascript:alert(1))"
        )
        self.assertIn("<h1>Plan</h1>", rendered)
        self.assertIn("<strong>Bold</strong>", rendered)
        self.assertIn('<code class="md-inline">code</code>', rendered)
        self.assertIn('<span class="md-check on">✓</span>', rendered)
        self.assertIn('<div class="md-table-wrap">', rendered)
        self.assertIn('class="language-python"', rendered)
        self.assertIn("print(&#x27;&lt;unsafe&gt;&#x27;)", rendered)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", rendered)
        self.assertNotIn("<script>", rendered)
        self.assertNotIn('href="javascript:', rendered)

    def test_feed_is_chat_and_separates_command_from_output(self):
        rendered = render_feed([
            {"kind": "text", "detail": "## Update\n\nTests are **green**.", "ok": None},
            {"kind": "tool", "tool": "Bash", "title": "Bash · run tests",
             "input": "npm test", "output": "4 passed", "language": "shell",
             "output_language": "terminal", "input_label": "command", "ok": True},
            {"kind": "result", "title": "success · 2 turns", "detail": "G3 passed", "ok": True},
        ])
        self.assertIn('class="chat-row assistant-message"', rendered)
        self.assertIn("<h2>Update</h2>", rendered)
        self.assertIn("Tests are <strong>green</strong>.", rendered)
        self.assertIn('<details class="tool-card ok">', rendered)
        self.assertIn('<span class="code-label">command</span>', rendered)
        self.assertIn('<span class="code-label">output</span>', rendered)
        self.assertIn('class="code-viewer terminal"', rendered)
        self.assertIn("npm test", rendered)
        self.assertIn("4 passed", rendered)
        self.assertIn('class="chat-row result-event"', rendered)

    def test_live_dashboard_has_accessible_transcript_controls(self):
        root = Path(tempfile.mkdtemp()) / ".foreman"
        task = root / "modules" / "M01" / "tasks" / "T-01-01.md"
        task.parent.mkdir(parents=True)
        task.write_text(
            "# T-01-01 — Render task transcript\n"
            "**Module** M01 · **Status** `[~]` · **Parallel** [P]\n"
            "**Session** dev-m01-01 · **Est** 4 turns\n\n"
            "## Acceptance\n- [ ] WHEN opened THE SYSTEM SHALL show activity\n"
        )
        sdir = root / "work" / "sessions" / "dev-m01-01"
        sdir.mkdir(parents=True)
        (sdir / "status.json").write_text(json.dumps({
            "name": "dev-m01-01", "agent": "foreman-developer",
            "state": "running", "turns": 2,
        }))
        (sdir / "stream.jsonl").write_text(
            '{"type":"assistant","message":{"content":['
            '{"type":"text","text":"**Working**"}]}}\n'
        )
        rendered = render_dashboard(root, static=False)
        self.assertIn('id="feed" class="feed" aria-hidden="true" inert', rendered)
        self.assertIn('role="dialog" aria-modal="true"', rendered)
        self.assertIn('data-open-session="dev-m01-01"', rendered)
        self.assertIn('data-toggle-tools', rendered)
        self.assertIn('data-feed-latest', rendered)
        self.assertIn('data-title="T-01-01 — Render task transcript"', rendered)
        self.assertIn('data-live="true"', rendered)
        self.assertIn('data-summary="dev-m01-01 · foreman-developer · running · 2 turns · 1 events"', rendered)
        self.assertIn("Chat transcript from stream.jsonl", rendered)


class StopGateTests(unittest.TestCase):
    def _task(self, body: str) -> Path:
        p = Path(tempfile.mkdtemp()) / "T-01-01.md"
        p.write_text(body)
        return p

    def test_missing_task_file_line_blocks(self):
        problems = task_gate_problems("foreman-developer", "no line here", Path("."))
        self.assertTrue(any("Task file" in p for p in problems))

    def test_missing_path_blocks(self):
        problems = task_gate_problems(
            "foreman-developer",
            "**Task file** /no/such/task.md\n",
            Path("."),
        )
        self.assertTrue(any("does not exist" in p for p in problems))

    def test_missing_acceptance_blocks(self):
        p = self._task("# T-01-01 — x\n**Status** `[~]`\n\n## Why\nhi\n")
        problems = task_gate_problems(
            "foreman-developer", BRIEF.format(path=p), Path(".")
        )
        self.assertTrue(any("Acceptance" in p for p in problems))

    def test_developer_x_rejected(self):
        p = self._task(TASK_DEV_DONE)
        problems = task_gate_problems(
            "foreman-developer", BRIEF.format(path=p), Path(".")
        )
        self.assertTrue(any("[x]" in p and "[t]" in p for p in problems))

    def test_developer_t_accepted(self):
        p = self._task(TASK_DEV_T)
        problems = task_gate_problems(
            "foreman-developer", BRIEF.format(path=p), Path(".")
        )
        self.assertEqual(problems, [])

    def test_unchecked_still_blocks(self):
        p = self._task(TASK_UNCHECKED)
        problems = task_gate_problems(
            "foreman-developer", BRIEF.format(path=p), Path(".")
        )
        self.assertTrue(any("unchecked" in p for p in problems))

    def test_tester_may_leave_t(self):
        p = self._task(TASK_DEV_T)
        problems = task_gate_problems(
            "foreman-tester", BRIEF.format(path=p), Path(".")
        )
        self.assertEqual(problems, [])

    def test_tester_may_report_a_falsified_criterion(self):
        p = self._task(TASK_UNCHECKED.replace(
            "- 2026-08-26 npm test -- session → 4 passed", ""
        ))
        problems = task_gate_problems(
            "foreman-tester", BRIEF.format(path=p), Path(".")
        )
        self.assertEqual(problems, [])

    def test_session_resolves_relative_task_in_worker_cwd(self):
        manager = Path(tempfile.mkdtemp())
        worker = Path(tempfile.mkdtemp())
        rel = Path(".foreman/modules/M01/tasks/T-01-01.md")
        (manager / rel).parent.mkdir(parents=True)
        (worker / rel).parent.mkdir(parents=True)
        (manager / rel).write_text(TASK_UNCHECKED)
        (worker / rel).write_text(TASK_DEV_T)
        sdir = Path(tempfile.mkdtemp())
        (sdir / "brief.md").write_text(BRIEF.format(path=rel))
        status = {"agent": "foreman-developer", "cwd": str(worker)}
        problems = session_gate_problems(sdir, status)
        self.assertEqual(problems, [])

    def test_deferred_gate_with_open_problems_needs_review(self):
        task = self._task(TASK_DEV_T)
        sdir = Path(tempfile.mkdtemp())
        (sdir / "brief.md").write_text(BRIEF.format(path=task))
        (sdir / "status.json").write_text(json.dumps({
            "name": "test-m01-01", "agent": "foreman-tester", "pid": 0,
            "cwd": str(Path(tempfile.mkdtemp())), "gate_blocks": 3,
            "started_at": int(time.time()),
        }))
        (sdir / "stream.jsonl").write_text(
            '{"type":"result","subtype":"success"}\n'
        )
        from unittest.mock import patch
        with patch.dict(os.environ, {"FOREMAN_SESSION_DIR": str(sdir)}, clear=False):
            self.assertEqual(stop_hook(), 0)
        status = json.loads((sdir / "status.json").read_text())
        self.assertTrue(status["gate_deferred"])
        self.assertEqual(assess(sdir, time.time())["state"], "review:gate_deferred")

    def test_deferred_gate_with_complete_artefacts_is_ready(self):
        task = self._task(TASK_DEV_T)
        sdir = Path(tempfile.mkdtemp())
        (sdir / "brief.md").write_text(BRIEF.format(path=task))
        (sdir / "status.json").write_text(json.dumps({
            "name": "dev-m01-01", "agent": "foreman-developer", "pid": 0,
            "cwd": str(task.parent), "gate_deferred": True,
            "gate_problems": ["legacy provenance was unavailable"],
            "started_at": int(time.time()),
        }))
        (sdir / "stream.jsonl").write_text(
            '{"type":"result","subtype":"success"}\n'
        )
        result = assess(sdir, time.time())
        self.assertEqual(result["completion_problems"], [])
        self.assertEqual(result["state"], "ready:gate_deferred")


class EvidenceGateTests(unittest.TestCase):
    def test_tester_requires_case_and_result_files(self):
        sdir = Path(tempfile.mkdtemp())
        self.assertTrue(tester_evidence_problems(sdir))
        (sdir / "testcases.md").write_text(
            "# Cases\n\n## TC-01 — happy path\n\n**Expected** success\n"
        )
        self.assertTrue(tester_evidence_problems(sdir))

    def test_tester_failure_is_complete_evidence(self):
        sdir = Path(tempfile.mkdtemp())
        (sdir / "testcases.md").write_text(
            "# Cases\n\n## TC-01 — happy path\n\n**Expected** success\n\n"
            "## TC-02 — malformed input\n\n**Expected** validation error\n"
        )
        (sdir / "results.md").write_text(
            "# Results\n\n**Verdict** fail\n\n"
            "## TC-01 — happy path\n**Outcome** pass\n**Evidence** command exited 0\n\n"
            "## TC-02 — malformed input\n**Outcome** fail\n"
            "**Evidence** expected 400, got 500\n"
        )
        self.assertEqual(tester_evidence_problems(sdir), [])

    def test_results_cover_every_declared_case(self):
        sdir = Path(tempfile.mkdtemp())
        (sdir / "testcases.md").write_text(
            "# Cases\n\n## TC-01 — one\n\n**Expected** A\n\n"
            "## TC-02 — two\n\n**Expected** B\n"
        )
        (sdir / "results.md").write_text(
            "# Results\n\n**Verdict** pass\n\n"
            "## TC-01 — one\n**Outcome** pass\n**Evidence** A observed\n"
        )
        problems = tester_evidence_problems(sdir)
        self.assertTrue(any("TC-02" in p for p in problems))

    def test_beta_requires_structured_review(self):
        sdir = Path(tempfile.mkdtemp())
        self.assertTrue(beta_evidence_problems(sdir))
        (sdir / "beta-review.md").write_text(
            "# Beta review\n\n**Surface** no-ui\n**Verdict** pass\n\n"
            "## Findings\n\n- None.\n\n## What worked\n\n- Clear errors.\n"
        )
        self.assertEqual(beta_evidence_problems(sdir), [])

    def test_beta_finding_requires_severity_place_and_fix(self):
        sdir = Path(tempfile.mkdtemp())
        (sdir / "beta-review.md").write_text(
            "# Beta review\n\n**Surface** ui\n**Verdict** fail\n\n"
            "## Findings\n\n### B-01 — vague\n\nSomething felt wrong.\n\n"
            "## What worked\n\n- Navigation.\n"
        )
        problems = beta_evidence_problems(sdir)
        self.assertTrue(any("Severity" in p for p in problems))
        self.assertTrue(any("Place" in p for p in problems))
        self.assertTrue(any("Fix" in p for p in problems))


class WorktreeHandoffTests(unittest.TestCase):
    TASK_BACKLOG = """# T-01-01 — Feature
**Status** `[ ]`

## Acceptance
- [ ] WHEN invoked THE SYSTEM SHALL return the feature

## Activity log
"""
    TASK_IN_PROGRESS = TASK_BACKLOG.replace("**Status** `[ ]`", "**Status** `[~]`")
    TASK_IN_TEST = TASK_IN_PROGRESS.replace(
        "**Status** `[~]`", "**Status** `[t]`"
    ).replace("- [ ] WHEN", "- [x] WHEN") + "\n- verify → EXIT=0\n"

    def setUp(self):
        self.project = Path(tempfile.mkdtemp())
        self._git("init", "-b", "master")
        self._git("config", "user.email", "foreman-tests@example.test")
        self._git("config", "user.name", "Foreman Tests")
        (self.project / ".gitignore").write_text(
            ".claude/worktrees/\n.grok/worktrees/\n"
        )
        self.root = self.project / ".foreman"
        (self.root / "work" / "sessions").mkdir(parents=True)
        (self.root / ".gitignore").write_text("work/\n")
        (self.root / "task.md").write_text(self.TASK_BACKLOG)
        (self.root / "log.md").write_text("# Activity log\n")
        (self.project / "feature.txt").write_text("base\n")
        self._git(
            "add", ".gitignore", ".foreman/.gitignore", ".foreman/task.md",
            ".foreman/log.md", "feature.txt",
        )
        self._git("commit", "-m", "base")

    def _git(self, *args: str, cwd: Path | None = None) -> str:
        p = subprocess.run(
            ["git", "-C", str(cwd or self.project), *args],
            check=True, capture_output=True, text=True,
        )
        return p.stdout.strip()

    def _prepare_dev(self, name: str = "dev-m01-01") -> dict:
        (self.root / "task.md").write_text(self.TASK_IN_PROGRESS)
        result = prepare_worker_worktree(
            self.project, self.root, name=name, agent="foreman-developer",
            harness="claude",
        )
        self._write_status(name, result)
        return result

    def _write_status(self, name: str, result: dict, *, pid: int = 0,
                      agent: str = "foreman-developer") -> None:
        sdir = self.root / "work" / "sessions" / name
        sdir.mkdir(parents=True, exist_ok=True)
        status = {
            "name": name, "agent": agent, "pid": pid,
            "state": "done",
            **{k: result[k] for k in (
                "cwd", "branch", "base_ref", "base_commit", "start_commit",
                "lineage_start_commit", "base_session",
            )},
        }
        (sdir / "status.json").write_text(json.dumps(status))
        (sdir / "brief.md").write_text(
            BRIEF.format(path=".foreman/task.md")
        )
        if agent == "foreman-tester":
            (sdir / "testcases.md").write_text(
                "# Cases\n\n## TC-01 — feature\n**Expected** feature is returned\n"
            )
            (sdir / "results.md").write_text(
                "# Results\n\n**Verdict** pass\n\n"
                "## TC-01 — feature\n**Outcome** pass\n"
                "**Evidence** command exited 0\n"
            )

    def _commit_dev_work(self, result: dict) -> str:
        cwd = Path(result["cwd"])
        (cwd / "feature.txt").write_text("developer version\n")
        (cwd / ".foreman" / "task.md").write_text(self.TASK_IN_TEST)
        self._git("add", "feature.txt", ".foreman/task.md", cwd=cwd)
        self._git("commit", "-m", "implement task", cwd=cwd)
        return self._git("rev-parse", "HEAD", cwd=cwd)

    def test_uninferable_start_is_unknown_not_zero(self):
        snap = worktree_snapshot(self.project)
        self.assertIsNone(snap["commits_ahead"])
        self.assertEqual(snap["start_commit_source"], "unknown")

    def test_tester_defaults_to_committed_developer_branch(self):
        dev = self._prepare_dev()
        dev_tip = self._commit_dev_work(dev)
        tester = prepare_worker_worktree(
            self.project, self.root, name="test-m01-01", agent="foreman-tester",
            harness="claude",
        )
        self.assertEqual(tester["base_ref"], "foreman/dev-m01-01")
        self.assertEqual(tester["base_commit"], dev_tip)
        self.assertEqual(
            (Path(tester["cwd"]) / "feature.txt").read_text(),
            "developer version\n",
        )
        self._git("merge-base", "--is-ancestor", dev_tip, tester["branch"])

    def test_git_tester_cannot_bypass_handoff_with_no_worktree(self):
        dev = self._prepare_dev()
        self._commit_dev_work(dev)
        with self.assertRaisesRegex(WorktreeError, "requires an isolated git worktree"):
            prepare_worker_worktree(
                self.project, self.root, name="test-m01-01",
                agent="foreman-tester", harness="claude", use_worktree=False,
            )

    def test_root_snapshot_excludes_manager_owned_log(self):
        (self.root / "log.md").write_text("# Activity log\n\n- manager spawn\n")
        dev = self._prepare_dev()
        self.assertEqual(
            (Path(dev["cwd"]) / ".foreman" / "log.md").read_text(),
            "# Activity log\n",
        )

    def test_dirty_predecessor_is_not_claimed_as_preserved(self):
        dev = self._prepare_dev()
        self._commit_dev_work(dev)
        (Path(dev["cwd"]) / "lost.txt").write_text("uncommitted\n")
        with self.assertRaisesRegex(WorktreeError, "uncommitted work"):
            prepare_worker_worktree(
                self.project, self.root, name="test-m01-01",
                agent="foreman-tester", harness="claude",
            )

    def test_foreman_base_without_session_metadata_is_rejected(self):
        dev = self._prepare_dev()
        self._commit_dev_work(dev)
        status_path = (
            self.root / "work" / "sessions" / "dev-m01-01" / "status.json"
        )
        status_path.unlink()
        with self.assertRaisesRegex(WorktreeError, "no matching session metadata"):
            prepare_worker_worktree(
                self.project, self.root, name="test-m01-01",
                agent="foreman-tester", harness="claude",
            )

    def test_empty_predecessor_branch_is_rejected(self):
        self._prepare_dev()
        with self.assertRaisesRegex(WorktreeError, "no worker commit"):
            prepare_worker_worktree(
                self.project, self.root, name="test-m01-01",
                agent="foreman-tester", harness="claude",
            )

    def test_inherited_commit_does_not_hide_empty_developer_session(self):
        first = self._prepare_dev("dev-m01-01")
        self._commit_dev_work(first)
        second = prepare_worker_worktree(
            self.project, self.root, name="dev-m01-02",
            agent="foreman-developer", harness="claude",
            requested_base="foreman/dev-m01-01",
        )
        self._write_status("dev-m01-02", second)
        with self.assertRaisesRegex(WorktreeError, "no worker commit"):
            prepare_worker_worktree(
                self.project, self.root, name="test-m01-02",
                agent="foreman-tester", harness="claude",
            )

    def test_fix_worker_may_base_on_tester_with_no_new_commit(self):
        dev = self._prepare_dev()
        self._commit_dev_work(dev)
        tester = prepare_worker_worktree(
            self.project, self.root, name="test-m01-01",
            agent="foreman-tester", harness="claude",
        )
        self._write_status("test-m01-01", tester, agent="foreman-tester")
        fix = prepare_worker_worktree(
            self.project, self.root, name="dev-m01-01-fix-1",
            agent="foreman-developer", harness="claude",
            requested_base="foreman/test-m01-01",
        )
        self.assertEqual(fix["base_session"], "test-m01-01")
        self.assertEqual(fix["base_commit"], tester["base_commit"])

    def test_corrupt_predecessor_lineage_is_rejected(self):
        dev = self._prepare_dev()
        self._commit_dev_work(dev)
        unrelated = self._git("commit-tree", "HEAD^{tree}", "-m", "unrelated")
        status_path = (
            self.root / "work" / "sessions" / "dev-m01-01" / "status.json"
        )
        status = json.loads(status_path.read_text())
        status["lineage_start_commit"] = unrelated
        status_path.write_text(json.dumps(status))
        with self.assertRaisesRegex(WorktreeError, "unverifiable handoff"):
            prepare_worker_worktree(
                self.project, self.root, name="test-m01-01",
                agent="foreman-tester", harness="claude",
            )

    def test_legacy_status_infers_real_worker_commit(self):
        dev = self._prepare_dev()
        dev_tip = self._commit_dev_work(dev)
        sdir = self.root / "work" / "sessions" / "dev-m01-01"
        (sdir / "status.json").write_text(json.dumps({
            "name": "dev-m01-01", "agent": "foreman-developer", "pid": 0,
            "cwd": dev["cwd"], "branch": dev["branch"],
        }))
        tester = prepare_worker_worktree(
            self.project, self.root, name="test-m01-01", agent="foreman-tester",
            harness="claude",
        )
        self.assertEqual(tester["base_commit"], dev_tip)

    def test_legacy_bookkeeping_only_branch_is_rejected(self):
        dev = self._prepare_dev()
        sdir = self.root / "work" / "sessions" / "dev-m01-01"
        (sdir / "status.json").write_text(json.dumps({
            "name": "dev-m01-01", "agent": "foreman-developer", "pid": 0,
            "cwd": dev["cwd"], "branch": dev["branch"],
        }))
        with self.assertRaisesRegex(WorktreeError, "no worker commit"):
            prepare_worker_worktree(
                self.project, self.root, name="test-m01-01",
                agent="foreman-tester", harness="claude",
            )

    def test_live_predecessor_is_rejected(self):
        dev = self._prepare_dev()
        self._commit_dev_work(dev)
        self._write_status("dev-m01-01", dev, pid=os.getpid())
        with self.assertRaisesRegex(WorktreeError, "still running"):
            prepare_worker_worktree(
                self.project, self.root, name="test-m01-01",
                agent="foreman-tester", harness="claude",
            )

    def test_same_name_retry_resumes_after_manager_head_moves(self):
        dev = self._prepare_dev()
        self._commit_dev_work(dev)
        (self.root / "log.md").write_text("# Activity log\n\n- manager advanced\n")
        self._git("add", ".foreman/log.md")
        self._git("commit", "-m", "manager bookkeeping")
        resumed = prepare_worker_worktree(
            self.project, self.root, name="dev-m01-01",
            agent="foreman-developer", harness="claude",
        )
        self.assertTrue(resumed["reused"])
        self.assertEqual(resumed["cwd"], dev["cwd"])

    def test_snapshot_reports_dirty_and_commits_ahead(self):
        dev = self._prepare_dev()
        self._commit_dev_work(dev)
        cwd = Path(dev["cwd"])
        (cwd / "probe.mjs").write_text("scratch\n")
        snap = worktree_snapshot(cwd, dev["start_commit"])
        self.assertEqual(snap["commits_ahead"], 1)
        self.assertIn("probe.mjs", snap["dirty_paths"])

    def test_legacy_snapshot_infers_start_and_committed_paths(self):
        dev = self._prepare_dev()
        self._commit_dev_work(dev)
        cwd = Path(dev["cwd"])
        snap = worktree_snapshot(cwd)
        self.assertEqual(snap["start_commit_source"], "inferred:primary-merge-base")
        self.assertEqual(snap["effective_start_commit"], dev["start_commit"])
        self.assertEqual(snap["commits_ahead"], 1)
        self.assertIn("feature.txt", snap["committed_paths"])
        self.assertNotIn(".foreman/log.md", snap["committed_paths"])

    def test_legacy_status_no_longer_reads_as_zero_commits(self):
        dev = self._prepare_dev()
        self._commit_dev_work(dev)
        sdir = self.root / "work" / "sessions" / "dev-m01-01"
        status = json.loads((sdir / "status.json").read_text())
        for key in ("start_commit", "base_commit", "lineage_start_commit"):
            status.pop(key, None)
        self.assertEqual(session_gate_problems(sdir, status), [])

    def test_legacy_status_still_detects_committed_manager_paths(self):
        dev = self._prepare_dev()
        self._commit_dev_work(dev)
        cwd = Path(dev["cwd"])
        (cwd / ".foreman" / "log.md").write_text(
            "# Activity log\n\n- committed by worker\n"
        )
        self._git("add", ".foreman/log.md", cwd=cwd)
        self._git("commit", "-m", "worker changed manager log", cwd=cwd)
        sdir = self.root / "work" / "sessions" / "dev-m01-01"
        status = json.loads((sdir / "status.json").read_text())
        for key in ("start_commit", "base_commit", "lineage_start_commit"):
            status.pop(key, None)
        problems = session_gate_problems(sdir, status)
        self.assertTrue(any("manager-owned" in problem for problem in problems))

    def test_completed_worker_at_turn_cap_is_ready(self):
        dev = self._prepare_dev()
        self._commit_dev_work(dev)
        sdir = self.root / "work" / "sessions" / "dev-m01-01"
        status = json.loads((sdir / "status.json").read_text())
        status.update(pid=0, started_at=int(time.time()), max_turns=10)
        status.pop("start_commit", None)  # exercise the legacy inference path too
        (sdir / "status.json").write_text(json.dumps(status))
        (sdir / "stream.jsonl").write_text(
            '{"type":"result","subtype":"error_max_turns","is_error":true}\n'
        )
        result = assess(sdir, time.time())
        self.assertEqual(result["completion_problems"], [])
        self.assertEqual(result["state"], "ready:error_max_turns")

    def test_supervisor_flags_dirty_checkpoint_and_salvage(self):
        dev = self._prepare_dev()
        self._commit_dev_work(dev)
        cwd = Path(dev["cwd"])
        (cwd / "unfinished.ts").write_text("work\n")
        sdir = self.root / "work" / "sessions" / "dev-m01-01"
        status = json.loads((sdir / "status.json").read_text())
        status.update(
            pid=os.getpid(), max_turns=10, started_at=int(time.time()),
            deadline_ts=int(time.time()) + 3600, budget_usd=15, compact_pct=55,
        )
        (sdir / "status.json").write_text(json.dumps(status))
        (sdir / "stream.jsonl").write_text("".join(
            '{"type":"assistant","message":{"usage":{"input_tokens":1}}}\n'
            for _ in range(4)
        ))
        running = assess(sdir, time.time())
        self.assertTrue(running["checkpoint_pressure"])
        self.assertFalse(running["needs_salvage"])
        status["pid"] = 0
        (sdir / "status.json").write_text(json.dumps(status))
        stopped = assess(sdir, time.time())
        self.assertTrue(stopped["needs_salvage"])

    def test_beta_gate_rejects_source_edits_and_commits(self):
        beta = prepare_worker_worktree(
            self.project, self.root, name="beta-m01",
            agent="foreman-beta-tester", harness="claude",
        )
        self._write_status(
            "beta-m01", beta, agent="foreman-beta-tester",
        )
        sdir = self.root / "work" / "sessions" / "beta-m01"
        (sdir / "beta-review.md").write_text(
            "# Beta review\n\n**Surface** no-ui\n**Verdict** pass\n\n"
            "## Findings\n\n- None.\n\n## What worked\n\n- Clear output.\n"
        )
        cwd = Path(beta["cwd"])
        (cwd / "feature.txt").write_text("beta edit\n")
        status = json.loads((sdir / "status.json").read_text())
        problems = session_gate_problems(sdir, status)
        self.assertTrue(any("uncommitted" in p for p in problems))

        self._git("add", "feature.txt", cwd=cwd)
        self._git("commit", "-m", "beta must not change source", cwd=cwd)
        problems = session_gate_problems(sdir, status)
        self.assertTrue(any("review-only" in p for p in problems))

    def _integrate(self, name: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(ROOT / "scripts" / "integrate.sh"), "--name", name,
             "--root", str(self.root), "--base", "master"],
            cwd=self.project, capture_output=True, text=True,
        )

    def test_integrate_refuses_dirty_worktree_without_sweeping_it(self):
        dev = self._prepare_dev()
        self._commit_dev_work(dev)
        cwd = Path(dev["cwd"])
        (cwd / "zz-probe1.mjs").write_text("do not ship\n")
        result = self._integrate("dev-m01-01")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("uncommitted work", result.stdout + result.stderr)
        self.assertTrue((cwd / "zz-probe1.mjs").exists())
        show = subprocess.run(
            ["git", "-C", str(self.project), "show", "master:zz-probe1.mjs"],
            capture_output=True, text=True,
        )
        self.assertNotEqual(show.returncode, 0)

    def test_integrate_refuses_live_worker(self):
        dev = self._prepare_dev()
        self._commit_dev_work(dev)
        self._write_status("dev-m01-01", dev, pid=os.getpid())
        result = self._integrate("dev-m01-01")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("still running", result.stdout + result.stderr)
        self.assertTrue(Path(dev["cwd"]).is_dir())

    def test_integrate_refuses_prelaunch_status_with_pid_zero(self):
        dev = self._prepare_dev()
        self._commit_dev_work(dev)
        status_path = (
            self.root / "work" / "sessions" / "dev-m01-01" / "status.json"
        )
        status = json.loads(status_path.read_text())
        status.update(state="starting", pid=0)
        status_path.write_text(json.dumps(status))

        result = self._integrate("dev-m01-01")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not in a terminal state", result.stdout + result.stderr)
        self.assertTrue(Path(dev["cwd"]).is_dir())

    def test_integrate_accepts_complete_worker_stopped_at_turn_cap(self):
        dev = self._prepare_dev()
        self._commit_dev_work(dev)
        status_path = (
            self.root / "work" / "sessions" / "dev-m01-01" / "status.json"
        )
        status = json.loads(status_path.read_text())
        status.update(state="stopped:error_max_turns", pid=0)
        status_path.write_text(json.dumps(status))

        result = self._integrate("dev-m01-01")
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertIn("validated completed artefacts", output)
        self.assertEqual((self.project / "feature.txt").read_text(), "developer version\n")

    def test_integrate_infers_lineage_for_legacy_capped_session(self):
        dev = self._prepare_dev()
        self._commit_dev_work(dev)
        status_path = (
            self.root / "work" / "sessions" / "dev-m01-01" / "status.json"
        )
        status = json.loads(status_path.read_text())
        status.update(state="stopped:error_max_turns", pid=0)
        for key in ("start_commit", "base_commit", "lineage_start_commit"):
            status.pop(key, None)
        status_path.write_text(json.dumps(status))

        result = self._integrate("dev-m01-01")
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertIn("inferred legacy lineage start", output)
        self.assertEqual((self.project / "feature.txt").read_text(), "developer version\n")

    def test_integrate_legacy_done_checks_committed_manager_paths(self):
        dev = self._prepare_dev()
        self._commit_dev_work(dev)
        cwd = Path(dev["cwd"])
        (cwd / ".foreman" / "log.md").write_text(
            "# Activity log\n\n- worker-owned mistake\n"
        )
        self._git("add", ".foreman/log.md", cwd=cwd)
        self._git("commit", "-m", "worker changed manager log", cwd=cwd)
        status_path = (
            self.root / "work" / "sessions" / "dev-m01-01" / "status.json"
        )
        status = json.loads(status_path.read_text())
        for key in ("start_commit", "base_commit", "lineage_start_commit"):
            status.pop(key, None)
        status_path.write_text(json.dumps(status))

        result = self._integrate("dev-m01-01")
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("manager-owned", output)
        self.assertTrue(cwd.is_dir())

    def test_foreman_only_conflict_is_not_called_a_planning_error(self):
        dev = self._prepare_dev()
        cwd = Path(dev["cwd"])
        (cwd / ".foreman" / "log.md").write_text(
            "# Activity log\n\n- worker append\n"
        )
        self._git("add", ".foreman/log.md", cwd=cwd)
        self._git("commit", "-m", "worker touched coordination log", cwd=cwd)
        (self.root / "log.md").write_text(
            "# Activity log\n\n- manager append\n"
        )

        result = self._integrate("dev-m01-01")
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("bookkeeping/coordination conflict", output)
        self.assertNotIn("planning error", output)
        self.assertTrue(cwd.is_dir())

    def test_integrate_rejects_complete_but_failing_tester_verdict(self):
        dev = self._prepare_dev()
        self._commit_dev_work(dev)
        tester = prepare_worker_worktree(
            self.project, self.root, name="test-m01-01",
            agent="foreman-tester", harness="claude",
        )
        self._write_status("test-m01-01", tester, agent="foreman-tester")
        results = (
            self.root / "work" / "sessions" / "test-m01-01" / "results.md"
        )
        results.write_text(results.read_text().replace(
            "**Verdict** pass", "**Verdict** fail"
        ))

        result = self._integrate("test-m01-01")
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not `pass`", output)
        self.assertTrue(Path(tester["cwd"]).is_dir())
        self.assertEqual((self.project / "feature.txt").read_text(), "base\n")

    def test_clean_tester_branch_carries_developer_work_into_master(self):
        dev = self._prepare_dev()
        self._commit_dev_work(dev)
        tester = prepare_worker_worktree(
            self.project, self.root, name="test-m01-01", agent="foreman-tester",
            harness="claude",
        )
        self._write_status(
            "test-m01-01", tester, agent="foreman-tester",
        )
        (self.root / "log.md").write_text(
            "# Activity log\n\n- manager changed while workers ran\n"
        )
        result = self._integrate("test-m01-01")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("command not found", result.stdout + result.stderr)
        self.assertEqual((self.project / "feature.txt").read_text(), "developer version\n")
        self.assertFalse(Path(tester["cwd"]).exists())
        self.assertFalse(Path(dev["cwd"]).exists())
        self.assertNotEqual(
            subprocess.run(
                ["git", "-C", str(self.project), "show-ref", "--verify", "--quiet",
                 "refs/heads/foreman/dev-m01-01"],
            ).returncode,
            0,
        )


class HarnessTests(unittest.TestCase):
    def test_spawn_adapters_persist_start_commit(self):
        for harness in ("claude", "grok"):
            source = (
                ROOT / "scripts" / "adapters" / harness / "spawn.sh"
            ).read_text()
            self.assertIn('"start_commit": prep["start_commit"]', source)
            self.assertIn(
                '"lineage_start_commit": prep["lineage_start_commit"]', source
            )

    def test_explicit_env_wins(self):
        import os
        from unittest.mock import patch
        with patch.dict(os.environ, {"FOREMAN_HARNESS": "grok", "CLAUDE_PLUGIN_ROOT": "/x"}, clear=False):
            self.assertEqual(detect_harness(), "grok")
        with patch.dict(os.environ, {"FOREMAN_HARNESS": "claude", "GROK_SESSION_ID": "abc"}, clear=False):
            self.assertEqual(detect_harness(), "claude")

    def test_stamp_file(self):
        import os
        from unittest.mock import patch
        d = Path(tempfile.mkdtemp())
        (d / "work").mkdir()
        (d / "work" / "harness").write_text("grok\n")
        env = {k: v for k, v in os.environ.items()
               if k not in ("FOREMAN_HARNESS", "GROK_SESSION_ID", "GROK_AGENT",
                            "GROK_PLUGIN_ROOT", "CLAUDECODE", "CLAUDE_CODE")}
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(detect_harness(d), "grok")

    def test_grok_session_id(self):
        import os
        from unittest.mock import patch
        env = {k: v for k, v in os.environ.items() if k != "FOREMAN_HARNESS"}
        env["GROK_SESSION_ID"] = "sess"
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(detect_harness(), "grok")

    def test_default_claude(self):
        import os
        from unittest.mock import patch
        keep = {k: v for k, v in os.environ.items()
                if k not in ("FOREMAN_HARNESS", "GROK_SESSION_ID", "GROK_AGENT",
                             "GROK_PLUGIN_ROOT", "CLAUDECODE", "CLAUDE_CODE",
                             "CLAUDE_PLUGIN_ROOT")}
        with patch.dict(os.environ, keep, clear=True):
            self.assertEqual(detect_harness(), "claude")


class StreamTests(unittest.TestCase):
    def test_claude_result_success(self):
        p = Path(tempfile.mkdtemp()) / "stream.jsonl"
        p.write_text(
            '{"type":"assistant","message":{"model":"claude-opus-4","usage":'
            '{"input_tokens":10,"cache_read_input_tokens":2,"cache_creation_input_tokens":0}}}\n'
            '{"type":"result","subtype":"success","total_cost_usd":1.25}\n'
        )
        s = read_stream(p)
        self.assertTrue(s["finished"])
        self.assertEqual(s["result_subtype"], "success")
        self.assertEqual(s["cost_usd"], 1.25)
        self.assertEqual(s["turns"], 1)
        self.assertEqual(s["context_tokens"], 12)

    def test_grok_result_end_turn(self):
        p = Path(tempfile.mkdtemp()) / "stream.jsonl"
        p.write_text(
            '{"type":"assistant","message":{"model":"grok-4.6","usage":'
            '{"input_tokens":8,"cache_read_input_tokens":0,"cache_creation_input_tokens":0}}}\n'
            '{"type":"result","subtype":"success","is_error":false,"num_turns":4,'
            '"total_cost_usd":0.5,"stop_reason":"end_turn"}\n'
        )
        s = read_stream(p)
        self.assertTrue(s["finished"])
        self.assertEqual(s["result_subtype"], "success")
        self.assertEqual(s["turns"], 4)
        self.assertEqual(s["cost_usd"], 0.5)

    def test_grok_end_event(self):
        p = Path(tempfile.mkdtemp()) / "stream.jsonl"
        p.write_text('{"type":"end","stopReason":"end_turn","num_turns":2,"total_cost_usd":0.1}\n')
        s = read_stream(p)
        self.assertTrue(s["finished"])
        self.assertEqual(s["result_subtype"], "success")


class StreamActivityTests(unittest.TestCase):
    def test_skips_system_and_pairs_tool_output(self):
        p = Path(tempfile.mkdtemp()) / "stream.jsonl"
        p.write_text(
            '{"type":"system","subtype":"init"}\n'
            '{"type":"assistant","message":{"content":['
            '{"type":"text","text":"Starting."},'
            '{"type":"tool_use","id":"t1","name":"Bash",'
            '"input":{"command":"npm test","description":"run tests"}}]}}\n'
            '{"type":"user","message":{"content":['
            '{"type":"tool_result","tool_use_id":"t1","content":"ok\\n4 passed"}]}}\n'
            '{"type":"result","subtype":"success","is_error":false,'
            '"num_turns":2,"total_cost_usd":1.5,"result":"G3 passed"}\n'
        )
        feed = parse_stream_activity(p)
        kinds = [e["kind"] for e in feed]
        self.assertEqual(kinds, ["text", "tool", "result"])
        self.assertEqual(feed[0]["detail"], "Starting.")
        self.assertIn("run tests", feed[1]["title"])
        self.assertIn("npm test", feed[1]["detail"])
        self.assertIn("4 passed", feed[1]["detail"])
        self.assertEqual(feed[1]["input"], "npm test")
        self.assertEqual(feed[1]["output"], "ok\n4 passed")
        self.assertEqual(feed[1]["language"], "shell")
        self.assertEqual(feed[1]["output_language"], "terminal")
        self.assertEqual(feed[1]["input_label"], "command")
        self.assertTrue(feed[1]["ok"])
        self.assertIn("success", feed[2]["title"])
        self.assertIn("$1.50", feed[2]["title"])
        self.assertTrue(feed[2]["ok"])

    def test_tool_input_json_and_block_result_remain_readable(self):
        p = Path(tempfile.mkdtemp()) / "stream.jsonl"
        p.write_text(
            '{"type":"assistant","message":{"content":['
            '{"type":"tool_use","id":"t1","name":"Read",'
            '"input":{"file_path":"src/app.py","offset":10}}]}}\n'
            '{"type":"user","message":{"content":['
            '{"type":"tool_result","tool_use_id":"t1","content":['
            '{"type":"text","text":"line 10"},'
            '{"type":"text","text":"line 11"}]}]}}\n'
        )
        feed = parse_stream_activity(p)
        self.assertEqual(len(feed), 1)
        self.assertEqual(feed[0]["language"], "json")
        self.assertIn('"file_path": "src/app.py"', feed[0]["input"])
        self.assertEqual(feed[0]["output"], "line 10\nline 11")
        self.assertTrue(feed[0]["ok"])

    def test_missing_stream_is_empty(self):
        p = Path(tempfile.mkdtemp()) / "nope.jsonl"
        self.assertEqual(parse_stream_activity(p), [])


if __name__ == "__main__":
    unittest.main()
