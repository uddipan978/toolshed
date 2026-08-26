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
    critique_is_clear,
    critique_is_well_formed,
    critique_problems,
    detect_harness,
    has_ui,
    parse_critique,
    parse_task,
    read_stream,
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
