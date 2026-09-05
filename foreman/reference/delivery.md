# Delivery planning and runtime

Foreman has two delivery modes. `product` plans an MVP and a production milestone.
`targeted` scopes one change to a small sprint and applies only the relevant checks.
Neither mode promises that arbitrary engineering problems can be solved unattended.
Dependencies, unknowns and failed experiments remain visible work.

## Visible progress in product builds

For a UI product, start with a runnable static frontend preview **in parallel with
backend implementation**. Use the agreed design direction and realistic fixtures.
The preview has no backend dependency. It must show the actual main journey and its
empty, loading, error and permission states; do not deliver an unrelated shell.

Record API shapes, error semantics and fixture data in `contracts.md` before workers
split. Frontend and backend use this contract. Give them disjoint file ownership.
A separate integration task depends on both and replaces fixture adapters with real
services, exercising contract tests and the complete journey. Show the preview to
the user as soon as it passes browser G4, stating clearly which data is still mocked.

Each sprint has a demonstrable goal. The first usable MVP is a complete narrow
journey. Later sprints expand capability and satisfy the production exit criteria:
the relevant authorization, data integrity, migrations, recovery, observability,
performance, accessibility and release/rollback checks. Select these from the actual
product risks; do not impose irrelevant work on a targeted change.

## Files and commands

Copy and fill `.foreman/templates/delivery.json` as `.foreman/delivery.json` during G1.
The plan contains:

- `version: 1`, `mode: product|targeted`, `surface: ui|no-ui`.
- `milestones`: stable ID, kind (`mvp`, `production`, or `change`), user outcome,
  checkable `exit_criteria`; production milestones also carry `release_checks` commands.
- `sprints`: ID, milestone, goal, runnable `demo` command, total `turn_budget`,
  ordered task IDs and `tracer` (the first complete vertical slice). The first UI
  product sprint also names its `preview` task.
- `limits`: `workers` (1–5, default 3), `test_reserve` (default 1),
  `max_fix_rounds` (default 3), `cpu_pause_pct` (85), `min_available_mb` (1024),
  `min_available_pct` (15). These are configurable conservative defaults.

Task headers declare `**Files**` (comma-separated repository paths/globs),
`**Surface** ui|no-ui`, `**Validation** browser|command`, and
`**Track** frontend|backend|integration|general`. The JSON sprint task list owns
membership; optional task `Sprint`/`Milestone` labels must agree with it.
Tasks intentionally left out of this delivery use `**Milestone** later.

```bash
python3 "$PLUGIN_ROOT/scripts/delivery.py" check --root .foreman
# After G2 clears:
python3 "$PLUGIN_ROOT/scripts/delivery.py" start S01 --root .foreman
```

Starting freezes the commitment in tracked `sprints/S01.json`. Runtime rejects
unrecorded scope changes. For a justified addition/removal, edit the plan, validate
it and run `delivery.py amend --reason 'specific reason'`. The original denominator
and before/after scopes remain recorded. Re-critique material plan changes before
dispatch. Do not turn every optional finding into a sprint task.

At sprint review, run the recorded demo and save its command, real output and
`**Verdict** pass in a file. Close with `delivery.py close --demo-evidence PATH`.
All committed tasks must have passed G5. Production sprints also execute their
release checks; a failure keeps the sprint open. Handoff reports the active sprint,
MVP scope and production gaps separately from total repository backlog.

## Managed loop

Write complete briefs, then queue jobs with the plugin; no project-local scheduler
is needed:

```bash
python3 "$PLUGIN_ROOT/scripts/scheduler.py" enqueue --root .foreman \
  --name s01-preview --agent foreman-developer --brief PATH
python3 "$PLUGIN_ROOT/scripts/scheduler.py" run --root .foreman --interval 30
```

Use the host's persistent monitoring mechanism for the loop. It acquires a single
instance lock, reconciles session evidence, samples resources, dispatches ready
jobs and regenerates all four views every sweep. It prioritizes tests and the
frontend preview, reserves testing capacity when G4 work is waiting, validates
dependency integration and overlapping file scopes, and stops adding work at the
sprint turn budget. Brief/launch failures remain in the queue with their reason.
A crash after reservation is recovered as launched or interrupted; no blind respawn.

