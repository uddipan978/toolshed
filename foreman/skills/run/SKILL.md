---
name: run
description: G3–G5 of the Foreman lifecycle — acts as the manager, spawning developer, tester and beta-tester sessions, supervising them against budgets and deadlines, and routing failures back for correction. Use once the plan has been critiqued and tasks are ready to build.
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*), Bash(bash ${CLAUDE_PLUGIN_ROOT}/scripts/*), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/*), Bash(git worktree *), Bash(git status *), Bash(git diff *), Bash(git log *), Bash(git branch *)
---

# G3–G5 — Run the work

You are the manager now. **You coordinate; you do not implement.** The moment you start
writing product code you have taken a worker's job and stopped watching everyone else.

You write only inside `.foreman/`.

## Sizing — before you spawn anything

Multi-agent runs cost roughly 15× a single session, and coding parallelises far worse than
research does. So:

- **3–5 concurrent workers, never more.** Three focused workers beat five scattered ones.
- **Fan out only across `[P]` tasks with genuinely disjoint file sets.** Two workers in
  one file is a merge conflict you scheduled deliberately.
- **Scale to the request.** A small change gets one session through thin gates, not a fleet.

## Start the supervisor once

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/supervise.py --root .foreman --interval 30
```

Run it with the Monitor tool, `persistent: true`. Every line it emits is an event to act
on. Never poll workers with "are you done?" — the supervisor is how you know.

## Brief, then spawn

Write `.foreman/work/sessions/<name>/brief.md` carrying **all four fields**. A brief missing any
of them produces duplicated work or silent gaps:

```markdown
**Task file** .foreman/modules/M01-auth/tasks/T-01-02-session-cookie.md

## Objective
<what done looks like, one paragraph>

## Output format
<which files to write, and where>

## Tools and sources
<what to use; what is already established so it isn't re-derived>

## Boundaries
<explicitly out of scope; files not to touch>
```

Then:

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/spawn.sh --name dev-m01-02 --agent foreman-developer \
  --brief .foreman/work/sessions/dev-m01-02/brief.md --root .foreman \
  --budget 15 --turns 120 --deadline 60
```

Name workers for their task (`dev-m01-02`, `test-m01-02`, `beta-m01`). The name is the
address other sessions use to reach them. Set the task file's `**Session**` field to match.

## Reacting to the supervisor

| Event | What you do |
|---|---|
| `POKE` | `SendMessage` that worker asking for a one-line status. Do not replace it yet. |
| `STUCK` | Read its `progress.md` and the tail of `stream.jsonl`. Unblock by message, or stop and respawn from its handover. |
| `OVERDUE` | Stop it. Read the newest `handover-N.md`. Spawn a successor seeded from that file. |
| `COMPACT` | Informational — it self-compacted and wrote a handover. No action. |
| `TURNS` | It has used 80% of its turn cap. Narrow the remaining scope or prepare a successor. |
| `BUDGET` | Its cap stopped it. Successor or descope; record which and why. |
| `DONE` | **Verify before advancing.** Open the task file: are the acceptance boxes actually checked and does the Activity log carry real Verify output? |
| `FAILED` | Read `stderr.log`. Fix the brief, then respawn — never respawn an unchanged brief. |

A worker reporting success is a claim, not evidence. Check the artefact. Advancing a gate
on a worker's say-so is the most common way systems like this ship defects.

## G4 — Test

When a task's development passes, spawn a tester against it:

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/spawn.sh --name test-m01-02 --agent foreman-tester \
  --brief .foreman/work/sessions/test-m01-02/brief.md --root .foreman --deadline 45
```

Set the task status to `in_test`. A failure routes back to the developer who wrote it, with
the tester's reproduction steps in the new brief. Then it is re-tested — a fix is not
verified by the person who made it.

## Integrate as soon as a task passes G4

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/integrate.sh --name dev-m01-02 --root .foreman
```

This merges the worker's branch into the base branch and removes its worktree.

**Do this per task, not at the end of the run.** `spawn.sh` branches from HEAD, so a
task spawned before its dependency is integrated will never see that dependency's code —
it silently builds against a stale tree. Integrating incrementally is what keeps the
dependency order you planned in G1 actually true on disk.

A merge conflict here is reported, never auto-resolved, and the merge is aborted so the
base branch is untouched. Treat it as a **planning error**: two tasks you marked `[P]`
touched the same files. Fix the decomposition, do not hand-resolve and move on.

## G5 — Beta

Only once every task in the module passes G4. One beta session per module, not per task —
this gate is about the feature as a whole.

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/spawn.sh --name beta-m01 --agent foreman-beta-tester \
  --brief .foreman/work/sessions/beta-m01/brief.md --root .foreman --deadline 45
```

The brief must tell it how to run the app (from `constitution.md`) and point at the user
journey in `REQUIREMENTS.md` — **and nothing about the implementation.** Its value comes
from not knowing how the thing was built.

Severity 3–4 findings route back as new tasks. Severity 0–2 go to the user at G6 as
known-and-accepted, not silently dropped.

## Keep the board honest

After every status change:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/board.py --root .foreman
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/dashboard.py --root .foreman
```

Workers forget to close out tasks — this is the single most common coordination failure.
Reconcile every sweep: any task whose session is `done` but whose file still reads `[~]` is
yours to correct or re-dispatch.

Append every spawn, transition, failure and fix to `.foreman/log.md`.

## When you need the user

Recommended option first, labelled `(Recommended)`. On a timeout, take it, write
`.foreman/decisions/DNN-<slug>.md` with `auto_selected: true`, and continue. Never stall.
