# Gate definitions

## Contents
- The rule about skipping
- Severity (0–4)
- G0 Intake · G1 Plan · G2 Critique · G3 Develop · G4 Test · G5 Beta · G6 Handoff
- Scaling gates to small work

This file is the source of truth for entry, exit, severity, and who owns each
gate. Skills describe the procedure; they do not restate these criteria.
Delivery scope and the executable runtime contract are in [delivery.md](delivery.md).
G3–G6 operate on the active sprint, not the entire future product backlog.

## The rule about skipping

A gate is never skipped to move faster. It can be **scaled** — a small change
gets a thin version of each gate — but a gate you skipped is a defect you chose
to ship.

Scaling means fewer sessions and shorter artefacts. It never means zero
verification. The difference matters: a thin G4 is one tester session running
four cases; a skipped G4 is code nobody ran.

If the user explicitly asks to skip one, say in one sentence what it protects
against, do as they ask, and record it in `.foreman/log.md`.

## Severity (0–4)

Used by G2, G4 observations and G5 findings. One scale. A failed acceptance
criterion remains blocking at any score; optional observations do not automatically
become task files. `findings.py` records and deduplicates them before disposition.

| Score | Means | G2 | G5 |
|---|---|---|---|
| 0 | Cosmetic | close it; does not block | carry to G6 as known |
| 1 | Nit | close it; does not block | carry to G6 as known |
| 2 | Real, bounded gap | close it (`fixed` or `refuted`); does not by itself force a re-critique | carry to G6 as known |
| 3 | Must change the plan / blocks the task | plan edit. **Re-critique** `pending` only if `--g2-may-pending` exits 0 (graph-changing attack, round under 4) | raise as a new task |
| 4 | Blocks the run | same as 3; do not spawn G3 while it is `open` | raise as a new task |

## G0 — Intake

**Entry:** a requirement in any form, including one sentence.
**Owner:** the main session, using the `mattpocock-skills:grilling` skill.

**Exit:**
- [ ] Zero clarification markers in `REQUIREMENTS.md`
- [ ] Every acceptance criterion in EARS form and mechanically checkable
- [ ] `constitution.md` Commands table has real commands
- [ ] The user has confirmed the requirement is understood
- [ ] Product/targeted mode, MVP outcome (for products), surface and first visible demo recorded

## G1 — Plan

**Entry:** G0 clear.
**Owner:** the main session.

**Exit:**
- [ ] Every requirement traces to ≥1 task; every task traces back to a requirement
- [ ] Each task fits one fresh context window
- [ ] Each sprint demonstrates a vertical slice; UI preview/backend tracks use a shared contract and explicit wiring dependencies
- [ ] Each task has a runnable Verify command and checkable acceptance boxes
- [ ] Dependency order holds
- [ ] `[P]` markers name genuinely disjoint file sets
- [ ] `delivery.py check` passes; product plans have MVP and production milestones
- [ ] UI product sprint one includes a static frontend preview with no backend dependency

Then return to `/foreman`. Do **not** critique in the planning session.

## G2 — Critique

**Entry:** G1 clear.
**Attack owner:** `foreman-critic`, forked via `/foreman:critique`. Cannot see the
planning conversation. Writes findings only. Must not edit the plan. Must not
close findings.
**Disposition owner:** the manager session (`/foreman`). Closes findings. Edits
the plan.

Schema: [critique-format.md](critique-format.md). File existence is **not** G2.

G2a is capped at **4 rounds**. Spawn is `--g2-spawn`, not a prompt `if`.
`done` is not a toggle.

### G2a — Attack

```bash
python3 ${GROK_PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/verify_gate.py --g2-spawn --root .foreman
```

Exit 0: invoke `/foreman:critique` (Claude) or spawn `g2-critic-<N>` (Grok).
Exit 1: do **not** spawn — read stderr. Open findings with `done` are G2b.
`pending` at round 4 is G2b: set `done`, close findings.

When the critic returns:

```bash
python3 ${GROK_PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/verify_gate.py --check-critique --root .foreman
```

