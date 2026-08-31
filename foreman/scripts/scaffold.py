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

sys.path.insert(0, str(Path(__file__).resolve().parent))
from foreman_lib import stamp_harness  # noqa: E402

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

MEMORY = """# Working memory

> **Read this first.** The running state of the work.
> `.foreman/work/` is gitignored, so nothing here ships — machine-local detail is
> safe to record. Update this at the end of every unit of work.
>
> The team-facing view is `../STATUS.md` and `../board.md`. This file is for agents.

**Last updated:** _never_
**Branch:** _unknown_ · **uncommitted:** _unknown_

---

## 0. Immediate attention

Things the next agent must not walk past. Severity first, newest last.
Use 🔴 for "this blocks work" and 🟠 for "this will bite you".

| | Item | Where |
|---|---|---|
| | _nothing yet_ | |

## 1. What is in flight

Which tasks are being worked, by which session, and what state each is really in —
including anything the task file does not yet say.

## 2. What was just finished

The last few units of work, and anything they changed that other tasks depend on.

## 3. Known traps

Things that already cost someone an hour. Be concrete: the symptom, the cause, the fix.

## 4. Open threads

Started but not finished. What was tried, what remains.
"""

GLOSSARY = """# Glossary

The domain vocabulary. **Use these words exactly.**

Several terms usually have near-synonyms that mean something subtly different, and the
difference is often a correctness or security boundary. Record the distinction, not just
the definition.

Every entry should be checked against source, with the date it was checked.

---

## The parties
_Who is involved, and what each is allowed to decide._

## The core objects
_The nouns the system is about, and the states they move through._

## Words that look interchangeable but are not
_The highest-value section. One line each on why the distinction matters._

| Term | Not to be confused with | Why it matters |
|---|---|---|
"""

CODE_STANDARDS = """# Code standards

What a review reviews against, and what any agent writing code here must not break.

**Map to the authorities, do not copy them.** If this repo already documents its
standards, point at those files and record only what is not written down elsewhere. A
second copy goes stale and then actively misleads.

Order rules by consequence: correctness and security first, taste last. A change that
breaks a §1 rule is wrong regardless of how clean it looks.

---

## 1. Invariants — never break these
_Rules where a violation is a defect, not a preference. Note which are enforced by a
test, and which are honoured by hand._

## 2. Structure and boundaries
_Where things live, what may import what, which layers own which decisions._

## 3. Testing
_What must have a test, at which seam, and what a good test looks like here._

## 4. Taste
_Naming, formatting, idiom. Real but negotiable._
"""

DOMAIN = """# Domain docs

How to consume this repository's documentation before exploring the code.

The risk in a well-documented repo is not missing documentation — it is **trusting a
stale section**. Say which documents are authoritative, in what order to read them, and
which parts are known to drift.

---

## 1. Read these, in order, stopping when you have enough

1. _highest authority first_

## 2. Where status actually lives

Status lives in the task file, not in commit messages. Note here if any area of this
repo deviates from that.

## 3. Known stale sections

| Document | Section | Why it drifts | Trust instead |
|---|---|---|---|
"""

CRITIQUE_TEMPLATE = """# Critique

**Verdict** not-fit
**Re-critique** not-required
**Round** 1
**Date**

## F-01 — title
**Severity** 3
**Attack** decomposition
**Evidence**
**Change**
**Status** open
**Cites**
**Disposition**

## Attacks that did not land

-
"""

ADR_TEMPLATE = """# ADR {num} — {title}

**Date** {date} · **Status** proposed | accepted | superseded by ADR-{num}

## Context
What forces are at play. What made this a decision rather than an obvious step.

## Decision
What we are doing, stated plainly and in the active voice.

## Consequences
What becomes easier, what becomes harder, and what we are now committed to.

## Alternatives considered
What else was on the table and why it lost. This is what stops the decision being
re-litigated in six months.
"""

GITIGNORE = """# The agent scratchpad. Sessions, working memory, evidence and the
# generated dashboard — none of it should reach a teammate's checkout.
work/
"""

