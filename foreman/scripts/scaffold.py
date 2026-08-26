#!/usr/bin/env python3
"""Create the .foreman/ working directory in a project.

  scaffold.py [project_dir] [--force]

Idempotent: existing files are never overwritten unless --force is passed, so it
is safe to run at the start of every Foreman session.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

CONSTITUTION = """# Project constitution

Non-negotiables for this project. Foreman reads this at every gate; a worker that
cannot satisfy something here must stop and report rather than work around it.

## Commands
Recorded once at G0 and reused unattended thereafter. If a command here is wrong,
fix it here rather than in a task file.

| Purpose | Command |
|---|---|
| install | _not yet recorded_ |
| build   | _not yet recorded_ |
| test    | _not yet recorded_ |
| lint / typecheck | _not yet recorded_ |
| run (dev server) | _not yet recorded_ |
| app URL | _not yet recorded_ |

## Standards
- _Add the conventions a reviewer should hold this code to._

## Gates
No gate is skipped. A trivial change runs a thin version of each gate; it does not
bypass one. Gate definitions live in the foreman plugin's `reference/gates.md`.

## Complexity tracking
Anything that violates a standard above must be recorded here with its reason,
not silently accepted.

| Deviation | Why it was necessary | Decided in |
|---|---|---|
"""

REQUIREMENTS = """# Requirements

_Written at G0 by `/foreman:intake`. Do not hand-write; grill first._

## Problem statement

## User journey

## Current state vs expected state

| Today | After |
|---|---|

## Acceptance criteria (EARS)

Written as `WHEN <condition> THE SYSTEM SHALL <behaviour>` so each one converts
directly into a test name.

## Out of scope

## Open questions

_Each unresolved item is tagged with the clarification marker documented in the
foreman plugin's `reference/task-format.md`. G1 cannot start while any remain._
"""

MODULE_TEMPLATE = """# M{num} — {title}

**Status** `[ ]` · **Depends on** — · **Tasks** 0

## Problem statement

## In plain English

## User journey

## Current state vs expected state

| Today | After |
|---|---|

## Technical implementation draft

## Dependencies

## Acceptance criteria (EARS)

## Risks and edge cases

## Sub-task checklist
"""

TASK_TEMPLATE = """# T-{num} — {title}

**Module** M{module} · **Status** `[ ]` · **Parallel** {parallel} · **Depends on** {depends}
**Session** — · **Est** {estimate}
**Traces to** {traces}

## Why
_What breaks if this is absent or wrong._

## Build

## Acceptance
_EARS form. Each box is checkable by someone who did not write the task._
- [ ] WHEN ... THE SYSTEM SHALL ...

## Verify
```bash
```

## Out of scope
_As load-bearing as Build._

## Activity log
"""

GITIGNORE = """# Captured worker streams are large and regenerable.
sessions/*/stream.jsonl
sessions/*/stderr.log
dashboard.html
"""

README = """# .foreman

Working directory for the `foreman` SDLC orchestration plugin.

| Path | What it is |
|---|---|
| `constitution.md` | project non-negotiables and the run/build/test commands |
| `REQUIREMENTS.md` | the grilled requirement with EARS acceptance criteria |
| `modules/M*/MODULE.md` | one file per module |
| `modules/M*/tasks/T-*.md` | one file per task — **the source of truth** |
| `sessions/<name>/` | per-worker brief, status, captured stream, handovers |
| `decisions/D*.md` | human-in-the-loop ledger, including auto-selected calls |
| `board.md` | Obsidian Kanban view — derived, regenerable |
| `dashboard.html` | browser view — derived, regenerable |
| `log.md` | append-only activity log |

`board.md` and `dashboard.html` are generated from the task files. Delete them any
time; `/foreman:board` rebuilds both.

Status legend: `[ ]` backlog · `[>]` planned · `[~]` in progress · `[t]` in test ·
`[b]` beta · `[x]` done · `[!]` blocked · `[?]` awaiting human.
"""


def scaffold(project: Path, force: bool) -> list[str]:
    root = project / ".foreman"
    created = []
    for d in ("modules", "sessions", "decisions", "templates"):
        (root / d).mkdir(parents=True, exist_ok=True)

    files = {
        "constitution.md": CONSTITUTION,
        "REQUIREMENTS.md": REQUIREMENTS,
        "README.md": README,
        ".gitignore": GITIGNORE,
        "log.md": "# Activity log\n\nAppend-only. Newest entries at the bottom.\n\n",
        "templates/MODULE.md": MODULE_TEMPLATE,
        "templates/TASK.md": TASK_TEMPLATE,
    }
    for rel, body in files.items():
        p = root / rel
        if p.exists() and not force:
            continue
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)
        created.append(str(p.relative_to(project)))
    return created


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("project", nargs="?", default=".")
    ap.add_argument("--force", action="store_true", help="overwrite existing files")
    a = ap.parse_args()

    project = Path(a.project).resolve()
    if not project.is_dir():
        sys.exit(f"scaffold.py: no such directory: {project}")

    created = scaffold(project, a.force)
    if created:
        print(f"scaffolded .foreman/ in {project}")
        for c in created:
            print(f"  + {c}")
    else:
        print(f".foreman/ already present in {project} (nothing to do)")
