# G4 and G5 evidence formats

The Stop hook validates these files mechanically. A failing review is allowed to
finish; missing or ambiguous evidence is not.

## G4 — `testcases.md`

Write this file before executing any case. Case IDs are stable and must appear in
`results.md` exactly.

```markdown
# Test cases

## TC-01 — session survives reload
**Traces to** task acceptance criterion 1
**Setup** signed-in user with a valid session
**Action** reload the page
**Expected** the same user remains signed in
```

Include the happy path, each stated boundary, malformed input, and the error path.

## G4 — `results.md`

Create it as soon as execution starts and grow it one case at a time.

```markdown
# Results

**Verdict** pass

## TC-01 — session survives reload
**Outcome** pass
**Command** `npm test -- session`
**Evidence** 4 passed; relevant output follows

<real output or concise reproduction evidence>
```

`Verdict` and every `Outcome` are exactly `pass`, `fail`, or `could-not-run`.
Every case from `testcases.md` needs an outcome. `fail` and `could-not-run` are
complete reports, not Stop-gate failures; the manager decides whether G4 passed.
IDs must be unique, and results cannot invent undeclared cases. An overall `pass`
requires every outcome to pass and all acceptance criteria to remain satisfied.

For a task with `**Validation** browser`, a passing report also requires:

```markdown
**Browser** Chromium, version recorded from the browser
**Viewport** 1440x900 and 390x844
**Browser evidence** screenshots/focus.png, screenshots/mobile.png
```

Drive the real browser for focus, layout, contrast, animation and interaction claims.
Browser evidence is a comma-separated list of existing, nonempty artifact paths,
absolute or relative to the session directory. Put measurements and tab sequences
in the body; absent artifacts cannot support a pass.
Wait for relevant transitions to settle before measuring; record timing conditions.
Use a positive control for behavior probes. Test the criterion's full promised
surface, including native interactive elements and embedded frames where applicable.
Do not narrow an unqualified acceptance criterion to today's markup.

## G5 — `beta-review.md`

```markdown
# Beta review

**Surface** ui
**Verdict** pass

## Findings

### B-01 — specific title
**Severity** 2
**Place** exact screen, command, or step
**Fix** specific change

## What worked

- A concrete strength.
```

`Surface` is `ui` or `no-ui`; `Verdict` is `pass` or `fail`. If there are no
findings, write `- None.` under `## Findings`. Severity 3–4 still becomes a new
fix candidate; severity 0–2 is recorded through `findings.py` and carried to G6.
`**Acceptance** yes` marks a finding that falsifies acceptance regardless of severity.
A `pass` with severity 3–4 or a failed acceptance finding is contradictory and rejected.
Deferred issues are known, not automatically accepted by the user.

Managed integration/G5 disposition copies the compact report into tracked
`.foreman/evidence/<session>/` with a task-bound receipt and content hashes before
cleaning up worktrees. Raw transcripts and large browser scratch remain local.
