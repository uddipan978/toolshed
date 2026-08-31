#!/usr/bin/env python3
"""Fixture tests for G2 schema, status tokens, and the stop gate."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from foreman_lib import (  # noqa: E402
    MAX_G2A_ROUNDS,
    MAX_G2A_SCHEMA_RETRIES,
    critique_is_clear,
    critique_is_well_formed,
    critique_problems,
    critique_round,
    detect_harness,
    finding_forces_recritique,
    has_ui,
    load_g2_state,
    may_set_pending,
    parse_critique,
    parse_task,
    read_stream,
    should_spawn_critic,
)
from verify_gate import task_gate_problems  # noqa: E402


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


class HarnessTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