Non-zero: re-invoke at most 3 times (`--g2-spawn` counts schema retries). After
3 thin files, stop and report. Do not proceed on a thin file. Do not critique
in the manager session.

### G2b — Disposition

Every finding starts `open`. The manager sets `fixed` or `refuted` and fills
**Disposition**.

- `fixed`: the plan files changed as **Change** specified. Quote the edit.
- `refuted`: **Disposition** cites a file-level reason the finding is wrong.
  Not “we’ll live with it” unless the user chose that.

Then:

```bash
python3 ${GROK_PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/verify_gate.py --g2-may-pending --root .foreman
```

Exit 0: set **Re-critique** to `pending` and return to G2a. Exit 1: leave
**Re-critique** `done` (or `not-required`). Do not rewind `done` to `pending`.

`--g2-may-pending` is 0 only when every finding is closed, **Round** is under 4,
and at least one `fixed` finding is severity 4, or severity 3 whose **Attack**
is `decomposition`, `missing-work`, or `traceability`. Severity 3 `acceptance`
edits the manager verifies — they do not buy another fork.

### Exit (G2 clear)

```bash
python3 ${GROK_PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/verify_gate.py --g2-clear --root .foreman
```

That command exits 0 only when the file is well-formed, no finding is `open`,
and **Re-critique** is not `pending`. The router uses this, not `CRITIQUE.md`
presence. The dashboard badge uses this. After round 4, close whatever remains
and set `done` — do not spawn.

## G3 — Develop

**Entry:** G2 clear, a valid frozen active sprint, complete brief, satisfied
dependencies, disjoint parallel scope and available RAM/CPU/worker capacity.
The shared dispatch path enforces these for both manual and scheduled launches.
**Owner:** `foreman-developer`, one session per task, isolated worktree.

**Exit, per task:**
- [ ] All acceptance boxes checked
- [ ] Verify command actually run, real output pasted in the Activity log
- [ ] Task file status `[t]` — never `[x]`. `[x]` is after independent test
- [ ] Files outside the stated scope untouched
- [ ] Task-scoped changes committed with explicit paths; worktree clean; branch ahead of its recorded `start_commit`

Enforced by the `Stop` hook (`scripts/verify_gate.py`), which resolves the task against
the worker `cwd` and refuses the stop while boxes are unchecked, the Activity log is
empty, the branch is dirty/empty, the brief has no `**Task file**`, or a developer has
marked `[x]` — up to three times, then it defers to the manager.
The fourth attempt may exit to avoid trapping a worker forever, but status is marked
`gate_deferred`. The supervisor re-runs the gate and emits `READY:gate_deferred` if
the current artefacts pass, otherwise `REVIEW:gate_deferred` with
`completion_problems`. `READY` means ready for manager disposition; a tester's complete
`fail` report still routes back to development. Deferred is not synonymous with failed work.

**Then:** G4, not integrate. Integrate after G4 passes.

A developer marking `[x]` is a defect in the gate, not a completed task.

## G4 — Test

**Entry:** a task passed G3, verified against its stopped developer session and
content-bound Verify output. A `[t]` marker alone is not sufficient.
**Owner:** `foreman-tester`, a different session from the developer.

The tester branch must contain the developer branch. `spawn.sh --base <branch>` selects
it; the normal `test-X` name defaults to `foreman/dev-X`. Spawn refuses a live, dirty,
or empty predecessor rather than silently falling back to HEAD.

**Exit:**
- [ ] `testcases.md` written **before** execution
- [ ] Happy path, each boundary, one malformed input, and the error path covered
- [ ] Browser flows exercised via Playwright MCP where the feature has a UI
- [ ] Overall pass agrees with every unique case outcome and all acceptance criteria
- [ ] Anything worth re-running left behind as a committed `.spec.ts`
- [ ] `results.md` states pass / fail / **could not run** for every case
- [ ] Integration validates replay, archives G4 evidence, records `[b]` and refreshes all views before cleanup

