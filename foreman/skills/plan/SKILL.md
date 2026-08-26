---
name: plan
description: G1 of the Foreman lifecycle — decomposes a clarified requirement into module and task files with dependencies, parallel-safety markers, EARS acceptance criteria and LLM-unit estimates. Use after intake has produced a clean REQUIREMENTS.md and before any code is written.
---

# G1 — Plan

Turn `.foreman/REQUIREMENTS.md` into files a fresh session can execute cold.

**Do not start while any clarification marker remains in REQUIREMENTS.md.** Go back to G0.

## Modules

Group the work into modules — one coherent capability each. Create
`.foreman/modules/M<NN>-<slug>/MODULE.md` from `.foreman/templates/MODULE.md` and fill in
every section: problem statement, plain-English explanation, user journey, current vs
expected, technical implementation draft, dependencies, EARS acceptance criteria, risks
and edge cases.

The technical draft is a real draft — name the files, the functions, the tables, the
endpoints. "Add authentication" is not a draft.

## Tasks

Under each module, `tasks/T-<NN>-<NN>-<slug>.md` from `.foreman/templates/TASK.md`.

Three sizing rules, all of which matter:

**One task fits in one fresh context window.** If a task needs more, it is two tasks. This
is the constraint that makes handovers rare instead of constant.

**Each task is a vertical slice.** A narrow but *complete* path through every layer, that
can be demonstrated on its own. Horizontal slices ("do all the database work") produce
tasks that cannot be verified until everything else lands.

The exception is a wide refactor — renaming a column, retyping a shared symbol. Do not
force a tracer bullet through that. Sequence it **expand → migrate in batches → contract**,
each batch its own task, the build green between every one.

**Mark `[P]` only where context genuinely isolates.** Two tasks are parallel-safe when
they touch disjoint file sets. If you cannot name the disjoint sets, they are not
parallel, whatever the dependency graph says. This marker sets the fan-out width at G3, so
an optimistic `[P]` becomes a real merge conflict.

## Estimates

In LLM units: turns, approximate tool calls, complexity band (low/medium/high). Never days.
`12 turns / ~40 tool calls / medium` is useful. "Half a day" is not.

## Acceptance criteria

Inherit from the module, in EARS form, each one a checkbox. Add the **Verify** command —
something that actually runs, taken from `constitution.md`. A criterion whose Verify is
`# TODO` is not a criterion.

Write **Out of scope** on every task. It is what stops a worker quietly expanding its remit.

## Exit criteria

G1 exit is in [reference/gates.md](../../reference/gates.md). In short:

- [ ] Every requirement in `REQUIREMENTS.md` traces to at least one task
- [ ] Every task traces back to a requirement section (`**Traces to**`)
- [ ] Every task has a runnable Verify command and checkable acceptance boxes
- [ ] Dependency order holds — no task needs output from a later one
- [ ] `[P]` markers name genuinely disjoint file sets

Regenerate the views, append to `.foreman/log.md`, and **return to `/foreman`**,
which routes to G2. Do not critique in this session — the planner attacking its
own plan is how G2 isolation dies.

```bash
PLUGIN_ROOT="${GROK_PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}"
python3 "$PLUGIN_ROOT/scripts/board.py" --root .foreman
python3 "$PLUGIN_ROOT/scripts/dashboard.py" --root .foreman
```
