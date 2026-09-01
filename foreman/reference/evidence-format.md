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
task; severity 0–2 is carried to G6.