A case that could not run is neither pass nor fail. Say so explicitly — silence
about a skipped case reads as a pass, and that is how defects ship.

File schema: [evidence-format.md](evidence-format.md). The Stop hook requires every
declared `TC-NN` to have `pass`, `fail`, or `could-not-run`. It permits a failing report
to finish; the manager decides whether G4 passed and routes failures.

Failures route back to the developer who wrote the code, then are re-tested. A
fix is never verified by the person who made it.

**Then integrate the tester session**: `scripts/integrate.sh --name test-<task>` replays
the exact tested branch's worker commits—which contain the developer work and any committed
regression spec—onto the base, excluding the synthetic launch snapshot. It refuses a
non-terminal or live/dirty session and verifies recorded ancestry. A terminal
`error_max_turns`/budget/deferred session may integrate only after the same completion
gate passes on its current artefacts; tester integration additionally requires overall
`**Verdict** pass`. Do this before spawning a dependent task, because root workers branch
from HEAD.

## G5 — Beta

**Entry:** the declared coherent journey scope in the active sprint passed G4.
**Owner:** `foreman-beta-tester`, no implementation knowledge. A module's future
backlog does not delay review of the current sprint increment.

G5 **always runs**. It scales to the surface, which is `ui` or `no-ui`:

```bash
python3 ${GROK_PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/verify_gate.py --has-ui --root .foreman
```

Managed runs use explicit plan/task surface. A UI task with no runnable app URL
is a setup blocker. `--has-ui` is a legacy helper; an empty URL cannot waive UI tests.

**Exit, UI:**
- [ ] The real user journey walked end to end, desktop and mobile widths
- [ ] Discoverability, trunk test, workflow coherence, error and empty states all assessed
- [ ] `/impeccable audit` run; Lighthouse run via `chrome-devtools` MCP
- [ ] Findings scored 0–4 with a specific place and a specific fix each
- [ ] Severity 3–4 and acceptance failures routed to fixes; 0–2 recorded as known, without claiming user acceptance
- [ ] `state.py --finish-beta SESSION` verifies scope/evidence and sets its tasks to `[x]`

**Exit, no-UI:**
- [ ] The user journey in `REQUIREMENTS.md` walked using the recorded run/test commands
- [ ] Happy path, one malformed input, and the error path exercised
- [ ] Findings scored 0–4 the same way
- [ ] Severity 3–4 raised as new tasks; 0–2 carried to G6
- [ ] `state.py --finish-beta SESSION` verifies scope/evidence and sets its tasks to `[x]`

No browser, no Lighthouse, no `/impeccable` on the no-UI path.

Write only under `.foreman/work/` (the review and screenshots). Do not edit source.
`beta-review.md` follows [evidence-format.md](evidence-format.md); the Stop hook requires
its surface, verdict, findings, and what-worked sections while allowing a failing review.
It also rejects a dirty beta worktree or repository commits made during G5.

## G6 — Handoff

**Entry:** G3, G4 and G5 passed for the active sprint. Run its demo and close it
through `delivery.py`; final production handoff also requires production release checks.
**Owner:** the manager.

**Exit:** the user has received what was built, how to run it, what to check by
hand, **every auto-selected decision**, what was left out, and total spend and
wall time.

## Scaling gates to small work

| Size | G0 | G1 | G2 | G3 | G4 | G5 |
|---|---|---|---|---|---|---|
| One-line fix | 2–3 questions | one task file | forked critic, short file | 1 session | 1 case | `ui` or `no-ui` path, one pass |
| Single feature | full grill | 3–6 tasks | forked critic | 1–3 sessions | 1 tester | 1 beta, scaled by `--has-ui` |
| Module | full grill | 8–20 tasks, modules | forked critic | 3–5 concurrent | 1 tester per task | 1 beta per module, scaled by `--has-ui` |

G2 is always a fork. The planner never critiques its own plan, including for a
one-line fix.

The concurrency ceiling is 3–5 workers regardless of size. Anthropic's own data:
three focused workers outperform five scattered ones, and most coding work
parallelises far worse than research does.
