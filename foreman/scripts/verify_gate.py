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
    critique_problems,
    has_ui,
    load_json,
    may_set_pending,
    parse_critique,
    parse_task,
    save_json,
    should_spawn_critic,
)

# A blocking hook that can never be satisfied would trap the agent in a loop.
MAX_BLOCKS = 3

TASK_FILE_LINE = re.compile(r"^\*\*Task file\*\*\s*(.+)$", re.M)


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


def session_gate_problems(sdir: Path, status: dict) -> list[str]:
    agent = status.get("agent")
    if agent == "foreman-critic":
        root = Path(os.environ.get("FOREMAN_ROOT") or status.get("root") or "")
        if not root:
            # Critic writes CRITIQUE.md at <cwd>/.foreman when forked in-tree.
            cwd = Path(status.get("cwd") or sdir)
            root = cwd / ".foreman" if (cwd / ".foreman").is_dir() else cwd
        return critique_problems(root, require_clear=False)

    if agent not in ("foreman-developer", "foreman-tester"):
        return []

    brief_path = sdir / "brief.md"
    brief = brief_path.read_text(errors="replace") if brief_path.exists() else ""
    if not brief:
        return [
            "brief.md is missing. A worker cannot be done without the brief that "
            "named its task file."
        ]
    cwd = Path(status.get("cwd") or ".")
    return task_gate_problems(agent, brief, cwd)


def stop_hook() -> int:
    sdir_env = os.environ.get("FOREMAN_SESSION_DIR")
    if not sdir_env:
        return 0
    sdir = Path(sdir_env)
    if not sdir.is_dir():
        return 0

    status = load_json(sdir / "status.json")
    agent = status.get("agent")
    if agent not in ("foreman-developer", "foreman-tester", "foreman-critic"):
        return 0

    blocks = int(status.get("gate_blocks", 0))
    if blocks >= MAX_BLOCKS:
        # Stop insisting; the manager will catch it at the gate instead.
        return 0

    problems = session_gate_problems(sdir, status)
    if not problems:
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
    ap.add_argument("--has-ui", action="store_true",
                    help="print 'ui' or 'no-ui' from constitution.md's app URL")
    ap.add_argument("--root", default=".foreman")
    args = ap.parse_args()

    if args.has_ui or args.check_critique or args.g2_clear or args.g2_spawn \
            or args.g2_may_pending:
        root = Path(args.root).resolve()
        if args.has_ui:
            print("ui" if has_ui(root) else "no-ui")
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
