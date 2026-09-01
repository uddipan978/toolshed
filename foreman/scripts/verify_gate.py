#!/usr/bin/env python3
"""Stop-hook gate and G2 checks.

Anthropic's documented failure mode for multi-agent systems is the early-victory
problem — a worker declaring success after minimal verification. Prompt wording
does not fix it; a hook that blocks the stop does.

Exit 2 on a Stop hook prevents the stop and feeds stderr back to the agent, so it
keeps working. Exit 0 lets it finish.

Only the Stop-hook path no-ops when FOREMAN_SESSION_DIR is unset (every other
session is untouched). CLI flags always run.

  verify_gate.py                         Stop hook (reads FOREMAN_SESSION_DIR)
  verify_gate.py --check-critique        CRITIQUE.md is well-formed (open findings OK)
  verify_gate.py --g2-clear              G2 exit: well-formed, no open findings,
                                         re-critique not pending
  verify_gate.py --g2-spawn              G2a: exit 0 iff a critic should run (capped)
  verify_gate.py --g2-may-pending        G2b: exit 0 iff Re-critique may be set pending
  verify_gate.py --check-memory          work/memory.md **Gate** matches artefacts
  verify_gate.py --has-ui                print "ui" or "no-ui"
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from foreman_lib import (  # noqa: E402
    MANAGER_OWNED_PATHS,
    critique_problems,
    has_ui,
    infer_gate,
    load_json,
    may_set_pending,
    memory_problems,
    parse_critique,
    parse_task,
    save_json,
    should_spawn_critic,
    worktree_snapshot,
)

# A blocking hook that can never be satisfied would trap the agent in a loop.
MAX_BLOCKS = 3
GATED_AGENTS = frozenset({
    "foreman-developer", "foreman-tester", "foreman-critic",
    "foreman-beta-tester",
})

TASK_FILE_LINE = re.compile(r"^\*\*Task file\*\*\s*(.+)$", re.M)
CASE_HEADING = re.compile(r"^##\s+(TC-\d+)\b.*$", re.M | re.I)
BETA_FINDING = re.compile(r"^###\s+(B-\d+)\b.*$", re.M | re.I)
FIELD_LINE = re.compile(r"^\*\*([^*]+)\*\*\s*(.*?)\s*$", re.M)


def _field(text: str, name: str) -> str:
    wanted = name.strip().lower()
    for key, value in FIELD_LINE.findall(text):
        if key.strip().lower() == wanted:
            return value.strip().strip("`").lower().replace(" ", "-")
    return ""


def task_gate_problems(agent: str, brief: str, cwd: Path) -> list[str]:
    """Schema/acceptance problems that must block a developer or tester stop.

    Missing **Task file**, a path that does not exist, or a missing Acceptance
    section used to fail *open* — which is the early-victory case. They block.
    """
    problems: list[str] = []
    m = TASK_FILE_LINE.search(brief)
    if not m:
        problems.append(
            "brief.md has no `**Task file**` line, so the stop gate cannot find "
            "acceptance criteria. Add it. A stop without that line is not evidence."
        )
        return problems

    raw = m.group(1).strip()
    path = Path(raw)
    if not path.is_absolute():
        path = cwd / path
    if not path.exists():
        problems.append(
            f"Task file `{raw}` does not exist (resolved to `{path}`). "
            "Fix the path in the brief — do not stop without the criteria."
        )
        return problems

    text = path.read_text(errors="replace")
    acc = re.search(r"^##\s+Acceptance.*?$(.*?)(?=^##\s|\Z)", text, re.M | re.S)
    if not acc:
        problems.append(
            f"`{path.name}` has no `## Acceptance` section. That is a planning "
            "error — stop and report it, do not invent a pass."
        )
        return problems
    boxes = re.findall(r"^\s*-\s+\[([ xX])\]", acc.group(1), re.M)
    if not boxes:
        problems.append(
            f"`{path.name}` Acceptance section has no checkboxes."
        )
        return problems

    # A tester may correctly falsify a criterion and report a failure. Requiring
    # it to re-tick the criterion confuses "evidence produced" with "G4 passed"
    # and burns Stop rounds. G4 disposition belongs to the manager.
    if agent.split(":")[-1] == "foreman-tester":
        return problems

    unchecked = sum(1 for b in boxes if b == " ")
    log = re.search(r"^##\s+Activity log(.*)$", text, re.M | re.S)
    log_body = (log.group(1).strip() if log else "")

    if unchecked:
        problems.append(
            f"{unchecked} of {len(boxes)} acceptance criteria in {path.name} are still "
            f"unchecked. Either satisfy them or report a blocker — do not stop in between."
        )
    if not log_body:
        problems.append(
            f"The Activity log in {path.name} is empty. Record the Verify command you "
            f"ran and paste its real output; a claim of success without it is not evidence."
        )

    if problems:
        return problems

    # Developer Verify is G3, not Done. [x] is reserved for after independent test.
    if agent == "foreman-developer":
        task = parse_task(path)
        st = task.get("status")
        if st == "done":
            problems.append(
                f"Status in {path.name} is `[x]`. Independent test (G4) has not run. "
                "Set `**Status**` to `[t]`."
            )
        elif st not in ("in_test", "beta"):
            problems.append(
                f"Verify passed — set `**Status**` in {path.name} to `[t]`, not `[x]`. "
                "G4 has not run."
            )
    return problems


def tester_evidence_problems(sdir: Path) -> list[str]:
    """G4 evidence may report pass, fail, or could-not-run; silence is invalid."""
    problems: list[str] = []
    cases_path = sdir / "testcases.md"
    results_path = sdir / "results.md"
    if not cases_path.is_file():
        problems.append("testcases.md is missing; write the cases before executing them")
        return problems
    cases_text = cases_path.read_text(errors="replace")
    case_heads = list(CASE_HEADING.finditer(cases_text))
    case_ids = [x.group(1).upper() for x in case_heads]
    if not case_ids:
        problems.append(
            "testcases.md has no `## TC-NN — ...` cases; use stable case IDs before execution"
        )
    for i, heading in enumerate(case_heads):
        end = case_heads[i + 1].start() if i + 1 < len(case_heads) else len(cases_text)
        block = cases_text[heading.end():end]
        if not _field(block, "Expected"):
            problems.append(
                f"{heading.group(1).upper()} needs a mechanically checkable `**Expected**`"
            )
    if not results_path.is_file():
        problems.append(
            "results.md is missing; write it early and record every case outcome"
        )
        return problems
    results_text = results_path.read_text(errors="replace")
    verdict = _field(results_text, "Verdict")
    if verdict not in ("pass", "fail", "could-not-run"):
        problems.append(
            "results.md needs `**Verdict** pass|fail|could-not-run`"
        )
    result_heads = list(CASE_HEADING.finditer(results_text))
    result_by_id: dict[str, str] = {}
    for i, heading in enumerate(result_heads):
        end = result_heads[i + 1].start() if i + 1 < len(result_heads) else len(results_text)
        result_by_id[heading.group(1).upper()] = results_text[heading.end():end]
    for cid in case_ids:
        block = result_by_id.get(cid)
        if block is None:
            problems.append(f"results.md has no outcome section for {cid}")
            continue
        outcome = _field(block, "Outcome")
        if outcome not in ("pass", "fail", "could-not-run"):
            problems.append(
                f"{cid} needs `**Outcome** pass|fail|could-not-run` in results.md"
            )
        if not _field(block, "Evidence"):
            problems.append(f"{cid} needs concrete `**Evidence**` in results.md")
    try:
        if cases_path.stat().st_mtime > results_path.stat().st_mtime:
            problems.append(
                "testcases.md is newer than results.md; cases must be fixed before "
                "execution, then results grown against those IDs"
            )
    except OSError:
        pass
    return problems


def beta_evidence_problems(sdir: Path) -> list[str]:
    """Minimum durable G5 review shape. The manager still dispositions findings."""
    path = sdir / "beta-review.md"
    if not path.is_file():
        return ["beta-review.md is missing; G5 cannot finish without review evidence"]
    text = path.read_text(errors="replace")
    problems = []
    if _field(text, "Surface") not in ("ui", "no-ui"):
        problems.append("beta-review.md needs `**Surface** ui|no-ui`")
    if _field(text, "Verdict") not in ("pass", "fail"):
        problems.append("beta-review.md needs `**Verdict** pass|fail`")
    findings_h = re.search(r"^##\s+Findings\s*$", text, re.M | re.I)
    worked_h = re.search(r"^##\s+What worked\s*$", text, re.M | re.I)
    if not findings_h:
        problems.append("beta-review.md needs a `## Findings` section (write `- None.` if empty)")
    if not worked_h:
        problems.append("beta-review.md needs a `## What worked` section")
    if findings_h:
        findings_end = worked_h.start() if worked_h and worked_h.start() > findings_h.end() else len(text)
        findings_body = text[findings_h.end():findings_end]
        heads = list(BETA_FINDING.finditer(findings_body))
        if not heads and not re.search(r"^\s*-\s+None\.?\s*$", findings_body, re.M | re.I):
            problems.append(
                "Findings must use `### B-NN — ...` with Severity/Place/Fix, or `- None.`"
            )
        for i, heading in enumerate(heads):
            end = heads[i + 1].start() if i + 1 < len(heads) else len(findings_body)
            block = findings_body[heading.end():end]
            severity = _field(block, "Severity")
            if severity not in ("0", "1", "2", "3", "4"):
                problems.append(f"{heading.group(1).upper()} needs `**Severity** 0|1|2|3|4`")
            if not _field(block, "Place"):
                problems.append(f"{heading.group(1).upper()} needs a specific `**Place**`")
            if not _field(block, "Fix"):
                problems.append(f"{heading.group(1).upper()} needs a specific `**Fix**`")
    if worked_h:
        worked_body = text[worked_h.end():].strip()
        if not worked_body:
            problems.append("`## What worked` is empty")
    return problems


def repository_state_problems(
    agent: str,
    status: dict,
    snapshot: dict | None = None,
) -> list[str]:
    """A successor can inherit only committed work; integration requires clean state."""
    short_agent = agent.split(":")[-1]
    if short_agent not in (
        "foreman-developer", "foreman-tester", "foreman-beta-tester"
    ):
        return []
    cwd_raw = os.environ.get("FOREMAN_WORKTREE_ROOT") or status.get("cwd")
    if not cwd_raw:
        return ["worker cwd is missing from status.json; branch ancestry cannot be verified"]
    cwd = Path(cwd_raw)
    if not cwd.is_dir():
        return [
            f"worker worktree `{cwd}` no longer exists. The manager must not remove "
            "a worktree before its session exits"
        ]
    snap = snapshot or worktree_snapshot(
        cwd, status.get("start_commit"), status.get("base_commit")
    )
    if not snap["is_repo"]:
        return []  # Non-git projects still use the evidence gates.
    problems = []
    dirty = snap["dirty_paths"]
    if dirty:
        sample = ", ".join(dirty[:8])
        more = f" (+{len(dirty) - 8} more)" if len(dirty) > 8 else ""
        problems.append(
            f"worktree has uncommitted files: {sample}{more}. Commit only the "
            "task-scoped paths explicitly; never use `git add -A`"
        )
    ahead = snap["commits_ahead"]
    if ahead is None:
        problems.append(
            "worker start commit is unknown, so committed work and protected paths "
            "cannot be verified. Restore `start_commit` in status.json or provide a "
            "valid recorded base for merge-base inference"
        )
    elif short_agent == "foreman-developer" and ahead < 1:
        problems.append(
            "developer branch has no worker commit beyond its start commit; a tester "
            "or successor would not inherit this work"
        )
    if short_agent == "foreman-beta-tester" and ahead:
        problems.append(
            "beta tester committed repository changes. G5 is review-only; restore the "
            "branch to its start commit and write evidence under the session directory"
        )
    forbidden = sorted(set(snap.get("committed_paths") or []) & MANAGER_OWNED_PATHS)
    if forbidden:
        problems.append(
            "worker commit modified manager-owned Foreman files: "
            + ", ".join(forbidden)
            + ". Restore them from the start commit and amend; workers update only "
              "their task file under `.foreman/`"
        )
    return problems


def session_gate_problems(
    sdir: Path,
    status: dict,
    repository_snapshot: dict | None = None,
) -> list[str]:
    agent = status.get("agent") or ""
    short_agent = agent.split(":")[-1]
    if short_agent == "foreman-critic":
        root_raw = os.environ.get("FOREMAN_ROOT") or status.get("root") or ""
        if root_raw:
            root = Path(root_raw)
        else:
            # Critic writes CRITIQUE.md at <cwd>/.foreman when forked in-tree.
            cwd = Path(status.get("cwd") or sdir)
            root = cwd / ".foreman" if (cwd / ".foreman").is_dir() else cwd
        return critique_problems(root, require_clear=False)

    if short_agent == "foreman-beta-tester":
        problems = beta_evidence_problems(sdir)
        problems.extend(repository_state_problems(
            short_agent, status, repository_snapshot
        ))
        return problems

    if short_agent not in ("foreman-developer", "foreman-tester"):
        return []

    brief_path = sdir / "brief.md"
    brief = brief_path.read_text(errors="replace") if brief_path.exists() else ""
    if not brief:
        return [
            "brief.md is missing. A worker cannot be done without the brief that "
            "named its task file."
        ]
    cwd = Path(
        os.environ.get("FOREMAN_WORKTREE_ROOT") or status.get("cwd") or "."
    )
    problems = task_gate_problems(short_agent, brief, cwd)
    if short_agent == "foreman-tester":
        problems.extend(tester_evidence_problems(sdir))
    problems.extend(repository_state_problems(
        short_agent, status, repository_snapshot
    ))
    return problems


def session_completion_problems(
    sdir: Path,
    status: dict | None = None,
    repository_snapshot: dict | None = None,
) -> list[str]:
    """Read-only completion check used after any process termination subtype."""
    status = status if status is not None else load_json(sdir / "status.json")
    short_agent = (status.get("agent") or "").split(":")[-1]
    if short_agent not in GATED_AGENTS:
        return [
            f"session agent `{short_agent or 'unknown'}` has no completion gate; "
            "cannot classify it as ready"
        ]
    return session_gate_problems(sdir, status, repository_snapshot)


def session_pass_problems(
    sdir: Path,
    status: dict | None = None,
    repository_snapshot: dict | None = None,
) -> list[str]:
    """Completion plus a passing outcome where the worker owns a verdict."""
    status = status if status is not None else load_json(sdir / "status.json")
    problems = session_completion_problems(sdir, status, repository_snapshot)
    if problems:
        return problems
    short_agent = (status.get("agent") or "").split(":")[-1]
    if short_agent == "foreman-tester":
        verdict = _field((sdir / "results.md").read_text(errors="replace"), "Verdict")
        if verdict != "pass":
            problems.append(
                f"tester verdict is `{verdict or 'missing'}`, not `pass`; route it "
                "back to development instead of integrating"
            )
    elif short_agent == "foreman-beta-tester":
        verdict = _field((sdir / "beta-review.md").read_text(errors="replace"), "Verdict")
        if verdict != "pass":
            problems.append(
                f"beta verdict is `{verdict or 'missing'}`, not `pass`; disposition "
                "findings before advancing G5"
            )
    return problems


def stop_hook() -> int:
    sdir_env = os.environ.get("FOREMAN_SESSION_DIR")
    if not sdir_env:
        return 0
    sdir = Path(sdir_env)
    if not sdir.is_dir():
        return 0

    status = load_json(sdir / "status.json")
    agent = status.get("agent")
    short_agent = (agent or "").split(":")[-1]
    if short_agent not in GATED_AGENTS:
        return 0

    problems = session_gate_problems(sdir, status)
    if not problems:
        status.pop("gate_deferred", None)
        status.pop("gate_problems", None)
        save_json(sdir / "status.json", status)
        return 0

    blocks = int(status.get("gate_blocks", 0))
    if blocks >= MAX_BLOCKS:
        # Let the process exit so a malformed plan cannot trap it forever, but
        # preserve the unresolved evidence for the supervisor's REVIEW state.
        status["gate_deferred"] = True
        status["gate_problems"] = problems
        save_json(sdir / "status.json", status)
        return 0

    status["gate_blocks"] = blocks + 1
    save_json(sdir / "status.json", status)
    print("[foreman gate] Not done yet:\n- " + "\n- ".join(problems), file=sys.stderr)
    return 2


def cli_report(problems: list[str], ok_msg: str) -> int:
    if problems:
        print("[foreman gate] CRITIQUE.md is not ready:\n- " + "\n- ".join(problems),
              file=sys.stderr)
        return 1
    print(ok_msg)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check-critique", action="store_true",
                    help="exit 1 unless CRITIQUE.md is well-formed")
    ap.add_argument("--g2-clear", action="store_true",
                    help="exit 1 unless G2 is clear (no open findings, re-critique not pending)")
    ap.add_argument("--g2-spawn", action="store_true",
                    help="exit 0 iff G2a should spawn a critic (counts toward the round cap)")
    ap.add_argument("--g2-may-pending", action="store_true",
                    help="exit 0 iff G2b may set Re-critique pending")
    ap.add_argument("--no-count", action="store_true",
                    help="with --g2-spawn, do not increment work/g2.json")
    ap.add_argument("--check-memory", action="store_true",
                    help="exit 1 unless work/memory.md **Gate** matches artefacts")
    ap.add_argument("--check-session", metavar="SESSION_DIR",
                    help="exit 1 unless a stopped worker's current artefacts pass its gate")
    ap.add_argument("--require-pass", action="store_true",
                    help="with --check-session, also require a passing tester/beta verdict")
    ap.add_argument("--has-ui", action="store_true",
                    help="print 'ui' or 'no-ui' from constitution.md's app URL")
    ap.add_argument("--root", default=".foreman")
    args = ap.parse_args()

    if args.require_pass and not args.check_session:
        ap.error("--require-pass requires --check-session")

    if args.check_session:
        sdir = Path(args.check_session).resolve()
        problems = (
            session_pass_problems(sdir)
            if args.require_pass else session_completion_problems(sdir)
        )
        if problems:
            print("[foreman gate] session is not ready:\n- "
                  + "\n- ".join(problems), file=sys.stderr)
            return 1
        print("session artefacts are ready")
        return 0

    if args.has_ui or args.check_critique or args.g2_clear or args.g2_spawn \
            or args.g2_may_pending or args.check_memory:
        root = Path(args.root).resolve()
        if args.has_ui:
            print("ui" if has_ui(root) else "no-ui")
            return 0
        if args.check_memory:
            problems = memory_problems(root)
            expected = infer_gate(root)
            if problems:
                print("[foreman gate] memory.md is stale:\n- "
                      + "\n- ".join(problems), file=sys.stderr)
                print(f"expected **Gate** {expected}", file=sys.stderr)
                return 1
            print(f"memory.md is current (**Gate** {expected})")
            return 0
        if args.g2_spawn:
            spawn, reason = should_spawn_critic(root, count=not args.no_count)
            if spawn:
                print(reason)
                return 0
            print("[foreman gate] " + reason, file=sys.stderr)
            return 1
        if args.g2_may_pending:
            allowed, reason = may_set_pending(parse_critique(root / "CRITIQUE.md"))
            if allowed:
                print(reason)
                return 0
            print("[foreman gate] " + reason, file=sys.stderr)
            return 1
        require_clear = bool(args.g2_clear)
        problems = critique_problems(root, require_clear=require_clear)
        ok = ("G2 is clear" if require_clear
              else "CRITIQUE.md is well-formed (findings may still be open)")
        return cli_report(problems, ok)

    try:
        sys.stdin.read()  # drain the hook payload; state is on disk
        return stop_hook()
    except Exception as exc:  # noqa: BLE001 — a broken hook must never trap a session
        print(f"[foreman] verify_gate error: {exc}", file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main())