README = """# .foreman

Working directory for the `foreman` SDLC orchestration plugin.

It has two halves, and one question decides which side a file belongs on:
**would a teammate reviewing the pull request want this?**

## Tracked — commit this

What the team reads. Stable, reviewable, meaningful in a diff.

| Path | What it is |
|---|---|
| `STATUS.md` | generated markdown board — start here, renders anywhere |
| `board.html` | generated visual board — open in a browser, no plugin needed |
| `board.md` | Obsidian Kanban view — drag-and-drop |
| `REQUIREMENTS.md` | the grilled requirement, EARS acceptance criteria |
| `constitution.md` | project non-negotiables and the run/build/test commands |
| `CRITIQUE.md` | G2 findings; the gate is `--g2-clear`, not file presence |
| `modules/M*/MODULE.md` | one file per module |
| `modules/M*/tasks/T-*.md` | one file per task — **the source of truth** |
| `decisions/D*.md` | human-in-the-loop ledger, including auto-selected calls |
| `adr/NNNN-*.md` | architectural decisions with lasting consequences |
| `agents/glossary.md` | domain vocabulary — use these words exactly |
| `agents/code-standards.md` | what a review reviews against |
| `agents/domain.md` | how to read this repo's docs, and which parts drift |
| `log.md` | append-only activity log |

`STATUS.md`, `board.html` and `board.md` are generated from the task files. Delete any
of them; `/foreman:board` rebuilds them. Three formats because no one format reaches
everyone: a `board.md` wikilink renders as literal text on GitHub, and a repo browser
shows HTML as source.

## Scratchpad — `work/`, gitignored

What the agents use. Churns constantly, machine-local, worthless to a reviewer.

| Path | What it is |
|---|---|
| `work/memory.md` | **read this first** — running state, immediate attention |
| `work/sessions/<name>/` | brief, progress, status, captured stream, handovers |
| `work/research/` | investigation notes that feed tasks |
| `work/screenshots/` | evidence from testers and beta review |
| `work/errors/` | failure triage in progress |
| `work/dashboard.html` | generated browser view |

Nothing in `work/` ships. That is exactly what makes it safe to record a branch name,
an uncommitted change or a half-formed theory there.

## Why sessions are not tracked

`status.json` is rewritten on every supervisor sweep and handovers are transient
scaffolding. The durable record of how a task got built is the **task file's Activity
log**, which carries the Verify command and its real output. That is what a reviewer
needs; the session directory is only how it got made.

## Worker worktrees

They live outside this directory at `<project>/.claude/worktrees/` (Claude) or
`<project>/.grok/worktrees/` (Grok) and are added to the project `.gitignore` by
the scaffolder. `scripts/integrate.sh` merges a finished worker's branch back and
removes its worktree. The path is stored on the session `status.json`.

## Status legend

`[ ]` backlog · `[>]` planned · `[~]` in progress · `[t]` in test ·
`[b]` beta · `[x]` done · `[!]` blocked · `[?]` awaiting human
"""


# Worker worktrees live at <project>/.claude/worktrees/. They are real git
# worktrees inside the working tree, so without this they show up as untracked
# and get swept into a commit.
GIT_EXCLUDES = [
    (".claude/worktrees/", "Foreman worker git worktrees (Claude) — never commit these"),
    (".grok/worktrees/", "Foreman worker git worktrees (Grok) — never commit these"),
]


def ensure_gitignore(project: Path) -> list[str]:
    """Add Foreman's exclusions to the project .gitignore, idempotently."""
    if not (project / ".git").exists():
        return []
    gi = project / ".gitignore"
    existing = gi.read_text(errors="replace") if gi.exists() else ""
    missing = [(pat, why) for pat, why in GIT_EXCLUDES
               if not any(l.strip() == pat for l in existing.splitlines())]
    if not missing:
        return []
    block = "" if not existing or existing.endswith("\n") else "\n"
    block += "\n# --- foreman ---\n"
    for pat, why in missing:
        block += f"# {why}\n{pat}\n"
    with gi.open("a") as fh:
        fh.write(block)
    return [f"{pat} -> .gitignore" for pat, _ in missing]


def scaffold(project: Path, force: bool) -> list[str]:
    root = project / ".foreman"
    created = []
    for d in ("modules", "decisions", "templates", "adr", "agents",
              "work", "work/sessions", "work/research", "work/screenshots", "work/errors"):
        (root / d).mkdir(parents=True, exist_ok=True)

    files = {
        "constitution.md": CONSTITUTION,
        "REQUIREMENTS.md": REQUIREMENTS,
        "README.md": README,
        ".gitignore": GITIGNORE,
        "log.md": "# Activity log\n\nAppend-only. Newest entries at the bottom.\n\n",
        "templates/MODULE.md": MODULE_TEMPLATE,
        "templates/TASK.md": TASK_TEMPLATE,
        "templates/ADR.md": ADR_TEMPLATE,
        "templates/CRITIQUE.md": CRITIQUE_TEMPLATE,
        "agents/glossary.md": GLOSSARY,
        "agents/code-standards.md": CODE_STANDARDS,
        "agents/domain.md": DOMAIN,
        "work/memory.md": MEMORY,
    }
    for rel, body in files.items():
        p = root / rel
        if p.exists() and not force:
            continue
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)
        created.append(str(p.relative_to(project)))
    stamp_harness(root)
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
    created += ensure_gitignore(project)
    if created:
        print(f"scaffolded .foreman/ in {project}")
        for c in created:
            print(f"  + {c}")
    else:
        print(f".foreman/ already present in {project} (nothing to do)")
