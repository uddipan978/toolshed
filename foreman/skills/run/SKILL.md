---
name: run
description: Run an active Foreman sprint through development, independent testing and beta review, with resource-aware worker dispatch, durable events, recovery and automatic progress views. Also handles targeted changes with a thin sprint.
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*), Bash(bash ${CLAUDE_PLUGIN_ROOT}/scripts/*), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/*), Bash(python3 ${GROK_PLUGIN_ROOT}/scripts/*), Bash(bash ${GROK_PLUGIN_ROOT}/scripts/*), Bash(${GROK_PLUGIN_ROOT}/scripts/*), Bash(git worktree *), Bash(git status *), Bash(git diff *), Bash(git log *), Bash(git branch *)
---

# Run an active sprint

Read [gates.md](../../reference/gates.md) and
[delivery.md](../../reference/delivery.md) before dispatch. You coordinate the
work; workers implement scoped product changes. User instructions and existing
authorization determine scope and permission.

```bash
PLUGIN_ROOT="${GROK_PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}"
python3 "$PLUGIN_ROOT/scripts/delivery.py" check --root .foreman
python3 "$PLUGIN_ROOT/scripts/verify_gate.py" --g2-clear --root .foreman
python3 "$PLUGIN_ROOT/scripts/events.py" --root .foreman
```

Start the planned sprint with `delivery.py start SNN` if none is active. Do not
reinterpret historical backlog as the current MVP. Resolve pending events and
dirty stopped worktrees before claiming their work survived.

## Dispatch

Write each brief using [delegation-brief.md](../../reference/delegation-brief.md).
All four sections are enforced at launch. Name the task by `**Task file**`, not
by guessing an ID from a session name. Beta briefs name `**Tasks** T-NN-NN, ...`.
Use a new session name for each attempt so evidence and exit records survive.

For UI products, queue the static frontend preview alongside backend work with
disjoint file ownership and the shared `contracts.md`. The preview must not wait
on the backend. Queue wiring separately with both dependencies. Present the preview
as soon as it passes browser G4, stating which data is mocked and what is connected.

```bash
python3 "$PLUGIN_ROOT/scripts/scheduler.py" enqueue --root .foreman \
  --name s01-preview --agent foreman-developer --brief PATH
python3 "$PLUGIN_ROOT/scripts/scheduler.py" run --root .foreman --interval 30
```

Run the loop with the host's persistent monitoring mechanism. It owns resource
checks, slot filling, evidence reconciliation and view refresh. One loop per
project. Do not add a second supervisor or a project-local fill-slots script.
Direct `spawn.sh` uses the same guarded path. It handles status/session bookkeeping
and refuses invalid gates, scope, dependencies, capacity or resource conditions.

## React and reconcile

Notifications are hints. Read the durable pending events on resume and at least
every five minutes, even when the monitor is quiet:

```bash
python3 "$PLUGIN_ROOT/scripts/events.py" --root .foreman
```

- `DONE` / `READY`: inspect the current evidence and verdict, then advance or route.
  A complete failure report is ready for disposition, not a passing gate.
- `REVIEW`: inspect `completion_problems`; resume only the missing work.
- `CHECKPOINT` / `SALVAGE`: preserve the worktree. Inspect recovery manifest and
  commit explicit scoped paths before any successor or cleanup.
- `POKE` / `STUCK` / `OVERDUE`: read progress and process state, then unblock or
  stop and hand over. A stop must preserve uncommitted work first where possible.
- `RESOURCE`: launch admission paused/recovered. Let existing workers checkpoint;
  do not kill them to free a slot.
- `SPRINT_BUDGET`: report remaining work and gate costs; amend/replan within user
  scope. Do not mark incomplete work passed.

After acting, acknowledge the event with `events.py --ack ID --disposition '...'`.
Give the user meaningful progress at least every five minutes during unattended
runs: visible result, current gate, real blockers and next demonstrable outcome.
State how many G4/G5 sessions remain when asked to bring all work to beta/done.

## G4 and integration

Spawn the independent tester from the actual stopped, clean developer branch:

```bash
"$PLUGIN_ROOT/scripts/spawn.sh" --name test-s01-preview --agent foreman-tester \
  --brief PATH --root .foreman --base foreman/s01-preview
```

Testers record cases before execution and grow results during execution. UI tasks
require real browser evidence. See [evidence-format.md](../../reference/evidence-format.md).
An overall pass cannot contain failed or unrun cases or unchecked acceptance.

Integrate passing G4 promptly with `integrate.sh --name TEST_SESSION --root .foreman`.
The script archives evidence, validates the replay, records `[b]` and refreshes views
before safe cleanup. Preserve conflicts for explicit resolution; never union task
headers. Only structured Activity evidence can be combined after inspecting both sides.

For a failed acceptance criterion, reopen the same task with a new developer session,
`--reason` and `--base foreman/FAILED_TEST_SESSION`, then retest independently.
Optional findings go through `findings.py` into the known-issues ledger. Do not turn
severity 0–2 observations into blocking tasks. An acceptance failure remains blocking
at any severity; do not weaken the criterion to satisfy a hook.

## G5 and sprint review

Review the integrated user journey, scoped to the active sprint. Beta can cover a
coherent set of tasks without waiting for future work in the same module. UI/no-UI
comes from explicit task/plan surface, never from a missing app URL. A missing URL
for a UI product is a setup blocker.

Beta writes `beta-review.md` and does not change product files. Advance with
`state.py --finish-beta SESSION --root .foreman`; it checks scope, current product
and evidence before writing `[x]`. Known issues are disclosed, not silently accepted.

Run the sprint demo, record command/output/verdict, then close with
`delivery.py close --demo-evidence PATH`. Report committed/done scope, additions,
remaining tests and what the user can run now. Continue the next sprint within the
authorized objective. Final production handoff also requires the production checks.

## State and views

Never edit manager status tokens independently of `state.py`. The managed loop
repairs generated views; `refresh.py --root .foreman` regenerates all four on demand.
Raw transcripts remain on disk; the dashboard embeds bounded recent previews.
Keep manager working memory current with verified branch facts and pending events.
Workers write their session progress; they must not race to overwrite manager memory.
