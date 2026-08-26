---
name: run
description: G3–G5 of the Foreman lifecycle — acts as the manager, spawning developer, tester and beta-tester sessions, supervising them against budgets and deadlines, and routing failures back for correction. Use once the plan has been critiqued and tasks are ready to build.
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*), Bash(bash ${CLAUDE_PLUGIN_ROOT}/scripts/*), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/*), Bash(python3 ${GROK_PLUGIN_ROOT}/scripts/*), Bash(bash ${GROK_PLUGIN_ROOT}/scripts/*), Bash(${GROK_PLUGIN_ROOT}/scripts/*), Bash(git worktree *), Bash(git status *), Bash(git diff *), Bash(git log *), Bash(git branch *)
---

# G3–G5 — Run the work

```bash
PLUGIN_ROOT="${GROK_PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}"
```

Worker launch: [reference/harness.md](../../reference/harness.md). You are the manager now. **You coordinate; you do not implement.** The moment you start
writing product code you have taken a worker's job and stopped watching everyone else.

You write only inside `.foreman/`. Status tokens and who may write them:
[reference/task-format.md](../../reference/task-format.md). You set `[>]` `[~]`
`[b]` `[x]` `[!]` `[?]`. Developers set `[t]` on Verify pass; you may also set
`[t]` when spawning the tester. Only you write `[x]`, and only after G5.

## Sizing — before you spawn anything

Multi-agent runs cost roughly 15× a single session, and coding parallelises far worse than
research does. So:

- **3–5 concurrent workers, never more.** Three focused workers beat five scattered ones.
- **Fan out only across `[P]` tasks with genuinely disjoint file sets.** Two workers in
  one file is a merge conflict you scheduled deliberately.
- **Scale to the request.** A small change gets one session through thin gates, not a fleet.

## Start the supervisor once

```bash
python3 "$PLUGIN_ROOT/scripts/supervise.py" --root .foreman --interval 30
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
"$PLUGIN_ROOT/scripts/spawn.sh" --name dev-m01-02 --agent foreman-developer \
  --brief .foreman/work/sessions/dev-m01-02/brief.md --root .foreman \
  --budget 15 --turns 120 --deadline 60
```

Name workers for their task (`dev-m01-02`, `test-m01-02`, `beta-m01`). The name is the
address other sessions use to reach them. Set the task file's `**Session**` field to
match, and `**Status**` to `[~]` for a developer spawn.

## Reacting to the supervisor

| Event | What you do |
|---|---|
| `POKE` | Claude: `SendMessage` that worker for a one-line status. Grok: log only — `-p` workers have no inbound channel. Do not replace it yet. |
| `STUCK` | Read its `progress.md` and the tail of `stream.jsonl`. Unblock by message, or stop and respawn from its handover. |
| `OVERDUE` | Stop it. Read the newest `handover-N.md`. Spawn a successor seeded from that file. |
| `COMPACT` | Informational — it self-compacted and wrote a handover. No action. |
| `TURNS` | It has used 80% of its turn cap. Narrow the remaining scope or prepare a successor. |
| `BUDGET` | Its cap stopped it. Successor or descope; record which and why. |
| `DONE` | **Verify before advancing.** Open the task file: are the acceptance boxes actually checked, does the Activity log carry real Verify output, and is status `[t]` (developer) — never `[x]` before G4? |
| `FAILED` | Read `stderr.log`. Fix the brief, then respawn — never respawn an unchanged brief. |

A worker reporting success is a claim, not evidence. Check the artefact. Advancing a gate
on a worker's say-so is the most common way systems like this ship defects.

## G4 — Test

When a task's development passes, spawn a tester against it:

```bash
"$PLUGIN_ROOT/scripts/spawn.sh" --name test-m01-02 --agent foreman-tester \
  --brief .foreman/work/sessions/test-m01-02/brief.md --root .foreman --deadline 45
```

Set the task status to `[t]` if the developer has not already. A failure routes back to
the developer who wrote it, with the tester's reproduction steps in the new brief. Then
it is re-tested — a fix is not verified by the person who made it. Testers write
`results.md`; they do not set `[x]`.

After G4 **passes**, set status `[b]`. G5 always runs (`--has-ui` only selects the
path). `[x]` is after G5, never after the developer.

## Integrate as soon as a task passes G4

```bash
"$PLUGIN_ROOT/scripts/integrate.sh" --name dev-m01-02 --root .foreman
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
this gate is about the feature as a whole. G5 always runs; `--has-ui` selects the path
(see [reference/gates.md](../../reference/gates.md)).

```bash
python3 "$PLUGIN_ROOT/scripts/verify_gate.py" --has-ui --root .foreman
```

Put `ui` or `no-ui` in the brief. For `ui`, tell it how to run the app (from
`constitution.md`) and point at the user journey — **and nothing about the
implementation.** For `no-ui`, give it the recorded run/test commands and the same
journey; no browser, no Lighthouse, no `/impeccable`.

```bash
"$PLUGIN_ROOT/scripts/spawn.sh" --name beta-m01 --agent foreman-beta-tester \
  --brief .foreman/work/sessions/beta-m01/brief.md --root .foreman --deadline 45
```

Severity 3–4 findings route back as new tasks. Severity 0–2 go to the user at G6 as
known-and-accepted, not silently dropped. After G5 passes, set the module's tasks to
`[x]`. The beta tester writes only under `.foreman/work/`.

## Keep the board honest

After every status change:

```bash
python3 "$PLUGIN_ROOT/scripts/board.py" --root .foreman
python3 "$PLUGIN_ROOT/scripts/dashboard.py" --root .foreman
```

Workers forget to close out tasks — this is the single most common coordination failure.
Reconcile every sweep: a developer session `done` whose file still reads `[~]` should
be `[t]` (or re-dispatched). A file at `[x]` whose G4 has not passed is a gate error
— revert to `[t]`.

Append every spawn, transition, failure and fix to `.foreman/log.md`.

## When you need the user

Recommended option first, labelled `(Recommended)`. On a timeout, take it, write
`.foreman/decisions/DNN-<slug>.md` with `auto_selected: true`, and continue. Never stall.
