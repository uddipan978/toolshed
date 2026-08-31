---
name: intake
description: G0 of the Foreman lifecycle — interrogates a requirement until nothing is assumed, then writes REQUIREMENTS.md with EARS acceptance criteria and the project's run/build/test commands. Use when starting Foreman work on a new requirement, or when an existing requirement still carries clarification markers.
argument-hint: "[requirement]"
---

# G0 — Intake

**Requirement:** $ARGUMENTS

Nothing gets built from this until it is unambiguous. The whole cost of this gate is
recovered the first time it stops a worker building the wrong thing.

## Grill it

**First step, before anything else: invoke the `mattpocock-skills:grilling` skill.**
It is installed and does exactly this job:

> Interview relentlessly, walking the decision tree one branch at a time. One question per
> turn. Every question carries a recommended answer. Facts you can look up, you look up;
> decisions belong to the user.

That last split is the important one. **Do not ask the user anything the filesystem can
answer.** Which framework, which test runner, whether an endpoint already exists, what the
existing table looks like — go and find out. Spend their attention only on genuine
decisions: scope, trade-offs, priorities, what "good" means here.

Keep grilling until you can state the requirement back with no hedging and the user agrees
you have it. Ambiguity that survives this gate becomes rework at G3, at roughly 15× the
price.

## Record the commands

While you are exploring, work out and confirm the project's commands, then write them into
the **Commands** table in `.foreman/constitution.md`: install, build, test, lint/typecheck,
dev server, app URL.

Infer them from `package.json`, `Makefile`, `docker-compose.yml`, CI config. Propose what
you found and confirm **once**. Every later session reads this table instead of guessing,
which is what makes unattended testing possible.

## Write REQUIREMENTS.md

Fill in `.foreman/REQUIREMENTS.md`:

- **Problem statement** — what is wrong today, concretely.
- **User journey** — the path a real person takes, start to finish, including how they
  arrive and what they do next.
- **Current vs expected state** — a two-column table. Specific rows, not adjectives.
- **Acceptance criteria in EARS form** — `WHEN <condition> THE SYSTEM SHALL <behaviour>`.
  Each one must be mechanically checkable and convert straight into a test name. If you
  cannot imagine the test, the criterion is still too vague.
- **Out of scope** — as load-bearing as the scope. Write it down or it will be argued
  about later.
- **Open questions** — anything genuinely unresolved, tagged with the clarification marker
  from [reference/task-format.md](../../reference/task-format.md).

## Exit criteria

G0 is not clear until:

- [ ] Zero clarification markers remain in `REQUIREMENTS.md`
- [ ] Every acceptance criterion is in EARS form and is mechanically checkable
- [ ] `constitution.md`'s Commands table has real commands, not placeholders
- [ ] The user has confirmed you have understood the requirement

Then append to `.foreman/log.md`, rewrite `.foreman/work/memory.md` (**Gate** `G1`
once requirements are clean; live traps under *Immediate attention*), run
`--check-memory` until it exits 0, and return to `/foreman`, which routes to G1.
