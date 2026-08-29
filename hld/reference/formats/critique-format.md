<!-- Absorbed from foreman/reference/critique-format.md @ 31b38123fb47ca1fe8aa73a4108d4b9e03ce4194 (MIT, (c) 2026 Uddipan Dey). See CREDITS.md. -->
# CRITIQUE.md schema

This is the only definition of the file. The critic writes it; the manager
closes findings; `scripts/verify_gate.py --check-critique` / `--g2-clear`
parse it. Do not invent fields.

Severity scores (0–4) are defined once in [gates.md](gates.md).

## Shape

```markdown
# Critique

**Verdict** not-fit
**Re-critique** not-required
**Date** 2026-08-26

## F-01 — [P] on T-01-02 and T-01-03 share src/lib/session.ts
**Severity** 3
**Attack** decomposition
**Evidence** `modules/M01-auth/tasks/T-01-02-session.md` Build and `T-01-03-refresh.md` Build both name `src/lib/session.ts`
**Change** drop `[P]` on T-01-03; add `**Depends on** T-01-02`
**Status** open
**Disposition**

## Attacks that did not land

- Traceability: every requirement section has at least one `**Traces to**` and no task invents scope.
```

## Document fields

| Field | Values | Who writes |
|---|---|---|
| **Verdict** | `fit` or `not-fit` | critic (updates on a re-critique round) |
| **Re-critique** | `not-required` · `pending` · `done` | critic starts `not-required`; manager sets `pending` after a severity 3–4 plan edit; critic sets `done` on the next round |
| **Date** | ISO date | critic |

Default the plan to **not-fit**. `fit` is earned by naming the strongest attacks that failed, in **Attacks that did not land**.

## Finding fields

Headings are `## F-<NN> — <title>`, numbered from 01 in order.

| Field | Values | Who writes |
|---|---|---|
| **Severity** | `0` `1` `2` `3` `4` | critic |
| **Attack** | `traceability` · `decomposition` · `acceptance` · `missing-work` · `over-engineering` · `other` | critic |
| **Evidence** | a path and a concrete quote or overlap — not a vibe | critic |
| **Change** | the specific plan edit | critic |
| **Status** | `open` · `fixed` · `refuted` | critic writes `open`. Only the manager may set `fixed` or `refuted` |
| **Disposition** | empty until the manager closes it | manager. For `fixed`: what changed in which file. For `refuted`: the file-level reason the finding is wrong |

The critic does not fill **Disposition** and does not close **Status**.

## Attacks that did not land

A heading `## Attacks that did not land` with at least one bullet. Required
when **Verdict** is `fit`. Allowed when `not-fit`. This is what makes a `fit`
verdict worth anything.

## Well-formed ( `--check-critique` )

- File exists
- **Verdict** is `fit` or `not-fit`
- **Re-critique** is `not-required`, `pending`, or `done`
- `not-fit` ⇒ at least one finding
- `fit` ⇒ **Attacks that did not land** has a real bullet
- Every finding has Severity 0–4, Attack, Evidence, Change, and Status
- Status is `open`, `fixed`, or `refuted`

A file that is only "looks reasonable" fails this check.

## Clear ( `--g2-clear` )

Well-formed, **and** no finding is `open`, **and** **Re-critique** is not
`pending`. File existence is not G2.

## Re-critique round

When the manager has set **Re-critique** to `pending` and edited the plan:

- Keep existing findings. Do not change their **Status** or **Disposition**.
- If a `fixed` item is still wrong, add a new finding (`F-N+1`) that cites it.
- Set **Re-critique** to `done`.
- Update **Verdict**.
