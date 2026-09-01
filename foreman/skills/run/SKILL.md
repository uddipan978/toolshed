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
of them produces duplicated work or silent gaps. A worked example of each field is in
[reference/delegation-brief.md](../../reference/delegation-brief.md) — read it before writing
your first brief of the run:

```markdown
**Task file** .foreman/modules/M01-auth/tasks/T-01-02-session-cookie.md

## Objective
<what done looks like, one paragraph>

## Output format
<which files to write, and where>

## Tools and sources
<what to use; what is already established so it isn't re-derived>
<name the skills for this task: `mattpocock-skills:tdd` for the red/green loop,
`mattpocock-skills:diagnosing-bugs` when something fails for a non-obvious reason>

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
| `CHECKPOINT` | At 40% of the turn cap, the worktree is still dirty. Tell the worker to commit explicit task-scoped paths now; never `git add -A`. |
| `SALVAGE` | A stopped worker has uncommitted files. Do not remove, integrate, or claim its branch preserved them. Inspect and commit explicit paths, then base the successor on that branch. |
| `TURNS` | It has used 80% of its turn cap. Narrow the remaining scope or prepare a successor. |
| `BUDGET` | Its cap was reached. Wait for `READY`/`REVIEW`; choose a successor only if the completion evidence names missing work. |
| `DONE` | **Verify before advancing.** Open the task file in `status.json`'s `cwd`: are the acceptance boxes checked, does the Activity log carry real Verify output, is status `[t]`, is the worktree clean, and is the branch ahead of `start_commit`? |
| `READY` | The process hit a cap/deferred stop, but its completion evidence is valid. Review the verdict, then advance or route exactly as for any completed session; do not redevelop it merely because of the subtype. |
| `REVIEW` | Read `status.json.completion_problems` and the artefacts. Repair or salvage only what is actually missing; do not equate the process subtype with failed work. |
| `FAILED` | An ungated process failed. Read `stderr.log` and its result subtype before deciding whether to resume or respawn. |

A worker reporting success is a claim, not evidence. Check the artefact. Advancing a gate
on a worker's say-so is the most common way systems like this ship defects.

## G4 — Test

When a task's development passes, wait for the supervisor's `DONE` or `READY` event. Its
branch must be clean and contain a worker commit. Then spawn a tester against that exact
branch:

```bash
"$PLUGIN_ROOT/scripts/spawn.sh" --name test-m01-02 --agent foreman-tester \
  --brief .foreman/work/sessions/test-m01-02/brief.md --root .foreman \
  --base foreman/dev-m01-02 --deadline 45
```

`--base` is optional for the normal naming pair: `test-m01-02` automatically resolves
to `foreman/dev-m01-02`. Keep it explicit in unusual/fix-round names. Spawn verifies the
predecessor is stopped and clean, that a developer predecessor committed work after its
own `start_commit`, and that the new branch contains the recorded base commit. A tester
predecessor may add no commit because its evidence lives in the session directory. A
failed check is a rescue, not a reason to fall back to HEAD.

Confirm the task is `[t]` in the developer worktree. Do not mirror-edit the manager
checkout's older copy before integration; that creates an avoidable task-file conflict.
A failure routes back to the developer who wrote it, with the tester's reproduction steps in the new brief. Then
it is re-tested — a fix is not verified by the person who made it. Base a fix worker on
the failed tester branch so it inherits the exact tree and any committed regression test:

```bash
"$PLUGIN_ROOT/scripts/spawn.sh" --name dev-m01-02-fix-1 --agent foreman-developer \
  --brief .foreman/work/sessions/dev-m01-02-fix-1/brief.md --root .foreman \
  --base foreman/test-m01-02
```

Testers write `testcases.md` and `results.md` to
[reference/evidence-format.md](../../reference/evidence-format.md); they do not set
`[x]`. A `fail` or `could-not-run` verdict is valid evidence and may stop—the manager
routes it. Missing case outcomes may not stop.

After G4 **passes**, integrate the tested branch first, then set the manager copy to
`[b]`. G5 always runs (`--has-ui` only selects the path). `[x]` is after G5, never
after the developer.

## Integrate as soon as a task passes G4

```bash
"$PLUGIN_ROOT/scripts/integrate.sh" --name test-m01-02 --root .foreman
```

This integrates the **tested branch**. The tester branch contains the developer commit it
was based on, plus any committed regression spec. The script checks recorded ancestry,
then rebases only worker-produced commits after `lineage_start_commit` onto the manager
branch and fast-forwards it. That deliberately excludes the synthetic `.foreman` snapshot
that otherwise conflicts with normal manager status/log edits. It refuses live or dirty
worktrees, removes the tester worktree, and cleans the stopped/clean developer predecessor
when safe.

**Do this per task, not at the end of the run.** A root worker with no `--base` starts
from the manager's current HEAD. A successor that must start before its predecessor is
integrated needs an explicit `--base foreman/<predecessor>`; tester names get that base
automatically. Incremental integration keeps the dependency order planned in G1 true on
disk and keeps the main branch green.

A merge conflict here is reported, never auto-resolved, and the merge is aborted so the
base branch is untouched. A product-file conflict may mean overlapping `[P]` scope or a
stale base. A `.foreman/`-only conflict is coordination/bookkeeping drift—not evidence of
a decomposition failure. Preserve task evidence and regenerate manager-owned log/boards.

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
`[x]`. The beta tester writes only under `.foreman/work/`; `beta-review.md` follows
[reference/evidence-format.md](../../reference/evidence-format.md) and is enforced by
the Stop hook.

## Keep the board honest

After every status change:

```bash
python3 "$PLUGIN_ROOT/scripts/board.py" --root .foreman
python3 "$PLUGIN_ROOT/scripts/dashboard.py" --root .foreman
```

Workers forget to close out tasks — this is the single most common coordination failure.
While a branch is unintegrated, inspect its task through the session `cwd`; the manager
checkout may correctly remain `[~]`. Do not copy-edit it to `[t]` before the tested branch
lands. After integration, reconcile the manager copy to `[b]`. A file at `[x]` whose G5
has not passed is a gate error—revert it to `[b]`.

Append every spawn, transition, failure and fix to `.foreman/log.md`. Rewrite
`.foreman/work/memory.md` the same moment — **Gate** `G3` until every task is
`[x]`, *What is in flight* matching the workers you just spawned, live traps
under *Immediate attention*. `--check-memory` must exit 0 before you compact
or end the session.

## When you need the user

Recommended option first, labelled `(Recommended)`. On a timeout, take it, write
`.foreman/decisions/DNN-<slug>.md` with `auto_selected: true`, and continue. Never stall.
