---
name: foreman
description: Runs a requirement through a full gated SDLC — grill, plan, critique, build, test, beta-review, hand off — by spawning and supervising independent Claude sessions with budgets, deadlines and stuck-detection. Use whenever the user asks to build, implement or ship a feature or module of any real size, or says "foreman", "orchestrate this", "run this through the lifecycle", "manage this build", or asks for multi-session or multi-agent development. Also use when work already under Foreman needs resuming, re-planning or a status read. Not for one-line edits, answering questions about existing code, or reviewing a diff (use /code-review).
argument-hint: "[requirement, or 'status' / 'resume']"
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*), Bash(bash ${CLAUDE_PLUGIN_ROOT}/scripts/*), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/*), Bash(python3 ${GROK_PLUGIN_ROOT}/scripts/*), Bash(bash ${GROK_PLUGIN_ROOT}/scripts/*), Bash(${GROK_PLUGIN_ROOT}/scripts/*), Bash(git worktree *), Bash(git status *), Bash(git diff *), Bash(git log *)
---

# Foreman

Drives one requirement from a sentence to a verified, human-reviewable feature through
seven gates, using separate worker sessions for the work and this session as the manager.

**Requirement:** $ARGUMENTS

Entry and exit for every gate: [reference/gates.md](../../reference/gates.md). Read it
once per run before spawning anything. Do not restate it; follow it.

Worker launch is harness-specific: [reference/harness.md](../../reference/harness.md).
Claude is the default adapter; Grok uses `GROK_SESSION_ID` or `--harness grok`.

## Step 0 — preflight, always

```bash
PLUGIN_ROOT="${GROK_PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}"
python3 "$PLUGIN_ROOT/scripts/preflight.py"
```

This installs anything missing and reports what changed. Relay that report to the user in
one short block — they need to know their machine was modified. If it exits non-zero, a
dependency could not be satisfied: surface it as a decision and stop. Do not proceed with
a half-satisfied toolchain.

Then scaffold the project if it isn't already:

```bash
python3 "$PLUGIN_ROOT/scripts/scaffold.py" .
```

## Step 1 — route

**Read `.foreman/work/memory.md` first.** If a previous session left anything under
*Immediate attention*, deal with it before starting new work — that table exists because
someone already paid for the lesson.

Then check it is not stale (a G0 label surviving through G2 is how a compact
handover restarts finished work):

```bash
python3 "$PLUGIN_ROOT/scripts/verify_gate.py" --check-memory --root .foreman
```

Non-zero: rewrite `work/memory.md` — set **Gate** to the value on stderr, refresh
*Immediate attention* with live traps only — and re-run until it exits 0. Do not
route, spawn, or compact on a stale file.

Then read `.foreman/` and decide where this run picks up. Do not restart a gate that already
has its artefact. **G2 is not an artefact check for `CRITIQUE.md` — it is `--g2-clear`.**

```bash
python3 "$PLUGIN_ROOT/scripts/verify_gate.py" --g2-clear --root .foreman
```

| State on disk | Go to |
|---|---|
| No `REQUIREMENTS.md`, or it still carries clarification markers | **G0** — `/foreman:intake` |
| Requirements clean, no task files under `modules/*/tasks/` | **G1** — `/foreman:plan` |
| Task files exist, `--g2-clear` exits non-zero | **G2** — below |
| `--g2-clear` exits 0, tasks not all `[x]` | **G3–G5** — `/foreman:run` |
| All tasks `[x]` | **G6** — hand off (below) |

If the user said `status`, skip straight to the board and report — do not advance anything.

**No gate is skipped to save time.** Scale a gate down — never skip it. If the user asks
you to skip one, say what it protects against, then do as they ask and record it in
`.foreman/log.md`.

## G2 — two steps, both required

Do **not** critique in this session. The planner must not attack its own plan.

G2a is capped at **4 rounds**. Spawn is `--g2-spawn`, not a prompt `if`. `done` is
not a toggle — set `pending` only when `--g2-may-pending` exits 0.

### G2a — spawn the critic

Ask the script. Do not interpret the file:

```bash
python3 "$PLUGIN_ROOT/scripts/verify_gate.py" --g2-spawn --root .foreman
```

Exit 0: spawn (the script has counted this round). Exit 1: do **not** spawn —
read stderr. Open findings with **Re-critique** `done` are G2b, not another fork.
`pending` at round 4 is also not a fork: set `done` and close findings.

**Claude:** invoke `/foreman:critique` (forked skill). **Grok:** `context: fork` is not a
skill field — spawn a critic worker, same tree, as in [harness.md](../../reference/harness.md).
Name it `g2-critic-<N>` for the round about to run:

```bash
"$PLUGIN_ROOT/scripts/spawn.sh" --name g2-critic-1 --agent foreman-critic \
  --brief .foreman/work/sessions/g2-critic-1/brief.md --root .foreman \
  --worktree no --deadline 45 --turns 80
```

When the critic returns:

```bash
python3 "$PLUGIN_ROOT/scripts/verify_gate.py" --check-critique --root .foreman
```

Non-zero: re-invoke at most 3 times (`--g2-spawn` counts schema retries). After 3
thin files, stop and report. Do not proceed on a thin file.

### G2b — disposition (this session)

Every finding starts `open`. You set `fixed` or `refuted` and fill **Disposition**.
Schema: [reference/critique-format.md](../../reference/critique-format.md).

- **`fixed`:** edit the plan as **Change** specified. Quote the edit in **Disposition**.
- **`refuted`:** **Disposition** cites a file-level reason the finding is wrong.
  Not "we'll live with it" unless the user chose that.

Then:

```bash
python3 "$PLUGIN_ROOT/scripts/verify_gate.py" --g2-may-pending --root .foreman
```

Exit 0: set **Re-critique** to `pending` and return to G2a (`--g2-spawn`).
Exit 1: leave **Re-critique** as `done` (or `not-required`). Do **not** rewind
`done` to `pending`.

`--g2-may-pending` is 0 only when every finding is closed, **Round** is under 4,
and at least one `fixed` finding is severity 4, or severity 3 whose **Attack** is
`decomposition`, `missing-work`, or `traceability`. Severity 3 `acceptance` /
`over-engineering` / `other` you verify yourself — they do not buy another fork.

Then `--g2-clear`. Non-zero: stay in G2 (G2b if `--g2-spawn` exits 1; G2a only if
`--g2-spawn` exits 0). Zero: rewrite `work/memory.md` (**Gate** `G3`) and go to
G3–G5.

A `CRITIQUE.md` that exists with open findings is not a passed gate.

## Standing rules for this whole run

**Task files are the source of truth.** `STATUS.md`, `board.md` and `dashboard.html` are
derived views; regenerate them, never hand-edit them. Status lives in the task file, not
in a commit message and not in your head. Tokens and who may write them:
[reference/task-format.md](../../reference/task-format.md). Developers never write `[x]`.

**`.foreman/` is tracked; `.foreman/work/` is not.** The line is one question: would a
teammate reviewing the PR want this? Tasks, decisions and the glossary, yes. A session's
churning `status.json`, no. Machine-local state — branch, uncommitted work, half-formed
theories — goes in `work/memory.md`, which never ships.

**Keep `work/memory.md` current.** Rewrite it at every gate exit, after every
spawn/`DONE`, and **before compact or ending the session**. Set **Gate** to what
`--check-memory` prints (`G0` `G1` `G2` `G3` `G6`). It is what a fresh session
reads first; its **Immediate attention** table is what stops the next agent
walking into a known trap. Prompt wording does not keep it current — the script
does.

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