RAM/CPU pressure pauses new workers; it does not kill existing ones. Hysteresis
requires recovery below the threshold before launch resumes. CPU is a conservative
pressure estimate from process CPU and normalized load, not an instantaneous meter.
Unknown metrics pause launch with an explicit reason. macOS uses `memory_pressure`
and `sysctl`; Linux uses `/proc/meminfo`. Both use `ps` and load average.

`supervise.py --once` remains a reconciliation fallback. Do not run a second
persistent supervisor beside the managed loop. `--prefix` filters session names,
never process liveness. A dead PID is precisely when a completion event matters.

## Task transitions and evidence

Use `state.py TASK --to STATUS --session SESSION` for manager transitions.
It validates the transition, task identity and gate evidence and refreshes all
views. Spawn owns `[~]`; workers update their own copy to `[t]` after Verify.
The scheduler can reconcile the manager's `[t]` from the stopped developer's
actual worktree. G4 integration owns `[b]`, backed by an archived receipt.
`state.py --finish-beta SESSION` validates G5 and advances only its recorded scope.
Blocking or reopening work requires `--reason`; respawn never silently erases a gate.

Managed developers run `verify.py --session-dir SESSION_DIR` to execute the task's
Verify command. It captures output/exit code and hashes scoped product files.
The G3 gate rejects missing records, failed commands or code changed after Verify.
Acceptance checkmarks and progress notes alone are insufficient.

G4/G5 reports and receipts live in tracked `evidence/<session>/`. Large transcripts
and browser scratch remain under `work/`. Integration preserves the tested Git
object under `refs/foreman/tested/<session>`, checks replayed managed work before
advancing the main branch and archives evidence before cleanup. Legacy pre-managed
sessions retain the existing integration path; their receipt is explicitly labelled
`G3-legacy` when independent G4 was not recorded, and cannot advance a task to beta.

Every supervisor event goes to `work/events/` before notification. Check
`events.py` on resume and at least once every five minutes even if no notification
arrived. Acknowledge with `events.py --ack ID --disposition 'what was done'` only
after acting. Restarting does not replay threshold history. A heartbeat reports
pending events; do not interpret a quiet monitor as proof that nothing finished.

## Findings and convergence

G4 acceptance failures and safety/correctness blockers stay blocking regardless of
cosmetic severity labels. Fix the original task and retest; do not narrow an
unqualified criterion to fit the implementation. Record optional observations
with `findings.py`; severity 0–2 goes to `KNOWN-ISSUES.md`, severity 3–4 or a broken
acceptance criterion routes to a fix. Deduplication links repeated findings to the
same ledger entry. The tool does not automatically create task files or change scope.
Deferred means known, **not user-accepted**. Acceptance requires an actual decision.
After the fix-round limit, diagnose/replan with evidence rather than repeating the
same developer/tester loop. Neither a round cap nor a deadline converts a failure
to a pass.

## Recovery and migration

During periodic dirty-work checks (after two minutes, then at most once per five
minutes), at 40% of a dirty worker's turn cap, on stopped-dirty detection, on compaction and
on managed process exit, Foreman preserves recovery copies plus a tracked diff.
Snapshots list skipped/oversized/changing files; they never imply a commit. Keep
the original worktree, inspect and commit explicit task paths, then spawn a successor
with a new name and an explicit base. Never claim preservation from branch existence.
Sudden OS failure before a checkpoint is still a recovery risk: workers commit at
the first coherent slice, at each passed acceptance/Verify boundary and before
yielding or compaction. No automatic copy can guarantee preservation across disk loss.

For an existing project, do not rerun completed development. Inspect current task
files, stopped worktrees and gate evidence; repair duplicate headers/IDs explicitly.
Fill the new delivery plan from remaining scope and annotate task surface/file
ownership. Preserve existing earned states and known issues. Review project-local
scripts and worker instructions: old instructions to mirror task files into the
manager checkout or filter completion events by PID must be retired when switching
to this runtime. The plugin does not silently modify another project's local scripts.
Existing pre-sprint runs retain a labelled launch compatibility path while this
migration is pending. Fresh projects and projects with recorded managed sprints
cannot enter that compatibility path merely by deleting delivery.json.
