---
name: plan
description: G1 of the Foreman lifecycle — decomposes a clarified requirement into module and task files with dependencies, parallel-safety markers, EARS acceptance criteria and LLM-unit estimates. Use after intake has produced a clean REQUIREMENTS.md and before any code is written.
---

# G1 — Plan

Turn `.foreman/REQUIREMENTS.md` into files a fresh session can execute cold.

Read [delivery.md](../../reference/delivery.md). Choose `product` for an end-to-end
build or `targeted` for a scoped change. Write `delivery.json` from its template.
For a product, define the first useful MVP and the later production exit criteria.
Do not schedule the entire repository backlog as one delivery. Commit small sprints
with a concrete demo, task scope and a total turn budget that includes G4 and G5.

For UI products, the first sprint builds a **static frontend preview in parallel
with the backend**, followed by explicit wiring tasks. Create `design.md` and
`contracts.md` before splitting workers: layout, real journey, UI states,
accessibility, API/response/error shapes and representative fixtures. Reuse available
design skills when helpful; record the direction selected within user authorization.
The preview must run without the backend and must be shown to the user after its
browser pass. Label mocked behavior. Wiring depends on frontend and backend readiness.
Do not postpone all visual progress until the backend is complete.

**Do not start while any clarification marker remains in REQUIREMENTS.md.** Go back to G0.

## Modules

Group the work into modules — one coherent capability each. Create
`.foreman/modules/M<NN>-<slug>/MODULE.md` from `.foreman/templates/MODULE.md` and fill in
every section: problem statement, plain-English explanation, user journey, current vs
expected, technical implementation draft, dependencies, EARS acceptance criteria, risks
and edge cases.

The technical draft is a real draft — name the files, the functions, the tables, the
endpoints. "Add authentication" is not a draft.

## Glossary

Before writing tasks, fill `.foreman/agents/glossary.md`. Invoke the
`mattpocock-skills:domain-modeling` skill to pin the ubiquitous language — every worker
reads this file and is told to use those words exactly, so a term you leave vague here
becomes three names for the same thing across three worktrees. Reach for
`mattpocock-skills:codebase-design` when a module's seams are the hard part.

## Tasks

Under each module, `tasks/T-<NN>-<NN>-<slug>.md` from `.foreman/templates/TASK.md`.

Three sizing rules, all of which matter:

**One task fits in one fresh context window.** If a task needs more, it is two tasks. This
is the constraint that makes handovers rare instead of constant.

**Each sprint delivers a vertical slice.** Tasks can be contract-backed frontend,
backend and wiring tracks so the user sees progress early. Each task has an independent
verification and demo appropriate to its track. A static preview is useful progress;
the MVP is not complete until the wiring task proves the real end-to-end journey.

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
Declare `**Files**`, `**Surface**`, `**Validation**` and `**Track**` as described in
delivery.md. UI tasks use browser validation even before an app URL is recorded.
Use `**Milestone** later` for deliberately deferred tasks; do not let them block the MVP.

## Exit criteria

G1 exit is in [reference/gates.md](../../reference/gates.md). In short:

- [ ] Every requirement in `REQUIREMENTS.md` traces to at least one task
- [ ] Every task traces back to a requirement section (`**Traces to**`)
- [ ] Every task has a runnable Verify command and checkable acceptance boxes
- [ ] Dependency order holds — no task needs output from a later one
- [ ] `[P]` markers name genuinely disjoint file sets
- [ ] `delivery.py check` passes: milestones, sprint scope, preview/wiring, dependencies and budgets
- [ ] The first visible result and how the user can open it are explicit

Regenerate the views, append to `.foreman/log.md`, rewrite `.foreman/work/memory.md`
(**Gate** `G2`; live traps under *Immediate attention*), run `--check-memory`
until it exits 0, and **return to `/foreman`**, which routes to G2. Do not critique
in this session — the planner attacking its own plan is how G2 isolation dies.

```bash
PLUGIN_ROOT="${GROK_PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}"
python3 "$PLUGIN_ROOT/scripts/delivery.py" check --root .foreman
python3 "$PLUGIN_ROOT/scripts/refresh.py" --root .foreman
```
