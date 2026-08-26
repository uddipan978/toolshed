# Gate definitions

## Contents
- The rule about skipping
- G0 Intake · G1 Plan · G2 Critique · G3 Develop · G4 Test · G5 Beta · G6 Handoff
- Scaling gates to small work

## The rule about skipping

A gate is never skipped to move faster. It can be **scaled** — a small change gets a thin
version of each gate — but a gate you skipped is a defect you chose to ship.

Scaling means fewer sessions and shorter artefacts. It never means zero verification. The
difference matters: a thin G4 is one tester session running four cases; a skipped G4 is
code nobody ran.

If the user explicitly asks to skip one, say in one sentence what it protects against, do
as they ask, and record it in `.foreman/log.md`.

## G0 — Intake

**Entry:** a requirement in any form, including one sentence.
**Owner:** the main session, using `/grilling`.

**Exit:**
- [ ] Zero clarification markers in `REQUIREMENTS.md`
- [ ] Every acceptance criterion in EARS form and mechanically checkable
- [ ] `constitution.md` Commands table has real commands
- [ ] The user has confirmed the requirement is understood

## G1 — Plan

**Entry:** G0 clear.
**Owner:** the main session.

**Exit:**
- [ ] Every requirement traces to ≥1 task; every task traces back to a requirement
- [ ] Each task fits one fresh context window
- [ ] Each task is a vertical slice (except a wide refactor, sequenced expand→migrate→contract)
- [ ] Each task has a runnable Verify command and checkable acceptance boxes
- [ ] Dependency order holds
- [ ] `[P]` markers name genuinely disjoint file sets

## G2 — Critique

**Entry:** G1 clear.
**Owner:** `foreman-critic`, forked so it cannot see the conversation that made the plan.

**Exit:**
- [ ] `.foreman/CRITIQUE.md` exists with a verdict
- [ ] Every finding is **refuted or fixed** — none merely noted
- [ ] Severity 3–4 findings resulted in a plan change

## G3 — Develop

**Entry:** G2 clear.
**Owner:** `foreman-developer`, one session per task, isolated worktree.

**Exit, per task:**
- [ ] All acceptance boxes checked
- [ ] Verify command actually run, real output pasted in the Activity log
- [ ] Task file status `[x]`, Activity log appended
- [ ] Files outside the stated scope untouched

Enforced by the `Stop` hook (`scripts/verify_gate.py`), which refuses the stop while boxes
are unchecked or the Activity log is empty — up to three times, then it defers to the
manager.

## G4 — Test

**Entry:** a task passed G3.
**Owner:** `foreman-tester`, a different session from the developer.

**Exit:**
- [ ] `testcases.md` written **before** execution
- [ ] Happy path, each boundary, one malformed input, and the error path covered
- [ ] Browser flows exercised via Playwright MCP where the feature has a UI
- [ ] Anything worth re-running left behind as a committed `.spec.ts`
- [ ] `results.md` states pass / fail / **could not run** for every case

A case that could not run is neither pass nor fail. Say so explicitly — silence about a
skipped case reads as a pass, and that is how defects ship.

Failures route back to the developer who wrote the code, then are re-tested. A fix is
never verified by the person who made it.

## G5 — Beta

**Entry:** every task in the module passed G4.
**Owner:** `foreman-beta-tester`, one session per module, no implementation knowledge.

**Exit:**
- [ ] The real user journey walked end to end, desktop and mobile widths
- [ ] Discoverability, trunk test, workflow coherence, error and empty states all assessed
- [ ] `/impeccable audit` run; Lighthouse run via `chrome-devtools` MCP
- [ ] Findings scored 0–4 with a specific place and a specific fix each
- [ ] Severity 3–4 raised as new tasks; 0–2 carried to G6 as known-and-accepted

## G6 — Handoff

**Entry:** G3, G4 and G5 all passed.
**Owner:** the manager.

**Exit:** the user has received what was built, how to run it, what to check by hand,
**every auto-selected decision**, what was left out, and total spend and wall time.

## Scaling gates to small work

| Size | G0 | G1 | G2 | G3 | G4 | G5 |
|---|---|---|---|---|---|---|
| One-line fix | 2–3 questions | one task file | inline self-review | 1 session | 1 case | skip if no UI change |
| Single feature | full grill | 3–6 tasks | forked critic | 1–3 sessions | 1 tester | 1 beta |
| Module | full grill | 8–20 tasks, modules | forked critic | 3–5 concurrent | 1 tester per task | 1 beta per module |

The concurrency ceiling is 3–5 workers regardless of size. Anthropic's own data: three
focused workers outperform five scattered ones, and most coding work parallelises far
worse than research does.
