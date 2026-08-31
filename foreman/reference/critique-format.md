# CRITIQUE.md schema

This is the only definition of the file. The critic writes it; the manager
closes findings; `scripts/verify_gate.py --check-critique` / `--g2-clear` /
`--g2-spawn` / `--g2-may-pending` parse it. Do not invent fields.

Severity scores (0–4) are defined once in [gates.md](gates.md).

## Shape

```markdown
# Critique

**Verdict** not-fit
**Re-critique** not-required
**Round** 1
**Date** 2026-08-26

## F-01 — [P] on T-01-02 and T-01-03 share src/lib/session.ts
**Severity** 3
**Attack** decomposition
**Evidence** `modules/M01-auth/tasks/T-01-02-session.md` Build and `T-01-03-refresh.md` Build both name `src/lib/session.ts`
**Change** drop `[P]` on T-01-03; add `**Depends on** T-01-02`
**Status** open
**Cites**
**Disposition**

## Attacks that did not land

- Traceability: every requirement section has at least one `**Traces to**` and no task invents scope.
```

## Document fields

| Field | Values | Who writes |
|---|---|---|
| **Verdict** | `fit` or `not-fit` | critic (updates on a re-critique round) |
| **Re-critique** | `not-required` · `pending` · `done` | critic starts `not-required`; manager sets `pending` only when `--g2-may-pending` exits 0; critic sets `done` on every later round. `done` is not a toggle — do not rewind it to `pending` unless that command exits 0 |
| **Round** | `1` `2` `3` `4` | critic. `1` on the first write; previous plus one on a re-critique, never above 4. Missing: `not-required`/`pending` → 1; `done` → 2 |
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
| **Cites** | `F-NN` of an earlier finding | required on round 2–4 for every **open** finding. Empty on round 1. The new finding must attack a previous fix that did not land, or a defect that fix introduced — not a new axis |
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
- Explicit **Round** ≥ 2: every **open** finding has **Cites** naming an earlier finding in this file

A file that is only "looks reasonable" fails this check. A recritique that opens
a new axis without **Cites** also fails.

## Clear ( `--g2-clear` )

Well-formed, **and** no finding is `open`, **and** **Re-critique** is not
`pending`. File existence is not G2. `pending` at round 4 is still not clear —
the manager sets `done` and closes findings; it does not spawn.

## Spawn ( `--g2-spawn` )

Exit 0 only when a critic should run. Cap is 4 G2a rounds (counted in
`.foreman/work/g2.json`, and by **Round**). Do not interpret `CRITIQUE.md` in
the manager prompt.

| State | Spawn? |
|---|---|
| File missing | yes (round 1) |
| Not well-formed, schema retries under 3 | yes (same round, pass stderr) |
| Not well-formed, schema retries ≥ 3 | **no** — stop and report |
| **Re-critique** `pending` and round under 4 | yes |
| **Re-critique** `pending` and round ≥ 4 | **no** — set `done`, G2b |
| Well-formed, not pending, open findings | **no** — G2b |
| G2 clear | **no** — G3 |

## Pending ( `--g2-may-pending` )

Exit 0 only when G2b may set **Re-critique** `pending`. All of:

- well-formed, no finding `open`
- **Round** under 4
- at least one **this-round** `fixed` finding is severity 4, or severity 3 whose
  **Attack** is `decomposition`, `missing-work`, or `traceability`. This-round
  means: round 1, every finding; round 2+, only findings with **Cites**.
  Historical F-01 does not keep buying forks.

Severity 3 `acceptance` / `over-engineering` / `other` does not buy a fork —
the manager verifies those edits. `done` is not a toggle.

## Re-critique round

When the manager has set **Re-critique** to `pending` and edited the plan:

- Keep existing findings. Do not change their **Status** or **Disposition**.
- If a `fixed` item is still wrong, or the fix introduced a defect, add a new
  finding (`F-N+1`) with **Cites** naming that item. No new attack axis.
- Set **Round** to previous plus one (max 4).
- Set **Re-critique** to `done`.
- Update **Verdict**.

A fourth completed round is the last. The manager must not set `pending` again.
