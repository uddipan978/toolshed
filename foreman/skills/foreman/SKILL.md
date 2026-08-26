---
name: foreman
description: Runs a requirement through a full gated SDLC — grill, plan, critique, build, test, beta-review, hand off — by spawning and supervising independent Claude sessions with budgets, deadlines and stuck-detection. Use whenever the user asks to build, implement or ship a feature or module of any real size, or says "foreman", "orchestrate this", "run this through the lifecycle", "manage this build", or asks for multi-session or multi-agent development. Also use when work already under Foreman needs resuming, re-planning or a status read. Not for one-line edits, answering questions about existing code, or reviewing a diff (use /code-review).
argument-hint: "[requirement, or 'status' / 'resume']"
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*), Bash(bash ${CLAUDE_PLUGIN_ROOT}/scripts/*), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/*), Bash(git worktree *), Bash(git status *), Bash(git diff *), Bash(git log *)
---

# Foreman

Drives one requirement from a sentence to a verified, human-reviewable feature through
seven gates, using separate Claude sessions for the work and this session as the manager.

**Requirement:** $ARGUMENTS

## Step 0 — preflight, always

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/preflight.py
```

This installs anything missing and reports what changed. Relay that report to the user in
one short block — they need to know their machine was modified. If it exits non-zero, a
dependency could not be satisfied: surface it as a decision and stop. Do not proceed with
a half-satisfied toolchain.

Then scaffold the project if it isn't already:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/scaffold.py .
```

## Step 1 — route

Read `.foreman/` and decide where this run picks up. Do not restart a gate that already
has its artefact.

| State on disk | Go to |
|---|---|
| No `REQUIREMENTS.md`, or it still carries clarification markers | **G0** — `/foreman:intake` |
| Requirements clean, no `modules/` | **G1** — `/foreman:plan` |
| Modules exist, no `CRITIQUE.md` | **G2** — `/foreman:critique` |
| Plan critiqued, tasks not all done | **G3–G5** — `/foreman:run` |
| All tasks `[x]` | **G6** — hand off (below) |

If the user said `status`, skip straight to the board and report — do not advance anything.

## The gates

Full entry and exit criteria: [reference/gates.md](../../reference/gates.md). Read it once
per run before spawning anything.

| | Gate | Skill |
|---|---|---|
| G0 | Intake — grill the requirement until nothing is assumed | `/foreman:intake` |
| G1 | Plan — modules, tasks, dependencies, parallel markers | `/foreman:plan` |
| G2 | Critique — adversarial review; findings refuted or fixed | `/foreman:critique` |
| G3 | Develop — worker sessions, one task each, isolated worktrees | `/foreman:run` |
| G4 | Test — explicit cases, executed, browser E2E where it applies | `/foreman:run` |
| G5 | Beta — fresh session, real-user perspective, scored | `/foreman:run` |
| G6 | Handoff — to the human, with every auto-decision listed | this skill |

**No gate is skipped to save time.** Scale a gate down for a small change — a thin
critique, one test session instead of three — but a gate you skipped is a defect you chose
to ship. If the user asks you to skip one, say what it protects against, then do as they
ask and record it in `.foreman/log.md`.

## Standing rules for this whole run

**Task files are the source of truth.** `board.md` and `dashboard.html` are derived views;
regenerate them, never hand-edit them. Status lives in the task file, not in a commit
message and not in your head.

**Estimate in LLM units** — turns, tool calls, complexity band, phases. Never days or
hours. A human calendar estimate for agent work is a fiction that misleads everyone.

**Every question to the user puts the recommended option first**, labelled
`(Recommended)`. If it times out and you are told the user may be away: take the
recommended option, write `.foreman/decisions/DNN-<slug>.md` with `auto_selected: true`
plus what you chose, what you rejected and why, append to `log.md`, and keep going. Never
stall the run.

**Log every significant action** to `.foreman/log.md` — spawns, gate transitions,
decisions, failures, fixes.

## G6 — handoff

Only reached when development, testing and beta review have all passed. Give the user:

1. What was built, in plain English — one paragraph, no jargon.
2. How to run and see it — the exact commands from `constitution.md`.
3. What to check by hand, and why those things specifically.
4. **Every auto-selected decision**, in one block, each reversible.
5. What was left out, and why.
6. Total spend and wall time across all sessions.

Then regenerate the board and dashboard and give them the dashboard path.

Point 4 is not optional. Decisions made on the user's behalf while they were away are the
thing they most need to see, and burying them is how this kind of system loses trust.
