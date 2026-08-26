# Task and module file format

## Contents
- Status legend
- The clarification marker
- Task file anatomy
- Field reference
- Why estimates are in LLM units

## Status legend

| Token | Lane | Means | Who writes it |
|---|---|---|---|
| `[ ]` | Backlog | not started | planner (G1) |
| `[>]` | Planned | briefed, waiting on a dependency or a free worker | manager |
| `[~]` | In Progress | a developer session is working it | manager, on spawn |
| `[t]` | In Test | G3 passed — developer Verify ran; G4 has it or is next | developer on Verify pass, or manager when spawning the tester |
| `[b]` | Beta | G4 passed and G5 will run for this module | manager, after G4 |
| `[x]` | Done | G4 passed **and** G5 passed | manager only |
| `[!]` | Blocked | reason recorded inline | whoever is blocked |
| `[?]` | Awaiting Human | needs a decision only the user can make | manager |

Every lane on the board has a token. A lane with no token can never be reached.

**Developers never write `[x]`.** Developer Verify is G3. The Stop hook rejects
a developer stop whose task is `[x]` and demands `[t]`. Testers do not set
`[x]` either — they write `results.md`; the manager advances the token.

## The clarification marker

Write `[NEEDS CLARIFICATION]` — square brackets, both words, a single space — anywhere an assumption is unresolved. It is greppable and it blocks G1:

```bash
grep -rn "NEEDS CLARIFICATION" .foreman/
```

G1 cannot start while any remain in `REQUIREMENTS.md`. A task carrying one is moved to
Awaiting Human automatically by the board generator.

## Task file anatomy

```markdown
# T-01-03 — Contact gate
**Module** M01 · **Status** `[~]` · **Parallel** [P] · **Depends on** T-01-01
**Session** dev-m01-03 · **Est** 12 turns / ~40 tool calls / medium
**Traces to** REQUIREMENTS.md §2.2

## Why
One paragraph. What breaks if this is absent or wrong.

## Build
- `src/components/ContactGate.tsx` — the gate itself
- `src/app/capture/page.tsx` — mount it ahead of the form

## Acceptance
- [ ] WHEN the officer answers "Not yet" THE SYSTEM SHALL persist nothing
- [ ] WHEN the officer answers "Yes" THE SYSTEM SHALL create the lead

## Verify
```bash
npm run typecheck && npm run test -- contact-gate
```

## Out of scope
Document upload. The bank-side rail.

## Activity log
- 2026-08-26 14:02 `npm run test -- contact-gate` → 4 passed
```

The two bold-prefixed lines carry several fields each, separated by `·`. The parser reads
every `**Key** value` pair on a line, so field order does not matter.

## Field reference

| Field | Notes |
|---|---|
| `Module` | `M<NN>` — which module owns this |
| `Status` | legend token in backticks |
| `Parallel` | `[P]` if this task's file set is disjoint from other `[P]` tasks |
| `Depends on` | task IDs, or `—` |
| `Session` | the worker session name, set by the manager on spawn |
| `Est` | LLM units — see below |
| `Traces to` | the requirement section this exists to satisfy. Mandatory. If you cannot fill it in, raise it before building it. |

**Acceptance criteria are EARS form**: `WHEN <condition> THE SYSTEM SHALL <behaviour>`.
That shape converts directly into a test name and cannot be satisfied by a vibe.

**Verify must be a command that actually runs.** A criterion whose Verify is `# TODO` is
not a criterion.

**Out of scope is as load-bearing as Build.** It is what stops a worker quietly expanding
its remit.

## Why estimates are in LLM units

Turns, tool calls, complexity band. Never days or hours.

A human calendar estimate for agent work is a fiction: it does not predict cost, it does
not predict wall time, and it cannot be checked against anything. Turns and tool calls map
directly onto the budget and turn caps the supervisor actually enforces, so an estimate
that says `12 turns / ~40 tool calls / medium` tells the manager whether a `--max-turns
120` worker will comfortably finish. "Half a day" tells it nothing.
